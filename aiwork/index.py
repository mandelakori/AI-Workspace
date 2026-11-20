from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from .schema import within
from .workspace import BUILDS, files

WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
STOP = {"the", "and", "for", "with", "this", "that", "from", "into", "will"}


def python_symbols(text: str) -> list[dict]:
    """Static qualified definitions, including methods, without importing code."""
    result = []
    def visit(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                result.append({"symbol": name, "line": min([node.lineno, *(d.lineno for d in node.decorator_list)]),
                               "end_line": node.end_lineno, "kind": "class" if isinstance(node, ast.ClassDef) else "function"})
                visit(node.body, name + ".")
    visit(ast.parse(text).body)
    return result


def python_metadata(data: bytes, name: str) -> tuple[list[str], list[str]]:
    try:
        tree = ast.parse(data, filename=name)
    except (SyntaxError, ValueError, RecursionError):
        return [], []
    symbols = []
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            if node.module:
                imports.append(module)
            else:
                imports.extend(module + alias.name for alias in node.names)
    return symbols[:32], list(dict.fromkeys(imports))[:32]


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
    for score, name, path in sorted(scored, key=lambda item: (-within(item[1], scopes), -item[0], item[1]))[:120]:
        symbols = []
        imports = []
        if path.suffix == ".py" and path.stat().st_size <= 256 * 1024:
            symbols, imports = python_metadata(path.read_bytes(), name)
            symbols = sorted(symbols, key=lambda symbol: -len(query & words(symbol)))[:12]
            imports = imports[:6]
        priority = score + 3 * len(query & words(" ".join(symbols + imports)))
        records.append((within(name, scopes), priority, {"path": name, "symbols": symbols, "imports": imports}))
    output = []
    size = len('{"matches":[]}')
    ordered = sorted(records, key=lambda item: (-item[0], -item[1]))
    for _, _, entry in ordered:
        width = len(json.dumps(entry)) + 2
        if size + width > limit:
            continue
        output.append(entry)
        size += width
    return json.dumps({"matches": output})
