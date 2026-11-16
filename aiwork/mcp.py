"""Task-local MCP stdio server exposing one operator-defined public check."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from time import time

from .changes import delta, git_patch, validate_changes
from .schema import Check
from .verify import pipeline
from .workspace import inventory, snapshot


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
            elif not ((name == "diff" and build and args == {}) or
                      (name == "check" and isinstance(args, dict) and set(args) == {"index"}
                       and type(index) is int and 0 <= index < len(checks))):
                value = {"error": "invalid tool or command index"}
            else:
                calls += 1
                try:
                    if build:
                        changed = delta(inventory(baseline), inventory(workspace))
                        validate_changes(changed, tuple(config["write_roots"]))
                    if name == "diff":
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
                                         config["image"], timeout=remaining, stop=stop)
                    value["stdout"] = value["stdout"][:4000]
                    value["stderr"] = value["stderr"][:4000]
                    error = not value["passed"]
                except (ValueError, OSError, RuntimeError) as exc:
                    value = {"error": str(exc)}
                with spec_path.with_name("mcp.jsonl").open("a", encoding="utf-8") as log:
                    log.write(json.dumps({"tool": name, "index": index, "call": calls, **value}) + "\n")
                if build and name == "check" and "passed" in value:
                    value = {key: value[key] for key in ("passed", "code", "stdout", "stderr") if key in value}
                    value["stdout"] = value.get("stdout", "")[-450:]
                    value["stderr"] = value.get("stderr", "")[-900:]
            response["result"] = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": error}
        else:
            response["error"] = {"code": -32601, "message": "method unavailable"}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve(Path(sys.argv[1]))
