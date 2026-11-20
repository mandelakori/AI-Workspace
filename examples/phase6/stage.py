"""Stage a frozen Click feature contract and public tests, without supplying implementation."""
from dataclasses import replace
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aiwork.controller import Controller, write_json
from aiwork.native import pin_runner
from aiwork.schema import Config
from aiwork.verify import invoke
from aiwork.schema import Check
from aiwork.workspace import inventory, snapshot

assets = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", type=Path)
parser.add_argument("--config", type=Path, default=Path(".aiwork/phase4-followup.local.toml"))
args = parser.parse_args()
root = args.root.resolve()
upstream = root/"upstream-click"
workspace = root/"workspace"
snapshot(upstream, workspace, ())
for original, destination in (("FEATURE.md", "FEATURE.md"), ("verify_public.py", "_aiwork_verify.py"),
                              ("probe_public.py", "_aiwork_probe.py")):
    shutil.copyfile(assets/original, workspace/destination)

cases = []
def case(name, value, expected):
    cases.append({"name": name, "stdin": json.dumps(value), "stdout": json.dumps(expected, sort_keys=True, separators=(",", ":"))+"\n",
                  "stderr": "", "code": 0})

case("public-export", {"kind":"metadata"}, {"export":True,"param_type":True,"name":"iso_datetime","repr":"ISODateTime","require_timezone":False,"normalize_to_utc":False})
for name, value, expected in (
    ("naive", "2024-06-18T07:08:09", "2024-06-18T07:08:09"),
    ("offset", "2024-06-18T07:08:09+05:30", "2024-06-18T07:08:09+05:30"),
    ("utc-z", "2024-06-18T07:08:09Z", "2024-06-18T07:08:09+00:00"),
    ("fraction", "2024-06-18T07:08:09.123456-04:00", "2024-06-18T07:08:09.123456-04:00"),
    ("date-only", "2024-02-29", "2024-02-29T00:00:00"),
): case(name, {"kind":"parse","value":value}, {"iso":expected})
case("object-identity", {"kind":"identity"}, {"iso":"2024-02-29T03:04:05+02:00","identity":True})
for name, value, flags in (("require-naive", "2024-01-01T12:00:00", {"require_timezone":True}),
                           ("require-date", "2024-01-01", {"require_timezone":True}),
                           ("normalize-naive", "2024-01-01T12:00:00", {"normalize_to_utc":True})):
    case(name, {"kind":"parse","value":value,"flags":flags,"timezone_error":True},
         {"error":"BadParameter","iso_hint":True,"timezone_hint":True})
case("require-aware", {"kind":"parse","value":"2024-01-01T12:00:00+00:00","flags":{"require_timezone":True}}, {"iso":"2024-01-01T12:00:00+00:00"})
case("normalize-boundary", {"kind":"parse","value":"2024-01-01T01:00:00+05:30","flags":{"normalize_to_utc":True}}, {"iso":"2023-12-31T19:30:00+00:00"})
case("policy-metadata", {"kind":"metadata","flags":{"require_timezone":True,"normalize_to_utc":True}}, {"export":True,"param_type":True,"name":"iso_datetime","repr":"ISODateTime","require_timezone":True,"normalize_to_utc":True})
for name,value in (("invalid-day","2024-02-30T12:00:00"),("invalid-text","tomorrow"),("invalid-number",123),("invalid-null",None)):
    case(name, {"kind":"parse","value":value}, {"error":"BadParameter","iso_hint":True})
case("cli-normalize", {"kind":"cli","flags":{"normalize_to_utc":True},"args":["--when","2024-01-01T01:00:00+05:30"]}, {"code":0,"output":"2023-12-31T19:30:00+00:00\n"})
case("cli-error", {"kind":"cli","args":["--when","yesterday"],"error":True}, {"code":2,"parameter_hint":True,"iso_hint":True})
case("cli-help", {"kind":"cli","args":["--help"],"help":True}, {"code":0,"metavar":True})
case("cli-env", {"kind":"cli","env":{"WHEN_VALUE":"2024-01-01T12:00:00Z"}}, {"code":0,"output":"2024-01-01T12:00:00+00:00\n"})
case("cli-default", {"kind":"cli","default":"2024-01-01T12:00:00Z"}, {"code":0,"output":"2024-01-01T12:00:00+00:00\n"})
case("cli-multiple", {"kind":"cli","multiple":True,"args":["--when","2024-01-01","--when","2024-02-01T12:30:00Z"]}, {"code":0,"output":"2024-01-01T00:00:00|2024-02-01T12:30:00+00:00\n"})
case("legacy-rejects-offset", {"kind":"legacy","value":"2024-01-01T12:00:00Z"}, {"error":"BadParameter"})
case("authored-tests-and-docs", {"kind":"repository"}, {"complete":True})
write_json(workspace/"_aiwork_public_cases.json",cases)

