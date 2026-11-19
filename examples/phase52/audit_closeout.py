"""Replay frozen public-selected ledger sources and failed balance edits without inference."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from time import monotonic

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import inspect, load_registration
from aiwork.native import pin_runner
from aiwork.oracle import evaluate
from aiwork.schema import Check, Config
from aiwork.verify import invoke
from aiwork.workspace import snapshot

cfg = Config.load(Path(sys.argv[1]))
controller = Controller(replace(cfg, verification_image=pin_runner(Controller(cfg))))
root = Path(sys.argv[2]).resolve()
root.mkdir(parents=True, exist_ok=False)
status = inspect(controller, "ledger-closeout", "trial")
write_json(root/"hierarchy.json", status)
_, registration = load_registration(controller, "ledger-closeout")
report = {"status": status["status"], "runner": controller.config.verification_image,
          "reused": status["reused"], "components": {}, "attempts": [],
          "final_sealed": "not_run_no_verified_integrated_candidate"}

def replay(task, source, destination, *, sanitized=False):
    snapshot(source, destination/"frozen", ())
    build = task.checks[0]
    if task.deliverables == ("balance.c",):
        flags = (["-O1", "-g", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"]
                 if sanitized else ["-O2"])
        build = Check(("gcc", "-std=c11", *flags, "-DBALANCE", "ledger_probe.c", "balance.c", "-o", "probe"))
    compilation = invoke(build, destination/"frozen", destination/"home", report["runner"])
    write_json(destination/"compilation.json", compilation)
    if not compilation["passed"]:
        return {"compiled": False, "total": None, "passed_cases": None}
    outcome = evaluate(replace(task.checks[1], oracle=task.public_cases), destination/"frozen",
                       destination/"home", task.workspace, report["runner"], 180, cfg.state/"STOP",
                       public=True)
    write_json(destination/"public.json", outcome)
    if len(outcome["cases"]) != outcome["total"]:
        raise ValueError("public audit did not complete every case")
    return {"compiled": True, "total": outcome["total"], "passed_cases": outcome["passed_cases"],
            "passed": outcome["passed"], "result": str(destination/"public.json")}

started = monotonic()
for name in ("framing", "validation", "balance"):
    job = cfg.state/"runs"/status["jobs"][name]
    task = controller.frozen_task(job, json.loads((job/"intake.json").read_bytes()))
    source = controller.checkpoint(task, job/"selection") or job/"baseline"
    receipt = json.loads((source.parent/"checkpoint.json" if source.name == "workspace"
                          else job/"baseline-public.json").read_bytes())
    # This immutable copy is made before any replay or generated diagnostic files.
    frozen = root/name/"selected"
    if snapshot(source, frozen, ()) != receipt["inventory"]:
        raise ValueError("selected source changed since public ranking")
    write_json(root/name/"frozen.json", receipt["inventory"])
    report["components"][name] = {
        "job": status["jobs"][name], "selected": str(source),
        "source_sha256": receipt["inventory"][name+".c"]["sha256"],
        "ordinary": replay(task, frozen, root/name/"ordinary"),
    }
    if name == "balance":
        report["components"][name]["ubsan"] = replay(task, frozen, root/name/"ubsan", sanitized=True)
    for attempt in sorted(job.glob("attempt-*")):
        evidence = json.loads((attempt/"evidence.json").read_bytes())
        prompt = json.loads((attempt/"proposal-context.json").read_bytes())
        response = json.loads((attempt/"proposal-response.json").read_bytes())
        context_allowed = set(task.source_context) | {
            key for key in prompt["approved_context"] if key.startswith(".handoff/")}
        if (set(prompt["approved_context"]) != context_allowed
                or not set(task.inputs) <= set(registration["inventory"])):
            raise ValueError("worker context exceeded registered public evidence")
        row = {"component": name, "attempt": attempt.name, "status": evidence["status"],
               "detail": evidence["detail"], "selection": evidence.get("selection"),
               "metrics": evidence.get("agent"), "elapsed": evidence["elapsed"],
               "finish_reason": response["choices"][0].get("finish_reason"),
               "public_cases_sent": len(prompt.get("public_cases", [])),
               "public_cases_omitted": prompt.get("public_cases_omitted"),
               "context_receipt": prompt.get("context_receipt"),
               "request": str(attempt/"proposal-context.json"),
               "response": str(attempt/"proposal-response.json")}
        if name == "balance":
            row["ubsan"] = replay(task, attempt/"workspace", root/name/attempt.name, sanitized=True)
        report["attempts"].append(row)
report["audit_seconds"] = round(monotonic()-started, 3)
report["model_requests"] = len(report["attempts"])
report["tokens"] = {key: sum((item["metrics"]["tokens"].get(key) or 0) for item in report["attempts"])
                    for key in ("input", "output")}
report["attempt_seconds"] = round(sum(item["elapsed"] for item in report["attempts"]), 3)
write_json(root/"report.json", report)
print(json.dumps({"report": str(root/"report.json"), "components": report["components"],
                  "model_requests": report["model_requests"], "tokens": report["tokens"]}, indent=2))
