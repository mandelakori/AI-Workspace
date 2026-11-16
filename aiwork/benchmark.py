from __future__ import annotations

from math import ceil
from pathlib import Path
from statistics import median
from time import monotonic
from uuid import uuid4

from .controller import Controller, write_json
from .schema import Task, bounded


def benchmark(controller: Controller, manifest: Path, profiles: list[str],
              repeats: int, trusted: bool) -> dict:
    bounded("repeats", repeats, 1, 20)
    configured = {profile.id for profile in controller.config.profiles}
    if len(set(profiles)) != len(profiles) or not set(profiles) <= configured:
        raise ValueError("benchmark requires distinct configured profiles")
    if Task.load(manifest).kind != "agent":
        raise ValueError("model comparison requires an agent fixture")
    directory = controller.config.state / "benchmarks" / uuid4().hex
    directory.mkdir(parents=True)
    report = {"manifest": str(manifest.resolve()), "repeats": repeats, "samples": [],
              "comparisons": {}, "report": str(directory / "report.json")}
    for repeat in range(repeats):
        # Rotate order to reduce systematic warm-start and temporal bias.
        cycle = profiles[repeat % len(profiles):] + profiles[:repeat % len(profiles)]
        for profile in cycle:
            if (controller.config.state / "STOP").exists():
                return report
            job = controller.submit(manifest, trusted, profile_id=profile)
            started = monotonic()
            result = controller.work(job)
            attempts = controller.state.attempts(job)
            report["samples"].append({
                "repeat": repeat + 1, "profile": profile, "job": job,
                "status": result["status"] if result else "queued",
                "elapsed": round(monotonic() - started, 3),
                "attempts": len(attempts),
                "first_pass": bool(attempts and attempts[0]["status"] == "verified"),
            })
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
