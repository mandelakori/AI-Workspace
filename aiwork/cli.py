from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import nullcontext
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import sleep

from .controller import Controller
from .harness import opencode_path, qwen_command
from .inference import Inference, ollama_inventory
from .process import executable
from .remote import a100_session, ssh_probe
from .router import gpu
from .schema import Config, Task


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aiwork", description="Run and independently verify engineering jobs.")
    try:
        release = version("ai-workspace")
    except PackageNotFoundError:
        release = "source checkout"
    root.add_argument("--version", action="version", version=f"%(prog)s {release}")
    root.add_argument("--config", type=Path, help="operator TOML file, defaults to aiwork.local.toml")
    commands = root.add_subparsers(dest="command", required=True)
    project = commands.add_parser("project", help="index repositories and retrieve scoped context or evidence")
    project.add_argument("action", choices=["index", "focus", "evidence"])
    project.add_argument("root", type=Path)
    project.add_argument("--query", default="")
    project.add_argument("--limit", type=int, default=20)
    project.add_argument("--scope", action="append", default=[])
    draft = commands.add_parser("draft", help="propose an execution policy for operator review")
    draft.add_argument("root", type=Path)
    draft.add_argument("objective")
    draft.add_argument("--profile", required=True)
    campaign = commands.add_parser("campaign", help="dispatch an authorized self-authored REA-Next fixture")
    campaign.add_argument("fixture", type=Path)
    campaign.add_argument("--profile", required=True)
    campaign.add_argument("--remote-root", required=True)
    campaign.add_argument("--image", required=True)
    recovery = commands.add_parser("campaign-recover", help="verify a reconstruction from static evidence")
    recovery.add_argument("archive", type=Path)
    recovery.add_argument("analysis", type=Path)
    recovery.add_argument("--profile", required=True)
    recovery.add_argument("--manifest", type=Path, help="use custom objective, deliverables and candidate recipes")
    native = commands.add_parser("native", help="reconstruct or independently grade an authorized native target")
    native_actions = native.add_subparsers(dest="action", required=True)
    reconstruction = native_actions.add_parser("run", help="run a configurable native development campaign")
    reconstruction.add_argument("manifest", type=Path)
    reconstruction.add_argument("--profile", required=True)
    reconstruction.add_argument("--evidence", choices=["static", "ghidra", "specialists", "combined"],
                                default="static")
    reconstruction.add_argument("--trusted", action="store_true", help="authorize configured host static tools")
    reconstruction.add_argument("--rea-archive", type=Path, help="import matching static REA-Next evidence")
    grading = native_actions.add_parser("grade", help="compare a frozen candidate against unseen inputs")
    grading.add_argument("run", type=Path)
    grading.add_argument("--cases", type=Path, required=True)
    grading.add_argument("--audit", type=Path, action="append", default=[])
    grading.add_argument("--workers", type=int, default=1)
    commands.add_parser("doctor", help="show Python, GPU and executable inventory")
    commands.add_parser("models", help="discover configured endpoints and model inventory")
    commands.add_parser("harnesses", help="show harness executable inventory")
    commands.add_parser("tools", help="list built-in tools and configured specialist adapters")
    remote = commands.add_parser("a100", help="inspect SSH and manage scoped Lambda lifecycle")
    remote.add_argument("action", nargs="?", choices=["status", "plan", "instances", "types",
                                                    "start", "stop"], default="status")
    remote.add_argument("--apply", action="store_true", help="apply the configured mutation")
    remote.add_argument("--instance")
    remote.add_argument("--timeout", type=int, default=900)
    comparison = commands.add_parser("benchmark", help="compare explicit profiles on frozen engineering fixtures")
    comparison.add_argument("manifest", type=Path)
    comparison.add_argument("--profile", action="append", required=True)
    comparison.add_argument("--repeats", type=int, default=1)
    comparison.add_argument("--trusted", action="store_true")
    comparison.add_argument("--suite", action="store_true", help="run all manifests in a suite")
    workflow = commands.add_parser("workflow", help="run or resume a deterministic dependency graph")
    workflow.add_argument("manifest", type=Path)
    workflow.add_argument("--id", required=True)
    workflow.add_argument("--workers", type=int, default=2)
    workflow.add_argument("--trusted", action="store_true")
    planning = commands.add_parser("plan", help="plan, run and integrate an engineering objective")
    planning.add_argument("manifest", type=Path)
    planning.add_argument("--id", required=True)
    planning.add_argument("--workers", type=int, default=2)
    planning.add_argument("--planner", default="")
    planning.add_argument("--max-steps", type=int, default=8)
    planning.add_argument("--min-steps", type=int, default=1)
    planning.add_argument("--cover-commands", action="store_true",
                          help="require every approved command to be assigned to a step")
    planning.add_argument("--plan-only", action="store_true")
    planning.add_argument("--reviewed", type=Path, help="operator-reviewed JSON graph")
    planning.add_argument("--supersedes", default="", help="reuse unchanged verified steps from a prior plan")
    planning.add_argument("--pause-after", type=int, default=0, help="checkpoint after this many steps")
    planning.add_argument("--trusted", action="store_true")
    promotion = commands.add_parser("patch", help="inspect the verified patch and optionally check a Git checkout")
    promotion.add_argument("id")
    promotion.add_argument("--plan", action="store_true")
    promotion.add_argument("--check", type=Path)
    self_task = commands.add_parser("self", help="propose a read-only index improvement from a committed checkout")
    self_task.add_argument("--repo", type=Path, default=Path("."))
    self_task.add_argument("--profile", default="")
    self_task.add_argument("--objective", default="")
    self_task.add_argument("--manifest", type=Path, help="reviewed engineering scope and checks for the checkout")
    self_task.add_argument("--trusted", action="store_true")
    task = commands.add_parser("task", help="submit, inspect, or resume a job")
    actions = task.add_subparsers(dest="action", required=True)
    for name in ("submit", "run", "inspect"):
        command = actions.add_parser(name)
        command.add_argument("manifest", type=Path)
        if name != "inspect":
            command.add_argument("--profile", default="")
            command.add_argument("--trusted", action="store_true",
                                 help="allow reviewed source and checks to execute on the host")
    resume = actions.add_parser("resume")
    resume.add_argument("job")
    resume.add_argument("--interrupted", action="store_true",
                        help="requeue a running job after confirming its worker exited")
    resume.add_argument("--reset", action="store_true", help="resume from the frozen source without older edits")
    checkpoint = actions.add_parser("verify-checkpoint", help="retest an engineering checkpoint without inference")
    checkpoint.add_argument("job")
    checkpoint.add_argument("--attempt", type=int, required=True)
    work = commands.add_parser("worker", help="consume the persistent queue")
    work.add_argument("--once", action="store_true")
    work.add_argument("--exclusive", action="store_true", help="allow one background worker per state directory")
    runs = commands.add_parser("runs", help="list jobs or inspect one job")
    runs.add_argument("job", nargs="?")
    emergency = commands.add_parser("control", help="pause new work or resume queue dispatch")
    emergency.add_argument("action", choices=["stop", "start", "status"])
    return root


