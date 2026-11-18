"""Matched local source-adapter comparison for two new stateful targets."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import monotonic
import json
import shutil
import sys

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import execute, inspect, prepare, register
from aiwork.native import Case, pin_runner, probe, returned
from aiwork.schema import Check, Config
from aiwork.verify import invoke
from aiwork.workspace import inventory

PROFILE = "laptop-ollama-8k"
FIXTURES = {
    "debt": {
        "step": "Add signed 32-bit adjustment to current state and saturate the mathematical sum to [-8,8]. The mathematical sum may exceed the signed 32-bit range.",
        "band": "Return N when state is negative, Z when zero, P when positive.",
        "reference": """long long sum = (long long)state + delta;
        state = sum < -8 ? -8 : sum > 8 ? 8 : (int)sum;
        printf("%c:%d\\n", state < 0 ? 'N' : state == 0 ? 'Z' : 'P', state);""",
        "bounds": (-8,8),
    },
    "water": {
        "step": "Negative sample resets state to zero. Otherwise retain the larger of old state and sample, capped at 15.",
        "band": "Return L for state 0 through 4, M for 5 through 9, H for 10 through 15.",
        "reference": """if (delta < 0) state = 0;
        else if (delta > state) state = delta > 15 ? 15 : delta;
        printf("%c:%d\\n", state < 5 ? 'L' : state < 10 ? 'M' : 'H', state);""",
        "bounds": (0,15),
    },
}
DRIVER = r'''#include <stdio.h>
#include "contract.h"
int main(void) {
    int state, input;
#ifdef ADVANCE
    if (scanf("%d", &state) != 1) return 3;
    while (scanf("%d", &input) == 1) {
        state = step(state, input);
        printf("%d\n", state);
    }
#else
    while (scanf("%d", &input) == 1) printf("%c\n", classify_state(input));
#endif
    return 0;
}'''
MAIN = r'''#include <stdio.h>
#include "contract.h"
int main(void) {
    int state = 0, delta;
    while (scanf("%d", &delta) == 1) {
        state = step(state, delta);
        printf("%c:%d\n", classify_state(state), state);
    }
    return 0;
}'''
CORPUS = [
    ("sign", "3 -8 4\n"),("levels","2 5 11 -1 4"),("empty",""),("eof","8"),
    ("syntax","1 -2 junk 4"),("blank","\r\n\t "),
    ("max-after-step","7 2147483647 -2"),("signed-min","3 -2147483648 2"),
    ("reset-then-grow","-12 0 14 -1 4"),
    ("multiple-zeroes","0 0 -0 +0"),("wide-spaces","\v +4\r\n\t-2"),
    ("boundaries","4 5 9 10 15 16 -10 8"),
]


def state_change(kind, state, adjust):
    if kind == "debt":
        return min(8, max(-8, state + adjust))
    return 0 if adjust < 0 else max(state, min(adjust, 15))


def band(kind, state):
    if kind == "debt":
        return "N" if state < 0 else "Z" if state == 0 else "P"
    return "L" if state < 5 else "M" if state < 10 else "H"


def row(name, data, stdout):
    return {"name":name,"stdin":data,"argv":[],"stdout":stdout,"stderr":"","code":0}


def build_fixture(controller, parent, kind, image):
    model = FIXTURES[kind]
    stage = parent/kind
    public = stage/"public"
    target = stage/"target"
    development = stage/"development"
    for folder in (public,target,development):
        folder.mkdir(parents=True)
    (target/"reference.c").write_text(
        "#include <stdio.h>\nint main(void) {int state=0, delta;"
        "while (scanf(\"%d\", &delta) == 1) {\n" + model["reference"] + "\n} return 0; }\n",
        encoding="ascii")
    build = Check(("gcc","-std=c11","-O0","reference.c","-o","reference.elf"))
    result = invoke(build,target,stage/"home",image)
    write_json(stage/"reference-build.json",result)
    if not result["passed"]:
        raise ValueError("controlled reference build failed")
    # Keep source separate from the executable mount and all workspaces.
    (target/"reference.c").replace(stage/"reference.c")
    reference = Check(("./reference.elf",),8)
    observations=[]
    for name,stimulus in CORPUS:
        result=probe(reference,Case(name,"public",stimulus,()),target,stage/"home",image,
                     controller.config.state/"STOP")
        if not returned(result):
            raise ValueError(f"unbounded reference observation {name}")
        observations.append(row(name,stimulus,result["stdout"]))
    expected = [{k:v for k,v in elem.items() if k!="name"} for elem in observations]
    write_json(development/"cases.json",expected)
    write_json(public/"whole.json",observations)
    write_json(public/"observations.json",observations)
    write_json(stage/"run.json", {"target":inventory(target),"development":inventory(development),"image":image,
        "candidate":asdict(Check(("./candidate",),8)), "reference":asdict(reference)})
    (public/"contract.h").write_text("int step(int state, int reading);\nchar classify_state(int state);\n",encoding="ascii")
    (public/"main.c").write_text(MAIN,encoding="ascii")
    (public/"probe.c").write_text(DRIVER,encoding="ascii")
    shutil.copyfile(Path(__file__).resolve().parents[1]/"phase5/verify_public.py",public/"verify_public.py")
    for part in ("advance","classify"):
        (public/f"{part}.txt").write_text(model["step" if part=="advance" else "band"],encoding="ascii")
    (public/"whole.txt").write_text(model["step"]+" "+model["band"],encoding="ascii")
    state_cases=[]
    for name,start,adjustments in (
        ("zero-start",0,[4,-1,12]),("wide-positive",6,[2147483647,-1]),("wide-negative",2,[-2147483648,3]),
        ("left-bound",model["bounds"][0],[-1,1]),("right-bound",model["bounds"][1],[1,0,-2]),
        ("recovery",2,[5,-1,4,-9,2,7]),
    ):
        state=start
        values=[]
        for adjust in adjustments:
            state=state_change(kind,state,adjust)
            values.append(str(state))
        state_cases.append(row(name," ".join(map(str,[start,*adjustments])),"\n".join(values)+"\n"))
    low, high=model["bounds"]
    band_cases=[row(f"range-{i}"," ".join(map(str,values)),"\n".join(band(kind,n) for n in values)+"\n")
                for i,values in enumerate((list(range(low,high+1)),[0,2,4],[high,low,high]))]
    write_json(public/"advance.json",state_cases)
    write_json(public/"classify.json",band_cases)
    return stage


def component(name, role, interface, inputs, outputs, checks, needs=()):
    return {"role":role,"interface":interface,"inputs":inputs,"outputs":outputs,"needs":list(needs),
            "checks":[{"argv":list(argv),"timeout":25} for argv in checks],"timeout":82 if role=="implementation" else 45}


def arm(model, staged, kind, method):
    public=staged/"public"
    parts=("advance","classify") if method=="hier" else ("solution",)
    nodes={}
    for part in parts:
        if method=="hier":
            interface = ("Implement int step(int state, int reading). "+model["step"] if part=="advance" else
                         "Implement char classify_state(int state). "+model["band"])
            inputs=["contract.h","probe.c",f"{part}.json",f"{part}.txt"]
            build=("gcc","-std=c11","-O2",f"-D{part.upper()}","probe.c",f"{part}.c","-o","program")
            corpus,text=f"{part}.json",f"{part}.txt"
        else:
            interface=("Implement both int step(int state, int reading) and char classify_state(int state) "
                       "in solution.c. "+model["step"]+" "+model["band"])
            inputs=["contract.h","main.c","whole.json","whole.txt"]
            build=("gcc","-std=c11","-O2","main.c","solution.c","-o","program")
            corpus,text="whole.json","whole.txt"
        entry=component(part,"implementation",interface,inputs,[f"{part}.c"],[build,("./program",)])
        entry.update(public_cases=corpus,source_context=["contract.h",text])
        nodes[part]=entry
    nodes["testing"]=component("testing","testing","Link verified sources and check the public executable.",
        ["verify_public.py","observations.json","contract.h","main.c"],["tested"],
        [("{python}","verify_public.py","test",*parts)],parts)
    nodes["integration"]=component("integration","integration","Recheck and publish the integrated executable.",
        ["verify_public.py","observations.json"],["candidate"],
        [("{python}","verify_public.py","integrate")],["testing"])
    policy=staged/f"{method}.json"
    write_json(policy,{"workspace":"public","components":nodes,"max_attempts":2 if method=="hier" else 4})
    tree=staged/f"{method}-tree.json"
    write_json(tree,{"id":"plan","children":[
        {"id":"build","children":[{"component":part} for part in parts]},
        {"id":"release","children":[{"component":"testing"},{"component":"integration"}]},
    ]})
    return policy,tree


def run(config, parent):
    controller=Controller(Config.load(config))
    parent=parent.resolve()
    parent.mkdir(parents=True,exist_ok=False)
    image=pin_runner(controller)
    for kind,model in FIXTURES.items():
        staged=build_fixture(controller,parent,kind,image)
        for method in ("hier","single"):
            path,tree=arm(model,staged,kind,method)
            project=f"adaptive-{kind}-{method}"
            register(controller,project,path)
            for number in (1,2):
                run_id=f"trial-{number}"
                approval=prepare(controller,project,run_id,
                    f"Reconstruct {kind} behavior using the reviewed {method} contracts.",PROFILE,tree)
                start=monotonic()
                result=execute(controller,project,run_id,approval["approval"],1)
                status=inspect(controller,project,run_id)
                write_json(staged/f"{method}-{number}.json",{**status,"seconds":round(monotonic()-start,3)})
                print(kind,method,number,result["status"],result["steps"],flush=True)


if __name__=="__main__":
    run(Path(sys.argv[1]),Path(sys.argv[2]))
