"""One-shot measured phases. Reservations survive crashes; workers cannot resume."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import subprocess
from pathlib import Path
from time import monotonic, time
from uuid import uuid4

from .lock import file_lock
from .process import executable, run

FILE = "trial-budget.json"
PHASE_LIMITS = {"warm": 20, "work": 180, "grade": 40}


def write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def create(state: Path, approval: str, arm: str, limits: dict | None = None, *, quotas: dict | None = None,
           reviewed_caps: dict | None = None) -> None:
    state.mkdir(parents=True, exist_ok=False)
    caps=PHASE_LIMITS if reviewed_caps is None else reviewed_caps
    if (set(caps)!=set(PHASE_LIMITS) or any(type(v) is not int or not 1<=v<=3600 for v in caps.values())
            or sum(caps.values())>7200):
        raise ValueError('invalid reviewed phase caps')
    limits = limits or PHASE_LIMITS
    if set(limits) != set(PHASE_LIMITS) or any(type(limits[k]) not in (int,float) or not math.isfinite(limits[k])
                                            or not 0 < limits[k] <= caps[k] for k in limits):
        raise ValueError("invalid phase allocations")
    quotas = {'sessions':2,'planner_requests':1} if quotas is None else quotas
    if (set(quotas)!={'sessions','planner_requests'} or any(type(v) is not int for v in quotas.values())
            or not 0<=quotas['sessions']<=2 or not 0<=quotas['planner_requests']<=1):
        raise ValueError('invalid measured quotas')
    write(state / FILE, {"approval": approval, "arm": arm, "sessions": 0, "planner_requests": 0,
                        'quotas':quotas,
                        **({'reviewed_phase_caps':caps} if reviewed_caps is not None else {}),
                        "phases": {key: {"limit": value, "status": "PENDING"} for key, value in limits.items()}})


def current(state: Path | None = None) -> dict | None:
    configured = os.environ.get("AIWORK_TRIAL_BUDGET")
    expected = state / FILE if state is not None else None
    if not configured:
        if expected is not None and expected.exists():
            raise ValueError("measured trial requires its active budget lease; resume is forbidden")
        return None
    path = Path(configured).resolve()
    if expected is not None and path != expected.resolve():
        raise ValueError("measured trial cannot change controller state")
    data = json.loads(path.read_bytes())
    if data.get("quarantined"):
        raise ValueError("measured trial quarantined after cancellation/cleanup failure")
    phase = data["phases"][data["active"]]
    token = os.environ.get("AIWORK_TRIAL_TOKEN", "")
    if (phase["status"] != "RUNNING" or phase["token_sha256"] != hashlib.sha256(token.encode()).hexdigest()
            or remaining(phase) <= 0):
        raise ValueError("measured phase is closed or exhausted; resume is forbidden")
    return {**phase, "file": str(path), "phase": data["active"]}


def remaining(phase: dict) -> float:
    return max(0.0, min(phase["deadline_utc"] - time(), phase["deadline_monotonic"] - monotonic()))


def timeout(seconds: float) -> float:
    active = current()
    return min(seconds, remaining(active)) if active else seconds


def public_limit() -> dict | None:
    active = current()
    return {"label": active["label"], "deadline": active["deadline_utc"]} if active else None


def inference_interrupted() -> None:
    """Do not queue another request against an unowned provider after cancellation."""
    configured = os.environ.get("AIWORK_TRIAL_BUDGET")
    if not configured:
        return
    path = Path(configured)
    with file_lock(path.with_suffix(".lock")):
        data = json.loads(path.read_bytes())
        data["quarantined"] = True
        data["quarantine_reason"] = "inference client interrupted; backend cancellation latency unverified"
        write(path, data)


def claim(kind: str, state: Path) -> None:
    if kind not in {"worker", "planner"}:
        raise ValueError("unknown measured session kind")
    active = current(state)
    if not active:
        return
    path = Path(active["file"])
    with file_lock(path.with_suffix(".lock")):
        active = current(state)
        if active["phase"] != "work":
            raise ValueError("independent grading cannot dispatch model work")
        data = json.loads(path.read_bytes())
        key = 'sessions' if kind=='worker' else 'planner_requests'
        limit = data.get('quotas',{'sessions':2,'planner_requests':1})[key]
        if data[key] >= limit:
            raise ValueError(f"measured {kind} budget exhausted")
        data[key] += 1
        write(path, data)


def cleanup_containers(label: str, cwd: Path) -> dict:
    """Remove only positively labelled containers from this phase, within 10s."""
    if not re.fullmatch(r"aiwork-trial-[a-f0-9]{32}", label):
        raise ValueError("invalid trial container label")
    docker = executable("docker")
    if not docker:
        return {"passed": False, "error": "Docker CLI unavailable"}
    deadline = monotonic() + 10
    removed = []
    def call(*args):
        if monotonic() >= deadline:
            raise TimeoutError("owned-container cancellation deadline exhausted")
        return subprocess.run([docker, *args], capture_output=True, text=True,
                              timeout=max(.01, deadline-monotonic()))
    try:
        listed = call("ps", "-aq", "--filter", f"label=aiwork.trial={label}")
        if listed.returncode:
            return {"passed": False, "error": listed.stderr[-300:]}
        for identifier in listed.stdout.split():
            if not re.fullmatch(r"[a-f0-9]{12,64}", identifier):
                raise ValueError("invalid owned container ID")
            checked = call("inspect", "--format", '{{index .Config.Labels "aiwork.trial"}}', identifier)
            if checked.returncode:
                return {"passed": False, "error": "container ownership inspection failed"}
            if checked.stdout.strip() != label:
                raise ValueError("container ownership mismatch")
            stopped = call("rm", "-f", identifier)
            if stopped.returncode:
                return {"passed": False, "error": stopped.stderr[-300:]}
            removed.append(identifier)
        final = call("ps", "-aq", "--filter", f"label=aiwork.trial={label}")
        if final.returncode or final.stdout.strip():
            return {"passed": False, "error": "owned containers remain or final ownership check failed"}
        return {"passed": True, "removed": removed}
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        return {"passed": False, "error": str(error)}


def run_phase(state: Path, phase: str, argv: list[str], cwd: Path, *, containers: bool = True) -> dict:
    """The caller must validate operator authorization before entering this API."""
    if os.environ.get("AIWORK_TRIAL_BUDGET"):
        raise ValueError("a measured phase cannot create a nested budget")
    path = state / FILE
    with file_lock(path.with_suffix(".lock")):
        data = json.loads(path.read_bytes())
        if phase not in PHASE_LIMITS or data["phases"][phase]["status"] != "PENDING":
            raise ValueError("phase already consumed; it cannot be restarted or resumed")
        predecessor = {"work": "warm", "grade": "work"}.get(phase)
        allowed = {"FINISHED", "FAILED"} if phase == "grade" else {"FINISHED"}
        if predecessor and data["phases"][predecessor]["status"] not in allowed:
            raise ValueError("phase requires its completed predecessor")
        if data.get("quarantined"):
            raise ValueError("phase cleanup failed; trial quarantined")
        token = secrets.token_hex(32)
        started = monotonic()
        limit = data["phases"][phase]["limit"]
        active = {**data["phases"][phase], "status": "RUNNING", "started_utc": time(),
                  "deadline_utc": time()+limit, "deadline_monotonic": started+limit,
                  "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                  "label": "aiwork-trial-"+uuid4().hex}
        data["active"] = phase
        data["phases"][phase] = active
        write(path, data)  # Charge/reserve the entire one-shot phase before launching anything.
    env = os.environ.copy()
    env.update(AIWORK_TRIAL_BUDGET=str(path.resolve()), AIWORK_TRIAL_TOKEN=token)
    outcome = None
    error = ""
    try:
        outcome = run(argv, cwd, max(0, active["deadline_monotonic"]-monotonic()), env,
                      output_limit=8*1024*1024)
    except BaseException as exc:
        error = str(exc)
        raise
    finally:
        execution_elapsed = monotonic()-started
        cleanup_started = monotonic()
        if phase == "warm":
            cleanup = {"passed": True, "not_applicable": "warm phase forbids verification containers"}
        else:
            cleanup = cleanup_containers(active["label"], cwd) if containers else {"passed": True, "not_used": True}
        with file_lock(path.with_suffix(".lock")):
            data = json.loads(path.read_bytes())
            entry = data["phases"][phase]
            entry.update(status="FINISHED" if outcome and outcome.code == 0 and not outcome.timed_out else "FAILED",
                         finished_utc=time(),
                         execution_elapsed_with_termination=round(execution_elapsed, 6),
                         cancellation_cleanup_seconds=round(monotonic()-cleanup_started, 6), error=error,
                         timed_out=outcome.timed_out if outcome else True, cleanup=cleanup)
            data["quarantined"] = (data.get("quarantined", False) or not cleanup["passed"]
                                   or bool(phase in {"warm", "work"} and (outcome is None or outcome.timed_out)))
            write(path, data)
    return {"phase": phase, "code": outcome.code, "elapsed": outcome.elapsed,
            "timed_out": outcome.timed_out, "stdout": outcome.stdout, "stderr": outcome.stderr,
            "cleanup": cleanup}
