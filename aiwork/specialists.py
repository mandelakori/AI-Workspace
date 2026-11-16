from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict
from pathlib import Path

from .process import environment, executable, run
from .schema import Config, Task
from .workspace import contained, describe, inventory


def analyze(cfg: Config, task: Task, work: Path, attempt: Path) -> str:
    entries = describe(work, inventory(work))["binaries"]
    if len(entries) != 1:
        raise ValueError("specialist jobs require exactly one identified ELF or PE input")
    filename = next(iter(entries))
    binary = contained(work, filename)
    settings = cfg.specialists.get(task.specialist, {})
    output = {"binary": filename, "header": entries[filename],
              "strings": strings(binary), "specialist": task.specialist}
    artifact = attempt / "analysis.json"
    artifact.write_text(json.dumps(output, indent=2), encoding="utf-8")
    if task.specialist == "binary":
        return json.dumps(output)[:4500]
    env = environment(attempt / "specialist-home")
    if task.specialist == "ghidra":
        path = Path(settings.get("headless", "")).resolve()
        if not path.is_file():
            raise ValueError("set specialists.ghidra.headless to analyzeHeadless or analyzeHeadless.bat")
        script_dir = Path(__file__).parent.resolve() / "ghidra"
        function = settings.get("function", "")
        if function and not re.fullmatch(r"[a-zA-Z0-9_.$@:-]{1,100}", function):
            raise ValueError("invalid Ghidra function selector")
        if java_home := settings.get("java_home"):
            env["JAVA_HOME"] = java_home
        # Ghidra rejects any project path containing a dot-prefixed element.
        with tempfile.TemporaryDirectory(prefix="aiwork-ghidra-") as project:
            argv = [str(path), project, "analysis", "-import", str(binary), "-readOnly",
                    "-analysisTimeoutPerFile", "60", "-max-cpu", "2", "-scriptPath", str(script_dir),
                    "-postScript", "AiworkEvidence.java", *([function] if function else [])]
            if os.name == "nt" and path.suffix.lower() == ".bat":
                if any(re.search(r'["&|<>^%!\r\n]', arg) for arg in argv):
                    raise ValueError("Ghidra Windows paths contain unsupported cmd metacharacters")
                command = subprocess_batch(argv)
            else:
                command = argv
            result = run(command, work, min(100, task.timeout), env)
    else:
        if task.specialist not in {"rea", "rea-next"}:
            raise ValueError(f"unknown specialist: {task.specialist}")
        vector = settings.get("argv", [])
        if not vector or not (program := executable(vector[0])):
            raise ValueError(f"configure specialists.{task.specialist}.argv with a trusted adapter")
        command = [program, *(a.replace("{binary}", str(binary)).replace("{artifacts}", str(attempt))
                              for a in vector[1:])]
        result = run(command, work, min(100, task.timeout), env)
    (attempt / "specialist-process.json").write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    if result.code or result.timed_out or result.truncated:
        raise RuntimeError("specialist process failed; see specialist-process.json")
    if task.specialist == "ghidra":
        signals = [line for line in result.stdout.splitlines() if "AIWORK_" in line]
        if not any("AIWORK_FUNCTION" in line for line in signals):
            raise RuntimeError("Ghidra emitted no function evidence; see specialist-process.json")
        output["findings"] = signals[:128]
        before, marker, after = result.stdout.partition("AIWORK_DECOMPILE_BEGIN")
        if marker:
            output["decompilation"] = after.split("AIWORK_DECOMPILE_END", 1)[0].strip()[:6500]
    else:
        if settings.get("format") == "json":
            findings = json.loads(result.stdout)
            if not isinstance(findings, (dict, list)):
                raise ValueError("specialist did not return structured evidence")
            output["findings"] = findings
        else:
            output["findings"] = result.stdout[:8000]
    artifact.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return json.dumps({k: v for k, v in output.items() if k != "strings"})[:8000]


def subprocess_batch(argv: list[str]) -> str:
    cmd = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    return f'"{cmd}" /d /s /c "' + " ".join(f'"{arg}"' for arg in argv) + '"'


def strings(path: Path) -> list[str]:
    with path.open("rb") as stream:
        payload = stream.read(2 * 1024 * 1024)
    return [match.group()[:100].decode("ascii") for _, match in
            zip(range(80), re.finditer(rb"[ -~]{6,}", payload))]
