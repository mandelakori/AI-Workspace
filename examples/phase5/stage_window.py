"""Stage a new window-counter reference and public component checks."""
from dataclasses import asdict
from pathlib import Path
import json
import shutil
import sys

from aiwork.controller import Controller, write_json
from aiwork.native import pin_runner, probe, read_inputs, returned
from aiwork.schema import Check, Config
from aiwork.verify import invoke
from aiwork.workspace import inventory
from unit_context import unit_context

config, staging = map(Path, sys.argv[1:3])
source_only = "--source" in sys.argv[3:]
fixture = "meter" if "--meter" in sys.argv[3:] else "window"
staging = staging.resolve()
staging.mkdir(parents=True)
controller = Controller(Config.load(config))
image = pin_runner(controller)
assets = Path(__file__).resolve().parent
folder = assets / fixture
workspace = staging / "public"
workspace.mkdir()
target = staging / "target"
target.mkdir()
build = Check(("gcc", "-std=c11", "-O0", "-fno-inline", "reference.c", "-o", "reference.elf"))
ref = Check(("./reference.elf",), 12)
shutil.copyfile(folder / "reference.c", target / "reference.c")
compiled = invoke(build, target, staging / "home", image)
write_json(staging / "build.json", compiled)
if not compiled["passed"]:
    raise ValueError("reference build failed; inspect build.json")
(target / "reference.c").unlink()
rows = []
for case in read_inputs(folder / "development.json", 32):
    result = probe(ref, case, target, staging / "home", image, controller.config.state / "STOP")
    if not returned(result):
        raise ValueError(f"reference observation failed: {case.name}")
    rows.append({**asdict(case), **{key: result[key] for key in ("code", "stdout", "stderr")}})
public = staging / "development"
public.mkdir()
write_json(public / "cases.json", [{key: row[key] for key in ("stdin", "argv", "code", "stdout", "stderr")}
                                  for row in rows])
write_json(staging / "run.json", {
    "target": inventory(target), "image": image, "reference": asdict(ref),
    "candidate": asdict(Check(("./candidate",), 12)), "development": inventory(public)
})
for name in ("contract.h", "checks.c", "main.c"):
    shutil.copyfile(folder / name, workspace / name)
shutil.copyfile(assets / "verify_public.py", workspace / "verify_public.py")
write_json(workspace / "observations.json", rows)
write_json(workspace / "static.json", {"target_sha256": inventory(target)["reference.elf"]["sha256"],
                                     "syntax": {"format": "ELF"}})
window_evidence = {"syntax": ["args", "amount", "leading"], "state": ["overflow", "edge"]}
meter_evidence = {"state": ["under", "sat"], "band": ["bands", "zero"]}
evidence = meter_evidence if fixture == "meter" else window_evidence
write_json(workspace / "evidence-map.json", evidence)

def node(role, interface, inputs, outputs, args, needs=(), imports=None, timeout=45):
    row = {"role": role, "interface": interface, "inputs": inputs, "outputs": outputs,
           "checks": [{"argv": ["{python}", "verify_public.py", *args], "timeout": 25}],
           "needs": list(needs), "timeout": timeout}
    if imports:
        row["imports"] = imports
    return row

nodes = {"analysis": node("analysis", "Pair the staged executable identity with selected public observations.",
    ["verify_public.py", "observations.json", "static.json", "evidence-map.json"],
    [f"{key}.json" for key in evidence], ["analysis"])}
contracts = {
    "syntax": "Implement Input parse_window(const char *text) in syntax.c. C whitespace with no tokens yields BLANK. A separate + or - verb needs one signed decimal amount in 0..50. A separate ? verb takes no operands. All other text or surplus tokens yield BAD. Use exact token boundaries. No state or output.",
    "state": "Implement Effect step_window(int *state, Input input) in state.c. BLANK means SILENT. BAD means INVALID. QUERY returns NUMBER with current state. PLUS and MINUS apply their amount to state. If new state would fall outside 0..99, keep state and return LIMIT. Otherwise set state and return NUMBER with it. No output."
}
if fixture == "meter":
    contracts = {
        "state": "Write state.c defining int meter_step(int state, int delta). Return state plus delta, saturated to the inclusive range 0 to 9. Neither input is modified and there is no I/O.",
        "band": "Write band.c defining char meter_band(int state). Return the character L for state 0 through 2, M for state 3 through 6, and H for state 7 through 9. No I/O.",
    }
parts = list(contracts)
for key, text in contracts.items():
    nodes[key] = node("implementation", text, ["verify_public.py", "contract.h", "checks.c"],
                      [f"{key}.c"], ["component", key], ["analysis"], {"analysis": [f"{key}.json"]}, 100)
    if source_only:
        public_assertions = unit_context(workspace, key)
        nodes[key]["inputs"].append(public_assertions)
        nodes[key]["source_context"] = ["contract.h", public_assertions]
nodes["testing"] = node("testing", "Compile verified files together and replay the full public corpus.",
    ["verify_public.py", "observations.json", "contract.h", "main.c"], ["tested"], ["test", *parts], parts)
nodes["integration"] = node("integration", "Export the linked candidate after independently replaying the public corpus.",
    ["verify_public.py", "observations.json"], ["candidate"], ["integrate"], ["testing"])
write_json(workspace / "project.json", {"workspace": ".", "components": nodes, "max_attempts": 2})
