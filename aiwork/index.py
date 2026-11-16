from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from .schema import within
from .workspace import BUILDS, files

WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
STOP = {"the", "and", "for", "with", "this", "that", "from", "into", "will"}


def words(text: str) -> set[str]:
    return {token.lower() for token in WORD.findall(text) if len(token) >= 3} - STOP


def relevant(root: Path, objective: str, scopes: tuple[str, ...], limit: int = 6000) -> str:
    query = words(objective)
    scored = []
    for path in files(root):
        name = path.relative_to(root).as_posix()
        build = path.name in BUILDS
        score = 7 * len(query & words(name)) + 2 * within(name, scopes) + 3 * build
        scored.append((score, name, path))
    records = []
    for score, name, path in sorted(scored, key=lambda item: (-item[0], item[1]))[:120]:
        symbols = []
        imports = []
        if path.suffix == ".py" and path.stat().st_size <= 65536:
            try:
                tree = ast.parse(path.read_bytes(), filename=name)
                symbols = [n.name for n in tree.body if isinstance(
                    n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))][:16]
                imports = [n.module for n in tree.body if isinstance(n, ast.ImportFrom) and n.module][:12]
            except (SyntaxError, ValueError):
                pass
        priority = score + 3 * len(query & words(" ".join(symbols + imports)))
        records.append((priority, {"path": name, "symbols": symbols, "imports": imports}))
    output = []
    size = len('{"matches":[]}')
    ordered = sorted(records, key=lambda item: -item[0])
    for _, entry in ordered:
        width = len(json.dumps(entry)) + 2
        if size + width > limit:
            break
        output.append(entry)
        size += width
    return json.dumps({"matches": output})
