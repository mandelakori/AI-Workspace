"""Stage the ledger components using a previously verified public native run."""
from pathlib import Path
import json
import re
import shutil
import sys
from aiwork.workspace import inventory
from unit_context import unit_context

root, native = map(Path, sys.argv[1:3])
source_only = sys.argv[3:] == ["--source"]
root.mkdir(parents=True, exist_ok=False)
assets = Path(__file__).resolve().parent
for file in (assets / "ledger").iterdir():
    if file.is_file():
        shutil.copyfile(file, root / file.name)
shutil.copyfile(assets / "verify_public.py", root / "verify_public.py")
stage = native / "candidate"
reference = json.loads((native / "run.json").read_bytes())
notes = json.loads((stage / "ghidra-00.json").read_bytes())
observations = json.loads((stage / "examples.json").read_bytes())
canonical = [{key: row[key] for key in ("stdin", "argv", "code", "stdout", "stderr")} for row in observations]
if (canonical != json.loads((native / "development/cases.json").read_bytes()) or
        inventory(native / "target") != reference["target"] or
        inventory(native / "development") != reference["development"]):
    raise ValueError("archived ledger public evidence or reference changed")
digest = next(iter(reference["target"].values()))["sha256"]
public_strings = sorted({item for item in notes["strings"] if item in
                         {"show", "take", "reset", "error", "denied", "fgets", "printf", "strcmp"}})

def save(name, value):
    (root / name).write_text(json.dumps(value, indent=2), encoding="utf-8")

save("observations.json", observations)
save("static.json", {"target_sha256": digest,
     "framing": {"format": notes["header"]["format"],
                 "calls": re.findall(r"fgets\([^\n]{0,100}", notes["decompilation"])[:1]},
     "syntax": {"tokens": public_strings}, "balance": {"tokens": public_strings},
     "output": {"tokens": public_strings}})
save("evidence-map.json", {
    "framing": ["fits-buffer", "show-eof", "split-at-buffer"],
    "syntax": ["show-garbage", "reset-garbage", "extra-after-take", "tabbed-args", "blank-whitespace"],
    "balance": ["range-and-state", "cap-and-state"], "output": ["example-1", "example-2", "blank-after-add"],
})

interfaces = {
    "framing": "Implement int read_chunk(FILE *input, char chunk[LINE_CAPACITY]) in framing.c. One call returns 1 for one chunk of at most 95 bytes including a newline when present, terminated by NUL. A final nonempty chunk at EOF is valid. Return 0 when no bytes remain. Do not parse or print.",
    "syntax": "Implement Command parse_chunk(const char *chunk) in syntax.c. Recognize case-sensitive word tokens add, take, show, reset. Blank C whitespace is SKIP. Add and take require exactly one signed decimal integer token; carry its numeric value (range validation belongs to balance). Show and reset take zero operands. Any other or surplus non-whitespace token is BAD. No state, I/O or side effects.",
    "balance": "Implement Reply apply_command(int *balance, Command command) in balance.c. The balance starts at zero and stays 0..10000 inclusive. ADD/TAKE take amounts 0..1000 inclusive; other amounts or BAD mean ERROR and keep the balance. Arithmetic outside the balance range returns DENIED and keeps it. Successful changes return VALUE with the new balance. RESET returns VALUE 0. SHOW returns the current VALUE. SKIP returns QUIET unchanged. No I/O.",
    "output": "Implement void write_reply(FILE *output, Reply reply) in output.c. QUIET emits nothing. ERROR emits error then newline. DENIED emits denied then newline. VALUE emits the signed decimal value and newline. Always write to the supplied stream.",
}
def node(role, interface, inputs, outputs, args, needs=(), imports=None, timeout=80):
    row = {"role": role, "interface": interface, "inputs": inputs, "outputs": outputs,
           "checks": [{"argv": ["{python}", "verify_public.py", *args], "timeout": 25}],
           "needs": list(needs), "timeout": timeout}
    if imports is not None:
        row["imports"] = imports
    return row

parts = list(interfaces)
nodes = {"analysis": node("analysis", "Pair bounded static evidence with public executable observations.",
         ["verify_public.py", "observations.json", "static.json", "evidence-map.json"],
         [f"{key}.json" for key in parts], ["analysis"], timeout=45)}
for key, contract in interfaces.items():
    nodes[key] = node("implementation", contract, ["verify_public.py", "contract.h", "checks.c"],
                      [f"{key}.c"], ["component", key], ["analysis"], {"analysis": [f"{key}.json"]}, timeout=105)
    if source_only:
        public_assertions = unit_context(root, key)
        nodes[key]["inputs"].append(public_assertions)
        nodes[key]["source_context"] = ["contract.h", public_assertions]
nodes["testing"] = node("testing", "Link only independently verified component sources and compare all public behavior.",
    ["verify_public.py", "observations.json", "contract.h", "main.c"], ["tested"],
    ["test", *parts], parts, timeout=45)
nodes["integration"] = node("integration", "Publish the verified integrated executable and replay the public corpus.",
    ["verify_public.py", "observations.json"], ["candidate"], ["integrate"], ["testing"], timeout=45)
save("project.json", {"workspace": ".", "components": nodes, "max_attempts": 2})
