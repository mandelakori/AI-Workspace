"""Freeze a verified hierarchy output for the separate native grader."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import inspect
from aiwork.schema import Config
from aiwork.workspace import snapshot


def freeze(controller: Controller, project: str, run: str, native_reference: Path, destination: Path) -> dict:
    status = inspect(controller, project, run)
    if status["status"] != "verified":
        raise ValueError("the hierarchy has no verified integration candidate")
    output = status["outputs"]["integration"]["candidate"]
    binary = Path(output["path"])
    frozen = snapshot(binary.parent, destination / "frozen", (binary.name,))
    if frozen != {binary.name: {key: output[key] for key in ("bytes", "sha256")}}:
        raise ValueError("integration candidate changed after verification")
    native = json.loads((native_reference / "run.json").read_bytes())
    target = snapshot(native_reference / "target", destination / "target", ())
    public = snapshot(native_reference / "development", destination / "development", ())
    if target != native["target"] or public != native["development"]:
        raise ValueError("reference or public cases changed after staging")
    for filename in target:
        (destination / "target" / filename).chmod(0o555)
    write_json(destination / "frozen.json", frozen)
    write_json(destination / "run.json", {**native, "build_candidate": {"argv": ["chmod", "0555", "./candidate"]},
                                           "deliverables": ["candidate"], "hierarchy": status["workflow_report"],
                                           "job": status["jobs"]["integration"]})
    return {"candidate": frozen, "native_run": str(destination.resolve()), "workflow": status["workflow"]}


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("config", type=Path)
    arguments.add_argument("project")
    arguments.add_argument("run")
    arguments.add_argument("native_reference", type=Path)
    arguments.add_argument("destination", type=Path)
    args = arguments.parse_args()
    result = freeze(Controller(Config.load(args.config)), args.project, args.run,
                    args.native_reference, args.destination)
    print(json.dumps(result, indent=2))
