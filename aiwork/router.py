from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from contextlib import ExitStack, contextmanager
from time import monotonic, sleep

from .process import environment, executable, run
from .lock import file_lock
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
    def __init__(self, location: str, slots: int, state: Path):
        self.location = location
        self.slots = slots
        self.state = state

    @contextmanager
    def reserve(self, profile: Profile, timeout: float):
        deadline = monotonic() + timeout
        exclusive = profile.memory_mib > 0 or profile.engine == "ollama" or self.location == "a100"
        with ExitStack() as locks:
            while monotonic() < deadline and not (self.state / "STOP").exists():
                for slot in range(1 if exclusive else self.slots):
                    try:
                        locks.enter_context(file_lock(self.state / f"{self.location}-{slot}.lock"))
                    except TimeoutError:
                        continue
                    yield
                    return
                sleep(0.2)
        raise TimeoutError(f"{self.location} worker queue timed out or was stopped")
