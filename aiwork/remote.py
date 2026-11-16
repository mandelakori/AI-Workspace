from __future__ import annotations

import re
import subprocess
from contextlib import contextmanager
from time import monotonic, sleep
from urllib.parse import urlsplit

from .inference import Inference
from .process import executable
from .schema import Config, Profile

SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=2"]


def ssh_base(alias: str) -> list[str]:
    ssh = executable("ssh")
    if not ssh or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.@-]{0,159}", alias):
        raise ValueError("configure an existing SSH alias and install OpenSSH")
    return [ssh, *SSH_OPTIONS]


def ssh_probe(alias: str) -> dict:
    command = ["ssh"]  # Keep the user's Windows OpenSSH configuration and known_hosts.
    command = ssh_base(alias)
    answer = subprocess.run([*command, alias, "whoami; nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits"],
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=15, check=False)
    return {"ok": answer.returncode == 0, "code": answer.returncode,
            "inventory": answer.stdout.decode("utf-8", "replace")[:2000],
            "error": answer.stderr.decode("utf-8", "replace")[:1000]}


@contextmanager
def a100_session(cfg: Config, profile: Profile):
    alias = cfg.ssh.get("alias", "")
    if not alias:
        yield
        return
    port = urlsplit(profile.endpoint).port
    remote_port = cfg.ssh.get("remote_port", 18080)
    if type(remote_port) is not int or not 1 <= remote_port <= 65535 or not port:
        raise ValueError("configure explicit valid tunnel ports")
    if urlsplit(profile.endpoint).hostname != "127.0.0.1":
        raise ValueError("tunneled profiles must address 127.0.0.1")
    forward = f"127.0.0.1:{port}:127.0.0.1:{remote_port}"
    argv = [*ssh_base(alias), "-o", "ExitOnForwardFailure=yes", "-N", "-T", "-L", forward, alias]
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    try:
        deadline = monotonic() + 18
        while True:
            if proc.poll() is not None:
                message = proc.stderr.read(1500).decode("utf-8", "replace")
                raise RuntimeError(f"SSH forwarding failed: {message.strip()}")
            try:
                Inference(profile).ready()
                # Give OpenSSH time to report a bind failure before trusting the listener.
                sleep(0.2)
                if proc.poll() is None:
                    break
            except (OSError, RuntimeError, ValueError):
                if monotonic() >= deadline:
                    raise RuntimeError("remote model failed readiness through SSH")
                sleep(0.4)
        yield
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        proc.stderr.close()
