"""One model-authored documentation edit after executing its public examples."""
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aiwork.component_source import propose_source
from aiwork.controller import Controller, write_json
from aiwork.schema import Check, Config, Task
from aiwork.selection import compare, score
from aiwork.workspace import inventory, snapshot
from examples.phase6.repair_source import assemble

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=False)
controller = Controller(Config.load(Path(sys.argv[2])))
start = Path(sys.argv[3]).resolve()
documentation = Path(sys.argv[4]).resolve()
base = Path(sys.argv[5]).resolve()
image = controller.config.verification_image
profile, = controller.config.profiles
if profile.location != "local" or profile.model != "aiwork-qwen35-phase4:8k":
    raise ValueError("only the reviewed existing local model is allowed")
work = root / "candidate"
snapshot(start, work, ())
build = Check(("python", "_aiwork_verify.py", "upstream"), timeout=120)
run = Check(("python", "_aiwork_probe.py"), timeout=90)

def grade(name):
    receipt = score(build, run, work / "_aiwork_public_cases.json", work,
                    root / (name + "-home"), image, monotonic()+240, root / "STOP", [])
    receipt["inventory"] = inventory(work)
    write_json(root / (name + ".json"), receipt)
    return receipt

incumbent = grade("baseline")
if not incumbent["compiled"]:
    raise RuntimeError("upstream verifier unavailable; no inference allowed")
worker = root / "worker"
worker.mkdir()
for name in ("FEATURE.md",):
    (worker / name).write_bytes((start / name).read_bytes())
(worker / "documentation.md").write_bytes(documentation.read_bytes())
objective = (
    "Correct only the public documentation inconsistencies in current_source using 1-3 exact edits. "
    "The --start option uses default ISODateTime and accepts naive values, so its documented rejection is false. "
    "The displayed strptime formats error is also inaccurate for this type. Remove or correct that misleading "
    "error transcript using the option that actually requires a timezone. The --utc-normalize CLI flag is "
    "declared but never used: remove its decorator and matching unused callback parameter together. "
    "Preserve working CLI usage, both type flags, compatibility text and the API section. "
    "This is documentation only. Do not modify production source or tests."
)
task = Task(objective, worker, "agent", "phase6-docs-example", ("FEATURE.md",), ("documentation.md",),
            (build,), mode="engineering", location="local", profile=profile.id,
            agent_role="debugging", source_context=("FEATURE.md",), source_patch=True,
            write_roots=("documentation.md",))
task.validate()
attempt = root / "attempt"
attempt.mkdir()
write_json(root / "review.json", {"requests": 1, "task": objective, "baseline_inventory": incumbent["inventory"],
                                 "scope": "only prior model-authored documentation additions"})
try:
    propose_source(controller, task, profile, worker, attempt, monotonic()+120,
                   "Executed public documentation transcript exits 0 although it claims Error/exit 2. "
                   "--start permits naive dates; --end requires a timezone. Keep Click ISO 8601 diagnostics accurate.")
    assemble("docs-text", (worker / "documentation.md").read_text(encoding="utf-8"), work, base)
    challenger = grade("proposal")
    decision = compare(incumbent, challenger, protect_passing=True)
except (OSError, RuntimeError, ValueError) as error:
    decision = {"accepted": False, "reason": str(error)}
write_json(root / "selection.json", decision)
print(decision)
raise SystemExit(0 if decision["accepted"] else 1)
