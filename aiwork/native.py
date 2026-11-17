"""Run native reconstruction and final grading as separate operator actions."""
from __future__ import annotations

import json
import shutil
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import monotonic
from uuid import uuid4

from .controller import Controller, write_json
from .oracle import case_argv, load_cases
from .schema import Check, Task, bounded, relative
from .specialists import analyze
from .verify import invoke, runner_status
from .workspace import contained, describe, inventory, snapshot


@dataclass(frozen=True)
class Case:
    name: str
    group: str
    stdin: str
    argv: tuple[str, ...]

    @property
    def stimulus(self) -> tuple[str, tuple[str, ...]]:
        return self.stdin, self.argv


def read_inputs(path: Path, limit: int) -> list[Case]:
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("native inputs exceed 1 MiB")
    rows = json.loads(path.read_bytes())
    if not isinstance(rows, list) or not 1 <= len(rows) <= limit:
        raise ValueError(f"native input suite requires 1–{limit} cases")
    cases = []
    for row in rows:
        if not isinstance(row, dict) or row.keys() - {"name", "group", "stdin", "argv"}:
            raise ValueError("invalid native input case")
        name, group, stdin = row.get("name"), row.get("group", "unspecified"), row.get("stdin", "")
        if (not isinstance(name, str) or not 1 <= len(name) <= 100
            or not isinstance(group, str) or not 1 <= len(group) <= 100
            or not isinstance(stdin, str) or len(stdin.encode("utf-8")) > 16384):
            raise ValueError("invalid native input name, group or stdin")
        cases.append(Case(name, group, stdin, case_argv(row.get("argv", []))))
    if len({case.name for case in cases}) != len(cases) or len({c.stimulus for c in cases}) != len(cases):
        raise ValueError("native suite contains duplicate case names or stimuli")
    return cases


def pin_runner(controller: Controller) -> str:
    cfg = controller.config
    if not cfg.verification_image:
        raise ValueError("native execution requires a configured Linux Docker image")
    status = runner_status(cfg.state, cfg.verification_image)
    if not status["image_id"]:
        raise ValueError(f"offline native runner unavailable: {status}")
    return status["image_id"]


def probe(check: Check, case: Case, workspace: Path, home: Path, image: str, stop: Path) -> dict:
    return invoke(check, workspace, home, image, stdin=case.stdin.encode("utf-8"),
                  extra_args=case.argv, sealed=True, stop=stop)


def returned(response: dict) -> bool:
    return not response["timed_out"] and not response["truncated"] and 0 <= response["code"] <= 124


def build(check: Check | None, workspace: Path, home: Path, image: str, stop: Path, log: Path) -> bool:
    if check is None:
        return True
    outcome = invoke(check, workspace, home, image, stop=stop)
    write_json(log, outcome)
    return outcome["passed"]


def recipe(spec: dict, key: str) -> Check:
    check = Check.read(spec[key])
    if check.oracle or any("{verification}" in arg for arg in check.argv):
        raise ValueError("native recipes cannot reference private files")
    return check


def install_public_check(workspace: Path, compiler: Check, invocation: Check) -> Check:
    runner = "native_feedback.py"
    shutil.copyfile(Path(__file__).with_name(runner), workspace / runner)
    return Check(("{python}", runner, json.dumps(asdict(compiler)), json.dumps(asdict(invocation))), 30)


