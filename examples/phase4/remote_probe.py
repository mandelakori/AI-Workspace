"""Measure the existing A100 lane or interrupt one owned test tunnel."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from statistics import median
from time import monotonic
from unittest.mock import patch
from uuid import uuid4

from aiwork.cli import print_json
from aiwork.controller import Controller, write_json
from aiwork.harness import OpenCode, QwenCode
from aiwork.http import request
from aiwork.inference import Inference
from aiwork.remote import a100_session
from aiwork.schema import Config


def throughput(controller, profile):
    endpoint = profile.endpoint.rstrip("/")
    prompts = ["Write the integers 1 to 32, in order, separated by single spaces. No other text.",
               "Write the integers 33 to 64, in order, separated by single spaces. No other text."]

    def complete(index):
        started = monotonic()
        reply = request(endpoint + "/chat/completions", "POST", {
            "model": profile.model, "messages": [{"role": "user", "content": prompts[index]}],
            "temperature": 0, "max_tokens": 160, "seed": 42,
        }, timeout=45)
        words = reply["choices"][0]["message"]["content"].split()
        expected = [str(x) for x in range(index * 32 + 1, index * 32 + 33)]
        return {"prompt": index, "pass": words == expected, "response": words,
                "seconds": round(monotonic() - started, 3), "usage": reply.get("usage")}

    with controller.planes["a100"].reserve(profile, 400), a100_session(controller.config, profile):
        try:
            props = request(endpoint.removesuffix("/v1") + "/props")
        except (OSError, RuntimeError, ValueError):
            props = {}
        batches = []
        for workers in (1, 2, 2, 1, 1, 2):
            started = monotonic()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                rows = list(pool.map(complete, (0, 1)))
            batches.append({"workers": workers, "seconds": round(monotonic() - started, 3), "requests": rows})
    return {"reported_slots": props.get("total_slots"), "prompts": prompts, "batches": batches,
            "median_seconds": {workers: median(b["seconds"] for b in batches if b["workers"] == workers)
                               for workers in (1, 2)},
            "status": ("verified" if all(r["pass"] for batch in batches for r in batch["requests"])
                       else "failed")}


def recovery(controller, profile, fixture):
    from aiwork import remote

    harness = OpenCode if profile.harness == "opencode" else QwenCode
    execute = harness.execute
    owned = None
    fault = {}

    @contextmanager
    def record_tunnel(*args, **kwargs):
        nonlocal owned
        with a100_session(*args, **kwargs) as proc:
            owned = proc
            yield proc

    def disconnect(self, *args, **kwargs):
        if owned is None or owned.poll() is not None:
            raise RuntimeError("the disposable SSH forward was not active")
        owned.terminate()
        owned.wait(timeout=5)
        fault.update(local_ssh_pid=owned.pid, exit_code=owned.returncode)
        try:
            Inference(profile).ready()
        except (OSError, RuntimeError, ValueError) as exc:
            fault["readiness_error"] = str(exc)
        return execute(self, *args, **kwargs)

    job = controller.submit(fixture, profile_id=profile.id)
    started = monotonic()
    with patch.object(remote, "a100_session", record_tunnel), patch.object(harness, "execute", disconnect):
        failed = controller.run_submitted(job)
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
        result = (throughput(controller, profile) if args.action == "throughput"
                  else recovery(controller, profile, fixture))
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        result = {"status": "blocked", "detail": str(error)}
    write_json(root / "report.json", result)
    print_json({**result, "report": root / "report.json"})
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
