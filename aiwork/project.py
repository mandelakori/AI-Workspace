from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Set
from contextlib import contextmanager
from pathlib import Path

from .index import python_metadata, words
from .lock import file_lock
from .schema import relative, within
from .workspace import BUILDS, BYTE_LIMIT, FILE_LIMIT, ignore, linked

SCAN_FILES = 100_000
SCAN_BYTES = 512 * 1024 * 1024
PARSE_BYTES = 256 * 1024
PARSER = 1


def project_key(root: Path) -> str:
    return os.path.normcase(str(root.resolve()))


def sources(root: Path):
    def raise_error(error):
        raise error

    for folder, dirs, names in os.walk(root, onerror=raise_error):
        base = Path(folder)
        dirs[:] = sorted(name for name in dirs if not ignore(name) and not linked(base / name))
        for name in sorted(names):
            path = base / name
            if not ignore(name) and not linked(path) and path.is_file():
                yield path


def metadata(path: str, data: bytes | None) -> dict:
    symbols, imports = [], []
    suffix = Path(path).suffix.lower()
    if data is not None and suffix == ".py":
        symbols, imports = python_metadata(data, path)
    elif data is not None and suffix in {".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"}:
        text = data.decode("utf-8", "replace")
        symbols = re.findall(r"(?:^|\n)\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface)\s+([\w$]+)", text)
        imports = re.findall(r"""(?:from\s*|import\s*|require\(\s*)['"]([^'"]+)['"]""", text)
    return {"symbols": symbols[:32], "imports": list(dict.fromkeys(imports))[:32]}


def links(row: dict, paths: Set[str]) -> list[str]:
    source = Path(row["path"])
    result = set()
    for item in row["imports"]:
        if source.suffix == ".py":
            levels = len(item) - len(item.lstrip("."))
            module = item.lstrip(".").replace(".", "/")
            if levels:
                parent = source.parent
                for _ in range(levels - 1):
                    parent = parent.parent
                stems = [(parent / module).as_posix()]
            else:
                stems = [module, f"src/{module}"]
            candidates = [part for stem in stems for part in (stem + ".py", stem + "/__init__.py")]
        elif item.startswith("."):
            stem = os.path.normpath(source.parent / item).replace("\\", "/")
            candidates = [stem, *(stem + suffix for suffix in (".js", ".ts", ".mjs", "/index.js", "/index.ts"))]
        else:
            continue
        matches = set(candidates) & paths
        if len(matches) == 1:
            result |= matches
    result.discard(row["path"])
    return sorted(result)


