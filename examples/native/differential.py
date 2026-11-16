import itertools
import subprocess
from pathlib import Path

root = Path.cwd()
case_ids = itertools.product(range(-10, 81), (0, 1))
count = 0
for weight, priority in case_ids:
    arguments = [str(weight), str(priority)]
    reference = subprocess.check_output([str(root / "reference.exe"), *arguments], timeout=3)
    candidate = subprocess.check_output([str(root / "candidate.exe"), *arguments], timeout=3)
    if reference != candidate:
        raise SystemExit(f"mismatch at {arguments}: {reference!r} != {candidate!r}")
    count += 1
print(f"{count} finite cases matched")
