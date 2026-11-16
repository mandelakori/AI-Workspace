from __future__ import annotations

import os
import re
import sys
from uuid import uuid4
from dataclasses import asdict
from pathlib import Path
from time import monotonic

from .process import environment, executable, run
from .schema import Check
from .workspace import contained


def runner_status(root: Path, image: str) -> dict:
    docker = executable("docker")
    if not docker:
        return {"available": False, "image": image, "reason": "Docker CLI unavailable"}
    env = os.environ.copy()
    version = run([docker, "version", "--format", "{{.Server.Os}} {{.Server.Version}}"], root, 4, env)
    available = version.code == 0 and not version.timed_out and version.stdout.startswith("linux ")
    present = None
    if available and image:
        result = run([docker, "image", "inspect", "--format", "{{.Id}}", image], root, 4, env)
        present = result.code == 0 and not result.timed_out
    return {"available": available, "server": version.stdout.strip(), "image": image,
            "image_present": present, "diagnostic": version.stderr[-500:]}


def pipeline(setup: tuple[Check, ...], check: Check, workspace: Path, home: Path, image: str,
             *, timeout: float, stop: Path | None = None) -> dict:
    deadline = monotonic() + timeout
    for step in (*setup, check):
        remaining = deadline - monotonic()
        if remaining <= 0:
            return {"passed": False, "timed_out": True, "stdout": "", "stderr": "pipeline deadline"}
        outcome = invoke(step, workspace, home, image, timeout=remaining, stop=stop)
        if not outcome["passed"]:
            return outcome
    return outcome


def invoke(check: Check, workspace: Path, home: Path, image: str = "", *,
           timeout: float | None = None, private: Path | None = None,
           stop: Path | None = None) -> dict:
    env = environment(home)
    working = contained(workspace, check.cwd) if check.cwd else workspace
    if not working.is_dir():
        raise ValueError(f"command working directory does not exist: {check.cwd}")
    cwd = working
    # Avoid prepending the task workspace to executable resolution.
    if image:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_./:@-]*", image):
            raise ValueError("invalid runner image reference")
        docker = executable("docker")
        if not docker:
            raise ValueError("Docker CLI unavailable")
        if any("," in str(path) for path in (workspace, private)):
            raise ValueError("Docker mount paths cannot contain commas")
        container = f"aiwork-check-{uuid4().hex}"
        argv = [docker, "run", "--name", container, "--rm", "--pull=never", "--network=none",
                "--memory=2g", "--cpus=2", "--pids-limit=96", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--read-only", "--tmpfs=/tmp:size=128m",
                "--mount", f"type=bind,src={workspace},dst=/work",
                "--workdir", "/work" + ("/" + check.cwd if check.cwd else ""),
                "--env", "PYTHONDONTWRITEBYTECODE=1"]
        if private:
            argv += ["--mount", f"type=bind,src={private},dst=/verification,readonly"]
        # Docker Desktop configuration is needed by the trusted Docker client.
        env = os.environ.copy()
        vector = ["python" if arg == "{python}" else
                  arg.replace("{verification}", "/verification") if private else arg
                  for arg in check.argv]
        argv += [image, *vector]
        cwd = workspace
    else:
        program = executable(check.argv[0])
        if not program:
            raise ValueError(f"check executable not found or not native: {check.argv[0]}")
        argv = [program, *(arg.replace("{verification}", str(private)) if private else arg
                           for arg in check.argv[1:])]
        if check.argv[0] == "{python}":
            argv = [sys.executable, "-B", *argv[1:]]
    try:
        outcome = run(argv, cwd, min(check.timeout, timeout) if timeout is not None else check.timeout,
                      env, stop)
    except KeyboardInterrupt:
        if image:
            run([docker, "rm", "-f", container], workspace, 8, env)
        raise
    if image and outcome.timed_out:
        run([docker, "rm", "-f", container], workspace, 8, env)
    return {"argv": list(check.argv), "cwd": check.cwd, "runner": image or "trusted-host",
            **asdict(outcome),
            "passed": outcome.code == 0 and not outcome.timed_out and not outcome.truncated
            and (check.stdout is None or outcome.stdout.replace("\r\n", "\n") == check.stdout)}


def classify(outcome: dict) -> str:
    if outcome.get("timed_out"):
        return "timeout"
    if outcome.get("truncated"):
        return "output_limit"
    if outcome.get("passed"):
        return "pass"
    trace = (outcome.get("stderr", "") + "\n" + outcome.get("stdout", "")).lower()
    if re.search(r"syntaxerror|compile error|fatal error [a-z0-9]+:|error\[e\d+\]|error cs\d+", trace):
        return "compile"
    if "modulenotfounderror" in trace or "no matching distribution found" in trace:
        return "dependency"
    if re.search(r"assertionerror|failed \(|failures?:|\btest failed\b", trace):
        return "tests"
    if outcome.get("code") == 0:
        return "output_mismatch"
    return "command"