class ProjectStore:
    def __init__(self, state: Path):
        self.state = state
        state.mkdir(parents=True, exist_ok=True)
        with self.db() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS blobs(
                    digest TEXT NOT NULL, language TEXT NOT NULL, parser INTEGER NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(digest, language, parser)
                );
                CREATE TABLE IF NOT EXISTS files(
                    project TEXT NOT NULL, path TEXT NOT NULL, digest TEXT NOT NULL, size INTEGER NOT NULL,
                    stage TEXT NOT NULL, language TEXT NOT NULL, PRIMARY KEY(project, path)
                );
                CREATE TABLE IF NOT EXISTS evidence(
                    job TEXT PRIMARY KEY, project TEXT NOT NULL, verdict TEXT NOT NULL,
                    path TEXT NOT NULL, expectations TEXT NOT NULL
                );
            """)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.state / "projects.sqlite3", timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def refresh(self, root: Path) -> dict:
        root = root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("project root must be a directory")
        if self.state.is_relative_to(root) and not any(
            name.casefold() == ".aiwork" for name in self.state.relative_to(root).parts
        ):
            raise ValueError("index state in a project must be under .aiwork")
        key = project_key(root)
        stage = os.urandom(8).hex()
        count = changed = parsed = scanned = 0
        with file_lock(self.state / "project-index.lock", timeout=30), self.db() as db:
            for path in sources(root):
                name = relative(path.relative_to(root).as_posix())
                size = path.stat().st_size
                scanned += size
                count += 1
                if count > SCAN_FILES or scanned > SCAN_BYTES:
                    raise ValueError("project scan exceeded its file or byte budget; choose a narrower root")
                payload = path.read_bytes() if size <= PARSE_BYTES else None
                if payload is None:
                    with path.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                else:
                    digest = hashlib.sha256(payload).hexdigest()
                suffix = path.suffix.lower()
                cached = db.execute("SELECT digest FROM files WHERE project=? AND path=?", (key, name)).fetchone()
                changed += cached is None or cached["digest"] != digest
                if db.execute("SELECT 1 FROM blobs WHERE digest=? AND language=? AND parser=?",
                              (digest, suffix, PARSER)).fetchone() is None:
                    db.execute("INSERT INTO blobs VALUES(?,?,?,?)",
                               (digest, suffix, PARSER, json.dumps(metadata(name, payload))))
                    parsed += 1
                db.execute("INSERT INTO files VALUES(?,?,?,?,?,?) ON CONFLICT(project,path) DO UPDATE SET "
                           "digest=excluded.digest,size=excluded.size,stage=excluded.stage,language=excluded.language",
                           (key, name, digest, size, stage, suffix))
            removed = db.execute("DELETE FROM files WHERE project=? AND stage<>?", (key, stage)).rowcount
        return {"project": key, "files": count, "updated": changed, "removed": removed,
                "new_metadata": parsed, "bytes_hashed": scanned}

    def rows(self, root: Path) -> list[dict]:
        with self.db() as db:
            rows = db.execute("""
                SELECT f.path,f.digest,f.size,b.payload FROM files AS f JOIN blobs AS b
                ON f.digest=b.digest AND f.language=b.language AND b.parser=?
                WHERE f.project=? ORDER BY f.path
            """, (PARSER, project_key(root)))
            return [{**json.loads(row["payload"]), "path": row["path"],
                     "sha256": row["digest"], "bytes": row["size"]} for row in rows]

    def focus(self, root: Path, query: str, limit: int, scopes: tuple[str, ...] = ()) -> dict:
        rows = self.rows(root)
        entries = {row["path"]: row for row in rows}
        terms = words(query)
        selected = []
        seen = set()
        size = 0

        def include(name):
            nonlocal size
            entry = entries[name]
            if name in seen or size + entry["bytes"] > BYTE_LIMIT or len(selected) >= min(limit, FILE_LIMIT):
                return
            selected.append({**entry, "depends_on": links(entry, entries.keys())})
            seen.add(name)
            size += entry["bytes"]

        def rank(entry):
            name = entry["path"]
            return (-(9 * len(terms & words(name))
                      + 4 * len(terms & words(" ".join(entry["imports"] + entry["symbols"])))
                      + 4 * within(name, scopes) + 2 * (Path(name).name in BUILDS)), name)

        for row in sorted(rows, key=rank):
            include(row["path"])
            for name in links(row, entries.keys()):
                include(name)
            if len(selected) >= limit:
                break
        return {"inputs": [row["path"] for row in selected], "bytes": size,
                "matches": selected, "indexed_files": len(rows)}

    def record(self, job: str, project: Path, verdict: str, path: Path, expectations: dict) -> None:
        with self.db() as db:
            db.execute("INSERT INTO evidence VALUES(?,?,?,?,?) ON CONFLICT(job) DO NOTHING",
                       (job, project_key(project), verdict, str(path), json.dumps(expectations)))

    def recall(self, root: Path) -> list[dict]:
        current = {row["path"]: row["sha256"] for row in self.rows(root)}
        with self.db() as db:
            records = db.execute("SELECT * FROM evidence WHERE project=? ORDER BY rowid DESC LIMIT 50",
                                 (project_key(root),)).fetchall()
        return [{"job": r["job"], "verdict": r["verdict"], "evidence": r["path"],
                 "matches_index": all(current.get(path) == digest
                                      for path, digest in json.loads(r["expectations"]).items())} for r in records]
