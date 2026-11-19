"""Reproduce one approved public case on the selected component without inference."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from uuid import uuid4

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import inspect
from aiwork.native import pin_runner
from aiwork.oracle import evaluate, load_cases
from aiwork.schema import Config
from aiwork.verify import invoke
from aiwork.workspace import snapshot


config, project, run, component, case_name = sys.argv[1:]
cfg = Config.load(Path(config))
ctrl = Controller(replace(cfg, verification_image=pin_runner(Controller(cfg))))
status = inspect(ctrl, project, run)
job = cfg.state / "runs" / status["jobs"][component]
task = ctrl.frozen_task(job, json.loads((job / "intake.json").read_bytes()))
if not task.rank_public or not task.public_cases:
    raise ValueError("replay requires an approved named public corpus")
selected = ctrl.checkpoint(task, job / "selection") or job / "baseline"
receipt_file = selected.parent / "checkpoint.json" if selected.name == "workspace" else job / "baseline-public.json"
receipt = json.loads(receipt_file.read_bytes())
artifacts = cfg.state / "public-replays" / uuid4().hex
if snapshot(selected, artifacts / "candidate", ()) != receipt["inventory"]:
    raise ValueError("selected component changed before replay")
cases = [case for case in load_cases(task.workspace / task.public_cases, public=True)
         if case.get("name") == case_name]
if len(cases) != 1:
    raise ValueError("case must name exactly one approved public stimulus")
public = artifacts / "public"
public.mkdir()
write_json(public / "case.json", cases)
compiled = invoke(task.checks[0], artifacts / "candidate", artifacts / "home", ctrl.config.verification_image)
write_json(artifacts / "compilation.json", compiled)
if compiled["passed"]:
    outcome = evaluate(replace(task.checks[1], oracle="case.json"), artifacts / "candidate", artifacts / "home",
                       public, ctrl.config.verification_image, 30, cfg.state / "STOP", public=True)
else:
    outcome = compiled
write_json(artifacts / "result.json", outcome)
print(json.dumps({"artifact": str(artifacts), **outcome}, indent=2))