def reconstruct(controller: Controller, manifest: Path, profile: str, *, evidence: str,
                trusted: bool, rea_archive: Path | None = None) -> dict:
    spec = tomllib.loads(manifest.read_text(encoding="utf-8"))
    allowed = {"objective", "source", "source_inputs", "binary", "format", "development", "build_reference",
               "reference", "build_candidate", "candidate", "deliverables", "selectors", "attempts", "timeout",
               "category", "min_context", "specialists"}
    if extra := spec.keys() - allowed:
        raise ValueError(f"unknown native manifest fields: {sorted(extra)}")
    category = spec.get("category", "native-reconstruction")
    metadata_only = evidence == "static"
    root = controller.config.state / "native" / uuid4().hex
    work, public, target, outputs = (root / name for name in ("candidate", "development", "target", "analysis"))
    raw = manifest.resolve(strict=True).parent
    inputs = spec.get("source_inputs", [])
    deliverables = spec["deliverables"]
    for paths in (inputs, deliverables):
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ValueError("source_inputs and deliverables must be relative path arrays")
    if not deliverables or len(set(path.casefold() for path in deliverables)) != len(deliverables):
        raise ValueError("native tasks require distinct deliverables")
    candidate_build, candidate_run, reference_run = (recipe(spec, key) for key in
                                                     ("build_candidate", "candidate", "reference"))
    reference_build = recipe(spec, "build_reference") if "build_reference" in spec else None
    selectors = spec.get("selectors", [])
    specialists = spec.get("specialists", [])
    for values in (selectors, specialists):
        if (not isinstance(values, list) or len(values) > 8 or
            any(not isinstance(value, str) or not value or len(value) > 100 for value in values)):
            raise ValueError("invalid native selectors or specialists")
    if not metadata_only and not trusted:
        raise ValueError("external native analysis requires --trusted")
    if evidence == "specialists" and not specialists:
        raise ValueError("specialist evidence requires a configured specialists list")
    if profile not in {item.id for item in controller.config.profiles}:
        raise ValueError("native reconstruction requires a configured profile")
    public_cases = read_inputs(raw / spec["development"], 32)
    image = pin_runner(controller)
    stop = controller.config.state / "STOP"
    work.mkdir(parents=True)
    public.mkdir()
    outputs.mkdir()
    shutil.copyfile(manifest, root / "manifest.toml")
    task = Task(
        objective=spec["objective"], workspace=work, kind="agent", category=category, inputs=(),
        mode="engineering", write_roots=tuple(relative(p) for p in deliverables),
        deliverables=tuple(deliverables),
        commands=(install_public_check(work, candidate_build, candidate_run), candidate_build),
        checks=(candidate_build, replace(candidate_run, oracle="cases.json", timeout=120)),
        verification_dir=public, min_context=spec.get("min_context", 0),
        attempts=spec.get("attempts", 2), timeout=spec.get("timeout", 300),
    )
    task.validate()
    snapshot((raw / spec["source"]).resolve(strict=True), root / "reference-build", tuple(inputs))
    if not build(reference_build, root / "reference-build", root / "home", image, stop, root / "build.json"):
        raise ValueError(f"reference build failed; see {root / 'build.json'}")
    binary = relative(spec["binary"])
    snapshot(root / "reference-build", target, (binary,))
    (target / binary).chmod(0o755)
    target_inventory = inventory(target)
    target_format = describe(target, target_inventory)["binaries"].get(binary, {}).get("format")
    if target_format != spec["format"] or target_format not in {"ELF", "PE"}:
        raise ValueError("built artifact does not match the configured ELF or PE format")

    def collect(name: str, settings: dict, label: str) -> None:
        folder = outputs / label
        folder.mkdir()
        cfg = replace(controller.config, specialists=settings)
        analyze(cfg, replace(task, specialist=name), target, folder)
        shutil.copyfile(folder / "analysis.json", work / f"{label}.json")

    collect("binary", {}, "binary")
    if evidence in {"ghidra", "combined"}:
        for index, selector in enumerate(selectors or [""]):
            settings = controller.config.specialists.get("ghidra", {})
            collect("ghidra", {"ghidra": {**settings, "function": selector}}, f"ghidra-{index:02}")
    if evidence in {"specialists", "combined"}:
        for index, name in enumerate(specialists):
            collect(name, controller.config.specialists, f"specialist-{index:02}")
    if rea_archive:
        from .campaign import static_evidence
        rea = static_evidence(rea_archive, target_inventory[binary]["sha256"])
        write_json(outputs / "rea-next.json", rea)
        shutil.copyfile(outputs / "rea-next.json", work / "rea-next.json")
    if inventory(target) != target_inventory:
        raise ValueError("analysis changed the target artifact")

    samples = []
    for case in public_cases:
        outcome = probe(reference_run, case, target, root / "home", image, stop)
        if not returned(outcome):
            write_json(root / "development-error.json", {"case": asdict(case), "execution": outcome})
            raise ValueError(f"reference did not produce a bounded development observation; see {root}")
        samples.append({"stdin": case.stdin, "argv": list(case.argv), "code": outcome["code"],
                        **{channel: outcome[channel].replace("\r\n", "\n") for channel in ("stdout", "stderr")}})
    write_json(public / "cases.json", samples)
    load_cases(public / "cases.json")
    write_json(work / "examples.json", [{**asdict(case), **observation}
                                       for case, observation in zip(public_cases, samples, strict=True)])
    lane = Controller(replace(controller.config, verification_image=image))
    job = lane.submit_task(task, profile_id=profile)
    write_json(root / "run.json", {
        "job": job, "profile": profile, "evidence": evidence, "image": image, "target": target_inventory,
        "rea_archive": str(rea_archive.resolve()) if rea_archive else None,
        "build_candidate": asdict(candidate_build), "candidate": asdict(candidate_run),
        "reference": asdict(reference_run), "deliverables": deliverables, "development": inventory(public),
    })
    result = lane.run_submitted(job)
    if result["status"] == "verified":
        path = Path(result["artifacts"])
        attempt = sorted(path.glob("attempt-*/output-inventory.json"))[-1]
        verified = json.loads(attempt.read_bytes())
        frozen = snapshot(attempt.parent / "workspace", root / "frozen", tuple(deliverables))
        if any(meta != verified.get(name) for name, meta in frozen.items()):
            raise ValueError("verified candidate changed before freezing")
        write_json(root / "frozen.json", frozen)
    write_json(root / "result.json", result)
    return {**result, "native_run": str(root)}


