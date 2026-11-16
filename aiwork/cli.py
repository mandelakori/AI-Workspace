from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from time import sleep

from .controller import Controller
from .harness import opencode_path
from .inference import Inference, ollama_inventory
from .process import executable
from .remote import a100_session, ssh_probe
from .router import gpu
from .schema import Config, Task


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aiwork", description="Run and independently verify engineering jobs.")
    root.add_argument("--config", type=Path, default=Path("aiwork.local.toml"))
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="show Python, GPU and executable inventory")
    commands.add_parser("models", help="discover configured endpoints and model inventory")
    commands.add_parser("harnesses", help="show harness executable inventory")
    remote = commands.add_parser("a100", help="inspect SSH and manage scoped Lambda lifecycle")
    remote.add_argument("action", nargs="?", choices=["status", "plan", "instances", "types",
                                                    "start", "stop"], default="status")
    remote.add_argument("--apply", action="store_true", help="apply the configured mutation")
    remote.add_argument("--instance")
    remote.add_argument("--timeout", type=int, default=900)
    comparison = commands.add_parser("benchmark", help="compare explicit profiles on one frozen-input fixture")
    comparison.add_argument("manifest", type=Path)
    comparison.add_argument("--profile", action="append", required=True)
    comparison.add_argument("--repeats", type=int, default=1)
    comparison.add_argument("--trusted", action="store_true")
    workflow = commands.add_parser("workflow", help="run or resume a deterministic dependency graph")
    workflow.add_argument("manifest", type=Path)
    workflow.add_argument("--id", required=True)
    workflow.add_argument("--workers", type=int, default=2)
    workflow.add_argument("--trusted", action="store_true")
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
    return found


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        cfg = Config.load(args.config)
        controller = Controller(cfg)
        if args.command == "doctor":
            print_json({"python": sys.version, "state": cfg.state, "gpus": gpu(cfg.state),
                        "tools": {name: executable(name) for name in ("ssh", "docker", "git", "qwen")},
                        "opencode": opencode_path(cfg.opencode), "profiles": [p.id for p in cfg.profiles]})
        elif args.command == "harnesses":
            print_json({"opencode": opencode_path(cfg.opencode), "qwen": executable(cfg.qwen or "qwen")})
        elif args.command == "models":
            print_json(discover(cfg))
        elif args.command == "benchmark":
            from .benchmark import benchmark
            result = benchmark(controller, args.manifest, args.profile, args.repeats, args.trusted)
            print_json(result)
            return 0 if result["samples"] and all(
                row["status"] == "verified" for row in result["samples"]) else 1
        elif args.command == "workflow":
            from .workflow import execute
            result = execute(controller, args.manifest, args.workers, args.trusted, args.id)
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
                controller.resume(args.job, args.interrupted)
                print_json({"job": args.job, "status": "queued"})
            else:
                job = controller.submit(args.manifest, args.trusted, profile_id=args.profile)
                result = controller.work(job) if args.action == "run" else None
                print_json(result or {"job": job, "status": "queued"})
                return 0 if not result or result["status"] == "verified" else 1
        elif args.command == "runs":
            print_json({"jobs": controller.state.jobs(args.job),
                        "attempts": controller.state.attempts(args.job) if args.job else []})
        elif args.command == "control":
            marker = cfg.state / "STOP"
            if args.action == "stop":
                marker.touch()
            elif args.action == "start":
                marker.unlink(missing_ok=True)
            print_json({"paused": marker.exists()})
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
