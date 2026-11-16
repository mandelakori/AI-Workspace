from __future__ import annotations

import json
from pathlib import Path


def summarize_trace(text: str, attempt: Path) -> dict:
    tools: dict[str, int] = {}
    tokens = {"input": 0, "output": 0, "reasoning": 0}
    usage_reported = False
    peak_input = 0
    errors = 0
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        part = row.get("part", {})
        if not isinstance(part, dict):
            continue
        event = row.get("type")
        if event == "tool_use":
            name = part.get("tool", row.get("tool_name", "unknown"))
            if isinstance(name, str):
                tools[name] = tools.get(name, 0) + 1
            state = part.get("state", {})
            errors += isinstance(state, dict) and state.get("status") == "error"
        if event in {"assistant", "user"} and isinstance(row.get("message"), dict):
            usage = row["message"].get("usage")
            if isinstance(usage, dict) and type(usage.get("input_tokens")) is int:
                peak_input = max(peak_input, usage["input_tokens"])
            for item in row["message"].get("content", []):
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use" and isinstance(item.get("name"), str):
                    name = item["name"]
                    tools[name] = tools.get(name, 0) + 1
                if item.get("type") == "tool_result" and item.get("is_error") is True:
                    errors += 1
        if event == "result" and isinstance(row.get("usage"), dict):
            usage = row["usage"]
            for name in ("input", "output", "reasoning"):
                count = usage.get(name + "_tokens")
                if type(count) is int:
                    usage_reported = True
                    tokens[name] = count
        if event == "step_finish" and isinstance(part.get("tokens"), dict):
            usage_reported = True
            if type(part["tokens"].get("input")) is int:
                peak_input = max(peak_input, part["tokens"]["input"])
            for name in tokens:
                count = part["tokens"].get(name)
                if type(count) is int:
                    tokens[name] += count
    mcp_path = attempt / "mcp.jsonl"
    public_checks = 0
    if mcp_path.exists():
        for line in mcp_path.read_text(encoding="utf-8").splitlines():
            try:
                public_checks += json.loads(line).get("passed") is True
            except (ValueError, AttributeError):
                continue
    return {"tool_calls": tools, "tool_errors": errors,
            "tokens": tokens if usage_reported else None,
            "peak_reported_input_tokens": peak_input or None,
            "successful_public_mcp_checks": public_checks}
