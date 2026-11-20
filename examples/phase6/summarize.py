"""Summarize public run receipts; never opens private evaluation inputs."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2])

def read(path):
    return json.loads(path.read_bytes()) if path.exists() else {}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

sessions = []
for state in ("controller", "recovery-controller", "final-controller", "goal-controller"):
    for attempt in sorted((root / state / "runs").glob("*/attempt-*")):
        evidence = read(attempt / "evidence.json")
        metrics = read(attempt / "agent-metrics.json")
        process = read(attempt / "agent-process.json")
        cached = 0
        events = 0
        trace = attempt / "agent.jsonl"
        for line in trace.read_text(encoding="utf-8").splitlines() if trace.exists() else []:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") == "step_finish":
                events += 1
                cached += row.get("part", {}).get("tokens", {}).get("cache", {}).get("read", 0)
        sessions.append({"path": attempt.relative_to(root).as_posix(), "status": evidence.get("status"),
                         "elapsed": evidence.get("elapsed"), "harness_seconds": process.get("elapsed"),
                         "truncated": process.get("truncated"), "metrics": metrics,
                         "recorded_generation_events": events, "reported_cache_read": cached,
                         "trace_sha256": sha(trace)})

proposals = []
for experiment in ("source-recovery-v4", "refined-recovery", "thinking-recovery", "final-method-recovery",
                   "api-contract-recovery", "test-method-recovery", "docs-text-recovery", "final-docs-recovery"):
    for attempt in sorted((root / experiment).glob("*")):
        if attempt.is_dir() and (attempt / "proposal-request.json").exists():
            proposals.append(attempt)
proof = root / "docs-example-repair/attempt"
if (proof / "proposal-request.json").exists():
    proposals.append(proof)
rows = []
for attempt in proposals:
    request = read(attempt / "proposal-request.json")
    response = read(attempt / "proposal-response.json")
    selection = read(attempt / "selection.json") or read(attempt.parent / "selection.json")
    rows.append({"path": attempt.relative_to(root).as_posix(), "model": request["model"],
                 "reasoning_effort": request.get("reasoning_effort"), "max_tokens": request["max_tokens"],
                 "request_sha256": sha(attempt / "proposal-request.json"),
                 "response_sha256": sha(attempt / "proposal-response.json"),
                 "usage": response.get("usage"), "metrics": read(attempt / "agent-metrics.json"),
                 "selection": selection})
planner = read(root / "controller/plans/click-iso-plan/planner-evidence.json")
input_count = sum((session["metrics"].get("tokens") or {}).get("input", 0) for session in sessions)
output_count = sum((session["metrics"].get("tokens") or {}).get("output", 0) for session in sessions)
input_count += planner.get("usage", {}).get("prompt_tokens", 0)
output_count += planner.get("usage", {}).get("completion_tokens", 0)
input_count += sum((row["usage"] or {}).get("prompt_tokens", 0) for row in rows)
output_count += sum((row["usage"] or {}).get("completion_tokens", 0) for row in rows)
summary = {"planner_usage": planner.get("usage"), "engineering_sessions": sessions, "source_proposals": rows,
           "totals": {"engineering_sessions": len(sessions), "source_requests": len(rows),
                      "source_accepted": sum(row["selection"].get("accepted") is True for row in rows),
                      "source_regressions_rejected": sum(row["selection"].get("reason") == "public_regression" for row in rows),
                      "input_counter_lower_bound": input_count, "output_counter_lower_bound": output_count,
                      "engineering_attempt_seconds": round(sum(session["elapsed"] or 0 for session in sessions), 3),
                      "worker_tool_calls_lower_bound": sum(sum(session["metrics"].get("tool_calls", {}).values()) for session in sessions),
                      "source_request_seconds_known": round(sum(row["metrics"].get("proposal_seconds", 0) for row in rows), 3)},
           "limitations": ["Early OpenCode traces were truncated at 1 MiB; their counts are lower bounds.",
                           "Timed-out HTTP requests have no complete server usage receipt.",
                           "Reported OpenCode cache reads and source API cached-token fields are retained separately.",
                           "No matched hierarchy-versus-single-worker performance claim is supported."]}
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary["totals"], indent=2))
