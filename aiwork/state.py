from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


class State:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, spec TEXT NOT NULL, category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued', trusted INTEGER NOT NULL,
                    created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, detail TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    job TEXT NOT NULL, n INTEGER NOT NULL, profile TEXT NOT NULL,
                    status TEXT NOT NULL, elapsed REAL NOT NULL, evidence TEXT NOT NULL,
                    PRIMARY KEY(job, n)
                );
            """)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.root / "state.sqlite3", timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def submit(self, category: str, trusted: bool, prepare) -> str:
        job = uuid4().hex
        spec = self.root / "runs" / job / "task.toml"
        prepare(spec)
        with self.db() as db:
            db.execute("INSERT INTO jobs(id,spec,category,trusted) VALUES(?,?,?,?)",
                       (job, str(spec), category, trusted))
        return job

    def claim(self, job: str | None = None) -> dict | None:
        with self.db() as db:
            row = db.execute(
                """UPDATE jobs SET status='running', updated=CURRENT_TIMESTAMP
                   WHERE id=(SELECT id FROM jobs WHERE status='queued'
                   AND (? IS NULL OR id=?) ORDER BY created, rowid LIMIT 1)
                   RETURNING *""", (job, job)).fetchone()
        return dict(row) if row else None

    def finish(self, job: str, status: str, detail: str) -> None:
        with self.db() as db:
            db.execute("UPDATE jobs SET status=?, detail=?, updated=CURRENT_TIMESTAMP WHERE id=?",
                       (status, detail, job))

    def resume(self, job: str, interrupted: bool) -> None:
        with self.db() as db:
            row = db.execute("UPDATE jobs SET status='queued', updated=CURRENT_TIMESTAMP "
                             "WHERE id=? AND (status IN ('blocked','partial','failed') "
                             "OR (status='running' AND ?)) RETURNING id", (job, interrupted)).fetchone()
        if not row:
            raise ValueError("job cannot be resumed from its current state")

    def jobs(self, job: str | None = None) -> list[dict]:
        with self.db() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM jobs WHERE (? IS NULL OR id=?) ORDER BY created DESC,rowid DESC LIMIT 100",
                (job, job))]

    def attempts(self, job: str) -> list[dict]:
        with self.db() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM attempts WHERE job=? ORDER BY n", (job,))]

    def record(self, job: str, n: int, profile: str, result: dict) -> None:
        with self.db() as db:
            db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,?)",
                       (job, n, profile, result["status"], result["elapsed"], json.dumps(result)))

    def scores(self, category: str) -> dict[str, tuple[int, int, float]]:
        with self.db() as db:
            rows = db.execute("""
                SELECT profile, SUM(a.status='verified') AS passed, COUNT(*) AS total,
                       AVG(CASE WHEN a.status='verified' THEN elapsed END) AS seconds
                FROM attempts a JOIN jobs j ON j.id=a.job
                WHERE j.category=? AND a.status IN ('verified','failed','partial')
                GROUP BY profile
                """, (category,))
            return {row["profile"]: (row["passed"], row["total"], row["seconds"] or 0) for row in rows}