def print_json(data) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=True), flush=True)


def discover(cfg: Config) -> list[dict]:
    found = []
    for profile in cfg.profiles:
        try:
            connection = a100_session(cfg, profile) if profile.location == "a100" else nullcontext()
            with connection:
                data = Inference(profile).models()
                found.append({"profile": profile.id, "available": any(
                    p.get("id") == profile.model for p in data), "inventory": data,
                    **(ollama_inventory(profile.endpoint) if profile.engine == "ollama" else {})})
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            found.append({"profile": profile.id, "available": False, "error": str(exc)})
    if not cfg.profiles:
        from .http import request
        for engine, url in (("ollama", "http://127.0.0.1:11434/v1"),
                            ("openai", "http://127.0.0.1:8080/v1")):
            try:
                found.append({"engine": engine, "endpoint": url, "available": True,
                              "inventory": request(url + "/models", timeout=2)["data"],
                              **(ollama_inventory(url) if engine == "ollama" else {})})
            except (OSError, RuntimeError, ValueError, KeyError) as exc:
                found.append({"engine": engine, "endpoint": url, "available": False, "error": str(exc)})
    return found


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.config is not None and not args.config.is_file():
            raise ValueError(f"configuration file not found: {args.config}")
        cfg = Config.load(args.config or Path("aiwork.local.toml"))
        controller = Controller(cfg)
        if args.command == "project":
            from .project import ProjectStore
            from .schema import bounded, relative
            bounded("limit", args.limit, 1, 128)
            store = ProjectStore(cfg.state)
            updated = store.refresh(args.root)
            if args.action == "focus":
                updated["focus"] = store.focus(args.root, args.query, args.limit,
                                               tuple(relative(path) for path in args.scope))
            elif args.action == "evidence":
                updated["evidence"] = store.recall(args.root)
            print_json(updated)
        elif args.command == "draft":
            from .draft import draft
            result = draft(controller, args.root, args.objective, args.profile)
            print_json(result)
            return 0 if result["status"] == "review" else 1
        elif args.command == "campaign":
            from .campaign import campaign
            result = campaign(controller, args.fixture, args.profile, args.remote_root, args.image)
            print_json(result)
            return 0 if result["status"] == "verified" else 1
        elif args.command == "campaign-recover":
            from .native_recovery import recover
            result = recover(controller, args.archive, args.analysis, args.profile, args.manifest)
            print_json(result)
            return 0 if result["status"] == "verified" else 1
        elif args.command == "native":
            from .native import grade, reconstruct
            if args.action == "run":
                result = reconstruct(controller, args.manifest, args.profile,
                                     evidence=args.evidence, trusted=args.trusted, rea_archive=args.rea_archive)
            else:
                result = grade(controller, args.run, args.cases, args.audit, args.workers)
            print_json(result)
            return 0 if result["status"] == "verified" else 1
        elif args.command == "doctor":
            from .verify import runner_status
            print_json({"python": sys.version, "state": cfg.state, "gpus": gpu(cfg.state),
                        "tools": {name: executable(name) for name in ("ssh", "docker", "git")},
                        "qwen": qwen_command(cfg.qwen, cfg.state),
                        "opencode": opencode_path(cfg.opencode), "profiles": [p.id for p in cfg.profiles],
                        "verification_runner": runner_status(cfg.state, cfg.verification_image)})
        elif args.command == "harnesses":
            print_json({"opencode": opencode_path(cfg.opencode), "qwen": qwen_command(cfg.qwen, cfg.state)})
        elif args.command == "tools":
            from .specialists import capabilities
            print_json({"preprocessing": ["inventory", "sha256", "python-symbols", "binary"],
                        "specialists": ["binary", *sorted(cfg.specialists)],
                        "specialist_capabilities": capabilities(cfg),
                        "harness_mcp": ["checks:check (manifest test index)"],
                        "git": executable("git"), "verification_image": cfg.verification_image})
        elif args.command == "models":
            print_json(discover(cfg))
        elif args.command == "benchmark":
            from .benchmark import benchmark, suite
            evaluate = suite if args.suite else benchmark
            result = evaluate(controller, args.manifest, args.profile, args.repeats, args.trusted)
            print_json(result)
            return 0 if result["samples"] and all(
                row["status"] == "verified" for row in result["samples"]) else 1
        elif args.command == "workflow":
            from .workflow import execute
            result = execute(controller, args.manifest, args.workers, args.trusted, args.id)
            print_json(result)
            return 0 if result["status"] == "verified" else 1
        elif args.command == "plan":
            from .planner import planned
            result = planned(controller, args.manifest, args.id, args.workers, args.trusted,
                             args.planner, args.plan_only, args.max_steps, args.cover_commands, args.min_steps,
                             reviewed=args.reviewed, supersedes=args.supersedes, pause_after=args.pause_after)
            print_json(result)
            return 0 if result["status"] in {"verified", "paused"} or args.plan_only else 1
        elif args.command == "patch":
            import re
            from .planner import terminal
            if args.plan:
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}", args.id):
                    raise ValueError("invalid plan ID")
                record = json.loads((cfg.state / "plans" / args.id / "result.json").read_text(encoding="utf-8"))
            else:
                _, record = terminal(controller, args.id)
            if record["status"] != "verified" or not record.get("patch"):
                raise ValueError("no verified engineering patch")
            patch = Path(record["patch"])
            if hashlib.sha256(patch.read_bytes()).hexdigest() != record["patch_sha256"]:
                raise ValueError("patch hash no longer matches verification evidence")
            result = {"patch": patch, "sha256": record["patch_sha256"], "changed": record["changed"]}
            if args.check:
                from .process import run
                git = executable("git")
                if not git:
                    raise ValueError("Git executable unavailable")
                outcome = run([git, "-c", "core.autocrlf=false", "apply", "--check", "--", str(patch)],
                              args.check.resolve(strict=True),
                              30, os.environ.copy())
                result.update({"applies": outcome.code == 0 and not outcome.timed_out,
                               "diagnostic": outcome.stderr[-1000:]})
            print_json(result)
            return 0 if result.get("applies", True) else 1
        elif args.command == "self":
            from .selfdev import propose
            result = propose(controller, args.repo, args.profile, args.trusted, args.objective, args.manifest)
            print_json(result)
            return 0 if result["status"] == "verified" else 1
        elif args.command == "a100":
            if args.action != "status":
                from .cloud import Lambda, Lifecycle
                from .schema import bounded
                provider = Lambda(cfg.lambda_cloud.get("key_env", "LAMBDA_API_KEY"))
                lifecycle = Lifecycle(provider, cfg.lambda_cloud, cfg.state)
                if args.action == "instances":
                    result = provider.instances()
                elif args.action == "types":
                    result = provider.types()
                elif args.action == "stop":
                    if not args.instance:
                        raise ValueError("a100 stop requires --instance")
                    result = lifecycle.terminate(args.instance, apply=args.apply)
                elif args.action == "start" and args.apply:
                    bounded("timeout", args.timeout, 5, 3600)
                    result = lifecycle.acquire(args.timeout, allow_launch=True)
                else:
                    result = lifecycle.plan()
                print_json(result)
                return 0
            result = ssh_probe(cfg.ssh.get("alias", "aisak"))
            print_json(result)
            return 0 if result["ok"] else 1
        elif args.command == "task":
            if args.action == "inspect":
                print_json(Task.load(args.manifest).__dict__)
            elif args.action == "resume":
                controller.resume(args.job, args.interrupted, args.reset)
                print_json({"job": args.job, "status": "queued"})
            elif args.action == "verify-checkpoint":
                result = controller.verify_checkpoint(args.job, args.attempt)
                print_json(result)
                return 0 if result["status"] == "verified" else 1
            else:
                job = controller.submit(args.manifest, args.trusted, profile_id=args.profile)
                result = controller.run_submitted(job) if args.action == "run" else None
                print_json(result or {"job": job, "status": "queued"})
                return 0 if not result or result["status"] == "verified" else 1
        elif args.command == "runs":
            print_json({"jobs": controller.state.jobs(args.job),
                        "attempts": controller.state.attempts(args.job) if args.job else []})
        elif args.command == "control":
            from .lock import file_lock
            marker = cfg.state / "STOP"
            if args.action == "stop":
                marker.touch()
            elif args.action == "start":
                marker.unlink(missing_ok=True)
            try:
                with file_lock(cfg.state / "controller.lock"):
                    worker = False
            except TimeoutError:
                worker = True
            print_json({"paused": marker.exists(), "background_worker_active": worker})
        elif args.command == "worker":
            from .lock import file_lock
            with file_lock(cfg.state / "controller.lock") if args.exclusive else nullcontext():
                while True:
                    if (cfg.state / "STOP").exists():
                        return 0
                    result = controller.work()
                    if result:
                        print_json(result)
                    if args.once:
                        return 0 if not result or result["status"] == "verified" else 1
                    if not result:
                        sleep(1)
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        print(f"aiwork: {exc}", file=sys.stderr)
        return 2
