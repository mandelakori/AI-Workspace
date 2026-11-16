from __future__ import annotations

import re
import socket
import subprocess
from contextlib import contextmanager
from time import monotonic, sleep
from urllib.parse import urlsplit

from .inference import Inference
from .cloud import Lambda, Lifecycle
from .process import executable
from .schema import Config, Profile

SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=2", "-o", "ForwardAgent=no",
               "-o", "PermitLocalCommand=no", "-o", "ControlPath=none"]


def ssh_base(alias: str) -> list[str]:
    ssh = executable("ssh")
    if not ssh or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.@-]{0,159}", alias):
        raise ValueError("configure an existing SSH alias and install OpenSSH")
    return [ssh, *SSH_OPTIONS]


def ssh_probe(alias: str) -> dict:
    command = ssh_base(alias)
    answer = subprocess.run([*command, alias, "whoami; nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits"],
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=15, check=False)
    return {"ok": answer.returncode == 0, "code": answer.returncode,
            "inventory": answer.stdout.decode("utf-8", "replace")[:2000],
            "error": answer.stderr.decode("utf-8", "replace")[:1000]}


@contextmanager
def a100_session(cfg: Config, profile: Profile, *, dispatch: bool = False, timeout: float = 18):
    deadline = monotonic() + timeout
    alias = cfg.ssh.get("alias", "")
    overrides = []
    if profile.managed:
        settings = cfg.lambda_cloud
        lifecycle = Lifecycle(Lambda(settings.get("key_env", "LAMBDA_API_KEY")), settings, cfg.state)
        trust = settings.get("ssh_host_alias", "")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,149}", trust):
            raise ValueError("configure a trusted managed SSH host-key alias first")
        lookup = executable("ssh-keygen")
        enrollment = subprocess.run([lookup, "-F", trust], capture_output=True, timeout=5) if lookup else None
        if not enrollment or enrollment.returncode:
            raise ValueError("managed SSH host trust is absent from known_hosts")
        instance = lifecycle.acquire(max(0, deadline - monotonic()), allow_launch=dispatch)
        alias = f"{settings.get('ssh_user', 'ubuntu')}@{instance['ip']}"
        overrides += ["-o", f"HostKeyAlias={trust}"]
        if identity_alias := settings.get("ssh_config_alias"):
            ssh_base(identity_alias)
            overrides += ["-o", f"HostName={instance['ip']}"]
            alias = identity_alias
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
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise ValueError(f"configured local SSH tunnel port {port} is already in use")
    argv = [*ssh_base(alias), *overrides, "-o", "ExitOnForwardFailure=yes", "-N", "-T", "-L", forward, alias]
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    try:
        while monotonic() < deadline and not (cfg.state / "STOP").exists():
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
                sleep(0.4)
        else:
            raise RuntimeError("remote model failed readiness through SSH or was stopped")
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
