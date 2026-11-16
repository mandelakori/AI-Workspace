"""Task-local MCP stdio server exposing one operator-defined public check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .schema import Check
from .verify import invoke


def serve(spec_path: Path) -> None:
    config = json.loads(spec_path.read_text(encoding="utf-8"))
    checks = [Check.read(item) for item in config["checks"]]
    workspace = Path(config["workspace"])
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
            response["result"] = {"tools": [{
                "name": "check", "description": "Run an approved public workspace test by index.",
                "inputSchema": {"type": "object", "properties": {
                    "index": {"type": "integer", "minimum": 0, "maximum": len(checks) - 1},
                }, "required": ["index"], "additionalProperties": False},
            }]}
        elif method == "tools/call":
            params = message.get("params", {})
            args = params.get("arguments", {})
            index = args.get("index")
            error = True
            if (params.get("name") != "check" or set(args) != {"index"} or
                type(index) is not int or not 0 <= index < len(checks) or calls >= 6):
                value = {"error": "invalid tool, test index or call limit reached"}
            else:
                calls += 1
                try:
                    value = invoke(checks[index], workspace, spec_path.parent / "check-home",
                                   config["image"])
                    value["stdout"] = value["stdout"][:4000]
                    value["stderr"] = value["stderr"][:4000]
                    error = not value["passed"]
                except (ValueError, OSError) as exc:
                    value = {"error": str(exc)}
                with spec_path.with_name("mcp.jsonl").open("a", encoding="utf-8") as log:
                    log.write(json.dumps({"index": index, "call": calls, **value}) + "\n")
            response["result"] = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": error}
        else:
            response["error"] = {"code": -32601, "message": "method unavailable"}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve(Path(sys.argv[1]))
