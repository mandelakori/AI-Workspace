from __future__ import annotations

import os
import re
import sys
from uuid import uuid4
from dataclasses import asdict
from pathlib import Path

from .process import environment, executable, run
from .schema import Check


def invoke(check: Check, workspace: Path, home: Path, image: str = "", *,
           timeout: float | None = None, private: Path | None = None,
           stop: Path | None = None) -> dict:
    env = environment(home)
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
                "--workdir", "/work", "--env", "PYTHONDONTWRITEBYTECODE=1"]
        if private:
            argv += ["--mount", f"type=bind,src={private},dst=/verification,readonly"]
        # Docker Desktop configuration is needed by the trusted Docker client.
        env = os.environ.copy()
        vector = ["python" if arg == "{python}" else
                  arg.replace("{verification}", "/verification") if private else arg
                  for arg in check.argv]
        argv += [image, *vector]
    else:
        program = executable(check.argv[0])
        if not program:
            raise ValueError(f"check executable not found or not native: {check.argv[0]}")
        argv = [program, *(arg.replace("{verification}", str(private)) if private else arg
                           for arg in check.argv[1:])]
        if check.argv[0] == "{python}":
            argv = [sys.executable, "-B", *argv[1:]]
    try:
        outcome = run(argv, workspace, min(check.timeout, timeout) if timeout is not None else check.timeout,
                      env, stop)
    except KeyboardInterrupt:
        if image:
            run([docker, "rm", "-f", container], workspace, 8, env)
        raise
    if image and outcome.timed_out:
        run([docker, "rm", "-f", container], workspace, 8, env)
    return {"argv": list(check.argv), **asdict(outcome),
            "passed": outcome.code == 0 and not outcome.timed_out and not outcome.truncated
            and (check.stdout is None or outcome.stdout.replace("\r\n", "\n") == check.stdout)}
