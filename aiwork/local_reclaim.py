"""Opt-in graceful eviction from one reviewed local Ollama service."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
from time import monotonic, sleep

from .local_runtime import listener_owner, local_json
from .process import environment, run
from .schema import IdleOllama
from .trial_budget import write


REVIEWED_VERSION = '0.40.17'
RECLAIM_SECONDS = 8
RECHECK_RESERVE_SECONDS = 5


def listener_identity(endpoint: str) -> tuple[int, int, Path]:
    if os.name != 'nt':
        raise RuntimeError('external Ollama ownership verification requires Windows')
    pid = listener_owner(int(endpoint.rsplit(':', 1)[1]))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                  ctypes.POINTER(wintypes.DWORD))
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, *(ctypes.POINTER(wintypes.FILETIME),)*4)
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        image = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(image))
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)) or not kernel.GetProcessTimes(
                handle, *(ctypes.byref(value) for value in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        launched = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return pid, launched, Path(image.value).resolve(strict=True)
    finally:
        kernel.CloseHandle(handle)


def exact_model(rows: list, policy: IdleOllama) -> bool:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('invalid Ollama inventory')
    matches = [row for row in rows if row.get('name') == policy.model or row.get('model') == policy.model]
    if not matches:
        return False
    if (len(matches) != 1 or matches[0].get('digest') != policy.model_sha256
            or matches[0].get('remote_host') or matches[0].get('remote_model')):
        raise ValueError('enrolled Ollama model identity changed')
    return True


def unload_idle(policy: IdleOllama) -> dict:
    policy.validate()
    endpoint = policy.endpoint
    identity = listener_identity(endpoint)
    path = identity[2]
    if path != Path(policy.executable).resolve(strict=True):
        raise ValueError('enrolled Ollama listener executable changed')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != policy.executable_sha256:
            raise ValueError('enrolled Ollama executable hash changed')
    if local_json(endpoint, 'api/version', timeout=1).get('version') != REVIEWED_VERSION:
        raise ValueError('Ollama version lacks reviewed idle unload semantics')
    if not exact_model(local_json(endpoint, 'api/ps', timeout=1)['models'], policy):
        return {'status': 'not_resident', 'posts': 0}
    if not exact_model(local_json(endpoint, 'api/tags', timeout=1)['models'], policy):
        raise ValueError('enrolled Ollama model absent from installed inventory')
    if listener_identity(endpoint) != identity:
        raise ValueError('enrolled Ollama listener identity changed before unload')
    # The reviewed scheduler handles the idle check under its runner reference lock.
    # An active runner expires after its last request, without interrupting clients.
    ack = local_json(endpoint, 'api/generate', {'model': policy.model, 'keep_alive': 0, 'stream': False}, timeout=1)
    if ack.get('done') is not True or ack.get('done_reason') != 'unload' or ack.get('model') != policy.model:
        raise RuntimeError('Ollama did not acknowledge the scoped idle unload')
    for attempt in range(3):
        if attempt:
            sleep(.25)
        if listener_identity(endpoint) != identity:
            raise ValueError('enrolled Ollama listener identity changed after unload')
        if not exact_model(local_json(endpoint, 'api/ps', timeout=1)['models'], policy):
            return {'status': 'unloaded', 'posts': 1}
    return {'status': 'still_resident', 'posts': 1}


def reclaim_local_memory(policy: IdleOllama | None, artifacts: Path, deadline: float,
                         stop: Path | None = None) -> bool:
    """Call only while holding the exclusive local lane. Return whether to resample."""
    if policy is None:
        return False
    duration = min(RECLAIM_SECONDS, deadline - monotonic() - RECHECK_RESERVE_SECONDS)
    if duration <= 0 or stop is not None and stop.exists():
        write(artifacts/'memory-reclamation.json', {'status':'skipped_deadline_or_stop'})
        return False
    env = environment(artifacts/'reclaim-home')
    duration = min(duration, deadline - monotonic() - RECHECK_RESERVE_SECONDS)
    if duration <= 0:
        return False
    report = run([sys.executable, '-m', 'aiwork.local_reclaim'], Path(__file__).resolve().parents[1],
                 duration, env, stop, stdin=json.dumps(asdict(policy)).encode(), output_limit=8192)
    if report.timed_out:
        outcome = {'status': 'client_timed_out', 'posts': None}
    elif report.code or report.truncated:
        outcome = {'status': 'refused_or_failed', 'posts': None, 'detail': report.stderr[-600:]}
    else:
        outcome = json.loads(report.stdout)
    write(artifacts/'memory-reclamation.json', outcome | {'model':policy.model,'endpoint':policy.endpoint,
          'elapsed_seconds':report.elapsed})
    return True


if __name__ == '__main__':
    try:
        print(json.dumps(unload_idle(IdleOllama(**json.load(sys.stdin)))))
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
