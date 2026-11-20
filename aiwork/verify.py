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
    image_id = None
    if available and image:
        result = run([docker, "image", "inspect", "--format", "{{.Id}}", image], root, 4, env)
        present = result.code == 0 and not result.timed_out
        image_id = result.stdout.strip() if present else None
    return {"available": available, "server": version.stdout.strip(), "image": image,
            "image_present": present, "image_id": image_id, "diagnostic": version.stderr[-500:]}


def pipeline(setup: tuple[Check, ...], check: Check, workspace: Path, home: Path, image: str,
             *, timeout: float, stop: Path | None = None, trial: dict | None = None) -> dict:
    deadline = monotonic() + timeout
    for step in (*setup, check):
        remaining = deadline - monotonic()
        if remaining <= 0:
            return {"passed": False, "timed_out": True, "stdout": "", "stderr": "pipeline deadline"}
        options = {"trial": trial} if trial else {}
        outcome = invoke(step, workspace, home, image, timeout=remaining, stop=stop, **options)
        if not outcome["passed"]:
            return outcome
    return outcome


def invoke(check: Check, workspace: Path, home: Path, image: str = "", *,
           timeout: float | None = None, private: Path | None = None,
           stop: Path | None = None, stdin: bytes | None = None, sealed: bool = False,
           extra_args: tuple[str, ...] = (), trial: dict | None = None) -> dict:
    from .trial_budget import current, public_limit
    active = current()
    if active and active["phase"] == "warm":
        raise ValueError("warm phase cannot launch verification commands or containers")
    trial = trial or public_limit()
    if trial:
        from time import time
        if (set(trial) != {"label", "deadline"}
                or not re.fullmatch(r"aiwork-trial-[a-f0-9]{32}", trial["label"])):
            raise ValueError("invalid measured verifier lease")
        remaining = trial["deadline"] - time()
        if remaining <= 0:
            raise ValueError("measured verification deadline exhausted")
        timeout = min(timeout if timeout is not None else check.timeout, remaining)
    if check.oracle or sealed and (not image or private):
        raise ValueError("sealed candidate runs require Docker and no private mounts")
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
                "--mount", f"type=bind,src={workspace},dst=/work" + (",readonly" if sealed else ""),
                "--workdir", "/work" + ("/" + check.cwd if check.cwd else ""),
                "--env", "PYTHONDONTWRITEBYTECODE=1"]
        if stdin is not None:
            argv.append("-i")
        if private:
            argv += ["--mount", f"type=bind,src={private},dst=/verification,readonly"]
        # Docker Desktop configuration is needed by the trusted Docker client.
        env = os.environ.copy()
        vector = ["python" if arg == "{python}" else
                  arg.replace("{verification}", "/verification") if private else arg
                  for arg in check.argv]
        if trial:
            argv += ["--label", "aiwork.trial=" + trial["label"]]
            # The daemon's container has its own absolute-deadline watchdog, even if its CLI dies.
            watchdog = ("import os,sys,time; left=float(sys.argv[1])-time.time(); "
                        "sys.exit(124) if left<=0 else None; "
                        "os.execvp('timeout',['timeout','--signal=KILL',str(left),*sys.argv[2:]])")
            vector = ["python", "-I", "-c", watchdog, str(trial["deadline"]), *vector]
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
        vector = [*argv, *extra_args]
        outcome = run(vector, cwd, min(check.timeout, timeout) if timeout is not None else check.timeout,
                      env, stop, stdin=stdin, decode_errors="surrogateescape" if sealed else "replace")
    except KeyboardInterrupt:
        if image:
            run([docker, "rm", "-f", container], workspace, 8, env)
        raise
    if image and outcome.timed_out:
        run([docker, "rm", "-f", container], workspace, 8, env)
    return {"argv": [*check.argv, *extra_args], "cwd": check.cwd, "runner": image or "trusted-host",
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
