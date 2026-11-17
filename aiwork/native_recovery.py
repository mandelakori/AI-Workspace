"""Reconstruct an authorized toy from static evidence and grade it from a campaign archive."""
from __future__ import annotations

import hashlib
import json
import re
import tarfile
import tomllib
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from .controller import Controller, write_json
from .native import recipe
from .oracle import load_cases
from .schema import Task, relative


def recover(controller: Controller, archive: Path, analysis: Path, profile: str,
            manifest: Path | None = None) -> dict:
    if archive.stat().st_size > 32 * 1024 * 1024 or analysis.stat().st_size > 128 * 1024:
        raise ValueError("native recovery requires bounded campaign and static analysis artifacts")
    findings = json.loads(analysis.read_bytes())
    if findings.get("specialist") != "ghidra" or not isinstance(findings.get("decompilation"), str):
        raise ValueError("recovery requires AI Workspace Ghidra function evidence")
    intake_path = analysis.parent.parent / "intake.json"
    if intake_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("static input inventory exceeds the recovery budget")
    intake = json.loads(intake_path.read_bytes())
    selected = intake["inventory"][findings["binary"]]
    cases = []
    with tarfile.open(archive, "r:gz") as bundle:
        members = []
        expanded = 0
        for member in bundle:
            members.append(member)
            expanded += member.size
            if len(members) > 2048 or expanded > 64 * 1024 * 1024:
                raise ValueError("campaign archive exceeds the recovery expansion budget")

        def read(member: tarfile.TarInfo, limit: int) -> bytes:
            if not member.isfile() or member.size > limit:
                raise ValueError("campaign evidence must be a small regular file")
            with bundle.extractfile(member) as file:
                return file.read()

        digest = hashlib.sha256(read(bundle.getmember("program"), 2 * 1024 * 1024)).hexdigest()
        if selected["sha256"] != digest:
            raise ValueError("Ghidra evidence and archive describe different binaries")
        audit = sorted((member for member in members if re.fullmatch(r"result/audit-0/[0-9]{5}\.json",
                                                                    member.name)),
                       key=lambda member: member.name)
        if not 1 <= len(audit) <= 32:
            raise ValueError("campaign must contain a bounded, completed audit transcript")
        campaign = json.loads(read(bundle.getmember("result/state.json"), 128 * 1024))
        if (campaign.get("status") != "complete" or campaign.get("audit_total") != len(audit)
            or campaign.get("input_hashes", {}).get("target") != digest):
            raise ValueError("campaign audit is incomplete")
        for member in audit:
            row = json.loads(read(member, 64 * 1024))
            original = row["original"]
            if original["status"] != "returned" or original.get("files"):
                raise ValueError("recovery supports a stdin/stdout-only program")
            cases.append({"stdin": row["case"]["stdin"], "stdout": original["stdout"],
                          "stderr": original["stderr"], "code": original["returncode"]})

    root = controller.config.state / "native-recovery" / uuid4().hex
    workspace = root / "candidate"
    private = root / "acceptance"
    workspace.mkdir(parents=True, exist_ok=False)
    private.mkdir()
    evidence = findings["decompilation"]
    (workspace / "function-evidence.txt").write_text(evidence, encoding="utf-8")
    write_json(private / "cases.json", cases)
    load_cases(private / "cases.json")
    policy = tomllib.loads(manifest.read_text(encoding="utf-8")) if manifest else {
        "objective": "Reconstruct the authorized program in candidate.c from function-evidence.txt. "
                      "Preserve its stdin protocol, exact output and invalid input handling. "
                      "Run the public compile check.",
        "deliverables": ["candidate.c"],
        "build_candidate": {"argv": ["gcc", "-std=c11", "-O2", "candidate.c", "-o", "candidate"], "timeout": 20},
        "candidate": {"argv": ["./candidate"], "timeout": 50},
    }
    compile_check, run_check = (recipe(policy, key) for key in ("build_candidate", "candidate"))
    if (not isinstance(policy["deliverables"], list) or not policy["deliverables"] or
        any(not isinstance(path, str) for path in policy["deliverables"])):
        raise ValueError("recovery requires a deliverables array")
    deliverables = tuple(relative(path) for path in policy["deliverables"])
    task = Task(
        objective=policy["objective"],
        workspace=workspace, kind="agent", category=policy.get("category", "toy-ghidra-recovery"), inputs=(),
        mode="engineering", write_roots=deliverables, deliverables=deliverables,
        commands=(compile_check,), checks=(compile_check, replace(run_check, oracle="cases.json")),
        verification_dir=private, min_context=4096, attempts=2, timeout=150,
    )
    job = controller.submit_task(task, profile_id=profile)
    provenance = root / "provenance.json"
    write_json(provenance, {"job": job, "target_sha256": digest, "analysis": str(analysis.resolve()),
                            "campaign": str(archive.resolve()), "audit_examples": len(cases),
                            "assurance": "observed cases only"})
    return {**controller.run_submitted(job), "provenance": str(provenance)}
