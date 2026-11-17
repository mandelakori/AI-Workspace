from __future__ import annotations

import hashlib
import json
import re
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .controller import Controller, write_json
from .lock import file_lock
from .schema import Task, bounded
from .workspace import contained


@dataclass(frozen=True)
class Node:
    manifest: Path
    needs: tuple[str, ...]
    profile: str


def read_plan(path: Path) -> dict[str, Node]:
    plan = tomllib.loads(path.read_text(encoding="utf-8"))
    nodes = {}
    for name, data in plan["steps"].items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
            raise ValueError("invalid workflow step ID")
        source = (path.parent / data["manifest"]).resolve(strict=True)
        Task.load(source)
        needs = data.get("needs", [])
        if not isinstance(needs, list) or any(not isinstance(dep, str) for dep in needs):
            raise ValueError("workflow needs must be a string array")
        profile = data.get("profile", "")
        if not isinstance(profile, str) or data.keys() - {"manifest", "needs", "profile"}:
            raise ValueError("invalid workflow step fields")
        nodes[name] = Node(source, tuple(needs), profile)
    if not 1 <= len(nodes) <= 64:
        raise ValueError("workflow requires 1–64 steps")
    pending = set(nodes)
    while pending:
        ready = {n for n in pending if set(nodes[n].needs) <= nodes.keys() - pending}
        if not ready:
            raise ValueError("workflow has a cycle or a missing dependency")
        pending -= ready
    return nodes


def execute(controller: Controller, source: Path, workers: int, trusted: bool,
            workflow_id: str) -> dict:
    bounded("workers", workers, 1, 16)
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", workflow_id):
        raise ValueError("workflow id must contain 1–64 letters, digits, underscores or dashes")
    nodes = read_plan(source.resolve())
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    definitions = {name: hashlib.sha256(node.manifest.read_bytes()).hexdigest()
                   for name, node in nodes.items()}
    root = controller.config.state / "workflows" / workflow_id
    root.mkdir(parents=True, exist_ok=True)
    journal = root / "workflow.json"
    with file_lock(root / "workflow.lock"):
        result = (json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else
                  {"workflow": workflow_id, "plan": fingerprint, "definitions": definitions,
                   "trusted": trusted, "jobs": {}, "status": "running"})
        if (result["plan"] != fingerprint or result["definitions"] != definitions
            or result["trusted"] != trusted):
            raise ValueError("workflow plan, task manifests or authorization changed; use a new ID")
        write_json(journal, result)
        jobs = result["jobs"]
        states: dict[str, str] = {}

        def run_node(job: str) -> str:
            return controller.run_submitted(job)["status"]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            while not (controller.config.state / "STOP").exists():
                states = {name: controller.state.jobs(job)[0]["status"] for name, job in jobs.items()}
                ready = [name for name, node in nodes.items()
                         if name not in jobs and all(states.get(dep) == "verified" for dep in node.needs)]
                for name in ready:
                    node = nodes[name]
                    handoff = {}
                    handoff_hashes = {}
                    for dep in node.needs:
                        dep_job = jobs[dep]
                        attempts = controller.state.attempts(dep_job)
                        success = next(item for item in reversed(attempts) if item["status"] == "verified")
                        attempt = controller.config.state / "runs" / dep_job / f"attempt-{success['n']:03}"
                        upstream = Task.load(nodes[dep].manifest)
                        location = "verification" if upstream.kind == "direct" else "workspace"
                        record = attempt / ("verification-inventory.json" if upstream.kind == "direct"
                                            else "output-inventory.json")
                        verified = json.loads(record.read_bytes()) if record.is_file() else {}
                        for filename in upstream.deliverables:
                            key = f"{dep}/{filename}"
                            handoff[key] = contained(attempt / location, filename)
                            if filename in verified:
                                handoff_hashes[key] = verified[filename]["sha256"]
                            elif record.is_file() or upstream.kind == "agent":
                                raise ValueError(f"verified handoff artifact missing an inventory record: {key}")
                    jobs[name] = controller.submit(node.manifest, trusted, profile_id=node.profile,
                                                   handoff=handoff, handoff_hashes=handoff_hashes, job_id=uuid5(
                                                       NAMESPACE_URL, f"aiwork:{workflow_id}/{name}").hex)
                    states[name] = "queued"
                    write_json(journal, result)
                waiting = [jobs[name] for name, status in states.items() if status == "queued"]
                if waiting:
                    list(pool.map(run_node, waiting))
                elif "running" in states.values():
                    # An interrupted task remains visible and can be explicitly resumed.
                    break
                else:
                    break
        states = {name: controller.state.jobs(job)[0]["status"] for name, job in jobs.items()}
        result["steps"] = {name: states.get(name, "waiting_for_dependencies") for name in nodes}
        result["status"] = "verified" if len(states) == len(nodes) and all(
            status == "verified" for status in states.values()
        ) else "partial"
        write_json(journal, result)
        return result
