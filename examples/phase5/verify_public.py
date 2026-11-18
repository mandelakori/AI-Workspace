"""Run reviewed component commands and compare full executable observations."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

TEST_PART = sys.argv[1]
if TEST_PART == "analysis":
    rows = json.loads(Path("observations.json").read_bytes())
    static = json.loads(Path("static.json").read_bytes())
    mapping = json.loads(Path("evidence-map.json").read_bytes())
    assert static["target_sha256"]
    for name, labels in mapping.items():
        selected = [row for row in rows if row["name"] in labels]
        assert len(selected) == len(labels)
        Path(f"{name}.json").write_text(json.dumps({
            "target_sha256": static["target_sha256"], "observations": selected,
            "static": static.get(name, {}),
        }, indent=2))
elif TEST_PART == "component":
    component = sys.argv[2]
    subprocess.run(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-I.", f"-D{component.upper()}",
                    "checks.c", f"{component}.c", "-o", "unit"], check=True)
    subprocess.run(["./unit"], check=True, timeout=4)
elif TEST_PART == "test":
    files = [f".handoff/{name}/{name}.c" for name in sys.argv[2:]]
    subprocess.run(["gcc", "-std=c11", "-O2", "-I.", "main.c", *files, "-o", "tested"], check=True)
else:
    if TEST_PART != "integrate":
        raise ValueError("unknown reviewed check")
    shutil.copyfile(".handoff/testing/tested", "candidate")
    Path("candidate").chmod(0o555)

if TEST_PART in {"test", "integrate"}:
    binary = "./tested" if TEST_PART == "test" else "./candidate"
    rows = json.loads(Path("observations.json").read_bytes())
    failures = []
    for row in rows:
        result = subprocess.run([binary, *row["argv"]], input=row["stdin"].encode(), capture_output=True,
                                timeout=4, check=False)
        actual = (result.returncode, result.stdout.decode(), result.stderr.decode())
        if actual != (row["code"], row["stdout"], row["stderr"]):
            failures.append(row["name"])
    print(f"Public agreement: {len(rows)-len(failures)}/{len(rows)}")
    if failures:
        print("Mismatches:", ", ".join(failures))
        sys.exit(1)
