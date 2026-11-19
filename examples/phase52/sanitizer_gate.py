"""Compile the owned balance component and require every approved public case under UBSan."""
import json
import subprocess
from pathlib import Path

subprocess.run(["gcc", "-std=c11", "-O1", "-g", "-fsanitize=undefined",
                "-fno-sanitize-recover=undefined", "-DBALANCE", "ledger_probe.c",
                "balance.c", "-o", "probe"], check=True)
cases = json.loads(Path("balance-public.json").read_bytes())
failures = []
for case in cases:
    result = subprocess.run(["./probe", *case.get("argv", [])], input=case["stdin"],
                            capture_output=True, text=True, timeout=4)
    if (result.returncode, result.stdout, result.stderr) != (
            case.get("code", 0), case["stdout"], case.get("stderr", "")):
        failures.append(case["name"])
        print(json.dumps({"case": case["name"], "expected": case,
                          "observed": {"code": result.returncode, "stdout": result.stdout,
                                       "stderr": result.stderr}}))
print(f"Public balance UBSan gate: {len(cases)-len(failures)}/{len(cases)}")
raise SystemExit(bool(failures))
