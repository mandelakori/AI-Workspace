"""Dispatch a bounded REA-Next campaign in a fresh directory on a configured SSH host."""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import tarfile
import tomllib
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .controller import Controller, write_json
from .process import executable, run
from .remote import SSH_OPTIONS, ssh_base
from .oracle import case_argv
from .schema import Check
from .workspace import contained


def static_evidence(archive: Path, target_digest: str) -> list[dict]:
    if archive.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("campaign archive exceeds 32 MiB")
    with tarfile.open(archive, "r:gz") as bundle:
        expanded = 0
        seen = set()
        listings = {}
        findings = {}
        digest = None
        for index, member in enumerate(bundle):
            expanded += member.size
            if index >= 2048 or expanded > 64 * 1024 * 1024:
                raise ValueError("campaign archive exceeds the expansion budget")
            selected = re.fullmatch(r"(engine/runs/[a-zA-Z0-9_-]+/analysis)/"
                                    r"(analysis\.json|file\.txt|readelf\.txt|objdump\.txt)", member.name)
            if not selected and member.name != "program":
                continue
            if member.name in seen:
                raise ValueError("duplicate campaign evidence entry")
            seen.add(member.name)
            limit = 2 * 1024 * 1024 if member.name == "program" else 256 * 1024
            if not member.isfile() or member.size > limit:
                raise ValueError("campaign evidence requires bounded regular files")
            with bundle.extractfile(member) as stream:
                if selected and selected[2] == "analysis.json":
                    findings[selected[1]] = json.load(stream)
                elif selected:
                    listings[member.name] = stream.read()
                else:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if (digest != target_digest or not findings or len(findings) > 4
        or any(not isinstance(row, dict) or row.get("target_sha256") != digest for row in findings.values())):
        raise ValueError("REA-Next static evidence must match the selected target digest")
    collected = []
    for directory, row in sorted(findings.items()):
        evidence = {key: row[key] for key in ("target_sha256", "size", "format", "strings") if key in row}
        evidence["listings"] = {}
        for tool in ("file", "readelf", "objdump"):
            entry = row.get("tools", {}).get(tool, {})
            if output := listings.get(f"{directory}/{tool}.txt"):
                if hashlib.sha256(output).hexdigest() != entry.get("sha256"):
                    raise ValueError(f"REA-Next {tool} evidence digest changed")
                evidence["listings"][tool] = {"sha256": entry["sha256"],
                                              "text": output[:16384].decode("utf-8", "replace"),
                                              "truncated": len(output) > 16384}
        collected.append(evidence)
    return collected


def stage_fixture(fixture: Path, staging: Path) -> tuple[tuple[str, ...], dict]:
    """Stage the legacy bundle or an explicit executable/build and REA transport."""
    if fixture.is_dir():
        base = fixture
        spec = {"sources": ["source.c"], "build": {"argv": ["gcc", "-std=c11", "-O2", "-o",
                                                           "program", "source.c"]},
                "development": "development.jsonl", "audit": "audit.jsonl"}
    else:
        base = fixture.resolve(strict=True).parent
        spec = tomllib.loads(fixture.read_text(encoding="utf-8"))
    if spec.keys() - {"sources", "artifact", "build", "development", "audit", "input"}:
        raise ValueError("unknown campaign fixture fields")
    transport = spec.get("input", {"mode": "stdin", "args": []})
    if (not isinstance(transport, dict) or transport.keys() - {"mode", "args", "filename"}
        or transport.get("mode") not in {"stdin", "file"}):
        raise ValueError("campaign input mode must be stdin or file")
    case_argv(transport.get("args", []))
    filename = transport.get("filename", "input.txt")
    if not isinstance(filename, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", filename):
        raise ValueError("campaign input filename must be a simple filename")

    def copy(name: str, destination: str, limit: int) -> None:
        path = contained(base, name)
        if not path.is_file() or path.stat().st_size > limit:
            raise ValueError(f"fixture file exceeds campaign scope: {name}")
        shutil.copyfile(path, staging / destination)

    copy(spec["development"], "development.jsonl", 65536)
    copy(spec["audit"], "audit.jsonl", 65536)
    if "artifact" in spec:
        if "build" in spec or "sources" in spec:
            raise ValueError("campaign artifact and source build are mutually exclusive")
        copy(spec["artifact"], "program", 2 * 1024 * 1024)
        with (staging / "program").open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                raise ValueError("REA-Next Linux runner requires ELF")
        return (), transport
    sources = spec.get("sources")
    if (not isinstance(sources, list) or not 1 <= len(sources) <= 16 or
        any(not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", name)
            or name in {"program", "campaign.json", "synthesis.json", "development.jsonl", "audit.jsonl"}
            for name in sources) or len({name.casefold() for name in sources}) != len(sources)):
        raise ValueError("campaign sources require distinct flat filenames")
    check = Check.read(spec["build"])
    if set(spec["build"]) != {"argv"}:
        raise ValueError("campaign build expects only a Docker command vector")
    for name in sources:
        copy(name, name, 65536)
    return check.argv, transport


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
    compiler, transport = stage_fixture(fixture.resolve(strict=True), staging)
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
        "max_executions": 120, "audit_candidates": 1, "input": transport,
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
        build = (
            f"sudo -n docker run --rm --pull=never --network=none --cap-drop=ALL --memory=512m "
            f"--security-opt=no-new-privileges --pids-limit=64 --read-only --tmpfs /tmp "
            f"--user \"$(id -u):$(id -g)\" "
            f"--mount type=bind,src={location},dst=/fixture --workdir /fixture "
            f"--entrypoint {shlex.quote(compiler[0])} {image} "
            f"{shlex.join(compiler[1:])}; " if compiler else ""
        )
        script = (
            f"set -eu; cd {location}; mkdir engine; "
            f"cp -R {remote_root}/reanext engine/reanext; "
            f"cp -R {remote_root}/profiles engine/profiles; "
            f"sudo -n docker image inspect {image} >/dev/null; {build}"
            "chmod u+x program; "
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
