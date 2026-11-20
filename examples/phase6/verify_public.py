"""Approved offline commands for unchanged upstream tests and worker-authored tests."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path("src").resolve()))
import click
import pytest

assert Path(click.__file__).resolve().is_relative_to(Path("src").resolve())
mode = sys.argv[1] if len(sys.argv) > 1 else "upstream"
if mode == "upstream":
    result = pytest.main(["-q", "-p", "no:cacheprovider", "tests", "--ignore=tests/test_iso_datetime.py"])
elif mode == "feature":
    tests = Path("tests/test_iso_datetime.py")
    assert tests.is_file(), "add focused worker-authored feature tests"
    result = pytest.main(["-q", "-p", "no:cacheprovider", str(tests)])
elif mode == "all":
    result = pytest.main(["-q", "-p", "no:cacheprovider", "tests"])
elif mode == "public":
    from _aiwork_probe import evaluate
    failures = []
    for case in json.loads(Path("_aiwork_public_cases.json").read_bytes()):
        try:
            actual = evaluate(json.loads(case["stdin"]))
            expected = json.loads(case["stdout"])
            if actual != expected:
                failures.append(case["name"])
                print(json.dumps({"case": case["name"], "expected": expected, "observed": actual}))
        except Exception as error:
            failures.append(case["name"])
            print(case["name"], type(error).__name__, str(error))
    print("Failed public cases:", failures)
    result = bool(failures)
else:
    raise ValueError("unapproved check mode")
raise SystemExit(result)
