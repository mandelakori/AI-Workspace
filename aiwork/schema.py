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

    @classmethod
    def read(cls, data: dict) -> Check:
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
        return cls(tuple(argv), timeout, expected)


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

    @classmethod
    def load(cls, path: Path) -> Task:
        path = path.resolve(strict=True)
        d = tomllib.loads(path.read_text(encoding="utf-8"))
        allowed = {key for key in cls.__dataclass_fields__}
        if unknown := d.keys() - allowed:
            raise ValueError(f"unknown task fields: {sorted(unknown)}")
        for key in ("inputs", "deliverables"):
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
        d["checks"] = tuple(Check.read(c) for c in d.get("checks", []))
        task = cls(**d)
        if (not isinstance(task.objective, str) or not task.objective.strip() or
            len(task.objective) > 8000 or not task.workspace.is_dir()):
            raise ValueError("task requires a workspace directory and bounded objective")
        if task.kind not in {"agent", "direct"} or task.location not in {"auto", "local", "a100"}:
            raise ValueError("invalid task kind or location")
        if task.kind == "direct" and (task.profile or task.location == "a100"):
            raise ValueError("direct tasks execute on the controller")
        if task.kind == "agent" and not task.deliverables:
            raise ValueError("agent tasks require deliverables")
        if (
            not task.checks or len(task.checks) > 16 or len(task.inputs) > 128 or
            not all(isinstance(getattr(task, key), str) for key in ("profile", "category", "specialist")) or
            type(task.agent_checks) is not bool
        ):
            raise ValueError("task requires 1–16 checks, at most 128 inputs and valid policy fields")
        bounded("attempts", task.attempts, 1, 5)
        bounded("timeout", task.timeout, 5, 3600)
        bounded("complexity", task.complexity, 1, 5)
        return task


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
    discovery: dict = field(default_factory=dict)
    verification_image: str = ""

    @classmethod
    def load(cls, path: Path) -> Config:
        path = path.resolve()
        d = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        profiles = tuple(Profile(**p) for p in d.pop("profiles", []))
        if len({p.id for p in profiles}) != len(profiles):
            raise ValueError("profile IDs must be unique")
        for profile in profiles:
            profile.validate()
        if d.get("lambda_cloud", {}).get("user_data_file"):
            settings = d["lambda_cloud"]
            settings["user_data_file"] = str((path.parent / settings["user_data_file"]).resolve())
        cfg = cls((path.parent / d.pop("state", ".aiwork")).resolve(), profiles, **d)
        bounded("local_slots", cfg.local_slots, 1, 16)
        bounded("a100_slots", cfg.a100_slots, 1, 16)
        return cfg
