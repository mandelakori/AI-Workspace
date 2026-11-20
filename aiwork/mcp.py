"""Task-local MCP stdio server exposing one operator-defined public check."""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from time import time

from .changes import delta, git_patch, validate_changes
from .schema import Check
from .verify import pipeline
from .workspace import contained, ignore, inventory, snapshot
from .index import python_symbols


def reserve_trial_call(spec: Path, limit: int) -> int:
    """Reconnects cannot reset a measured session's public-tool allowance."""
    from .lock import file_lock
    from .trial_budget import write
    path = spec.with_name("trial-tool-calls.json")
    with file_lock(path.with_suffix(".lock")):
        used = json.loads(path.read_bytes())["used"] if path.exists() else 0
        if used >= limit:
            raise ValueError("measured public-tool budget exhausted")
        write(path, {"used": used + 1})
        return used + 1


def focus(workspace: Path, args: dict) -> dict:
    """Read a bounded public source window without exporting a whole file."""
    if (not isinstance(args, dict) or set(args) - {"path", "line", "symbol", "query"}
            or not isinstance(args.get("path"), str)
            or type(args.get("line", 1)) is not int or args.get("line", 1) < 1
            or not isinstance(args.get("symbol", ""), str) or len(args.get("symbol", "")) > 160
            or not isinstance(args.get("query", ""), str) or len(args.get("query", "")) > 160
            or args.get("symbol") and args.get("query")):
        raise ValueError("focus requires a relative path and optional line or Python symbol")
    name = args["path"]
    if any(ignore(part) for part in name.split("/")):
        raise ValueError("excluded inspection path")
    path = contained(workspace, name)
    if not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("inspection requires a text file no larger than 256 KiB")
    with path.open("rb") as stream:
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise ValueError("inspection source grew beyond 256 KiB")
    text = data.decode("utf-8")
    lines = text.splitlines(keepends=True)
    first = args.get("line", 1)
    end = len(lines)
    definitions = []
    if path.suffix == ".py":
        try:
            definitions = python_symbols(text)
        except (SyntaxError, RecursionError, ValueError):
            if args.get("symbol"):
                raise ValueError("symbol inspection requires parseable Python") from None
    selected_symbol = args.get("symbol", "")
    query = args.get("query", "").strip().casefold()
    matching = [d for d in definitions if query in d['symbol'].casefold()] if query else []
    if query:
        if matching:
            selected_symbol = min(matching, key=lambda d: (d['symbol'].casefold()!=query, len(d['symbol']), d['line']))['symbol']
        else:
            matches = [i for i, line in enumerate(lines, 1) if query in line.casefold()]
            if not matches:
                raise ValueError("query did not match; open the path to discover symbols")
            first = max(1, matches[0]-3)
    if selected_symbol:
        found = [(d['line'],d['end_line']) for d in definitions if d['symbol']==selected_symbol]
        if len(found) != 1:
            raise ValueError("Python symbol must match exactly once; use Class.method for methods")
        symbol_first, end = found[0]
        first = max(symbol_first, args.get("line", symbol_first))
        if first > end:
            raise ValueError("inspection line is past the selected symbol")
    if first > max(1, len(lines)):
        raise ValueError("inspection line is past EOF")
    selected = []
    size = 0
    for line in lines[first-1:min(end, first+59)]:
        width = len(line.encode("utf-8"))
        if size + width > 3000:
            break
        selected.append(line)
        size += width
    if not selected and lines:
        raise ValueError("source line exceeds the 3000-byte inspection budget")
    following = first + len(selected)
    outline = []
    candidates = matching or sorted(definitions, key=lambda d: ('.' in d['symbol'], d['kind']!='class', d['line']))
    for definition in candidates:
        if len(json.dumps([*outline, definition]).encode('utf-8')) > 1200 or len(outline)>=12:
            break
        outline.append(definition)
    return {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "line": first,
            "source": "".join(selected), "next_line": following if following <= end else None,
            "total_lines": len(lines), "selected_symbol":selected_symbol, "symbols":outline,
            "symbols_truncated":len(outline)<len(candidates)}


def inspect_source(spec: Path, workspace: Path, args: dict) -> dict:
    """Suppress unchanged duplicate excerpts, including across MCP reconnects."""
    from .lock import file_lock
    from .trial_budget import write
    value=focus(workspace,args)
    key=hashlib.sha256(json.dumps([value['path'],value['sha256'],value['line'],value['source']]).encode()).hexdigest()
    path=spec.with_name('source-navigation.json')
    with file_lock(path.with_suffix('.lock')):
        history=json.loads(path.read_bytes()) if path.exists() else []
        duplicate=key in history
        if not duplicate:
            history.append(key);write(path,history[-16:])
    if duplicate:
        value.update(source='',already_inspected=True,
                     navigation_hint='Unchanged excerpt already supplied. Select a listed symbol, use query or next_line, or edit and run a public check.')
    return value


