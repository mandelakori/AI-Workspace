from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Protocol

from .changes import delta, validate_changes
from .inference import Inference
from .process import Result, environment, executable, run
from .schema import Config, Profile, Task
from .workspace import inventory, snapshot


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
        started = monotonic()
        with TemporaryDirectory(prefix="aiwork-opencode-") as directory:
            isolated = Path(directory).resolve()
            if any((parent / ".git").exists() for parent in isolated.parents):
                raise ValueError("OpenCode temporary workspaces must be outside existing Git worktrees")
            stage = isolated / "workspace"
            before = snapshot(work, stage, ())
            if tool_spec:
                policy = json.loads(tool_spec.read_bytes())
                policy["workspace"] = str(stage)
                tool_spec = artifacts / "opencode-tool.json"
                tool_spec.write_text(json.dumps(policy), encoding="utf-8")
            result = self.run_session(profile, task, stage, artifacts, prompt,
                                      max(0, timeout - (monotonic() - started)), tool_spec, stop)
            try:
                changed = delta(before, inventory(stage))
                roots = task.write_roots if task.mode == "engineering" else task.deliverables
                validate_changes(changed, roots)
            except (OSError, ValueError):
                (artifacts / "agent.jsonl").write_text(result.stdout, encoding="utf-8")
                (artifacts / "agent.stderr.txt").write_text(result.stderr, encoding="utf-8")
                raise
            if changed:
                staged = artifacts / "opencode-output"
                snapshot(stage, staged, ())
                previous = artifacts / "pre-opencode"
                work.rename(previous)
                try:
                    staged.rename(work)
                except OSError:
                    previous.rename(work)
                    raise
            return result

    def run_session(self, profile: Profile, task: Task, work: Path, artifacts: Path, prompt: str,
                    timeout: float, tool_spec: Path | None, stop: Path | None) -> Result:
        env = environment(artifacts / "harness-home")
        key = Inference(profile).key()
        settings = {"baseURL": profile.endpoint.rstrip("/")}
        if key:
            env["AIWORK_ENDPOINT_TOKEN"] = key
            settings["apiKey"] = "{env:AIWORK_ENDPOINT_TOKEN}"
        body = request_options(profile)
        instructions = artifacts / "operator-task.md"
        instructions.write_text(
            "# Active operator task\n\n" + task.objective +
            "\n\nWritable paths: " + ", ".join(task.write_roots or task.deliverables) +
            "\nComplete the task by editing the authorized files and running approved checks. "
            "This objective remains active across context changes.\n", encoding="utf-8")
        actions = ["read", "glob", "grep", "list", "todowrite"]
        if task.mode == "engineering" and tool_spec and profile.context <= 8192:
            actions.remove("read")  # Use the bounded public MCP source inspector.
        permissions = [rule("*", "*", "deny"), *(rule(action) for action in actions)]
        permissions.append(rule("external_directory", effect="deny"))
        # Controller checks the actual changed file set again before verification.
        # V2 commonly normalizes mutation resources to absolute paths.
        allowed = task.deliverables if task.mode == "restricted" else tuple(
            f"{root}{suffix}" for root in task.write_roots for suffix in ("", "/**"))
        for action in ("edit", "write", "patch"):
            permissions.extend(rule(action, name) for name in allowed)
            permissions.extend(rule(action, (work / name).as_posix()) for name in allowed)
        config = {
            "instructions": [str(instructions.resolve())],
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
            "policies": [rule("tool.use", "external_directory:*", "deny")],
            "autoupdate": False,
        }
        if task.mode == "engineering":
            config["snapshots"] = False
            if profile.context <= 4096:
                config["compaction"] = {"auto": False}
        if tool_spec:
            config["mcp"] = {"servers": {"checks": {"type": "local", "command": tool_command(tool_spec),
                                                     "codemode": False}}}
            permissions.append(rule("checks_check"))
            if task.mode == "engineering":
                permissions.append(rule("checks_diff"))
                permissions.append(rule("checks_focus"))
        env.update({
            "OPENCODE_CONFIG_CONTENT": json.dumps(config),
            "OPENCODE_DISABLE_PROJECT_CONFIG": "true",
            "OPENCODE_DISABLE_MODELS_FETCH": "true",
            "OPENCODE_DISABLE_AUTOUPDATE": "true",
            "GIT_CEILING_DIRECTORIES": str(work.parent),
        })
        return run([self.binary, "run", "--standalone", "--format", "json",
                    "--model", config["model"], "--", prompt], work, timeout, env, stop,
                   output_limit=8 * 1024 * 1024)


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
        editable = (task.deliverables if task.mode == "restricted" else tuple(
            expression for root in task.write_roots for expression in (root, root + "/**")))
        config = {
            "security": {"auth": {"selectedType": "openai"}},
            "model": {"name": profile.model, "maxSessionTurns": profile.harness_turns or 12},
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
                "allow": [f"Edit(./{name})" for name in editable],
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
            if task.mode == "engineering":
                config["permissions"]["allow"].append("mcp__checks__diff")
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
                    "--model", profile.model, "--prompt", prompt], work, timeout, env, stop,
                   output_limit=8 * 1024 * 1024)
