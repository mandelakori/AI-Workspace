"""Authority-preserving decomposition of registered engineering contracts."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, replace
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

from .controller import Controller, write_json
from .harness import request_options
from .http import request
from .inference import Inference
from .lock import file_lock
from .native import pin_runner
from .planner import terminal
from .schema import Check, Task, bounded, relative, within
from .workflow import GraphTask, execute_graph
from .workspace import contained, inventory, snapshot


ROLES = {"analysis", "implementation", "testing", "debugging", "integration"}


def label(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", value):
        raise ValueError("IDs must be lowercase letters, digits or hyphens and start with a letter")
    return value


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def text_field(value: object, size: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > size:
        raise ValueError(f"expected nonempty text of at most {size} characters")
    return value.strip()


def array(data: dict, key: str, limit: int) -> list:
    value = data.get(key, [])
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{key} must be an array of at most {limit} entries")
    return value


def paths(data: dict, key: str) -> tuple[str, ...]:
    result = tuple(relative(item) for item in array(data, key, 16))
    if len({item.casefold() for item in result}) != len(result):
        raise ValueError(f"duplicate {key}")
    return result


def graph_tasks(policy: dict, stage: Path, profile: str,
                order: list[str] | None = None) -> dict[str, GraphTask]:
    entries = policy["components"]
    if not isinstance(entries, dict) or not 2 <= len(entries) <= 14:
        raise ValueError("a project requires 2–14 approved components")
    graph = {}
    outputs: list[str] = []
    for key in order or entries:
        node = entries[key]
        label(key)
        if set(node) - {"role", "interface", "inputs", "outputs", "needs", "imports", "checks", "timeout",
                        "source_context", "source_patch", "public_cases", "commands"}:
            raise ValueError(f"{key}: unknown component policy field")
        role = node["role"]
        if role not in ROLES:
            raise ValueError(f"{key}: invalid role")
        contract = text_field(node["interface"], 1100)
        checks = tuple(Check.read(row) for row in array(node, "checks", 4))
        commands = tuple(Check.read(row) for row in array(node, "commands", 4))
        if any(check.oracle or any("{verification}" in arg for arg in check.argv) for check in (*checks, *commands)):
            raise ValueError("registered component checks must be public")
        needs = tuple(label(item) for item in array(node, "needs", 12))
        if len(set(needs)) != len(needs) or key in needs:
            raise ValueError("invalid component dependencies")
        inputs, deliverables = paths(node, "inputs"), paths(node, "outputs")
        if not inputs or not deliverables:
            raise ValueError("each component requires staged public inputs and declared outputs")
        for item in inputs:
            if not contained(stage, item).is_file():
                raise ValueError(f"{key}: input must be an approved regular file: {item}")
        for item in deliverables:
            folded = item.casefold()
            if within(folded, tuple(outputs)) or any(within(other, (folded,)) for other in outputs):
                raise ValueError("component outputs must have disjoint ownership")
            outputs.append(folded)
        agent = role in {"implementation", "debugging"}
        if commands and not agent:
            raise ValueError("only engineering workers can invoke approved public tooling")
        objective = (f"Component: {key}.\nInterface contract: {contract}\n"
                     "Use the approved staged inputs and verified dependency artifacts. "
                     "Implement only your assigned deliverables.")
        source_context = paths(node, "source_context")
        corpus = node.get("public_cases", "")
        if agent and not source_context:
            objective += " Run the approved public check before finishing."
        task = Task(objective, stage, "agent" if agent else "direct", f"hierarchy-{key}", inputs,
                    deliverables, checks, location="local", timeout=node.get("timeout", 90),
                    attempts=policy["max_attempts"] if corpus else 1,
                    mode="engineering" if agent else "restricted", write_roots=deliverables if agent else (),
                    commands=(commands or checks) if agent else (),
                    baseline_check=agent, agent_role=role if agent else "",
                    source_context=source_context, profile=profile if source_context else "",
                    source_patch=node.get("source_patch", False),
                    rank_public=bool(corpus), public_cases=corpus,
                    attempt_limit=policy["max_attempts"] if corpus else 0)
        task.validate()
        requested = node.get("imports", {})
        if not isinstance(requested, dict) or requested.keys() - set(needs):
            raise ValueError("artifact imports must be scoped to declared dependencies")
        imports = {}
        for source in needs:
            allowed = paths(entries[source], "outputs") if source in entries else ()
            selected = paths(requested, source) if source in requested else allowed
            if not set(selected) <= set(allowed):
                raise ValueError("artifact imports exceed the dependency interface")
            imports[source] = selected
        graph[key] = GraphTask(task, needs, profile if agent and not source_context else "", imports=imports)
    pending = set(graph)
    while pending:
        ready = {name for name in pending if set(graph[name].needs) <= graph.keys() - pending}
        if not ready:
            raise ValueError("component graph contains a cycle or unknown dependency")
        pending -= ready
    return graph


def leaves(tree: dict, permitted: set[str]) -> list[str]:
    seen: set[str] = set()
    groups: set[str] = set()
    order: list[str] = []

    def visit(node: dict, depth: int) -> None:
        if depth > 4 or not isinstance(node, dict):
            raise ValueError("hierarchy exceeds its nesting limit")
        if set(node) in ({"component"}, {"component", "id"}):
            name = label(node["component"])
            if name not in permitted or name in seen:
                raise ValueError("leaf must reference a unique approved component")
            if "id" in node:
                label(node["id"])
            seen.add(name)
            order.append(name)
            return
        if set(node) != {"id", "children"}:
            raise ValueError("group accepts only id and children")
        name = label(node["id"])
        if name in groups or name in permitted:
            raise ValueError("group ID collides with a component or group")
        groups.add(name)
        children = node["children"]
        if not isinstance(children, list) or not 1 <= len(children) <= 14:
            raise ValueError("group requires bounded, nonempty children")
        for child in children:
            visit(child, depth + 1)

    visit(tree, 0)
    if "component" in tree or seen != permitted:
        raise ValueError("plan must cover every approved component exactly once")
    return order


def load_registration(controller: Controller, name: str) -> tuple[Path, dict]:
    root = controller.config.state / "hierarchy-projects" / label(name)
    data = json.loads((root / "registration.json").read_bytes())
    if inventory(root / "public") != data["inventory"]:
        raise ValueError("registered public workspace has changed")
    return root, data


def register(controller: Controller, name: str, descriptor: Path) -> dict:
    descriptor = descriptor.resolve(strict=True)
    policy = json.loads(descriptor.read_bytes())
    if set(policy) != {"workspace", "components", "max_attempts"}:
        raise ValueError("project descriptor requires workspace, components and max_attempts")
    bounded("max_attempts", policy["max_attempts"], 1, 5)
    workspace = (descriptor.parent / policy["workspace"]).resolve(strict=True)
    graph = graph_tasks(policy, workspace, "")
    files = tuple(sorted({item for node in graph.values() for item in node.task.inputs}))
    root = controller.config.state / "hierarchy-projects" / label(name)
    root.mkdir(parents=True, exist_ok=True)
    with file_lock(root / "registration.lock"):
        if (root / "registration.json").exists():
            raise ValueError("project already registered; choose a new name for a revision")
        staged = snapshot(workspace, root / "public", files)
        data = {"project": name, "policy": policy, "inventory": staged, "artifacts": str(root)}
        write_json(root / "registration.json", data)
    return data


def local_profile(controller: Controller, name: str):
    matches = [p for p in controller.config.profiles if p.id == name and p.location == "local" and not p.managed
               and urlsplit(p.endpoint).hostname in {"localhost", "127.0.0.1", "::1"}]
    if not matches:
        raise ValueError("hierarchy requires an existing local profile")
    return matches[0]


def propose(controller: Controller, profile, work: Path, objective: str, entries: dict, *, role: str,
            group: str = "objective") -> tuple[dict, dict]:
    catalog = {name: {field: node[field] for field in ("role", "interface", "needs") if field in node}
               for name, node in entries.items()}
    context = {"objective": objective, "components": catalog}
    if len(json.dumps(context)) > 11500:
        raise ValueError("planning context exceeds the bounded catalog size")
    ids = list(catalog)
    example = {"id": group, "children": [
        {"id": "work-package", "children": [{"component": name} for name in ids[:2]]},
        *({"component": name} for name in ids[2:]),
    ]}
    prompt = (
        f"You are the {role}. Restructure the supplied starting tree into logical groups. "
        f"Keep the root id exactly {group} and end with every existing leaf exactly once. "
        "Use component values verbatim. For groups use new lowercase hyphenated IDs up to 40 characters, "
        "at least two children below the root, and at most three nested levels. "
        "Return the tree object only. Include no code or permissions. "
        f"Starting tree: {json.dumps(example)}"
    )
    draft, evidence = ask_planner(controller, profile, work, prompt, context, role)
    leaves(draft, set(entries))
    return draft, evidence


def ask_planner(controller: Controller, profile, work: Path, prompt: str, context: dict,
                role: str) -> tuple[dict, dict]:
    start = monotonic()
    with controller.planes["local"].reserve(profile, 45):
        client = Inference(profile)
        client.ready()
        response = request(profile.endpoint.rstrip("/") + "/chat/completions", "POST", {
            "model": profile.model, "temperature": 0, "max_tokens": min(profile.output_tokens, 900),
            "response_format": {"type": "json_object"}, **request_options(profile),
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": json.dumps(context)}],
        }, key=client.key(), timeout=40)
    raw = response["choices"][0]["message"]["content"]
    evidence = {"role": role, "profile": profile.id, "input": context, "content": raw,
                "usage": response.get("usage"), "seconds": round(monotonic() - start, 3)}
    write_json(work, evidence)
    return json.loads(raw), evidence


def group_nodes(tree: dict):
    if "children" in tree:
        yield tree
        for child in tree["children"]:
            yield from group_nodes(child)


def component_names(tree: dict):
    if "component" in tree:
        yield tree["component"]
    else:
        for child in tree["children"]:
            yield from component_names(child)


def prepare(controller: Controller, project: str, run_id: str, objective: str, profile_id: str,
            reviewed: Path | None = None, *, from_run: str = "", group: str = "",
            reuse_from: str = "") -> dict:
    """Create a reviewable approval receipt. This action submits no component jobs."""
    root, registration = load_registration(controller, project)
    if not controller.config.verification_image:
        raise ValueError("hierarchy requires an offline verification image")
    image = pin_runner(controller)
    if bool(from_run) != bool(group) or (from_run and reviewed):
        raise ValueError("specialist proposals require a prior plan and a group")
    profile = local_profile(controller, profile_id)
    objective = text_field(objective, 1800)
    folder = root / "plans" / label(run_id)
    folder.mkdir(parents=True, exist_ok=False)
    policy = registration["policy"]
    origin = "reviewed" if reviewed else "model"
    if from_run:
        previous = json.loads((root / "plans" / label(from_run) / "approval.json").read_bytes())
        if previous["registration_sha256"] != digest(registration):
            raise ValueError("specialist proposal requires the same project authority")
        tree = previous["tree"]
        leaves(tree, set(policy["components"]))
        scope = next((node for node in group_nodes(tree) if node["id"] == group), None)
        if scope is None:
            raise ValueError("the reviewed tree has no such group")
        subset = set(component_names(scope))
        draft, _ = propose(controller, profile, folder / "specialist.json", objective,
                           {key: row for key, row in policy["components"].items() if key in subset},
                           role="component planning specialist", group=group)
        if draft["id"] != group:
            raise ValueError("specialist changed the parent group ID")
        scope.update(draft)
        origin = "specialist"
    else:
        tree = (json.loads(reviewed.read_bytes()) if reviewed else
                propose(controller, profile, folder / "planner.json", objective, policy["components"],
                        role="planning coordinator")[0])
    leaves(tree, set(policy["components"]))
    approval = {"project": project, "run": run_id, "objective": objective, "profile": profile_id,
                "model": profile.model, "profile_sha256": digest(asdict(profile)),
                "runner": controller.config.verification_image, "runner_image": image,
                "registration_sha256": digest(registration), "tree": tree,
                "permissions": policy["components"], "max_attempts": policy["max_attempts"],
                "origin": origin}
    if from_run:
        approval.update(parent_plan=from_run, refined_group=group)
    if reuse_from:
        source_project, _, source_run = reuse_from.partition("/")
        origin_root, _ = load_registration(controller, source_project)
        previous = json.loads((origin_root / "plans" / label(source_run) / "approval.json").read_bytes())
        if (source_project, source_run) == (project, run_id):
            raise ValueError("a plan cannot reuse itself")
        approval["reuse_from"] = {"project": source_project, "run": source_run, "approval": digest(previous)}
    write_json(folder / "approval.json", approval)
    return {"approval": digest(approval), "document": str(folder / "approval.json"), **approval}


def execute(controller: Controller, project: str, run_id: str, approval_hash: str,
            workers: int, retry: str = "") -> dict:
    root, registration = load_registration(controller, project)
    folder = root / "plans" / label(run_id)
    approval = json.loads((folder / "approval.json").read_bytes())
    profile = local_profile(controller, approval["profile"])
    if (approval_hash != digest(approval) or approval["project"] != project or approval["run"] != run_id
            or approval["registration_sha256"] != digest(registration)
            or approval["permissions"] != registration["policy"]["components"]
            or approval["max_attempts"] != registration["policy"]["max_attempts"]
            or approval["profile_sha256"] != digest(asdict(profile))
            or not approval["runner"] or approval["runner"] != controller.config.verification_image):
        raise ValueError("approval digest, registered authority, profile or offline runner changed")
    order = leaves(approval["tree"], set(approval["permissions"]))
    graph = graph_tasks(registration["policy"], root / "public", profile.id, order)
    if retry and (retry not in graph or graph[retry].task.kind != "agent"):
        raise ValueError("retry must name an approved agent component")
    workflow_id = "hierarchy-" + digest([project, run_id])[:24]
    runner = approval.get("runner_image")
    if runner and pin_runner(controller) != runner:
        raise ValueError("approved offline image digest changed")
    lane = Controller(replace(controller.config, verification_image=runner)) if runner else controller
    reused = compatible_jobs(controller, registration, approval, graph) if "reuse_from" in approval else {}
    result = execute_graph(lane, graph, workers, False, workflow_id, approval_hash,
                           {name: digest(approval["permissions"][name]) for name in graph},
                           retry=retry, max_attempts=approval["max_attempts"], reuse=reused)
    return {**result, "project": project, "run": run_id, "tree": approval["tree"],
            "workflow_report": str(controller.config.state / "workflows" / workflow_id / "workflow.json")}


def compatible_jobs(controller: Controller, registration: dict, approval: dict,
                    graph: dict[str, GraphTask]) -> dict[str, str]:
    link = approval["reuse_from"]
    project, run = link["project"], link["run"]
    root, previous = load_registration(controller, project)
    old = json.loads((root / "plans" / label(run) / "approval.json").read_bytes())
    if (digest(old) != link["approval"] or digest(previous) != old["registration_sha256"]
            or not approval.get("runner_image") or approval["runner_image"] != old.get("runner_image")
            or approval["profile_sha256"] != old["profile_sha256"]):
        raise ValueError("predecessor approval, profile or pinned verifier changed")
    result = inspect(controller, project, run)
    if result.get("plan") != link["approval"]:
        raise ValueError("predecessor execution does not match its approval")
    reused = {}
    pending = set(graph)
    while pending:
        ready = sorted(name for name in pending if not (set(graph[name].needs) & pending))
        for name in ready:
            node = graph[name]
            if (name in result["outputs"] and old["permissions"].get(name) == approval["permissions"][name]
                    and set(node.needs) <= reused.keys()
                    and all(previous["inventory"].get(file) == registration["inventory"][file]
                            for file in node.task.inputs)):
                reused[name] = result["jobs"][name]
        pending.difference_update(ready)
    return reused


def inspect(controller: Controller, project: str, run_id: str) -> dict:
    root, _ = load_registration(controller, project)
    folder = root / "plans" / label(run_id)
    approval = json.loads((folder / "approval.json").read_bytes())
    workflow_id = "hierarchy-" + digest([project, run_id])[:24]
    report = controller.config.state / "workflows" / workflow_id / "workflow.json"
    result = json.loads(report.read_bytes()) if report.exists() else {"status": "review", "jobs": {}}
    history = {name: controller.state.jobs(job)[0]["status"] for name, job in result["jobs"].items()}
    outputs = {}
    for name, job in result["jobs"].items():
        if history[name] != "verified":
            continue
        attempt, _ = terminal(controller, job)
        agent = approval["permissions"][name]["role"] in {"implementation", "debugging"}
        index = "output-inventory.json" if agent else "verification-inventory.json"
        receipt = json.loads((attempt / index).read_bytes())
        directory = attempt / ("workspace" if agent else "verification")
        actual = inventory(directory)
        files = approval["permissions"][name]["outputs"]
        if any(file not in receipt or actual.get(file) != receipt[file] for file in files):
            raise ValueError(f"{name}: verified output changed")
        outputs[name] = {file: {"path": str(directory / file), **receipt[file]} for file in files}
    return {**result, "current": history, "outputs": outputs, "approval": digest(approval), "tree": approval["tree"],
            "workflow_report": str(report)}
