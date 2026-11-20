"""Compare candidate behavior without mounting the oracle in the candidate container."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from time import monotonic

from .schema import Check
from .verify import invoke
from .workspace import contained


def diagnostic_excerpt(text: str) -> str:
    """Keep the exception at the end of a public traceback within the existing cap."""
    return text if len(text) <= 160 else text[:55] + "\n...\n" + text[-100:]


def case_argv(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 32 or any(
        not isinstance(arg, str) or len(arg) > 1024 or "\0" in arg
        or any(0xD800 <= ord(char) <= 0xDFFF for char in arg) for arg in value
    ):
        raise ValueError("invalid case argv")
    return tuple(value)


def load_cases(path: Path, *, public: bool = False) -> list[dict]:
    if path.stat().st_size > 256 * 1024:
        raise ValueError("sealed case file exceeds 256 KiB")
    cases = json.loads(path.read_bytes())
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("sealed oracle requires 1–32 cases")
    allowed = {"argv", "stdin", "stdout", "code", "stderr"}
    if public:
        allowed |= {"name", "group"}
    for case in cases:
        if (not isinstance(case, dict) or case.keys() - allowed
            or not isinstance(case.get("stdout"), str)
            or type(case.get("code", 0)) is not int or not 0 <= case.get("code", 0) <= 124
            or any(not isinstance(case[key], str) or len(case[key].encode("utf-8")) > 16384
                   for key in ("stdin", "stdout", "stderr") if key in case)):
            raise ValueError("invalid sealed case structure")
        if public and any(key in case and (not isinstance(case[key], str) or len(case[key]) > 100)
                          for key in ("name", "group")):
            raise ValueError("invalid public case label")
        case_argv(case.get("argv", []))
    return cases


def evaluate(check: Check, workspace: Path, home: Path, private: Path, image: str,
             time_limit: float, stop: Path | None, *, public: bool = False) -> dict:
    if not image:
        raise ValueError("sealed verification requires a configured Docker image")
    cases = load_cases(contained(private, check.oracle), public=public)
    command = replace(check, oracle="")
    deadline = monotonic() + (time_limit if public else min(check.timeout, time_limit))
    results = []
    discrepancies = []
    for case in cases:
        remaining = deadline - monotonic()
        if remaining <= 0 or stop and stop.exists():
            break
        response = invoke(command, workspace, home, image, timeout=remaining, stop=stop,
                          extra_args=case_argv(case.get("argv", [])),
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
        number = len(results) + 1
        results.append({"case": number, "verdict": category, "duration": round(response["elapsed"], 3),
                        **({"name": case.get("name", str(number))} if public else {})})
        if public and category != "pass":
            differences = []
            for key, default in (("code", 0), ("stdout", ""), ("stderr", "")):
                if key != "stderr" or key in case:
                    actual = response[key] if key == "code" else response[key].replace("\r\n", "\n")
                    if actual != case.get(key, default):
                        differences.append(key)
            discrepancies.append({
                "case": case.get("name", number), "index": number, "differences": differences,
                "stdin": case.get("stdin", "")[:180],
                "argv": [arg[:60] for arg in case.get("argv", [])[:4]], "classification": category,
                "expected": {"code": case.get("code", 0), "stdout": case["stdout"][:160],
                             "stderr": diagnostic_excerpt(case.get("stderr", ""))},
                "observed": {"code": response["code"], "stdout": response["stdout"][:160],
                             "stderr": diagnostic_excerpt(response["stderr"])},
            })
    passed = sum(result["verdict"] == "pass" for result in results)
    return {"runner": image, "kind": "public-regression" if public else "sealed-black-box",
            "passed": passed == len(cases),
            "total": len(cases), "passed_cases": passed, "cases": results,
            "classification": "pass" if passed == len(cases) else (
                "public_mismatch" if public else "sealed_mismatch"),
            **({"discrepancies": discrepancies} if public else {})}
