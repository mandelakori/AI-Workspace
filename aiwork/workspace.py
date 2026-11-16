from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
from pathlib import Path

FILE_LIMIT = 5000
BYTE_LIMIT = 64 * 1024 * 1024
SKIP = {".git", ".aiwork", ".venv", "node_modules", "__pycache__", ".opencode",
        "opencode.json", "opencode.jsonc", ".ssh", ".aws", ".codex", ".agents",
        ".env", ".hg", ".svn", ".github", ".pytest_cache"}
LANGUAGES = {".py": "Python", ".rs": "Rust", ".js": "JavaScript", ".ts": "TypeScript",
             ".c": "C", ".h": "C header", ".cpp": "C++", ".cs": "C#", ".go": "Go",
             ".java": "Java", ".ps1": "PowerShell", ".sh": "Shell"}
BUILDS = {"pyproject.toml", "requirements.txt", "package.json", "Cargo.toml",
          "CMakeLists.txt", "Makefile", "go.mod", "pom.xml"}


def linked(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def contained(root: Path, value: str) -> Path:
    from .schema import relative

    path = root
    for name in relative(value).split("/"):
        path = path / name
        try:
            unsafe = linked(path)
        except FileNotFoundError:
            continue
        if unsafe:
            raise ValueError(f"linked path is outside the file policy: {value}")
    return path


def ignore(name: str) -> bool:
    return (name.casefold() in SKIP or name.casefold().startswith(".env.") or
            Path(name).suffix.lower() in {".pem", ".key", ".pfx"})


def files(root: Path, *, exclude: bool = True):
    def fail(exc: OSError) -> None:
        raise exc

    for directory, dirs, leaves in os.walk(root, onerror=fail):
        base = Path(directory)
        dirs[:] = sorted(name for name in dirs if not exclude or not ignore(name))
        for name in dirs:
            if linked(base / name):
                raise ValueError(f"unexpected linked directory: {name}")
        for name in sorted(leaves):
            if exclude and ignore(name):
                continue
            source = base / name
            if linked(source) or not source.is_file():
                raise ValueError(f"unexpected nonregular file: {source.relative_to(root)}")
            yield source


def snapshot(source: Path, target: Path, inputs: tuple[str, ...]) -> dict[str, dict]:
    target.mkdir(parents=True, exist_ok=False)
    roots = [contained(source, i) for i in inputs] if inputs else [source]
    paths = (p for root in roots for p in (files(root) if root.is_dir() else (root,)))
    seen: set[str] = set()
    total = 0
    for path in paths:
        name = path.relative_to(source).as_posix()
        if any(ignore(part) for part in Path(name).parts):
            raise ValueError(f"excluded input: {name}")
        if name in seen:
            continue
        if linked(path) or not path.is_file():
            raise ValueError(f"invalid input: {name}")
        total += path.stat().st_size
        if len(seen) >= FILE_LIMIT or total > BYTE_LIMIT:
            raise ValueError("snapshot exceeds file or byte limit")
        seen.add(name)
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    return inventory(target)


def inventory(root: Path) -> dict[str, dict]:
    result = {}
    total = 0
    for path in files(root, exclude=False):
        size = path.stat().st_size
        total += size
        if len(result) >= FILE_LIMIT or total > BYTE_LIMIT:
            raise ValueError("inventory exceeds file or byte limit")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        result[path.relative_to(root).as_posix()] = {"bytes": size, "sha256": digest}
    return result


def describe(root: Path, entries: dict[str, dict]) -> dict:
    result = {"files": len(entries), "bytes": sum(e["bytes"] for e in entries.values()),
              "languages": sorted({LANGUAGES[Path(p).suffix] for p in entries if Path(p).suffix in LANGUAGES}),
              "build_files": [p for p in entries if Path(p).name in BUILDS][:40],
              "candidate_tests": [p for p in entries if re.search(r"(^|/)(tests?/|test_)", p)][:40],
              "binaries": {}}
    for name in entries:
        with (root / name).open("rb") as stream:
            head = stream.read(64)
            if head.startswith(b"\x7fELF") and len(head) >= 20:
                endian = "little" if head[5] == 1 else "big"
                result["binaries"][name] = {
                    "format": "ELF", "class": {1: 32, 2: 64}.get(head[4]),
                    "machine": int.from_bytes(head[18:20], endian),
                }
            elif head.startswith(b"MZ") and len(head) == 64:
                offset = int.from_bytes(head[60:64], "little")
                stream.seek(offset)
                pe = stream.read(6)
                if pe.startswith(b"PE\0\0") and len(pe) == 6:
                    result["binaries"][name] = {
                        "format": "PE", "machine": int.from_bytes(pe[4:6], "little"),
                    }
        if len(result["binaries"]) >= 20:
            break
    return result