def serve(spec_path: Path) -> None:
    config = json.loads(spec_path.read_text(encoding="utf-8"))
    checks = [Check.read(item) for item in config["checks"]]
    setup = tuple(Check.read(item) for item in config.get("setup", []))
    workspace = Path(config["workspace"])
    build = config.get("engineering", False)
    stop = Path(config["stop"]) if config.get("stop") else None
    baseline = Path(config["baseline"]) if build else None
    budget = 16 if build else 6
    calls = 0
    for line in iter(lambda: sys.stdin.buffer.readline(32769), b""):
        if len(line) > 32768:
            return
        message = json.loads(line)
        if "id" not in message:
            continue
        method = message.get("method")
        response = {"jsonrpc": "2.0", "id": message["id"]}
        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                "serverInfo": {"name": "aiwork", "version": "0.1.0"},
            }
        elif method == "ping":
            response["result"] = {}
        elif method == "tools/list":
            available = [{
                "name": "check", "description": "Run an approved public command by index in a disposable copy.",
                "inputSchema": {"type": "object", "properties": {
                    "index": {"type": "integer", "minimum": 0, "maximum": len(checks) - 1},
                }, "required": ["index"], "additionalProperties": False},
            }] if checks else []
            if build:
                available.append({"name": "focus", "description": "Discover qualified symbols and read bounded source (60 lines, 3000 UTF-8 bytes). Use query to find a name/text or symbol=Class.method to jump. Follow next_line; unchanged repeated excerpts are suppressed.",
                                  "inputSchema": {"type": "object", "properties": {
                                      "path": {"type": "string"}, "line": {"type": "integer", "minimum": 1},
                                      "symbol": {"type": "string"}, "query": {"type":"string"}}, "required": ["path"], "additionalProperties": False}})
                available.append({"name": "diff", "description": "Review a Git diff of current workspace edits.",
                                  "inputSchema": {"type": "object", "properties": {},
                                                  "additionalProperties": False}})
            response["result"] = {"tools": available}
        elif method == "tools/call":
            params = message.get("params", {})
            args = params.get("arguments", {})
            index = args.get("index") if isinstance(args, dict) else None
            name = params.get("name")
            error = True
            if calls >= budget or (stop and stop.exists()):
                value = {"error": "tool stopped or call limit reached"}
            elif not ((name == "focus" and build and isinstance(args, dict)) or
                      (name == "diff" and build and args == {}) or
                      (name == "check" and isinstance(args, dict) and set(args) == {"index"}
                       and type(index) is int and 0 <= index < len(checks))):
                value = {"error": "invalid tool or command index"}
            else:
                try:
                    calls = reserve_trial_call(spec_path, budget) if build or config.get("trial") else calls + 1
                    if build:
                        changed = delta(inventory(baseline), inventory(workspace))
                        validate_changes(changed, tuple(config["write_roots"]))
                    if name == "focus":
                        value = {**inspect_source(spec_path, workspace, args),
                                 "passed": True, "stdout": "", "stderr": ""}
                    elif name == "diff":
                        patch = git_patch(baseline, workspace, changed,
                                          spec_path.parent / f"agent-diff-{calls:02}")
                        patch_path = spec_path.parent / f"agent-diff-{calls:02}.patch"
                        patch_path.write_bytes(patch.encode("utf-8", "surrogateescape"))
                        value = {"stdout": patch, "stderr": "", "passed": True}
                    else:
                        check_root = spec_path.parent / f"public-check-{calls:02}"
                        snapshot(workspace, check_root, ())
                        remaining = config.get("deadline", time() + 900) - time()
                        value = pipeline(setup, checks[index], check_root, spec_path.parent / "check-home",
                                         config["image"], timeout=remaining, stop=stop, trial=config.get("trial"))
                    value["stdout"] = value["stdout"][-4000:]
                    value["stderr"] = value["stderr"][-4000:]
                    if build:
                        value.update(objective=config.get('objective','')[:1000],
                                     objective_truncated=len(config.get('objective',''))>1000,
                                     write_roots=config['write_roots'],remaining_calls=budget-calls)
                    error = not value["passed"]
                except (ValueError, OSError, RuntimeError) as exc:
                    value = {"error": str(exc)}
                with spec_path.with_name("mcp.jsonl").open("a", encoding="utf-8") as log:
                    log.write(json.dumps({"tool": name, "index": index, "call": calls, **value}) + "\n")
                if build and name == "check" and "passed" in value:
                    value = {key: value[key] for key in ("passed", "code", "stdout", "stderr", "objective", "objective_truncated", "write_roots", "remaining_calls") if key in value}
                    value["stdout"] = value.get("stdout", "")[-450:]
                    value["stderr"] = value.get("stderr", "")[-900:]
            response["result"] = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": error}
        else:
            response["error"] = {"code": -32601, "message": "method unavailable"}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve(Path(sys.argv[1]))
