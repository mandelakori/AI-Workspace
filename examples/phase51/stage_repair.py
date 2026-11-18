"""Stage a ranked repair of the archived model-authored meter arithmetic."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from aiwork.controller import write_json

cfg, stage, state = map(Path, sys.argv[1:])
phase5=Path(__file__).resolve().parents[1]/"phase5"
subprocess.run([sys.executable,str(phase5/"stage_window.py"),str(cfg),str(stage),"--source","--meter"],check=True)
assets=stage/"public"
policy=json.loads((assets/"project.json").read_bytes())
name="7268483ab1cd5229b3bb785db4a7f269"
job=state/"runs"/name/"attempt-001"
seed=(job/"workspace/state.c").read_bytes()
receipt=json.loads((job/"output-inventory.json").read_bytes())
if hashlib.sha256(seed).hexdigest()!=receipt["state.c"]["sha256"]:
    raise ValueError("archived source changed")
(assets/"state.c").write_bytes(seed)
(assets/"state-probe.c").write_text(r'''
#include "contract.h"
#include <stdio.h>
int main(void) {
    int state, adjustment;
    if (scanf("%d", &state) != 1) return 3;
    while (scanf("%d", &adjustment) == 1) {
        state = meter_step(state, adjustment);
        printf("%d\n", state);
    }
    return 0;
}
''',encoding="ascii")
def row(label, data, expected):
    return {"name":label,"stdin":data,"stdout":expected,"stderr":"","code":0}
cases=[
    row("small-moves","3 4 -2","7\n5\n"),row("floor","3 -8 1","0\n1\n"),
    row("ceiling","5 8 1","9\n9\n"),row("zero","3 0","3\n"),
    row("large-negative-then-recover","6 -2147483648 3","0\n3\n"),
    row("large-positive-from-nonzero","4 2147483647","9\n"),
    row("large-positive-and-preserve-transition","7 2147483644 -2","9\n7\n"),
]
write_json(assets/"state-corpus.json",cases)
(assets/"state-contract.txt").write_text("The operator-approved model adds state and adjustment mathematically "
    "before saturation to 0 through 9. Inputs include all signed int32 adjustments. The mathematical sum may "
    "exceed signed int32. Keep the public state transition invariant on every call.",encoding="ascii")
node=policy["components"]["state"]
node.update(
    interface="Repair int meter_step(int state, int delta) in state.c. Add delta to state mathematically and "
    "saturate the result to [0,9]. The adjustment can be any signed 32-bit integer and the intermediate "
    "sum may lie outside signed 32-bit range. Keep the existing function signature.",
    public_cases="state-corpus.json",
    inputs=["contract.h","state.c","state-probe.c","state-corpus.json","state-contract.txt"],
    source_context=["contract.h","state-contract.txt"],
    checks=[{"argv":["gcc","-std=c11","-O2","state-probe.c","state.c","-o","probe"]},{"argv":["./probe"]}],
)
write_json(assets/"project.json",policy)
write_json(assets/"tree.json",{"id":"adaptive-meter","children":[
    {"id":"repair","children":[{"component":key} for key in ("analysis","state","band")]},
    {"id":"release","children":[{"component":key} for key in ("testing","integration")]},
]})
