"""Audit preserved source-worker requests without changing their candidate files."""
from pathlib import Path
import hashlib
import json
import re
import sys

workspace=Path(sys.argv[1]).resolve()
destination=Path(sys.argv[2]).resolve()
families={"phase51":workspace/"phase51/ledger-result.json","phase5":workspace/"phase5/ledger-evidence-status.json"}
records={}
def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))
for family, summary in families.items():
    for name in ("framing","syntax","balance"):
        job=workspace/"phase4-followup/controller/runs"/read(summary)["jobs"][name]
        for attempt in sorted(job.glob("attempt-*")):
            if not (attempt/"proposal-context.json").is_file():
                continue
            context=read(attempt/"proposal-context.json")
            response=read(attempt/"proposal-response.json")
            choice=response["choices"][0]
            text=choice["message"].get("content","")
            try: candidate=json.loads(text).get("source","")
            except (ValueError,AttributeError): candidate=""
            verdict=read(attempt/"evidence.json")
            checkpoint=read(attempt/"checkpoint.json") if (attempt/"checkpoint.json").exists() else {}
            public=verdict.get("public",{})
            baseline = read(job/"baseline-public.json") if (job/"baseline-public.json").exists() else {}
            prior=Path(checkpoint["from"]) if checkpoint.get("from") else job/"baseline"
            actual=prior/f"{name}.c"
            classifications=[]
            if candidate and candidate==context.get("current_source"):
                classifications.append("unchanged_source")
                if baseline.get("compiled") and baseline["passed_cases"] < baseline["total"]:
                    classifications.append("incorrect_seed_logic_retained")
            if choice.get("finish_reason")=="length":
                classifications.append("incomplete_generation")
            supplied=len(context.get("current_source","").encode())
            if actual.is_file() and supplied < actual.stat().st_size:
                classifications.append("source_context_truncated")
            check=read(attempt/"check-00.json") if (attempt/"check-00.json").is_file() else {}
            build=public.get("build_diagnostic","") or check.get("stderr","")
            if re.search(r"\berror:|fatal error:|SyntaxError",build):
                classifications.append("compilation_failure")
            elif public.get("compiled") or check:
                classifications.append("incorrect_logic")
            files=context["approved_context"]
            facts={
                "classifications":classifications,"job":job.name,"attempt":attempt.name,
                "finish_reason":choice.get("finish_reason"),"token_usage":response.get("usage"),
                "input_context_bytes":{key:len(value.encode()) for key,value in files.items()},
                "selected_source_bytes":actual.stat().st_size if actual.is_file() else 0,
                "sent_source_bytes":supplied,"returned_source_bytes":len(candidate.encode()),
                "sent_public_diagnostic":context.get("public_diagnostic",""),
                "public_corpus_sent":any("public.json" in key for key in files),
                "baseline_public_score":{key:baseline.get(key) for key in ("passed_cases","total","compiled")},
                "outcome":verdict["detail"],"compiler_evidence":build,
                "request_sha256":hashlib.sha256((attempt/"proposal-context.json").read_bytes()).hexdigest(),
                "response_sha256":hashlib.sha256((attempt/"proposal-response.json").read_bytes()).hexdigest(),
            }
            records[f"{family}/{name}/{attempt.name}"]=facts
destination.write_text(json.dumps(records,indent=2),encoding="utf-8")
for key,facts in records.items():
    print(key,",".join(facts["classifications"]))