def grade(controller: Controller, run: Path, final: Path, audits: list[Path], workers: int) -> dict:
    bounded("grading workers", workers, 1, 8)
    run = run.resolve(strict=True)
    provenance = json.loads((run / "run.json").read_bytes())
    image, stop = provenance["image"], controller.config.state / "STOP"
    work, target = run / "frozen", run / "target"
    if inventory(target) != provenance["target"] or not work.is_dir():
        raise ValueError("final grading requires a frozen candidate and matching target")
    frozen = json.loads((run / "frozen.json").read_bytes())
    root = run / "final" / uuid4().hex
    candidate = root / "candidate"
    if snapshot(work, candidate, ()) != frozen:
        raise ValueError("frozen candidate digest changed")
    if inventory(run / "development") != provenance["development"]:
        raise ValueError("development suite digest changed")
    seen = {
        (row["stdin"], tuple(row["argv"]))
        for row in load_cases(run / "development" / "cases.json")
    }
    audit_inventory = {}
    for index, audit in enumerate(audits):
        audit_copy = root / "audit-inputs" / f"{index:02}.json"
        audit_copy.parent.mkdir(exist_ok=True)
        shutil.copyfile(audit, audit_copy)
        seen.update(c.stimulus for c in read_inputs(audit_copy, 512))
    if audits:
        audit_inventory = inventory(root / "audit-inputs")
    shutil.copyfile(final, root / "inputs.json")
    cases = read_inputs(root / "inputs.json", 512)
    if seen.intersection(case.stimulus for case in cases):
        raise ValueError("final stimuli overlap development or campaign audit")
    candidate_run, reference_run = (recipe(provenance, key) for key in ("candidate", "reference"))
    started = monotonic()
    if not build(recipe(provenance, "build_candidate"), candidate, root / "home", image,
                 stop, root / "build.json"):
        report = {"status": "failed", "detail": "final candidate build failed", "artifacts": str(root)}
        write_json(root / "report.json", report)
        return report
    traces = root / "observations"
    traces.mkdir()

    def compare(index_case: tuple[int, Case]) -> dict:
        index, case = index_case
        if stop.exists():
            return {"case": case.name, "group": case.group, "verdict": "inconclusive",
                    "differences": [], "detail": "stopped before invocation"}
        expected = probe(reference_run, case, target, root / "home", image, stop)
        actual = probe(candidate_run, case, candidate, root / "home", image, stop)
        differences = [field for field in ("code", "stdout", "stderr") if expected[field] != actual[field]]
        verdict = ("inconclusive" if not returned(expected) or not returned(actual)
                   else "mismatch" if differences else "pass")
        write_json(traces / f"{index:04}.json", {"reference": expected, "candidate": actual})
        return {"case": case.name, "group": case.group, "verdict": verdict, "differences": differences}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(compare, enumerate(cases)))
    counts = {key: sum(row["verdict"] == key for row in results) for key in ("pass", "mismatch", "inconclusive")}
    report = {
        "status": "failed" if counts["mismatch"] else "partial" if counts["inconclusive"] else "verified",
        "counts": counts, "cases": results, "seconds": round(monotonic() - started, 3),
        "artifacts": str(root), "image": image, "target": provenance["target"], "candidate": frozen,
        "audit_inventory": audit_inventory,
        "assurance": "Agreement on supplied invocations only. Unexercised inputs and environments remain unknown.",
    }
    write_json(root / "report.json", report)
    return report
