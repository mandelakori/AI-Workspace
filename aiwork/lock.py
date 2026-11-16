from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, sleep


@contextmanager
def file_lock(path: Path, timeout: float = 0):
    deadline = monotonic() + timeout
    with path.open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"\x00")
            handle.flush()
        handle.seek(0)
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if monotonic() >= deadline:
                    raise TimeoutError(f"resource is busy: {path.name}") from None
                sleep(0.15)
        yield
