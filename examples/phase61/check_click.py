"""Run deferred upstream checks on fresh baseline/candidate copies, never the freeze."""
from pathlib import Path
import json
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aiwork.controller import write_json
from aiwork.schema import Check
from aiwork.verify import invoke, runner_status
from aiwork.workspace import inventory, snapshot

root = Path(sys.argv[1]).resolve()
phase6 = Path(sys.argv[2]).resolve()
frozen = inventory(phase6 / "final-frozen")
image = runner_status(root, "aiwork-phase61-checks:local")["image_id"]
destination = root / "click-checks"
destination.mkdir(exist_ok=False)
commands = {
    "ruff": ("ruff", "check", "--no-fix", "--no-cache", "."),
    "format": ("ruff", "format", "--check", "--no-cache", "."),
    "mypy": ("mypy", "--cache-dir=/tmp/mypy"),
    "pyright": ("pyright", "--ignoreexternal", "--verifytypes", "click"),
    "sphinx": ("sphinx-build", "-E", "-W", "-b", "dirhtml", "docs", "/tmp/site"),
    "uv-lock": ("uv", "--cache-dir=/tmp/uv", "lock", "--check", "--offline"),
}
if (root / "python.inv").exists():
    commands["sphinx-cached"] = ("python", "-c",
        "from sphinx.application import Sphinx; import sys; "
        "app=Sphinx('/work/docs','/work/docs','/tmp/site','/tmp/doctrees','dirhtml',"
        "confoverrides={'intersphinx_mapping':{'python':('https://docs.python.org/3/','/work/_python.inv')}},"
        "warningiserror=True,freshenv=True); app.build(); sys.exit(app.statuscode)")
summary = {"runner": image, "checks": {}, "frozen_unchanged": False}
for variant in ("baseline", "candidate"):
    work = destination / variant
    snapshot(phase6 / "upstream-click", work, ())
    if variant == "candidate":
        for name in ("src/click/types.py", "src/click/__init__.py", "tests/test_iso_datetime.py", "docs/parameter-types.md", "docs/api.md"):
            shutil.copyfile(phase6 / "final-frozen" / name, work / name)
    if "sphinx-cached" in commands:
        shutil.copyfile(root / "python.inv", work / "_python.inv")
    summary["checks"][variant] = {}
    for name, argv in commands.items():
        outcome = invoke(Check(argv, timeout=120), work, destination / "home", image, sealed=True)
        write_json(destination / (variant + "-" + name + ".json"), outcome)
        summary["checks"][variant][name] = {key:outcome[key] for key in ("passed", "code", "elapsed", "timed_out")}
        print(variant, name, outcome["passed"], flush=True)
    assert inventory(phase6 / "final-frozen") == frozen
summary["frozen_unchanged"] = True
write_json(destination / "summary.json", summary)
