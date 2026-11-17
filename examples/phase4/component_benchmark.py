"""Compare serial and cross-plane execution of the same native component graph."""
import argparse
import hashlib
from dataclasses import replace
from pathlib import Path
from time import monotonic
from uuid import uuid4

from aiwork.cli import print_json
from aiwork.controller import Controller, write_json
from aiwork.schema import Config
from aiwork.verify import runner_status
from aiwork.workflow import execute
from aiwork.workspace import inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    cfg = Config.load(args.config)
    if args.local_only:
        cfg = replace(cfg, profiles=tuple(p for p in cfg.profiles if p.location == "local"))
    runner = runner_status(cfg.state, cfg.verification_image)
    if not runner["image_id"]:
        parser.error("configure a reachable, already installed Linux Docker verification image")
    controller = Controller(replace(cfg, verification_image=runner["image_id"]))
    fixture = Path(__file__).resolve().parent / "components"
    manifest = fixture / ("workflow-local.toml" if args.local_only else "workflow.toml")
    run_id = uuid4().hex[:16]
    root = cfg.state / "component-benchmarks" / run_id
    root.mkdir(parents=True)
    report = {"fixture": str(manifest), "inputs": inventory(fixture), "runner": runner, "samples": []}
    for workers in (1, 2):
        if inventory(fixture) != report["inputs"]:
            raise ValueError("component benchmark fixture changed between executions")
        started = monotonic()
        result = execute(controller, manifest, workers, False, f"{run_id}-{workers}")
        assertions = {}
        for step, job in result["jobs"].items():
            runs = cfg.state / "runs" / job
            attempts = controller.state.attempts(job)
            assertions[step] = {"job": job, "attempts": [row["status"] for row in attempts],
                                "intake_sha256": hashlib.sha256((runs / "intake.json").read_bytes()).hexdigest()}
        report["samples"].append({"workers": workers, "seconds": round(monotonic() - started, 3),
                                  "workflow": result, "evidence": assertions})
        write_json(root / "report.json", report)
    print_json({**report, "report": root / "report.json"})
    return 0 if all(sample["workflow"]["status"] == "verified" for sample in report["samples"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
