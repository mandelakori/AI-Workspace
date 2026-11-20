"""Audit public Phase 6 traces without reading private final evaluation material."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aiwork.controller import write_json
from aiwork.metrics import summarize_trace

phase6, phase61, destination = map(lambda value:Path(value).resolve(), sys.argv[1:4])
destination.mkdir(parents=True,exist_ok=True)
rows=[]
for state in ("controller","recovery-controller","final-controller","goal-controller"):
    for trace in sorted((phase6/state/"runs").glob("*/attempt-*/agent.jsonl")):
        reads=[]
        lost=False
        for line in trace.read_text(encoding="utf-8").splitlines():
            try: event=json.loads(line)
            except ValueError: continue
            part=event.get("part",{});data=part.get("state",{})
            if event.get("type")=="tool_use" and part.get("tool")=="read":
                args=data.get("input",{})
                reads.append((json.dumps(args,sort_keys=True),len(str(data.get("output","")))))
            if event.get("type")=="text":
                lost |= any(term in part.get("text","").lower() for term in ("no active work","no task was identified","fresh session"))
        process=json.loads(trace.with_name("agent-process.json").read_bytes())
        rows.append({"path":trace.relative_to(phase6).as_posix(),"sha256":hashlib.sha256(trace.read_bytes()).hexdigest(),
                     "read_calls":len(reads),"same_window_repeats":sum(count-1 for count in Counter(key for key,_ in reads).values()),
                     "outputs_over_20000_characters":sum(size>20000 for _,size in reads),
                     "largest_read_characters":max((size for _,size in reads),default=0),
                     "explicit_abandoned_objective":lost,"trace_truncated":process["truncated"]})
audit={"sessions":rows,"totals":{key:sum(row[key] for row in rows) for key in
       ("read_calls","same_window_repeats","outputs_over_20000_characters","explicit_abandoned_objective","trace_truncated")},
       "interpretation":"Counts are lower bounds from two truncated traces. Same-window repeats may include legitimate rereads after edits; they are not all proven redundant."}
write_json(destination/"trace-audit.json",audit)
smoke=json.loads((phase61/"focus-smoke.json").read_bytes())
attempt=phase61/"controller/runs"/smoke["job"]/"attempt-001"
original=json.loads((attempt/"agent-metrics.json").read_bytes())
recount=summarize_trace((attempt/"agent.jsonl").read_text(encoding="utf-8"),attempt)
write_json(destination/"focused-smoke.json",{"job":smoke["job"],"status":smoke["status"],
    "fixture":"existing conversion fixture; not unfamiliar-repository acceptance",
    "metrics":original,"actual_successful_public_checks":recount["successful_public_mcp_checks"],
    "metrics_note":"Original counter counted two successful inspections as checks. Raw evidence preserved; corrected recount is authoritative.",
    "operator_mid_run_guidance":False,"trace_sha256":hashlib.sha256((attempt/"agent.jsonl").read_bytes()).hexdigest()})
print(json.dumps(audit["totals"]))
