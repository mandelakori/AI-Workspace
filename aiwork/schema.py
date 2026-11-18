from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit


def relative(value: str) -> str:
    parts = value.split("/")
    if any(not p or p in {".", ".."} or p.endswith((" ", ".")) or
           re.search(r'[\\:*?"<>|\x00-\x1f]', p) or PureWindowsPath(p).is_reserved()
           for p in parts):
        raise ValueError(f"unsafe relative path: {value!r}")
    return value


def bounded(name: str, value: int, low: int, high: int) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be in {low}..{high}")


@dataclass(frozen=True)
class Check:
    argv: tuple[str, ...]
    timeout: int = 30
    stdout: str | None = None
    cwd: str = ""
    oracle: str = ""

    @classmethod
    def read(cls, data: dict) -> Check:
        if not isinstance(data, dict) or set(data) - {"argv", "timeout", "stdout", "cwd", "oracle"}:
            raise ValueError("checks must contain argv and supported runner options")
        argv = data["argv"]
        if not isinstance(argv, list) or not argv or any(
            not isinstance(arg, str) or not arg or "\0" in arg for arg in argv
        ):
            raise ValueError("check argv must be a nonempty string array")
        timeout = data.get("timeout", 30)
        bounded("check timeout", timeout, 1, 900)
        expected = data.get("stdout")
        if expected is not None and not isinstance(expected, str):
            raise ValueError("stdout must be a string")
        cwd = data.get("cwd", "")
        if not isinstance(cwd, str):
            raise ValueError("cwd must be a workspace-relative directory")
        oracle = data.get("oracle", "")
        if not isinstance(oracle, str):
            raise ValueError("oracle must be a private-directory-relative file")
        if oracle and (expected is not None or any("{verification}" in arg for arg in argv)):
            raise ValueError("sealed oracle commands cannot reference verifier files or inline answers")
        return cls(tuple(argv), timeout, expected, relative(cwd) if cwd else "",
                   relative(oracle) if oracle else "")


