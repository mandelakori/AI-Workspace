"""Frozen public ledger repair benchmark. Preparation and replay make no inference calls."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from time import monotonic

from .component_source import propose_source
from .controller import Controller, write_json
from .harness import request_options
from .hierarchy import digest, inspect
from .native import pin_runner
from .oracle import load_cases
from .schema import Check, Config, Profile, Task
from .selection import compare, passing
from .verify import invoke
from .workspace import inventory, snapshot

COMPONENTS = ("framing", "validation", "balance")


def implementation_hashes() -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))}


def compile_check(name: str) -> Check:
    args = ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra"]
    if name == "validation":
        args += ["syntax_probe.c", ".handoff/tokenize/tokenize.c", "validation.c", "-I."]
    else:
        args += [f"-D{name.upper()}", "ledger_probe.c", name+".c"]
    return Check(tuple([*args, "-o", "probe"]))


def prepare(controller: Controller, remote: Profile, destination: Path) -> dict:
    """Archive exact public inputs and all six exhausted proposals without touching their jobs."""
    remote.validate()
    if remote.location != "a100" or remote.managed or controller.config.ssh.get("alias") != "aisak":
        raise ValueError("prepare requires the existing unmanaged A100 profile through aisak")
    state = inspect(controller, "ledger-closeout", "trial")
    image = pin_runner(controller)
    destination.mkdir(parents=True, exist_ok=False)
    bundle = destination/"bundle"
    bundle.mkdir()
    components = {}
    local = None
    for name in COMPONENTS:
        job = controller.config.state/"runs"/state["jobs"][name]
        task = controller.frozen_task(job, json.loads((job/"intake.json").read_bytes()))
        baseline = json.loads((job/"baseline-public.json").read_bytes())
        start = f"{name}/start"
        if snapshot(job/"baseline", bundle/start, ()) != baseline["inventory"]:
            raise ValueError("starting checkpoint changed")
        attempts = []
        for attempt in sorted(job.glob("attempt-*")):
            route = json.loads((attempt/"route.json").read_bytes())["profile"]
            if local is None:
                local = route
            if local != route:
                raise ValueError("baseline proposals used different profiles")
            path = f"{name}/{attempt.name}"
            snapshot(attempt, bundle/path, ())
            evidence = json.loads((attempt/"evidence.json").read_bytes())
            attempts.append({"path": path, "original": str(attempt), "evidence": evidence})
        if len(attempts) != 2 or task.attempt_limit != 2 or not task.source_patch:
            raise ValueError("expected exactly two exhausted targeted proposals per component")
        specification = asdict(replace(task, workspace=Path("."), checks=(compile_check(name), task.checks[1])))
        specification["workspace"] = "."
        components[name] = {"job": state["jobs"][name], "task": specification,
                            "start": start, "attempts": attempts,
                            "starting_source": baseline["inventory"][name+".c"],
                            "public_corpus": baseline["corpus_sha256"]}
    budget = {"attempts_per_component": 2, "max_inference_requests": 6, "max_output_tokens": 2048,
              "request_timeout_seconds": 45, "attempt_timeout_seconds": 160, "worker_tool_calls": 0}
    configurations = {
        "local-baseline": {"status": "recorded_exhausted", "execution_allowed": False,
                           "profile": local, "budget": budget},
        "a100-prepared": {"status": "awaiting_separate_authorization", "execution_allowed": False,
                          "profile": asdict(replace(remote, output_tokens=2048)),
                          "budget": budget, "ssh": controller.config.ssh,
                          "live_availability": "UNTESTED", "request_options": request_options(remote)},
    }
    for name, value in configurations.items():
        write_json(bundle/(name+".json"), value)
    manifest = {"format": 1, "source_commit": "f78498b", "runner": image, "components": components,
                "budget": budget, "inventory": inventory(bundle),
                "implementation_sha256": implementation_hashes(),
                "sanitizer": {"required": True, "flags": ["-fsanitize=undefined", "-fno-sanitize-recover=undefined"]}}
    write_json(destination/"manifest.json", manifest)
    approval = digest(manifest)
    (destination/"manifest.sha256").write_text(approval, encoding="ascii")
    return {"benchmark": str(destination), "approval": approval, "a100": configurations["a100-prepared"],
            "local": "six historical requests archived; rerun prohibited"}


def load_benchmark(root: Path) -> dict:
    manifest = json.loads((root/"manifest.json").read_bytes())
    if digest(manifest) != (root/"manifest.sha256").read_text(encoding="ascii"):
        raise ValueError("benchmark manifest changed")
    if inventory(root/"bundle") != manifest["inventory"]:
        raise ValueError("frozen benchmark inputs or evidence changed")
    if implementation_hashes() != manifest["implementation_sha256"]:
        raise ValueError("benchmark verifier changed; prepare a separately reviewed benchmark")
    return manifest


def worker_task(entry: dict, workspace: Path) -> Task:
    row = dict(entry["task"], workspace=workspace)
    for key in ("inputs", "deliverables", "write_roots", "source_context"):
        row[key] = tuple(row[key])
    for key in ("checks", "commands", "setup"):
        row[key] = tuple(Check.read(check) for check in row[key])
    task = Task(**row)
    task.validate()
    return task


def public_execution(command: Check, workspace: Path, rows: list[dict], artifacts: Path,
                     image: str, deadline: float, *, sanitized: bool) -> dict:
    artifacts.mkdir()
    results, discrepancies, runtime_failures = [], [], []
    for number, row in enumerate(rows, 1):
        if monotonic() >= deadline:
            break
        raw = invoke(command, workspace, artifacts/"home", image, timeout=deadline-monotonic(),
                     stdin=row.get("stdin", "").encode(), sealed=True,
                     extra_args=tuple(row.get("argv", [])))
        write_json(artifacts/f"case-{number:02}.json", raw)
        observed = {key: raw[key] for key in ("code", "stdout", "stderr")}
        expected = {key: row.get(key, 0 if key == "code" else "") for key in observed}
        failed = [key for key in expected if observed[key] != expected[key]]
        verdict = "timeout" if raw["timed_out"] else "output_limit" if raw["truncated"] else (
            failed[0] if failed else "pass")
        label = row.get("name", str(number))
        results.append({"case": number, "name": label, "verdict": verdict, "duration": raw["elapsed"]})
        if verdict != "pass":
            discrepancies.append({"case": label, "stdin": row.get("stdin", ""),
                                  "argv": row.get("argv", []), "expected": expected, "observed": observed})
        if sanitized and (raw["timed_out"] or raw["truncated"] or raw["code"] != expected["code"]
                          or "runtime error:" in raw["stderr"] or "Sanitizer" in raw["stderr"]):
            runtime_failures.append(number)
    complete = len(results) == len(rows)
    passed = sum(item["verdict"] == "pass" for item in results)
    return {"total": len(rows), "completed": len(results), "passed_cases": passed, "complete": complete,
            "passed": complete and passed == len(rows), "cases": results, "discrepancies": discrepancies,
            "runtime_failures": runtime_failures}


def evaluate_candidate(task: Task, source: Path, destination: Path, image: str,
                       deadline: float) -> dict:
    """Measure three distinct stages, keeping raw public outputs outside the worker context."""
    started = monotonic()
    frozen = destination/"candidate"
    hashes = snapshot(source, frozen, ())
    rows = load_cases(frozen/task.public_cases, public=True)
    receipt = {"compiled": False, "sanitizer_required": True, "sanitizer_passed": None,
               "sanitizer_compilation": None, "sanitizer": None, "behavior": None,
               "sanitized_behavior": None, "missing": [], "total": len(rows), "cases": [],
               "passed_cases": 0, "public_passed": False, "promotion_eligible": False,
               "runner": image, "corpus_sha256": hashlib.sha256((frozen/task.public_cases).read_bytes()).hexdigest(),
               "inventory": hashes, "independent_verification": "not_run"}
    normal = invoke(task.checks[0], frozen, destination/"home", image,
                    timeout=max(0, deadline-monotonic()))
    receipt["compilation"] = normal
    receipt["compiled"] = normal["passed"]
    if normal["passed"]:
        ordinary = public_execution(task.checks[1], frozen, rows, destination/"ordinary", image,
                                    deadline, sanitized=False)
        receipt.update(behavior=ordinary, cases=ordinary["cases"], passed_cases=ordinary["passed_cases"])
        argv = list(task.checks[0].argv)
        argv[argv.index("-o")+1] = "probe-ubsan"
        argv = [arg for arg in argv if arg != "-O2"]
        argv[1:1] = ["-O1", "-g", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"]
        compilation = invoke(Check(tuple(argv)), frozen, destination/"sanitizer-home", image,
                             timeout=max(0, deadline-monotonic()))
        receipt["sanitizer_compilation"] = compilation
        if compilation["passed"]:
            sanitized = public_execution(Check(("./probe-ubsan",), timeout=task.checks[1].timeout),
                                         frozen, rows, destination/"sanitized", image, deadline, sanitized=True)
            success = sanitized["complete"] and not sanitized["runtime_failures"]
            receipt.update(sanitizer_passed=success, sanitized_behavior=sanitized,
                           sanitizer={"passed": success, "complete": sanitized["complete"],
                                      "failed_cases": sanitized["runtime_failures"]},
                           promotion_eligible=success and ordinary["complete"],
                           public_passed=success and ordinary["passed"] and sanitized["passed"])
        else:
            receipt["sanitizer_passed"] = False
    receipt["classification"] = ("compile_failure" if not receipt["compiled"] else
                                  "sanitizer_build_failure" if not receipt["sanitizer_compilation"]["passed"] else
                                  "sanitizer_failure" if not receipt["sanitizer_passed"] else
                                  "pass" if receipt["public_passed"] else "public_mismatch")
    receipt["elapsed"] = round(monotonic()-started, 3)
    write_json(destination/"receipt.json", receipt)
    return receipt


def replay_baseline(root: Path, destination: Path) -> dict:
    started = monotonic()
    manifest = load_benchmark(root)
    destination.mkdir(parents=True, exist_ok=False)
    report = {"configuration": "local-baseline", "status": "recorded_exhausted", "new_inference_requests": 0,
              "historical_requests": 6, "components": {}, "tokens": {"input": 0, "output": 0},
              "attempt_seconds": 0.0, "compiler_failures": 0, "sanitizer_failures": 0}
    for name, entry in manifest["components"].items():
        source = root/"bundle"/entry["start"]
        task = worker_task(entry, source)
        incumbent = evaluate_candidate(task, source, destination/name/"start", manifest["runner"], monotonic()+160)
        history = []
        for attempt in entry["attempts"]:
            original = root/"bundle"/attempt["path"]
            candidate = evaluate_candidate(task, original/"workspace", destination/name/original.name,
                                           manifest["runner"], monotonic()+160)
            selection = compare(incumbent, candidate, protect_passing=True)
            # Historical decisions remain authoritative. Replays do not promote or edit old jobs.
            history.append({"attempt": original.name, "source_sha256": candidate["inventory"][name+".c"]["sha256"],
                            "receipt": str(destination/name/original.name/"receipt.json"),
                            "compiled": candidate["compiled"], "sanitizer_passed": candidate["sanitizer_passed"],
                            "behavior_passed_cases": candidate["passed_cases"],
                            "regressions": sorted(passing(incumbent)-passing(candidate)),
                            "selection": selection, "historical_status": attempt["evidence"]["status"],
                            "metrics": attempt["evidence"]["agent"],
                            "attempt_seconds": attempt["evidence"]["elapsed"]})
            metrics = attempt["evidence"]["agent"]["tokens"]
            for key in report["tokens"]:
                report["tokens"][key] += metrics.get(key) or 0
            report["attempt_seconds"] += attempt["evidence"]["elapsed"]
            report["compiler_failures"] += not candidate["compiled"]
            report["sanitizer_failures"] += candidate["sanitizer_passed"] is False
        report["components"][name] = {"starting_source": entry["starting_source"],
                                     "compiled": incumbent["compiled"], "public": incumbent["passed_cases"],
                                     "total": incumbent["total"], "sanitizer_passed": incumbent["sanitizer_passed"],
                                     "sanitized_public": (incumbent["sanitized_behavior"] or {}).get("passed_cases"),
                                     "attempts": history}
    report["attempt_seconds"] = round(report["attempt_seconds"], 3)
    report["verification_seconds"] = round(monotonic()-started, 3)
    write_json(destination/"report.json", report)
    return report


def remote_plan(root: Path) -> dict:
    manifest = load_benchmark(root)
    config = json.loads((root/"bundle/a100-prepared.json").read_bytes())
    return {"status": "awaiting_separate_authorization", "approval": digest(manifest),
            "configuration": config, "runner": manifest["runner"],
            "components": {name: {"contract": row["task"]["objective"],
                                  "source": row["starting_source"], "public_corpus": row["public_corpus"]}
                           for name, row in manifest["components"].items()},
            "inference_requests_executed": 0}


def run_a100(controller: Controller, root: Path, destination: Path, approval: str) -> dict:
    """Explicit future operator dispatch only. Never invoked by prepare, plan or replay."""
    manifest = load_benchmark(root)
    if approval != digest(manifest):
        raise ValueError("separate explicit remote approval must match the frozen benchmark digest")
    config = json.loads((root/"bundle/a100-prepared.json").read_bytes())
    profile = Profile(**config["profile"])
    if profile.location != "a100" or profile.managed or config["ssh"] != controller.config.ssh:
        raise ValueError("remote scope changed")
    if pin_runner(controller) != manifest["runner"]:
        raise ValueError("offline verifier changed")
    destination.mkdir(parents=True, exist_ok=False)
    write_json(destination/"approval.json", {"approval": approval, "configuration": config})
    lane = Controller(replace(controller.config, state=destination/"state", verification_image=manifest["runner"]))
    report = {"components": {}, "inference_requests": 0, "status": "running"}
    for name, entry in manifest["components"].items():
        selected = root/"bundle"/entry["start"]
        task = worker_task(entry, selected)
        incumbent = evaluate_candidate(task, selected, destination/name/"start", manifest["runner"], monotonic()+160)
        attempts = []
        previous = ""
        for number in (1, 2):
            if incumbent["public_passed"] or (lane.config.state/"STOP").exists():
                break
            attempt = destination/name/f"attempt-{number:03}"
            work = attempt/"workspace"
            snapshot(selected, work, ())
            deadline = monotonic()+160
            findings = (f"Selected checkpoint passes {incumbent['passed_cases']}/{incumbent['total']} public cases. "
                        "Repair the public discrepancy without losing prior passes.\n" +
                        json.dumps((incumbent["behavior"] or {}).get("discrepancies", [])[:2]) +
                        "\nSanitizer: " + json.dumps(incumbent["sanitizer"]))
            report["inference_requests"] += 1  # Reserve the request before dispatch, including failed calls.
            started = monotonic()
            try:
                propose_source(lane, task, profile, work, attempt, deadline, findings, previous=previous,
                               remote_authorized=True)
                candidate = evaluate_candidate(task, work, attempt/"evaluation", manifest["runner"], deadline)
                selection = compare(incumbent, candidate, protect_passing=True)
                if selection["accepted"]:
                    incumbent, selected = candidate, work
                previous = json.dumps(selection)
                outcome = {"selection": selection, "public": candidate}
            except (OSError, RuntimeError, ValueError, KeyError) as exc:
                previous = str(exc)[:600]
                outcome = {"error": previous}
            outcome["elapsed"] = round(monotonic()-started, 3)
            metrics = attempt/"agent-metrics.json"
            if metrics.exists():
                outcome["metrics"] = json.loads(metrics.read_bytes())
            write_json(attempt/"evidence.json", outcome)
            attempts.append(outcome)
            report["components"][name] = {"selected": str(selected), "public": incumbent, "attempts": attempts}
            write_json(destination/"report.json", report)
    report["status"] = "complete"
    write_json(destination/"report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("config", type=Path)
    prep.add_argument("a100_config", type=Path)
    prep.add_argument("destination", type=Path)
    for name in ("replay-baseline", "plan-a100", "run-a100"):
        command = commands.add_parser(name)
        command.add_argument("benchmark", type=Path)
        if name != "plan-a100":
            command.add_argument("destination", type=Path)
        if name == "run-a100":
            command.add_argument("--config", type=Path, required=True)
            command.add_argument("--approve", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        cfg = Config.load(args.config)
        remote_cfg = Config.load(args.a100_config)
        remote = next(p for p in remote_cfg.profiles if p.id == "a100-existing")
        result = prepare(Controller(replace(cfg, ssh=remote_cfg.ssh)), remote, args.destination.resolve())
    elif args.command == "replay-baseline":
        result = replay_baseline(args.benchmark.resolve(), args.destination.resolve())
    elif args.command == "plan-a100":
        result = remote_plan(args.benchmark.resolve())
    else:
        result = run_a100(Controller(Config.load(args.config)), args.benchmark.resolve(),
                          args.destination.resolve(), args.approve)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
