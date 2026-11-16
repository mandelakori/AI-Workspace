from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .inference import Inference
from .process import Result, environment, executable, run
from .schema import Config, Profile, Task


class Harness(Protocol):
    def execute(self, profile: Profile, task: Task, work: Path, artifacts: Path,
                prompt: str, timeout: float, tool_spec: Path | None = None,
                stop: Path | None = None) -> Result: ...


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
                prompt: str, timeout: float, tool_spec: Path | None = None,
                stop: Path | None = None) -> Result:
        env = environment(artifacts / "harness-home")
        key = Inference(profile).key()
        settings = {"baseURL": profile.endpoint.rstrip("/")}
        if key:
            env["AIWORK_ENDPOINT_TOKEN"] = key
            settings["apiKey"] = "{env:AIWORK_ENDPOINT_TOKEN}"
        body = request_options(profile)
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
                           "capabilities": {"tools": True}, "body": body}},
            }},
            "model": f"aiwork/{profile.model}",
            "small_model": f"aiwork/{profile.model}",
            "permissions": permissions,
            "autoupdate": False,
        }
        if tool_spec:
            config["mcp"] = {"servers": {"checks": {"type": "local", "command": tool_command(tool_spec),
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
                    "--model", config["model"], "--", prompt], work, timeout, env, stop)


def rule(action: str, resource: str = "*", effect: str = "allow") -> dict:
    return {"action": action, "resource": resource, "effect": effect}


def tool_command(spec: Path) -> list[str]:
    return [sys.executable, "-B", "-c",
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
            "from aiwork.mcp import serve; serve(Path(sys.argv[2]))",
            str(Path(__file__).resolve().parent.parent), str(spec)]


def request_options(profile: Profile) -> dict:
    options = {}
    if profile.reasoning_effort:
        options["reasoning_effort"] = profile.reasoning_effort
        if profile.engine == "llamacpp" and profile.reasoning_effort == "none":
            options["chat_template_kwargs"] = {"enable_thinking": False}
    if profile.seed is not None:
        options["seed"] = profile.seed
    return options


def qwen_command(configured: str, state: Path) -> list[str] | None:
    pinned = state / "qwen-dependency/node_modules/@qwen-code/qwen-code/cli-entry.js"
    entry = Path(configured).resolve() if configured.endswith(".js") else pinned
    if (not configured or configured.endswith(".js")) and entry.is_file():
        node = executable("node")
        return [node, str(entry)] if node else None
    if binary := executable(configured or "qwen"):
        return [binary]
    return None


@dataclass(frozen=True)
class QwenCode:
    command: list[str]

    def execute(self, profile: Profile, task: Task, work: Path, artifacts: Path,
                prompt: str, timeout: float, tool_spec: Path | None = None,
                stop: Path | None = None) -> Result:
        env = environment(artifacts / "harness-home")
        generation = {"contextWindowSize": profile.context,
                      "samplingParams": {"max_tokens": profile.output_tokens}, "maxRetries": 1}
        if extra := request_options(profile):
            generation["extra_body"] = extra
        config = {
            "security": {"auth": {"selectedType": "openai"}},
            "model": {"name": profile.model, "maxSessionTurns": 12},
            "modelProviders": {"openai": [{
                "id": profile.model, "envKey": "OPENAI_API_KEY", "baseUrl": profile.endpoint.rstrip("/"),
                "generationConfig": generation,
            }]},
            "general": {"enableAutoUpdate": False, "enableUpdateNag": False},
            "telemetry": {"enabled": False, "logPrompts": False},
            "tools": {
                "core": ["read_file", "glob", "grep_search", "edit", "write_file", "list_directory"],
                "disabled": ["list_agents", "task_stop", "enter_worktree", "exit_worktree",
                             "record_artifact", "get_goal", "update_goal", "report_findings"],
            },
            "permissions": {
                "allow": [f"Edit(./{name})" for name in task.deliverables],
                "deny": ["Bash", "WebFetch", "WebSearch", "Agent", "skill", "send_message"],
            },
            "skills": {"disabledLevels": ["project", "user", "extension", "bundled"]},
            "memory": {"enableManagedAutoMemory": False, "enableManagedAutoDream": False,
                       "enableAutoSkill": False},
        }
        if tool_spec:
            tool = tool_command(tool_spec)
            config["mcpServers"] = {"checks": {"command": tool[0], "args": tool[1:]}}
            config["permissions"]["allow"].append("mcp__checks__check")
        config_path = artifacts / "qwen-settings.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        env.update({
            "QWEN_CODE_SYSTEM_SETTINGS_PATH": str(config_path),
            "QWEN_CODE_SYSTEM_DEFAULTS_PATH": str(artifacts / "harness-home/absent-defaults.json"),
            "OPENAI_BASE_URL": profile.endpoint.rstrip("/"),
            "OPENAI_API_KEY": Inference(profile).key() or "local",
            "OPENAI_MODEL": profile.model,
            "GIT_CEILING_DIRECTORIES": str(work.parent),
        })
        return run([*self.command, "--output-format", "stream-json", "--approval-mode", "default",
                    "--model", profile.model, "--prompt", prompt], work, timeout, env, stop)
