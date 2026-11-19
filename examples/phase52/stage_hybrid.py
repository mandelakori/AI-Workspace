"""Compose verified model-authored parts and expose original static evidence to remaining workers."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import inspect
from aiwork.schema import Config

cfg=Config.load(Path(sys.argv[1]))
ctrl=Controller(cfg)
root=Path(sys.argv[2]).resolve()
root.mkdir(parents=True,exist_ok=False)
prior=Path(".aiwork/phase52/context-review").resolve()
for path in prior.iterdir():
    if path.is_file():shutil.copyfile(path,root/path.name)
policy=json.loads((root/"tools-project.json").read_bytes())
nodes=policy["components"]
origin=Path(".aiwork/phase4-followup/controller/native/64685c5d53b9405298e778adce13e13f")
analysis=json.loads((origin/"candidate/ghidra-00.json").read_bytes())
original=json.loads((origin/"run.json").read_bytes())
target=original["target"]
intake=json.loads((cfg.state/"runs"/original["job"]/"intake.json").read_bytes())
if hashlib.sha256((origin/"candidate/ghidra-00.json").read_bytes()).hexdigest() != (
    intake["inventory"]["ghidra-00.json"]["sha256"]
):
    raise ValueError("archived Ghidra evidence changed")
write_json(root/"ghidra-ledger.json",{"target_sha256":next(iter(target.values()))["sha256"],
                                   "decompilation":analysis["decompilation"]})
seed_receipts={}
for name,project in (("tokenize","ledger-split-source"),("balance","ledger-split-tools")):
    report=inspect(ctrl,project,"trial")
    output=report["outputs"][name][name+".c"]
    source=Path(output["path"])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=output["sha256"]:
        raise ValueError("verified source changed")
    shutil.copyfile(source,root/(name+".c"))
    if name+".c" not in nodes[name]["inputs"]:
        nodes[name]["inputs"].append(name+".c")
    seed_receipts[name]={"project":project,"job":report["jobs"][name],"source":str(source),"receipt":output}
for name in ("framing","validation"):
    nodes[name]["inputs"].append("ghidra-ledger.json")
    nodes[name]["interface"] += " Inspect ghidra-ledger.json for the preserved reference behavior; implement only the assigned function."
    nodes[name]["role"]="debugging"
# Tokenizer and balance are recompiled and replayed from their verified source receipts.
write_json(root/"seed-provenance.json",seed_receipts)
write_json(root/"hybrid-project.json",policy)
