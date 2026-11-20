"""Freeze an unfamiliar public task and approval draft; never dispatch an agent."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aiwork.controller import write_json
from aiwork.schema import Check, Config
from aiwork.verify import invoke, runner_status
from aiwork.workspace import snapshot

root = Path(sys.argv[1]).resolve()
base = root / "httpx-upstream"
commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=base, capture_output=True, text=True, check=True).stdout.strip()
if commit != "26d48e0634e6ee9cdc0533996db289ce4b430177":
    raise ValueError("unexpected HTTPX baseline")
work = root / "httpx-task"
snapshot(base, work, ())
assets = Path(__file__).resolve().parent
shutil.copyfile(assets / "HTTPX-FEATURE.md", work / "FEATURE.md")
shutil.copyfile(assets / "httpx_public.py", work / "_public_checks.py")
image = runner_status(root, "aiwork-phase61-httpx:local")["image_id"]
commands = [Check(("python", "_public_checks.py"),timeout=60),
            Check(("python", "-m", "pytest", "-q", "-p", "anyio.pytest_plugin", "-p", "no:cacheprovider",
                   "tests/test_utils.py", "tests/client/test_client.py"),timeout=120)]
config = Config.load(root / "local.toml")
profile, = config.profiles
review = {
    "status":"PREPARED_NOT_AUTHORIZED", "execution_allowed":False,
    "source":"https://github.com/encode/httpx", "base_commit":commit,
    "feature_sha256":hashlib.sha256((work / "FEATURE.md").read_bytes()).hexdigest(),
    "public_sha256":hashlib.sha256((work / "_public_checks.py").read_bytes()).hexdigest(),
    "inventory":snapshot(work, root / "httpx-input-freeze", ()),
    "runner":image, "profile":asdict(profile),
    "read_scope":"staged public HTTPX source, tests, docs, project files and FEATURE.md; no private verification",
    "write_roots":["httpx/_utils.py","httpx/_client.py","tests/test_path_mounts.py","docs/advanced/transports.md"],
    "commands":[asdict(check) for check in commands],
    "denied":["network","host shell","cloud/remote tools","credential access","changes to public checks or existing tests"],
    "proposed_matched_budget":{"total_worker_sessions":2,"overall_seconds_including_planning":240,
                               "per_request_output_tokens":2048,"per_session_mcp_calls":16,
                               "context":8192,"workers":1},
    "budget_review":"Confirm cumulative deadline enforcement and cold/warm model protocol before dispatch. Tokens are measured, not claimed as an enforced total cap.",
    "operator_policy":"Approve initial permissions, image, profile and budgets once. No mid-run implementation guidance; otherwise classify the trial as assisted.",
    "final_evaluation":"Author new private inputs only after candidate freeze; no sealed feedback to a worker.",
    "comparison":"NOT_RUN; no model calls in preparation and no runnable task manifest emitted",
}
results={}
for name,check in zip(("public","upstream"),commands):
    outcome=invoke(check,work,root/"httpx-baseline-home",image,sealed=True)
    write_json(root / ("httpx-baseline-"+name+".json"),outcome)
    results[name]={"passed":outcome["passed"],"receipt_sha256":hashlib.sha256((root/("httpx-baseline-"+name+".json")).read_bytes()).hexdigest()}
    print(name,outcome["code"],outcome["stdout"][-250:],outcome["stderr"][-500:],flush=True)
review["baseline_results"]=results
review["baseline_ready"]=results["upstream"]["passed"]
digest = hashlib.sha256(json.dumps(review,sort_keys=True,default=str).encode()).hexdigest()
write_json(root / "httpx-review.json", {"approval_digest":digest,**review})
print("PREPARED_NOT_AUTHORIZED",digest)