old = Config.load(args.config)
image = pin_runner(Controller(replace(old,verification_image="aiwork-phase6-click:20261120")))
profile = next(p for p in old.profiles if p.id=="laptop-ollama-8k")
config = f'state = "controller"\nexecution_state = {json.dumps(str(old.execution_state).replace(chr(92),"/"))}\nverification_image = {json.dumps(image)}\n\n[[profiles]]\n'
for key in ("id","model","endpoint","engine","harness","location","context","output_tokens","reasoning_effort"):
    value=getattr(profile,key)
    config+=f'{key} = {json.dumps(value)}\n'
(root/"local.toml").write_text(config,encoding="utf-8")

objective=(workspace/"FEATURE.md").read_text()+"\nInspect the existing DateTime and ParamType implementations and public checker. Use the approved commands to implement and debug the feature, tests and documentation. Do not modify existing tests or verifier helpers."
roots=["src/click/types.py","src/click/__init__.py","tests/test_iso_datetime.py","docs/parameter-types.md","docs/api.md"]
commands=[{"argv":["{python}","_aiwork_verify.py",mode],"timeout":120} for mode in ("public","upstream","feature","all")]
base={"objective":objective,"workspace":workspace.as_posix(),"kind":"agent","mode":"engineering","location":"local",
      "profile":profile.id,"category":"click-iso-datetime","attempts":3,"timeout":600,"baseline_check":True,
      "inputs":["src","tests","docs","examples","pyproject.toml","README.md","LICENSE.txt","CHANGES.rst",
                "FEATURE.md","_aiwork_verify.py","_aiwork_probe.py","_aiwork_public_cases.json"],
      "min_context":8192,"write_roots":roots,"deliverables":[r for r in roots if not r.startswith("tests/")]}

def manifest(path, ranked):
    data=dict(base)
    data.update(rank_public=ranked,public_cases="_aiwork_public_cases.json" if ranked else "",attempt_limit=3 if ranked else 0)
    text="".join(f'{k} = {json.dumps(v)}\n' for k,v in data.items())
    for command in commands:
        text+='\n[[commands]]\n'+''.join(f'{k} = {json.dumps(v)}\n' for k,v in command.items())
    checks=([commands[1],{"argv":["{python}","_aiwork_probe.py"],"timeout":90}] if ranked else [commands[0],commands[3]])
    for check in checks:
        text+='\n[[checks]]\n'+''.join(f'{k} = {json.dumps(v)}\n' for k,v in check.items())
    path.write_text(text,encoding="utf-8")

manifest(root/"task.toml",True)
manifest(root/"planning.toml",False)
sources=inventory(workspace)
write_json(root/"frozen-spec.json",{"upstream":"https://github.com/pallets/click","commit":"052c006033729bbb422cbdad0c4fee988ecb5aa5",
    "release":"8.3.2","spec_sha256":hashlib.sha256((workspace/"FEATURE.md").read_bytes()).hexdigest(),"inventory":sources,
    "image":image,"public_cases":len(cases),"write_roots":roots,"implementation_sessions":3,"session_timeout":600,
    "private_evaluation":"not_created_until_candidate_frozen","wheels":inventory(root/"image/wheels")})
baseline=invoke(Check(("{python}","_aiwork_verify.py","upstream"),timeout=180),workspace,root/"baseline-home",image)
write_json(root/"baseline.json",baseline)
print(json.dumps({"image":image,"baseline_passed":baseline["passed"],"baseline_stdout":baseline["stdout"][-1700:],
                  "files":len(sources),"python_lines":sum((workspace/p).read_bytes().count(b'\n') for p in sources if p.startswith('src/') and p.endswith('.py')),"public_cases":len(cases)},indent=2))
if not baseline["passed"]: raise SystemExit(1)
