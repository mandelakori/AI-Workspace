"""Extract the existing public assertions for a worker's interface."""
from __future__ import annotations

import re
from pathlib import Path


def unit_context(root: Path, key: str) -> str:
    text = (root / "checks.c").read_text(encoding="utf-8")
    marker = re.compile(rf"^#(?:if|ifdef|elif).*\b{re.escape(key.upper())}\b[^\n]*\n", re.MULTILINE)
    match = marker.search(text)
    if not match:
        raise ValueError(f"no public unit checks for {key}")
    checks = re.split(r"^#(?:elif|endif)\b", text[match.end():], maxsplit=1, flags=re.MULTILINE)[0]
    name = f"{key}-assertions.txt"
    (root / name).write_text(checks, encoding="utf-8")
    return name
