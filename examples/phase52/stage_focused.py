"""Stage targeted, readable public diagnostics for the two remaining owned files."""
from dataclasses import replace
from pathlib import Path
import json
import shutil
import sys

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import inspect
from aiwork.native import pin_runner
from aiwork.schema import Config

cfg=Config.load(Path(sys.argv[1]))
controller=Controller(replace(cfg,verification_image=pin_runner(Controller(cfg))))
report=inspect(controller,"ledger-evidence-tools","trial")
root=Path(sys.argv[2]).resolve()
root.mkdir(parents=True,exist_ok=False)
old=Path(".aiwork/phase52/hybrid").resolve()
for item in old.iterdir():
    if item.is_file(): shutil.copyfile(item,root/item.name)
policy=json.loads((root/"hybrid-project.json").read_bytes())
sources={}
for name in ("framing","validation"):
    job=cfg.state/"runs"/report["jobs"][name]
    task=controller.frozen_task(job,json.loads((job/"intake.json").read_bytes()))
    selected=controller.checkpoint(task,job/"selection") or job/"baseline"
    receipt=json.loads((selected.parent/"checkpoint.json").read_bytes()) if selected.name=="workspace" else (
        json.loads((job/"baseline-public.json").read_bytes()))
    source=selected/(name+".c")
    import hashlib
    if hashlib.sha256(source.read_bytes()).hexdigest()!=receipt["inventory"][name+".c"]["sha256"]:
        raise ValueError("public-selected candidate changed")
    shutil.copyfile(source,root/(name+".c"))
    entry=policy["components"][name]
    if name+".c" not in entry["inputs"]:entry["inputs"].append(name+".c")
    entry["interface"] += " Use command 2 for the first targeted reproducer, command 3 for the next, and command 0 for all public cases."
    names=("retains-short-lines","split-keep-remainder") if name=="framing" else ("bare-show","reset-space")
    entry["commands"] += [{"argv":["{python}","component_check.py",name,case],"timeout":30} for case in names]
    sources[name]={"source":str(source),"inventory":receipt["inventory"][name+".c"],"job":report["jobs"][name]}
driver=(root/"component_check.py").read_text()
driver=driver.replace("part=sys.argv[1]", """part=sys.argv[1]
all_cases=json.load(open(part+'-public.json'))
cases=[row for row in all_cases if len(sys.argv)<3 or row['name']==sys.argv[2]]
if not cases: raise ValueError('unknown approved public case')
def show_chunks(text):
 try: return [bytes.fromhex(line).decode('utf-8','replace') for line in text.splitlines()]
 except ValueError: return text""")
driver=driver.replace("for row in json.load(open(part+'-public.json')):","for row in cases:")
driver=driver.replace("else: print(json.dumps({'case':row['name'],'input':row['stdin'],'argv':row.get('argv',[]),'expected':expected,'observed':actual}))",
"""else:
  detail={'case':row['name'],'input':row['stdin'],'argv':row.get('argv',[]),'expected':expected,'observed':actual}
  if part=='framing':
   detail['expected_chunks']=show_chunks(expected['stdout'])
   detail['observed_chunks']=show_chunks(actual['stdout'])
  if part=='validation': detail['input_words']=row['stdin'].split()
  print(json.dumps(detail))""")
driver=driver.replace("len(json.load(open(part+'-public.json')))","len(cases)")
(root/"component_check.py").write_text(driver,encoding="ascii")
policy["max_attempts"]=2
write_json(root/"focused-project.json",policy)
write_json(root/"focused-seeds.json",sources)
