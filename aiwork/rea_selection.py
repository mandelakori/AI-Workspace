"""Select locally among bounded REA-Next exports using public observations only."""
from __future__ import annotations

import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath
from time import monotonic
from uuid import uuid4

from .campaign import static_evidence
from .controller import Controller, write_json
from .native import recipe
from .schema import Check
from .selection import compare, score
from .workspace import inventory, snapshot


def exported_candidates(archive: Path, digest: str) -> list[tuple[str, dict, bytes]]:
    static_evidence(archive, digest)  # verifies archive budgets and original program bytes
    with tarfile.open(archive, "r:gz") as bundle:
        entries = {}
        for member in bundle:
            if member.name in entries:
                raise ValueError("duplicate REA-Next archive member")
            entries[member.name] = member

        def read(name: str, limit: int) -> bytes:
            entry = entries.get(name)
            if not entry or not entry.isfile() or not 1 <= entry.size <= limit:
                raise ValueError(f"missing or oversized REA-Next artifact: {name}")
            with bundle.extractfile(entry) as stream:
                return stream.read()

        state = json.loads(read("result/state.json", 131072))
        remote = PurePosixPath(state["config"]["target"]).parent
        report_name = PurePosixPath(state["report"]).relative_to(remote).as_posix()
        if (state["input_hashes"]["target"] != digest or
                not re.fullmatch(r"engine/runs/[A-Za-z0-9_-]+/reconstruction\.json", report_name)):
            raise ValueError("archive report does not match the approved target")
        report = json.loads(read(report_name, 2 * 1024 * 1024))
        rounds = report["rounds"]
        if report["target_sha256"] != digest or not 1 <= len(rounds) <= 16:
            raise ValueError("invalid REA-Next reconstruction rounds")
        candidates = []
        for index, row in enumerate(rounds, 1):
            if row["round"] != index:
                raise ValueError("unexpected REA-Next round identity")
            prefix = str(PurePosixPath(report_name).parent / f"round-{index}")
            for choice, item in enumerate(row["candidates"], 1):
                if len(candidates) >= 16:
                    raise ValueError("too many exported REA-Next candidates")
                member = PurePosixPath(item["candidate"]).relative_to(remote).as_posix()
                if not re.fullmatch(re.escape(prefix) + r"/[a-f0-9]{64}\.elf", member):
                    raise ValueError("invalid REA-Next executable member")
                content = read(member, 2 * 1024 * 1024)
                candidate_digest = hashlib.sha256(content).hexdigest()
                if candidate_digest != item["sha256"] or not content.startswith(b"\x7fELF"):
                    raise ValueError("REA-Next executable digest or ELF format mismatch")
                candidates.append((f"round-{index}-{choice}", {"member": member, "sha256": candidate_digest}, content))
    return candidates


def select(controller: Controller, archive: Path, native_run: Path) -> dict:
    native_run = native_run.resolve(strict=True)
    provenance = json.loads((native_run / "run.json").read_bytes())
    target = provenance["target"]
    if len(target) != 1 or inventory(native_run / "target") != target:
        raise ValueError("REA-Next selection requires one matching native reference artifact")
    candidates = exported_candidates(archive, next(iter(target.values()))["sha256"])
    root = controller.config.state / "rea-selection" / uuid4().hex
    corpus = root / "development"
    if snapshot(native_run / "development", corpus, ()) != provenance["development"]:
        raise ValueError("public development corpus changed")
    incumbent = None
    winner = None
    results = []
    image = provenance["image"]
    stop = controller.config.state / "STOP"
    build = Check(("chmod", "0555", "./candidate"))
    invocation = recipe(provenance, "candidate")
    for name, origin, content in candidates:
        if stop.exists():
            break
        work = root / name
        work.mkdir()
        (work / "candidate").write_bytes(content)
        hashes = inventory(work)
        outcome = score(build, invocation, corpus / "cases.json", work, root / "home", image,
                        monotonic() + 120, stop, [])
        complete = outcome["compiled"] and len(outcome["cases"]) == outcome["total"]
        decision = (compare(incumbent, outcome, protect_passing=False) if incumbent else
                    {"accepted": complete, "reason": "initial_complete_candidate" if complete else
                     "incomplete_evaluation", "lost_cases": [], "gained_cases": []})
        previous = winner
        if decision["accepted"]:
            incumbent, winner = outcome, name
        row = {"round_candidate": name, "origin": origin, "inventory": hashes,
               "public": outcome, "selection": {**decision, "previous": previous, "selected": winner,
                                                "rollback": bool(previous and not decision["accepted"]),
                                                "regression": bool(decision["lost_cases"])}}
        results.append(row)
        write_json(root / f"{name}.json", row)
    if winner:
        selected = next(row for row in results if row["round_candidate"] == winner)
        frozen = snapshot(root / winner, root / "frozen", ())
        if frozen != selected["inventory"]:
            raise ValueError("selected REA-Next bytes changed before freezing")
        write_json(root / "frozen.json", frozen)
        if snapshot(native_run / "target", root / "target", ()) != target:
            raise ValueError("REA-Next reference changed before freezing")
        (root / "target" / next(iter(target))).chmod(0o755)
        write_json(root / "run.json", {**provenance, "build_candidate": {"argv": list(build.argv)},
                                       "deliverables": ["candidate"], "development": inventory(corpus)})
    decision = {"status": "partial" if len(results) < len(candidates) else "selected" if winner else "failed",
                "selected": winner, "artifact": str(root), "archive": str(archive.resolve()),
                "public_run": str(native_run), "candidates": results}
    write_json(root / "result.json", decision)
    return decision
