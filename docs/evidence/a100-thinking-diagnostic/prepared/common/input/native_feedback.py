"""Run the staged public examples and show a bounded sample of discrepancies."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_public_checks(examples: Path, build: dict, candidate: dict) -> int:
    def invoke(recipe, *, args=(), stdin=b"", timeout=None):
        command = ["python" if item == "{python}" else item for item in recipe["argv"]]
        return subprocess.run(
            [*command, *args], cwd=recipe["cwd"] or ".", input=stdin, capture_output=True,
            timeout=recipe["timeout"] if timeout is None else min(recipe["timeout"], timeout),
            check=False,
        )

    def text(data):
        return data.decode("utf-8", "replace").replace("\r\n", "\n")

    try:
        compilation = invoke(build)
    except subprocess.TimeoutExpired:
        print("Public build timed out")
        return 1
    if compilation.returncode:
        print(text(compilation.stderr)[-600:])
        return 1
    cases = json.loads(examples.read_bytes())
    failed = 0
    for case in cases:
        expected = {key: case[key] for key in ("code", "stdout", "stderr")}
        try:
            result = invoke(candidate, args=case["argv"], stdin=case["stdin"].encode("utf-8"), timeout=5)
            observed = {"code": result.returncode, "stdout": text(result.stdout), "stderr": text(result.stderr)}
        except subprocess.TimeoutExpired:
            observed = {"error": "candidate timed out"}
        if observed != expected:
            failed += 1
            if failed <= 3:
                print(json.dumps({
                    "case": case["name"], "stdin": case["stdin"][:140], "argv": [arg[:60] for arg in case["argv"][:4]],
                    "expected": {key: val[:100] if isinstance(val, str) else val for key, val in expected.items()},
                    "observed": {key: val[:100] if isinstance(val, str) else val for key, val in observed.items()},
                }, separators=(",", ":")))
    print(f"Public examples passed: {len(cases) - failed}/{len(cases)}")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(run_public_checks(Path("examples.json"), json.loads(sys.argv[1]), json.loads(sys.argv[2])))
