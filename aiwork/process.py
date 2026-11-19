from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryFile
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from time import monotonic

OUTPUT_LIMIT = 1024 * 1024
SAFE_ENV = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "PROGRAMFILES",
            "PROGRAMFILES(X86)", "SYSTEMDRIVE", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
            "INCLUDE", "LIB", "LIBPATH", "JAVA_HOME"}


@dataclass(frozen=True)
class Result:
    code: int
    elapsed: float
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool


def environment(root: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k.upper() in SAFE_ENV}
    env.update({
        "TEMP": str(root), "TMP": str(root), "TMPDIR": str(root),
        "HOME": str(root), "USERPROFILE": str(root),
        "APPDATA": str(root / "appdata"), "LOCALAPPDATA": str(root / "localappdata"),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1", "NO_PROXY": "127.0.0.1,localhost,::1",
    })
    for name in ("DATA", "CONFIG", "STATE", "CACHE"):
        env[f"XDG_{name}_HOME"] = str(root / name.lower())
    return env


def executable(name: str) -> str | None:
    if name == "{python}":
        return sys.executable
    match = shutil.which(name)
    if os.name == "nt" and match and Path(match).suffix.lower() not in {".exe", ".com"}:
        return None
    return match


def kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        if job := getattr(proc, "_aiwork_job", None):
            job.terminate()
            return
        try:
            subprocess.run(["taskkill.exe", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, timeout=5, check=False)
        except subprocess.SubprocessError:
            pass
        if proc.poll() is None:
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


@contextmanager
def owned_process(*args, **kwargs):
    """Start a child before any descendants can escape the owned Windows job."""
    job = None
    proc = None
    if os.name == "nt":
        from .windows_job import Job
        job = Job()
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x4  # CREATE_SUSPENDED
    else:
        kwargs.setdefault("start_new_session", True)
    try:
        proc = subprocess.Popen(*args, **kwargs)
        if job:
            proc._aiwork_job = job
            job.attach_and_resume(proc)
        yield proc
    finally:
        if job:
            job.close()
        elif proc is not None and proc.poll() is None:
            kill_tree(proc)
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def run(argv: list[str] | str, cwd: Path, timeout: float, env: dict[str, str],
        stop: Path | None = None, *, decode_errors: str = "replace",
        stdin: bytes | None = None) -> Result:
    started = monotonic()
    source = TemporaryFile() if stdin is not None else None
    try:
        if source is not None:
            source.write(stdin)
            source.seek(0)
        owner = owned_process(argv, cwd=cwd, env=env,
                                stdin=source if source is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=os.name != "nt",
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        proc = owner.__enter__()
    finally:
        if source is not None:
            source.close()

    def drain(stream, buffer: bytearray) -> None:
        with stream:
            while block := stream.read1(16384):
                buffer.extend(block[:max(0, OUTPUT_LIMIT + 1 - len(buffer))])

    buffers = [bytearray(), bytearray()]
    threads = [Thread(target=drain, args=(stream, buffer), daemon=True)
               for stream, buffer in zip((proc.stdout, proc.stderr), buffers)]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        while proc.poll() is None:
            remaining = started + timeout - monotonic()
            if remaining <= 0 or stop and stop.exists():
                raise subprocess.TimeoutExpired(argv, timeout)
            try:
                proc.wait(timeout=min(0.25, remaining))
            except subprocess.TimeoutExpired:
                continue
        for thread in threads:
            thread.join(timeout=max(0, started + timeout - monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
    except KeyboardInterrupt:
        kill_tree(proc)
        proc.wait(timeout=5)
        raise
    finally:
        if proc.poll() is None or any(thread.is_alive() for thread in threads):
            timed_out = True
            kill_tree(proc)
            proc.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=1)
        owner.__exit__(None, None, None)
    output = [bytes(b[:OUTPUT_LIMIT]).decode("utf-8", decode_errors) for b in buffers]
    return Result(proc.returncode, monotonic() - started, *output, timed_out,
                  any(len(b) > OUTPUT_LIMIT for b in buffers))
