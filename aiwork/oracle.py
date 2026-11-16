"""Compare candidate behavior without mounting the oracle in the candidate container."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from time import monotonic

from .schema import Check
from .verify import invoke
from .workspace import contained


def load_cases(path: Path) -> list[dict]:
    if path.stat().st_size > 256 * 1024:
        raise ValueError("sealed case file exceeds 256 KiB")
    cases = json.loads(path.read_bytes())
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("sealed oracle requires 1–32 cases")
    for case in cases:
        if (not isinstance(case, dict) or case.keys() - {"stdin", "stdout", "code", "stderr"}
            or not isinstance(case.get("stdout"), str)
            or type(case.get("code", 0)) is not int or not 0 <= case.get("code", 0) <= 125
            or any(not isinstance(case[key], str) or len(case[key].encode("utf-8")) > 16384
                   for key in ("stdin", "stdout", "stderr") if key in case)):
            raise ValueError("invalid sealed case structure")
    return cases


def evaluate(check: Check, workspace: Path, home: Path, private: Path, image: str,
             time_limit: float, stop: Path | None) -> dict:
    if not image:
        raise ValueError("sealed verification requires a configured Docker image")
    cases = load_cases(contained(private, check.oracle))
    command = replace(check, oracle="")
    deadline = monotonic() + min(check.timeout, time_limit)
    results = []
    for case in cases:
        remaining = deadline - monotonic()
        if remaining <= 0 or stop and stop.exists():
            break
        response = invoke(command, workspace, home, image, timeout=remaining, stop=stop,
                          stdin=case.get("stdin", "").encode("utf-8"), sealed=True)
        category = "pass"
        if response["timed_out"]:
            category = "timeout"
        elif response["truncated"]:
            category = "output_limit"
        elif response["code"] != case.get("code", 0):
            category = "exit"
        elif response["stdout"].replace("\r\n", "\n") != case["stdout"]:
            category = "stdout"
        elif "stderr" in case and response["stderr"].replace("\r\n", "\n") != case["stderr"]:
            category = "stderr"
        results.append({"case": len(results) + 1, "verdict": category,
                        "duration": round(response["elapsed"], 3)})
    passed = sum(result["verdict"] == "pass" for result in results)
    return {"runner": image, "kind": "sealed-black-box", "passed": passed == len(cases),
            "total": len(cases), "passed_cases": passed, "cases": results,
            "classification": "pass" if passed == len(cases) else "sealed_mismatch"}
