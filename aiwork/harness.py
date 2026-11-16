from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .inference import Inference
from .process import Result, environment, executable, run
from .schema import Profile, Task


def opencode_path(configured: str = "") -> str | None:
    if configured:
        return executable(configured)
    direct = executable("opencode")
    if direct:
        return direct
    shim = shutil.which("opencode.cmd")
    if shim:
        path = Path(shim).parent / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe"
        if path.is_file():
            return str(path)
    return None


@dataclass(frozen=True)
class OpenCode:
    binary: str

    def execute(self, profile: Profile, task: Task, work: Path, artifacts: Path,
                prompt: str, timeout: float, tool_spec: Path | None = None) -> Result:
        env = environment(artifacts / "harness-home")
        key = Inference(profile).key()
        settings = {"baseURL": profile.endpoint.rstrip("/")}
        if key:
            env["AIWORK_ENDPOINT_TOKEN"] = key
        actions = ["read", "glob", "grep", "list", "todowrite"]
        permissions = [rule("*", "*", "deny"), *(rule(action) for action in actions)]
        # Controller checks the actual changed file set again before verification.
        permissions.extend(rule("edit", name) for name in task.deliverables)
        permissions.extend(rule("write", name) for name in task.deliverables)
        permissions.extend(rule("patch", name) for name in task.deliverables)
        # V2 commonly normalizes mutation resources to absolute paths.
        for action in ("edit", "write", "patch"):
            permissions.extend(rule(action, (work / name).as_posix()) for name in task.deliverables)
        config = {
            "providers": {"aiwork": {
                "name": "AI Workspace", "package": "@opencode/ai/providers/openai-compatible",
                "settings": settings, "env": ["AIWORK_ENDPOINT_TOKEN"] if key else [],
                "models": {profile.model: {"name": profile.model,
                           "limit": {"context": profile.context, "output": profile.output_tokens},
                           "capabilities": {"tools": True}}},
            }},
            "model": f"aiwork/{profile.model}",
            "small_model": f"aiwork/{profile.model}",
            "permissions": permissions,
            "autoupdate": False,
        }
        if tool_spec:
            argv = [sys.executable, "-B", "-c",
                    "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                    "from aiwork.mcp import serve; serve(Path(sys.argv[2]))",
                    str(Path(__file__).resolve().parent.parent), str(tool_spec)]
            config["mcp"] = {"servers": {"checks": {"type": "local", "command": argv,
                                                     "codemode": False}}}
            permissions.append(rule("checks_check"))
        env.update({
            "OPENCODE_CONFIG_CONTENT": json.dumps(config),
            "OPENCODE_DISABLE_PROJECT_CONFIG": "true",
            "OPENCODE_DISABLE_MODELS_FETCH": "true",
            "OPENCODE_DISABLE_AUTOUPDATE": "true",
            "GIT_CEILING_DIRECTORIES": str(work.parent),
        })
        return run([self.binary, "run", "--standalone", "--format", "json",
                    "--model", config["model"], "--", prompt], work, timeout, env)


def rule(action: str, resource: str = "*", effect: str = "allow") -> dict:
    return {"action": action, "resource": resource, "effect": effect}
