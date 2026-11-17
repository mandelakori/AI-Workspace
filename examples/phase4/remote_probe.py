"""Measure the existing A100 lane or interrupt one owned test tunnel."""
import argparse
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from statistics import median
from time import monotonic
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from aiwork.cli import print_json
from aiwork.controller import Controller, write_json
from aiwork.harness import OpenCode, QwenCode, request_options
from aiwork.http import request
from aiwork.inference import Inference
from aiwork.remote import a100_session
from aiwork.schema import Config


def throughput(controller, profile, artifacts):
    endpoint = profile.endpoint.rstrip("/")
    prompts = ["Write the integers 1 to 32, in order, separated by single spaces. No other text.",
               "Write the integers 33 to 64, in order, separated by single spaces. No other text."]
    options = request_options(profile)

    def complete(index):
        started = monotonic()
        try:
            reply = request(endpoint + "/chat/completions", "POST", {
                "model": profile.model, "messages": [{"role": "user", "content": prompts[index]}],
                "temperature": 0, "max_tokens": 160, "seed": 42, **options,
            }, timeout=45)
        except (OSError, RuntimeError, ValueError) as exc:
            return {"prompt": index, "pass": False, "error": str(exc),
                    "seconds": round(monotonic() - started, 3), "usage": None}
        choices = reply.get("choices") or [{}]
        choice = choices[0] if isinstance(choices, list) and isinstance(choices[0], dict) else {}
        message = choice.get("message")
        message = message if isinstance(message, dict) else {}
        content = message.get("content")
        words = content.split() if isinstance(content, str) else []
        expected = [str(x) for x in range(index * 32 + 1, index * 32 + 33)]
        return {"prompt": index, "pass": words == expected, "response": words,
                "seconds": round(monotonic() - started, 3), "usage": reply.get("usage"),
                "finish_reason": choice.get("finish_reason"),
                "reasoning_present": bool(message.get("reasoning_content"))}

    with controller.planes["a100"].reserve(profile, 400), a100_session(controller.config, profile):
        try:
            props = request(endpoint.removesuffix("/v1") + "/props")
            props_error = None
        except (OSError, RuntimeError, ValueError) as exc:
            props = {}
            props_error = str(exc)
        capacity = {"total_slots": props.get("total_slots"),
                    "default_context": (props.get("default_generation_settings") or {}).get("n_ctx"),
                    "error": props_error}
        write_json(artifacts / "capacity.json", capacity)
        batches = []
        for workers in (1, 2, 2, 1, 1, 2):
            if (controller.config.state / "STOP").exists():
                break
            started = monotonic()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                rows = list(pool.map(complete, (0, 1)))
            batches.append({"workers": workers, "seconds": round(monotonic() - started, 3), "requests": rows})
            write_json(artifacts / f"batch-{len(batches):02}.json", batches[-1])
    requests = [row for batch in batches for row in batch["requests"]]
    return {"reported_slots": capacity["total_slots"], "capacity": capacity, "prompts": prompts, "batches": batches,
            "request_options": options,
            "request_count": len(requests), "correct": sum(row["pass"] for row in requests),
            "median_seconds": {workers: median(times) for workers in (1, 2)
                               if (times := [b["seconds"] for b in batches if b["workers"] == workers])},
            "status": ("partial" if len(requests) != 12 else
                       "verified" if all(row["pass"] for row in requests) else "failed")}


def recovery(controller, profile, fixture, artifacts):
    from aiwork import remote

    harness = OpenCode if profile.harness == "opencode" else QwenCode
    owned = None
    fault = {}

    @contextmanager
    def record_tunnel(*args, **kwargs):
        nonlocal owned
        with a100_session(*args, **kwargs) as proc:
            owned = proc
            yield proc

    def disconnect(self, *args, **kwargs):
        cfg = controller.config
        port = urlsplit(profile.endpoint).port
        forward = f"127.0.0.1:{port}:127.0.0.1:{cfg.ssh.get('remote_port', 18080)}"
        expected = ["-N", "-T", "-L", forward, cfg.ssh["alias"]]
        if (not isinstance(owned, subprocess.Popen) or owned.poll() is not None
            or list(owned.args[-5:]) != expected):
            raise RuntimeError("could not confirm the test-owned SSH forwarding subprocess")
        fault.update(local_ssh_pid=owned.pid, test_pid=os.getpid(), argv=owned.args,
                     ownership="Popen handle returned to this test by a100_session")
        write_json(artifacts / "fault.json", fault)
        owned.terminate()
        owned.wait(timeout=5)
        fault.update(exit_code=owned.returncode)
        try:
            Inference(profile).ready()
        except (OSError, RuntimeError, ValueError) as exc:
            fault["readiness_error"] = str(exc)
            write_json(artifacts / "fault.json", fault)
            raise RuntimeError("test-owned SSH forward disconnected; model readiness failed") from exc
        write_json(artifacts / "fault.json", fault)
        raise RuntimeError("endpoint remained reachable after stopping the test-owned forward")

    job = controller.submit(fixture, profile_id=profile.id)
    started = monotonic()
    with patch.object(remote, "a100_session", record_tunnel), patch.object(harness, "execute", disconnect):
        failed = controller.run_submitted(job)
    write_json(artifacts / "first.json", failed)
    if "readiness_error" not in fault or failed["status"] not in {"blocked", "failed", "partial"}:
        return {"status": "failed", "first": failed, "fault": fault}
    controller.resume(job)
    recovered = controller.run_submitted(job)
    return {"status": recovered["status"], "first": failed, "recovered": recovered, "fault": fault,
            "seconds": round(monotonic() - started, 3),
            "attempts": [row["status"] for row in controller.state.attempts(job)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("throughput", "recovery"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    cfg = Config.load(args.config)
    controller = Controller(cfg)
    profile = next((p for p in cfg.profiles if p.id == args.profile and p.location == "a100"
                    and p.engine == "llamacpp" and not p.managed and not p.api_key_env), None)
    if not profile or not cfg.ssh.get("alias"):
        parser.error("select an existing private llama.cpp SSH profile")
    fixture = Path(__file__).resolve().parents[1] / "coding.toml"
    if args.action == "recovery" and not cfg.verification_image:
        parser.error("recovery requires the offline verification image")
    root = cfg.state / "remote-probes" / uuid4().hex
    root.mkdir(parents=True)
    write_json(root / "inputs.json", {"action": args.action, "profile": asdict(profile)})
    try:
        result = (throughput(controller, profile, root) if args.action == "throughput"
                  else recovery(controller, profile, fixture, root))
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        result = {"status": "blocked", "detail": str(error)}
    write_json(root / "report.json", result)
    print_json({**result, "report": root / "report.json"})
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
