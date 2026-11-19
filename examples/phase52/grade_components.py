"""Evaluate a frozen component with separate invocation and suite time budgets."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from time import monotonic

from aiwork.controller import write_json
from aiwork.oracle import evaluate, load_cases
from aiwork.schema import Check


def evaluate_component(command: Check, workspace: Path, cases: Path, artifacts: Path,
                       image: str, stop: Path | None = None, suite_timeout: int = 180) -> dict:
    rows = load_cases(cases)
    artifacts.mkdir(parents=True, exist_ok=False)
    private = artifacts / "private"
    private.mkdir()
    results = []
    deadline = monotonic() + suite_timeout
    for number, row in enumerate(rows):
        if deadline <= monotonic() or stop and stop.exists():
            break
        case_file = private / f"case-{number:02}.json"
        write_json(case_file, [row])
        outcome = evaluate(
            replace(command, oracle=case_file.name), workspace, artifacts / "home", private, image,
            min(command.timeout, deadline-monotonic()), stop,
        )
        write_json(artifacts / f"case-{number:02}-verdict.json", outcome)
        completed = outcome["cases"]
        verdict = completed[0]["verdict"] if completed else "inconclusive"
        results.append({"case": number + 1, "verdict": verdict})
    complete = len(results) == len(rows) and all(row["verdict"] != "inconclusive" for row in results)
    passed = sum(row["verdict"] == "pass" for row in results)
    report = {
        "status": ("verified" if passed == len(rows) else "failed") if complete else "inconclusive",
        "total": len(rows), "completed": len(results), "passed": passed, "complete": complete,
        "cases": results, "per_case_timeout": command.timeout, "suite_timeout": suite_timeout,
    }
    write_json(artifacts / "report.json", report)
    return report
