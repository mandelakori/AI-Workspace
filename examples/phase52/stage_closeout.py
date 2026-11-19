"""Stage one bounded closeout using public-selected model sources and compatible verified work."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sys

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import inspect
from aiwork.native import pin_runner
from aiwork.schema import Config

cfg = Config.load(Path(sys.argv[1]))
controller = Controller(replace(cfg, verification_image=pin_runner(Controller(cfg))))
prior = inspect(controller, "ledger-targeted-tools", "trial")
root = Path(sys.argv[2]).resolve()
root.mkdir(parents=True, exist_ok=False)
for path in Path(".aiwork/phase52/focused").iterdir():
    if path.is_file():
        shutil.copyfile(path, root/path.name)
policy = json.loads((root/"focused-project.json").read_bytes())
provenance = {}
diagnostics = {
    "framing": "Public a\\nbc\\n must yield two chunks, retaining each newline. Current fread reads past "
               "the first newline. Static evidence uses fgets with capacity 0x60 (96). Preserve 95-byte "
               "chunks, EOF fragments, and the unread remainder. Repair only read_chunk.",
    "validation": "Current alphabetic and short-word tests run over numeric operands, rejecting valid "
                  "+031, -15, INT_MAX and INT_MIN. Restrict command-name rules to the verb. Parse the "
                  "operand as a complete signed decimal with range checks, preserve its sign for TAKE. "
                  "Keep arity, case sensitivity, malformed-token rejection and all previous passes.",
    "balance": "Public UBSan fails because the code computes a new balance before rejecting INT_MAX. "
               "Validate ADD/TAKE amounts before arithmetic. Bounds are balance 0..10000, amount 0..1000. "
               "Other operations ignore the unused amount field. Reject invalid operations without "
               "changing state. Preserve all public behavior and pass the sanitizer gate.",
}
for name, diagnostic in diagnostics.items():
    job = cfg.state/"runs"/prior["jobs"][name]
    task = controller.frozen_task(job, json.loads((job/"intake.json").read_bytes()))
    selected = controller.checkpoint(task, job/"selection") or job/"baseline"
    receipt = json.loads((selected.parent/"checkpoint.json" if selected.name == "workspace"
                          else job/"baseline-public.json").read_bytes())
    file = name+".c"
    source = selected/file
    expected = receipt["inventory"][file]["sha256"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError("selected source hash changed")
    shutil.copyfile(source, root/file)
    provenance[name] = {"job": prior["jobs"][name], "source": str(source), "sha256": expected}
    facts = name+"-closeout.txt"
    (root/facts).write_text(diagnostic, encoding="utf-8")
    node = policy["components"][name]
    node.update(role="debugging", source_context=["contract.h", facts], source_patch=True)
    if name == "framing":
        node["source_context"].append("ghidra-ledger.json")
    node["inputs"].append(facts)
    if file not in node["inputs"]:
        node["inputs"].append(file)

# These cases follow existing public interface contracts, including unused fields.
cases = json.loads((root/"balance-public.json").read_bytes())
cases.extend([
    {"name": "non-numeric-ignores-amount", "stdin": "0 -2147483648\n5 -1\n4 -7\n5 2147483647\n",
     "argv": ["9"], "stdout": "quiet:9\nvalue:9:9\nvalue:0:0\nvalue:0:0\n", "stderr": "", "code": 0},
    {"name": "invalid-commands-preserve", "stdin": "1 -1\n9 7\n5 0\n",
     "argv": ["13"], "stdout": "error:13\nerror:13\nvalue:13:13\n", "stderr": "", "code": 0},
])
write_json(root/"balance-public.json", cases)
shutil.copyfile(Path(__file__).with_name("sanitizer_gate.py"), root/"sanitizer_gate.py")
gate = {"argv": ["{python}", "sanitizer_gate.py"], "timeout": 25}
balance = policy["components"]["balance"]
balance["inputs"].append("sanitizer_gate.py")
balance["checks"][0] = gate
balance["commands"][1] = gate
write_json(root/"balance-recipe.json", {"build": ["python3", "sanitizer_gate.py"]})
policy["max_attempts"] = 2
write_json(root/"closeout-project.json", policy)
write_json(root/"seed-provenance.json", provenance)