@dataclass(frozen=True)
class Task:
    objective: str
    workspace: Path
    kind: str
    category: str
    inputs: tuple[str, ...]
    deliverables: tuple[str, ...]
    checks: tuple[Check, ...]
    location: str = "auto"
    profile: str = ""
    complexity: int = 1
    timeout: int = 300
    attempts: int = 2
    agent_checks: bool = False
    specialist: str = ""
    verification_dir: Path | None = None
    mode: str = "restricted"
    write_roots: tuple[str, ...] = ()
    commands: tuple[Check, ...] = ()
    setup: tuple[Check, ...] = ()
    baseline_check: bool = False
    min_context: int = 0
    preferred_profile: str = ""
    rank_public: bool = False
    agent_role: str = ""
    source_context: tuple[str, ...] = ()
    public_cases: str = ""
    attempt_limit: int = 0

    @classmethod
    def load(cls, path: Path) -> Task:
        path = path.resolve(strict=True)
        d = tomllib.loads(path.read_text(encoding="utf-8"))
        allowed = {key for key in cls.__dataclass_fields__}
        if unknown := d.keys() - allowed:
            raise ValueError(f"unknown task fields: {sorted(unknown)}")
        for key in ("inputs", "deliverables", "write_roots", "source_context"):
            values = d.get(key, [])
            if type(values) is not list or any(type(i) is not str for i in values):
                raise ValueError(f"{key} must be an array of relative paths")
            d[key] = tuple(relative(i) for i in values)
            if len({i.casefold() for i in values}) != len(values):
                raise ValueError(f"duplicate {key}")
        d["workspace"] = (path.parent / d["workspace"]).resolve(strict=True)
        if d.get("verification_dir"):
            d["verification_dir"] = (path.parent / d["verification_dir"]).resolve(strict=True)
            if not d["verification_dir"].is_dir() or (
                d["verification_dir"].is_relative_to(d["workspace"]) or
                d["workspace"].is_relative_to(d["verification_dir"])
            ):
                raise ValueError("verification_dir must be a separate directory")
        else:
            d["verification_dir"] = None
        for key in ("checks", "commands", "setup"):
            checks = d.get(key, [])
            if not isinstance(checks, list):
                raise ValueError(f"{key} must be an array of tables")
            d[key] = tuple(Check.read(c) for c in checks)
        task = cls(**d)
        task.validate()
        return task

    def validate(self) -> None:
        task = self
        if (not isinstance(task.objective, str) or not task.objective.strip() or
            len(task.objective) > 8000 or not task.workspace.is_dir()):
            raise ValueError("task requires a workspace directory and bounded objective")
        if task.kind not in {"agent", "direct"} or task.location not in {"auto", "local", "a100"}:
            raise ValueError("invalid task kind or location")
        if task.kind == "direct" and (task.profile or task.location == "a100"):
            raise ValueError("direct tasks execute on the controller")
        if task.mode not in {"restricted", "engineering"}:
            raise ValueError("mode must be restricted or engineering")
        if task.mode == "engineering":
            from .workspace import ignore
            if task.kind != "agent" or task.specialist or not 1 <= len(task.write_roots) <= 64:
                raise ValueError("engineering mode requires an agent and explicit write_roots")
            for name in (*task.write_roots, *task.deliverables):
                if any(ignore(part) or part.casefold() == ".handoff" for part in relative(name).split("/")):
                    raise ValueError(f"excluded engineering path: {name}")
            if any(not within(name, task.write_roots) for name in task.deliverables):
                raise ValueError("engineering deliverables must be within write_roots")
        elif task.write_roots or task.commands or task.setup or task.baseline_check:
            raise ValueError("write_roots, commands, setup and baseline_check require engineering mode")
        if task.kind == "agent" and task.mode == "restricted" and not task.deliverables:
            raise ValueError("agent tasks require deliverables")
        if (
            not task.checks or len(task.checks) > 16 or len(task.inputs) > 128 or
            not all(isinstance(getattr(task, key), str) for key in
                    ("profile", "preferred_profile", "category", "specialist")) or
            type(task.agent_checks) is not bool
        ):
            raise ValueError("task requires 1–16 checks, at most 128 inputs and valid policy fields")
        bounded("attempts", task.attempts, 1, 5)
        bounded("timeout", task.timeout, 5, 3600)
        bounded("complexity", task.complexity, 1, 5)
        bounded("min_context", task.min_context, 0, 2_000_000)
        if len(task.commands) > 16 or len(task.setup) > 8 or type(task.baseline_check) is not bool:
            raise ValueError("invalid engineering command or setup budget")
        if task.baseline_check and not task.commands:
            raise ValueError("baseline_check requires an approved commands entry at index zero")
        if type(task.rank_public) is not bool or task.rank_public and (
            task.mode != "engineering" or task.verification_dir or task.setup or
            len(task.checks) != 2 or any(check.oracle for check in task.checks) or
            not task.deliverables
        ):
            raise ValueError("public ranking requires an engineering build and invocation without private checks")
        if not isinstance(task.public_cases, str) or task.public_cases and (
            not task.rank_public or relative(task.public_cases) not in task.inputs
            or within(task.public_cases, task.write_roots)
        ):
            raise ValueError("public_cases must identify a read-only staged input for ranked verification")
        bounded("attempt_limit", task.attempt_limit, 0, 5)
        if task.attempt_limit and (not task.rank_public or task.attempts > task.attempt_limit):
            raise ValueError("attempt_limit bounds a ranked engineering job")
        if task.agent_role not in {"", "implementation", "debugging"} or (
            task.agent_role and task.mode != "engineering"
        ):
            raise ValueError("agent_role is only available for scoped engineering workers")
        if task.source_context and (
            not task.agent_role or task.location != "local" or len(task.source_context) > 4 or
            len(task.deliverables) != 1 or task.deliverables != task.write_roots or
            not set(task.source_context) <= set(task.inputs)
        ):
            raise ValueError("source proposals require a local worker, explicit staged context and one writable file")
        if any(check.oracle for check in (*task.commands, *task.setup)):
            raise ValueError("sealed oracles are only allowed in independent checks")
        if any(check.oracle for check in task.checks) and not task.verification_dir:
            raise ValueError("sealed oracles require verification_dir")
        if any(check.oracle for check in task.checks) and any(
            "{verification}" in arg for check in task.checks for arg in check.argv
        ):
            raise ValueError("sealed oracles cannot share a task with mounted private checks")


