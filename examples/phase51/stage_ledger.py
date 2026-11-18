"""Stage ranked ledger components from hashed public Phase 5 artifacts."""
import json
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

from aiwork.controller import write_json
from ledger_behavior import check, chunks

root, old_run, state = (Path(item).resolve() for item in sys.argv[1:4])
phase5 = Path(__file__).resolve().parents[1] / "phase5"
subprocess.run([sys.executable, str(phase5/"stage_ledger.py"), str(root), str(old_run), "--source"], check=True)

def read(path):
    return json.loads(path.read_bytes())

policy = read(root/"project.json")
static = read(root/"static.json")
ghidra = read(old_run/"candidate/ghidra-00.json")["decompilation"]
tokens = set(re.findall(r'\bputs\("([^"]+)"\)', ghidra))
tokens.update(re.findall(r'\bstrcmp\([^,]+,"([^"]+)"\)', ghidra))
static["syntax"]["tokens"] = sorted(tokens)
write_json(root/"behavior-static.json",static)
model = {
    "target_sha256": static["target_sha256"],
    "grammar": {"chunk_bytes": 95, "line_end": "newline included when it fits",
                "eof": "last nonempty fragment is a chunk", "role_of_blank": "silent",
                "operands": {"add":1,"take":1,"reset":0,"show":0}, "numeric_token": "signed decimal"},
    "state": {"initial":0,"min":0,"max":10000,"amount_min":0,"amount_max":1000,
              "transitions":{"add":{"coefficient":1},"take":{"coefficient":-1},"reset":{"assign":0},"show":{}}},
    "replies": {"invalid":"error\n","denied":"denied\n","value":"{}\n","silent":"",
                "stderr":"","exit_code":0,"on_error":"preserve the balance"},
}
write_json(root/"behavior.json", model)
write_json(root/"behavior-preview.json", check(root/"behavior.json", root/"observations.json",
                                               root/"behavior-static.json"))
assets = Path(__file__).resolve().parent
for file in ("ledger_probe.c", "ledger_behavior.py"):
    shutil.copyfile(assets/file, root/file)
policy["max_attempts"] = 3
components = policy["components"]
components["behavior"] = {
    "role":"analysis","interface":"Validate the structured behavior against static evidence and public observations.",
    "inputs":["ledger_behavior.py","behavior.json","observations.json","behavior-static.json"],
    "outputs":["behavior-verdict.json"],"checks":[{"argv":["{python}","ledger_behavior.py"]}],
}
def row(name, data, expected, argv=()):
    return dict(name=name, stdin=data, stdout=expected, stderr="", code=0, argv=list(argv))

frames = [
    ("empty",""),("retains-short-lines","a\nbc\n"),("eof-fragment","last word"),
    ("exact-width","x"*94+"\n"),("newline-alone-next","x"*95+"\n"),
    ("split-keep-remainder","a\n"+"x"*95+"y\nlast"),("blank-and-nonblank","\n\t\nx"),
]
frame_cases = [row(name, data, "".join(piece.encode().hex()+"\n" for piece in chunks(data,95)))
               for name,data in frames]
syntax = [
    ("blank","\n\f\v","skip"),("bare-show","show","show"),("reset-space","reset \n","reset"),
    ("positive-sign","\tadd +031\n","add:31"),("negative-sign","take -15","take:-15"),
    ("space-free-operand","add1","bad"),("invalid-suffix","add 5.0","bad"),
    ("surplus","add 2 tail","bad"),("missing","take","bad"),("show-extra","show 1","bad"),
    ("bad-verb","RESET","bad"),("lone-sign","add -","bad"),
    ("int-max","add 2147483647","add:2147483647"),("int-min","take -2147483648","take:-2147483648"),
]
syntax_cases = [row(name, data, expected+"\n") for name,data,expected in syntax]
def balance(name, initial, events, lines):
    return row(name, "".join(f"{op} {amount}\n" for op,amount in events),
               "".join(s+"\n" for s in lines), (str(initial),))
balance_cases = [
    balance("add-and-take",4,[(2,7),(3,6),(5,0)],["value:11:11","value:5:5","value:5:5"]),
    balance("denials-preserve",3,[(3,4),(5,0)],["denied:3","value:3:3"]),
    balance("top-range",9999,[(2,1),(2,1),(5,0)],["value:10000:10000","denied:10000","value:10000:10000"]),
    balance("reject-int-max-before-add",7,[(2,2147483647),(5,0)],["error:7","value:7:7"]),
    balance("reject-int-min-before-negation",7,[(3,-2147483648),(5,0)],["error:7","value:7:7"]),
    balance("error-and-empty",5,[(0,0),(1,0),(5,0)],["quiet:5","error:5","value:5:5"]),
    balance("reset",9,[(4,0),(5,0)],["value:0:0","value:0:0"]),
    balance("range-before-transition",3,[(2,1001),(3,-1),(2,1000)],["error:3","error:3","value:1003:1003"]),
]
formats = list(dict.fromkeys(re.findall(r'__isoc99_sscanf\([^,]+,"([^"]+)"',ghidra)))
facts = {
    "framing":{"static_calls":static["framing"]["calls"],"grammar":model["grammar"]},
    "syntax":{"static_format_strings":formats,"grammar":model["grammar"]},
    "balance":{"state":model["state"],"replies":model["replies"]},
}
for name,cases in (("framing",frame_cases),("syntax",syntax_cases),("balance",balance_cases)):
    node=components[name]
    casefile=f"{name}-public.json"
    evidence=f"{name}-facts.json"
    write_json(root/casefile,cases)
    write_json(root/evidence,facts[name])
    node.update(public_cases=casefile, inputs=["contract.h","ledger_probe.c",casefile,evidence],
                source_context=["contract.h",evidence], needs=["analysis","behavior"],
                imports={"analysis":[f"{name}.json"],"behavior":["behavior-verdict.json"]},
                checks=[{"argv":["gcc","-std=c11","-O2","-Wall","-Wextra",f"-D{name.upper()}",
                                 "ledger_probe.c",f"{name}.c","-o","probe"]},
                        {"argv":["./probe"],"timeout":5}], timeout=100)
    if name in ("framing","balance"):
        jobs={"framing":"61eb206001bf5070984ca49a82282b4b","balance":"f5c3fe129ae856f2849e1c70e5c4fdf1"}
        prior=state/"runs"/jobs[name]/"attempt-002"
        seed=prior/"workspace"/f"{name}.c"
        manifest=read(prior/"checkpoint.json")["inventory"]
        if hashlib.sha256(seed.read_bytes()).hexdigest()!=manifest[f"{name}.c"]["sha256"]:
            raise ValueError("archived failed seed changed")
        shutil.copyfile(seed,root/f"{name}.c")
        node["inputs"].append(f"{name}.c")
write_json(root/"project.json",policy)
tree={"id":"ledger-adaptation","children":[
    {"id":"evidence","children":[{"component":"analysis"},{"component":"behavior"}]},
    {"id":"reconstruct","children":[{"component":key} for key in ("framing","syntax","balance","output")]},
    {"id":"release","children":[{"component":"testing"},{"component":"integration"}]},
]}
write_json(root/"tree.json",tree)
