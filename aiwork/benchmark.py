from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict
from math import ceil
from pathlib import Path
from statistics import median
from time import monotonic
from uuid import uuid4

from .controller import Controller, write_json
from .schema import Task, bounded
from .verify import runner_status


def benchmark(controller: Controller, manifest: Path, profiles: list[str],
              repeats: int, trusted: bool) -> dict:
    bounded("repeats", repeats, 1, 20)
    configured = {profile.id for profile in controller.config.profiles}
    if not profiles or len(set(profiles)) != len(profiles) or not set(profiles) <= configured:
        raise ValueError("benchmark requires distinct configured profiles")
    if Task.load(manifest).kind != "agent":
        raise ValueError("model comparison requires an agent fixture")
    directory = controller.config.state / "benchmarks" / uuid4().hex
    directory.mkdir(parents=True)
    report = {"manifest": str(manifest.resolve()), "repeats": repeats, "samples": [],
              "profiles": [asdict(p) for p in controller.config.profiles if p.id in profiles],
              "verification_runner": runner_status(controller.config.state,
                                                   controller.config.verification_image),
              "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
              "comparisons": {}, "report": str(directory / "report.json")}
    write_json(directory / "report.json", report)
    baseline = None
    for repeat in range(repeats):
        # Rotate order to reduce systematic warm-start and temporal bias.
        cycle = profiles[repeat % len(profiles):] + profiles[:repeat % len(profiles)]
        for profile in cycle:
            if (controller.config.state / "STOP").exists():
                return report
            job = controller.submit(manifest, trusted, profile_id=profile)
            root = controller.config.state / "runs" / job
            intake = json.loads((root / "intake.json").read_text(encoding="utf-8"))
            assets = [intake["inventory"], intake["private_inventory"]]
            asset_hash = hashlib.sha256(json.dumps(assets, sort_keys=True).encode()).hexdigest()
            spec_hash = hashlib.sha256((root / "task.toml").read_bytes()).hexdigest()
            if baseline is None:
                baseline = asset_hash
                report["input_inventory_sha256"] = baseline
            if asset_hash != baseline or spec_hash != report["manifest_sha256"]:
                controller.state.finish(job, "blocked", "benchmark fixture changed between samples")
                raise RuntimeError("benchmark fixture changed between samples")
            started = monotonic()
            result = controller.run_submitted(job)
            attempts = controller.state.attempts(job)
            evidence = [json.loads(record["evidence"]) for record in attempts]
            report["samples"].append({
                "repeat": repeat + 1, "profile": profile, "job": job,
                "status": result["status"],
                "elapsed": round(monotonic() - started, 3),
                "attempts": len(attempts),
                "first_pass": bool(attempts and attempts[0]["status"] == "verified"),
                "agent": [record.get("agent") for record in evidence],
                "failure_categories": [failure(record) for record in evidence if record["status"] != "verified"],
            })
            report["comparisons"] = aggregate(report["samples"])
            write_json(directory / "report.json", report)
    return report


def failure(record: dict) -> str:
    if record.get("classification"):
        return record["classification"]
    text = record.get("detail", "").lower()
    for name, indicators in (
        ("endpoint", ("remote model", "connection", "inventory", "ssh forwarding")),
        ("context_or_harness", ("harness", "compaction", "serving context")),
        ("queue_or_timeout", ("timeout", "timed out", "deadline", "stop")),
        ("scope", ("outside write_roots", "invalid agent changes")),
        ("no_candidate", ("no edits", "missing deliverables")),
    ):
        if any(indicator in text for indicator in indicators):
            return name
    return record["status"]


def suite(controller: Controller, source: Path, profiles: list[str], repeats: int, trusted: bool) -> dict:
    data = tomllib.loads(source.read_text(encoding="utf-8"))
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list) or not 1 <= len(fixtures) <= 12:
        raise ValueError("suite requires 1–12 relative fixture paths")
    directory = controller.config.state / "suites" / uuid4().hex
    directory.mkdir(parents=True)
    report = {"suite": str(source.resolve()), "results": [], "samples": [],
              "report": str(directory / "report.json")}
    write_json(directory / "report.json", report)
    from .schema import relative
    for fixture in fixtures:
        if (controller.config.state / "STOP").exists():
            break
        path = (source.parent / relative(fixture)).resolve(strict=True)
        if not path.is_relative_to(source.parent.resolve()):
            raise ValueError("suite fixture escaped its directory")
        result = benchmark(controller, path, profiles, repeats, trusted)
        report["results"].append({"fixture": fixture, "report": result["report"]})
        report["samples"].extend({**sample, "fixture": fixture} for sample in result["samples"])
        report["comparisons"] = aggregate(report["samples"])
        write_json(directory / "report.json", report)
    return report


def aggregate(rows: list[dict]) -> dict:
    output = {}
    for profile in sorted({row["profile"] for row in rows}):
        samples = [row for row in rows if row["profile"] == profile]
        times = sorted(row["elapsed"] for row in samples)
        passed = sum(row["status"] == "verified" for row in samples)
        output[profile] = {
            "runs": len(samples), "verified": passed,
            "first_pass": sum(row["first_pass"] for row in samples),
            "blocked": sum(row["status"] == "blocked" for row in samples),
            "p50_seconds": median(times), "p95_seconds": times[ceil(0.95 * len(times)) - 1],
            "verified_per_execution_hour": round(3600 * passed / sum(times), 3) if sum(times) else None,
        }
    return output
