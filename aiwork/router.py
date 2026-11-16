from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore
from contextlib import contextmanager
from time import monotonic

from .process import environment, executable, run
from .schema import Profile, Task


@dataclass(frozen=True)
class Route:
    profile: Profile
    reason: str


def routes(task: Task, profiles: tuple[Profile, ...],
           scores: dict[str, tuple[int, int, float]]) -> list[Route]:
    eligible = [p for p in profiles if p.tools and
                (task.location == "auto" or p.location == task.location) and
                (not task.profile or p.id == task.profile)]
    preferred = "a100" if task.complexity >= 4 else "local"

    def rank(profile: Profile) -> tuple:
        passed, total, seconds = scores.get(profile.id, (0, 0, 0))
        smoothed = (passed + 1) / (total + 2)
        return (-smoothed, profile.location != preferred, seconds or float("inf"), profile.id)

    output = []
    for profile in sorted(eligible, key=rank):
        passed, total, seconds = scores.get(profile.id, (0, 0, 0))
        basis = "operator override" if task.profile or task.location != "auto" else (
            f"complexity {task.complexity} favors {preferred}; "
            f"{passed}/{total} verified prior attempts for {task.category}, mean success {seconds:.2f}s")
        output.append(Route(profile, basis))
    return output


def gpu(root: Path) -> list[dict]:
    program = executable("nvidia-smi")
    if not program:
        return []
    report = run([program, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                 root, 5, environment(root / "probe-home"))
    if report.code:
        return []
    rows = []
    for line in report.stdout.splitlines():
        try:
            name, total, free = line.split(",")
            rows.append({"name": name.strip(), "total_mib": int(total), "free_mib": int(free)})
        except ValueError:
            continue
    return rows


class Plane:
    def __init__(self, location: str, slots: int):
        self.location = location
        self.capacity = BoundedSemaphore(slots)
        self.model_slot = BoundedSemaphore(1)

    @contextmanager
    def reserve(self, profile: Profile, timeout: float):
        started = monotonic()
        if not self.capacity.acquire(timeout=timeout):
            raise TimeoutError(f"{self.location} worker queue timed out")
        exclusive = profile.memory_mib > 0 or profile.engine == "ollama"
        reserved = not exclusive or self.model_slot.acquire(timeout=max(0, timeout - (monotonic() - started)))
        try:
            if not reserved:
                raise TimeoutError(f"{self.location} model queue timed out")
            yield
        finally:
            if reserved and exclusive:
                self.model_slot.release()
            self.capacity.release()
