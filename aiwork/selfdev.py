from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from .controller import Controller, write_json
from .process import environment, executable, run
from .schema import Check, Task, relative
from .workspace import BYTE_LIMIT, FILE_LIMIT, contained, ignore


def checkout(repo: Path, root: Path) -> tuple[Path, str]:
    git = executable("git")
    if not git:
        raise ValueError("Git is required for self-development checkouts")
    env = environment(root / "git-home")
    commit = run([git, "rev-parse", "--verify", "HEAD"], repo, 15, env)
    if commit.code or commit.timed_out:
        raise ValueError("source repository has no Git HEAD to check out")
    revision = commit.stdout.strip()
    archive = root / "checkout.zip"
    result = run([git, "archive", "--format=zip", "--output", str(archive), revision], repo, 30, env)
    if result.code or result.timed_out:
        raise ValueError("could not archive the source commit")
    workspace = root / "checkout"
    workspace.mkdir()
    with ZipFile(archive) as package:
        entries = package.infolist()
        if len(entries) > FILE_LIMIT or sum(info.file_size for info in entries) > BYTE_LIMIT:
            raise ValueError("committed source exceeds checkout limits")
        for info in entries:
            name = relative(info.filename.removesuffix("/"))
            if info.is_dir() or any(ignore(part) for part in name.split("/")):
                continue
            mode = (info.external_attr >> 16) & 0o170000
            if mode not in {0, 0o100000}:
                raise ValueError(f"nonregular archive member: {name}")
            destination = contained(workspace, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with package.open(info) as data, destination.open("xb") as out:
                shutil.copyfileobj(data, out)
    return workspace, revision


def propose(controller: Controller, repo: Path, profile: str, trusted: bool,
            objective: str = "", manifest: Path | None = None) -> dict:
    if not controller.config.verification_image and not trusted:
        raise ValueError("self-development requires Docker or explicitly trusted regression checks")
    root = controller.config.state / "self" / uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    workspace, commit = checkout(repo.resolve(strict=True), root)
    if not (workspace / "aiwork/index.py").is_file() or not (workspace / "tests").is_dir():
        raise ValueError("self-development requires an AI Workspace checkout with regression tests")
    base = ("Inspect aiwork/index.py and choose a small improvement to repository relevance. "
            "Write a regression test in tests/test_index_extension.py and run the suite.")
    full_suite = Check(("{python}", "-m", "unittest", "discover", "-s", "tests", "-v"), 90)
    if manifest:
        requested = Task.load(manifest)
        if requested.mode != "engineering" or requested.workspace.resolve() != repo.resolve():
            raise ValueError("self manifest must authorize engineering against the named repository")
        for name in requested.write_roots:
            if (name == "tests" or name.startswith("tests/") and (workspace / name).exists()):
                raise ValueError("self proposals may add tests while preserving the committed regression suite")
        task = replace(requested, workspace=workspace, inputs=(), checks=(*requested.checks, full_suite),
                       baseline_check=False)
    else:
        task = Task(objective=objective or base, workspace=workspace, kind="agent",
                    category="aiwork-self-index", inputs=(), deliverables=("tests/test_index_extension.py",),
                    checks=(full_suite,), profile=profile, attempts=2, timeout=360,
                    mode="engineering", write_roots=("aiwork/index.py", "tests/test_index_extension.py"),
                    commands=(full_suite,), min_context=8192)
    job = controller.submit_task(task, trusted, profile_id=profile, source=manifest)
    write_json(root / "checkout.json", {"commit": commit, "workspace": str(workspace), "job": job})
    verified = controller.run_submitted(job)
    return {**verified, "base_commit": commit, "checkout_evidence": str(root / "checkout.json"),
            "integration": "review the proposed patch before applying"}