def within(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in roots)


@dataclass(frozen=True)
class Profile:
    id: str
    model: str
    endpoint: str
    engine: str = "openai"
    harness: str = "opencode"
    location: str = "local"
    context: int = 8192
    output_tokens: int = 2048
    memory_mib: int = 0
    quantization: str = ""
    source: str = ""
    tools: bool = True
    api_key_env: str = ""
    managed: bool = False
    reasoning_effort: str = ""
    seed: int | None = None
    harness_turns: int = 0

    def validate(self) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,50}", self.id) or not self.model or len(self.model) > 512:
            raise ValueError("invalid profile ID or model")
        if self.engine not in {"openai", "ollama", "llamacpp", "vllm"}:
            raise ValueError(f"unsupported engine {self.engine}")
        if self.location not in {"local", "a100"} or self.harness not in {"opencode", "qwen"}:
            raise ValueError("unsupported location or harness")
        if type(self.managed) is not bool or self.managed and self.location != "a100":
            raise ValueError("managed profiles require the A100 plane")
        url = urlsplit(self.endpoint)
        if (url.scheme not in {"http", "https"} or url.hostname not in {"127.0.0.1", "::1", "localhost"} or
            url.username or url.password or url.query or url.fragment or not url.path.rstrip("/").endswith("/v1")):
            raise ValueError("profile endpoints must be loopback /v1 URLs")
        bounded("context", self.context, 1024, 2_000_000)
        bounded("output_tokens", self.output_tokens, 128, self.context - 1)
        bounded("memory_mib", self.memory_mib, 0, 1_000_000)
        if type(self.tools) is not bool or self.api_key_env and not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]{0,99}", self.api_key_env
        ):
            raise ValueError("invalid tools capability or credential environment variable name")
        if self.reasoning_effort and not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", self.reasoning_effort):
            raise ValueError("invalid reasoning effort")
        if self.seed is not None:
            bounded("seed", self.seed, 0, 2**31 - 1)
        bounded("harness_turns", self.harness_turns, 0, 64)
        if self.harness_turns and self.harness != "qwen":
            raise ValueError("harness_turns is supported by Qwen Code profiles")


@dataclass(frozen=True)
class Config:
    state: Path
    profiles: tuple[Profile, ...] = ()
    opencode: str = ""
    qwen: str = ""
    local_slots: int = 1
    a100_slots: int = 1
    ssh: dict = field(default_factory=dict)
    lambda_cloud: dict = field(default_factory=dict)
    specialists: dict = field(default_factory=dict)
    verification_image: str = ""
    execution_state: Path | None = None

    @classmethod
    def load(cls, path: Path) -> Config:
        path = path.resolve()
        d = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        profiles = tuple(Profile(**p) for p in d.pop("profiles", []))
        if len(profiles) > 64:
            raise ValueError("a configuration supports up to 64 model profiles")
        if len({p.id for p in profiles}) != len(profiles):
            raise ValueError("profile IDs must be unique")
        for profile in profiles:
            profile.validate()
        if d.get("lambda_cloud", {}).get("user_data_file"):
            settings = d["lambda_cloud"]
            settings["user_data_file"] = str((path.parent / settings["user_data_file"]).resolve())
        if d.get("execution_state"):
            d["execution_state"] = (path.parent / d["execution_state"]).resolve()
        cfg = cls((path.parent / d.pop("state", ".aiwork")).resolve(), profiles, **d)
        bounded("local_slots", cfg.local_slots, 1, 16)
        bounded("a100_slots", cfg.a100_slots, 1, 1)
        return cfg
