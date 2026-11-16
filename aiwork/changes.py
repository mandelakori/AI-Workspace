from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from .process import environment, executable, run
from .schema import relative, within
from .workspace import contained, ignore, inventory


def delta(before: dict, after: dict) -> list[str]:
    return sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))


def validate_changes(changed: list[str], roots: tuple[str, ...]) -> None:
    for path in changed:
        if any(ignore(part) or part.casefold() == ".handoff" for part in relative(path).split("/")):
            raise ValueError(f"excluded changed path: {path}")
        if not within(path, roots):
            raise ValueError(f"change outside write_roots: {path}")


def checked_merge(base: Path, destination: Path, candidate: Path, names: list[str],
                  expected: dict) -> None:
    """Copy an attested delta against an expected predecessor, rejecting conflicts first."""
    current = inventory(destination)
    origin = inventory(base)
    source = inventory(candidate)
    for name in names:
        relative(name)
        if source.get(name) != expected.get(name):
            raise ValueError(f"verified artifact hash mismatch: {name}")
        if current.get(name) not in (origin.get(name), expected.get(name)):
            raise ValueError(f"integration conflict: {name}")
        path = contained(destination, name)
        if path.is_dir():
            raise ValueError(f"integration file/directory conflict: {name}")
        for parent in path.parents:
            if parent == destination:
                break
            if parent.is_file():
                raise ValueError(f"integration file/directory conflict: {name}")
    for name in names:
        path = contained(destination, name)
        if name not in source:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(contained(candidate, name), path)


def git_patch(before: Path, after: Path, changed: list[str], root: Path) -> str:
    """Use an isolated Git index to emit an applyable diff with original relative paths."""
    git = executable("git")
    if not git:
        raise ValueError("Git is required for engineering patch artifacts")
    root.mkdir(parents=True, exist_ok=False)
    work = root / "repo"
    work.mkdir()
    env = environment(root / "git-user")
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"})

    def command(*args: str) -> str:
        result = run([git, "-c", "core.longpaths=true", "-c", "core.autocrlf=false", "-c", "core.safecrlf=false",
                      "-c", "core.hooksPath=" + os.devnull, *args], work, 20, env)
        if result.code or result.timed_out or result.truncated:
            raise ValueError(f"Git {args[0]} could not create a bounded patch: {result.stderr[-600:]}")
        return result.stdout

    command("init", "-q", "--template=")
    for name in changed:
        source = contained(before, name)
        if source.is_file():
            target = contained(work, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    command("add", "-f", "--all")
    common = command("write-tree").strip()
    for name in changed:
        target = contained(work, name)
        if target.is_file():
            target.unlink()
    # A committed file may become a directory (or vice versa) only as part of the selected delta.
    for directory in sorted((p for p in work.rglob("*") if p.is_dir() and ".git" not in p.parts),
                            key=lambda p: len(p.parts), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    for name in changed:
        source = contained(after, name)
        if source.is_file():
            target = contained(work, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    command("add", "-f", "--all")
    return command("diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
                   "--no-renames", common, "--")


def save_patch(before: Path, after: Path, changed: list[str], root: Path) -> dict:
    patch = root / "proposed.patch"
    patch.write_bytes(git_patch(before, after, changed, root / "patch-index").encode("utf-8"))
    return {"patch": str(patch), "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
