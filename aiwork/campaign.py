"""Dispatch a bounded REA-Next campaign in a fresh directory on a configured SSH host."""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .controller import Controller, write_json
from .process import executable, run
from .remote import SSH_OPTIONS, ssh_base


def campaign(controller: Controller, fixture: Path, profile_id: str, remote_root: str,
             image: str) -> dict:
    if not re.fullmatch(r"/home/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+", remote_root):
        raise ValueError("remote checkout must be a concrete path under /home")
    if any(part in {".", ".."} for part in remote_root.split("/")):
        raise ValueError("invalid remote checkout")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_./:@-]{0,150}", image):
        raise ValueError("invalid sandbox image")
    cfg = controller.config
    profile = next((p for p in cfg.profiles if p.id == profile_id and p.location == "a100"
                    and not p.managed and not p.api_key_env), None)
    if not profile:
        raise ValueError("campaign requires an existing A100 profile with private loopback inference")
    alias = cfg.ssh.get("alias", "")
    ssh = ssh_base(alias)
    scp = executable("scp")
    if not scp:
        raise ValueError("scp is required")
    port = cfg.ssh.get("remote_port", 18080)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid remote inference port")
    output = cfg.state / "campaigns" / uuid4().hex
    output.mkdir(parents=True)
    staging = output / "fixture"
    staging.mkdir()
    for name in ("source.c", "development.jsonl", "audit.jsonl"):
        path = (fixture / name).resolve(strict=True)
        if not path.is_relative_to(fixture.resolve()) or path.stat().st_size > 65536:
            raise ValueError(f"fixture file exceeds campaign scope: {name}")
        shutil.copyfile(path, staging / name)
    case_inputs = {}
    for name in ("development.jsonl", "audit.jsonl"):
        entries = [json.loads(line) for line in (staging / name).read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        if not 1 <= len(entries) <= 32 or any(
            not isinstance(item, dict) or not isinstance(item.get("name"), str)
            or not isinstance(item.get("stdin"), str) for item in entries
        ):
            raise ValueError(f"{name} requires 1–32 named REA-Next cases")
        case_inputs[name] = {item["stdin"] for item in entries}
    if case_inputs["development.jsonl"] & case_inputs["audit.jsonl"]:
        raise ValueError("campaign audit inputs must be distinct from development")
    write_json(staging / "synthesis.json", {
        "endpoint": f"http://127.0.0.1:{port}/v1", "model": profile.model,
        "language": "c", "candidates": 1, "max_model_turns": 2, "max_tokens": 8192,
        "max_prompt_chars": 75000, "thinking": False, "http_timeout": 70,
    })
    write_json(staging / "campaign.json", {
        "target": "program", "cases": "development.jsonl", "holdout": "audit.jsonl",
        "synthesis": "synthesis.json", "directory": "result", "docker_image": image,
        "docker_command": ["sudo", "-n", "docker"], "timeout": 4, "rounds": 2,
        "probes": 3, "experiments": 2, "wall_s": 210, "adapter_timeout": 100,
        "max_executions": 120, "audit_candidates": 1, "input": {"mode": "stdin", "args": []},
    })
    stop = cfg.state / "STOP"
    import os
    env = os.environ.copy()

    def call(argv, label, timeout):
        result = run(argv, output, timeout, env, stop)
        write_json(output / f"{label}.json", asdict(result))
        if result.code or result.timed_out or result.truncated:
            raise RuntimeError(f"campaign {label} failed; see {output / (label + '.json')}")
        return result.stdout.strip()

    with controller.planes["a100"].reserve(profile, 120):
        location = call([*ssh, alias, "mktemp -d /tmp/aiwork-p3.XXXXXXXX"], "allocate", 15)
        if not re.fullmatch(r"/tmp/aiwork-p3\.[A-Za-z0-9]{8}", location):
            raise ValueError("unexpected campaign staging directory")
        write_json(output / "dispatch.json", {"ssh_alias": alias, "remote_directory": location,
                                               "checkout": remote_root, "image": image, "profile": profile.id})
        call([scp, *SSH_OPTIONS, *[str(path) for path in staging.iterdir()], f"{alias}:{location}/"],
             "upload", 30)
        # Each interpolated string above is restricted to literal POSIX path/image characters.
        script = (
            f"set -eu; cd {location}; mkdir engine; "
            f"cp -R {remote_root}/reanext engine/reanext; "
            f"cp -R {remote_root}/profiles engine/profiles; "
            f"sudo -n docker image inspect {image} >/dev/null; "
            f"sudo -n docker run --rm --pull=never --network=none --cap-drop=ALL --memory=512m "
            f"--security-opt=no-new-privileges --pids-limit=64 --read-only --tmpfs /tmp "
            f"--user \"$(id -u):$(id -g)\" "
            f"--mount type=bind,src={location},dst=/fixture --workdir /fixture "
            f"--entrypoint gcc {image} -std=c11 -O2 -o program source.c; "
            "file program > binary-metadata.txt; sha256sum program >> binary-metadata.txt; "
            "cd engine; "
            f"timeout --kill-after=10s 270s {remote_root}/.venv/bin/python -B -m reanext.campaign "
            f"run {location}/campaign.json"
        )
        error = ""
        try:
            call([*ssh, alias, script], "run", 285)
        except RuntimeError as exc:
            error = str(exc)
        if not stop.exists():
            # Retrieve selected evidence trees via a portable archive kept in the isolated directory.
            package = (f"cd {location}; set -- binary-metadata.txt program result engine/runs; "
                       "paths=''; for path do if test -e \"$path\"; then paths=\"$paths $path\"; fi; done; "
                       "test -n \"$paths\"; tar -czf evidence.tar.gz $paths; "
                       "test $(wc -c < evidence.tar.gz) -lt 33554432")
            try:
                call([*ssh, alias, package], "package", 30)
                call([scp, *SSH_OPTIONS, f"{alias}:{location}/evidence.tar.gz", str(output / "evidence.tar.gz")],
                     "download", 40)
            except RuntimeError as exc:
                error = error or str(exc)
    result = {"status": "blocked" if error else "completed", "detail": error,
              "artifacts": str(output), "remote_directory": location}
    archive = output / "evidence.tar.gz"
    if archive.exists():
        import tarfile
        with tarfile.open(archive, "r:gz") as bundle:
            try:
                member = bundle.getmember("result/state.json")
            except KeyError:
                pass
            else:
                if member.isfile() and member.size <= 131072:
                    with bundle.extractfile(member) as stream:
                        state = json.load(stream)
                    write_json(output / "campaign-state.json", state)
                    result["decision"] = state.get("final_decision", state.get("status"))
                    if result["decision"] == "observed_agreement":
                        result["status"] = "verified"
    write_json(output / "result.json", result)
    return result
