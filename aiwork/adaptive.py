"""Review-only engineering changes proposed from a failed public component."""
from __future__ import annotations

import json

from .controller import Controller, write_json
from .hierarchy import ask_planner, inspect, label, load_registration, local_profile, text_field
from .schema import relative, within
from .workspace import ignore


def references(value: object, universe: set[str]) -> list[str]:
    if not isinstance(value, list) or len(value) > 12:
        raise ValueError("dependency proposals must be bounded arrays")
    names = [label(item) for item in value]
    if len(set(names)) != len(names) or not set(names) <= universe:
        raise ValueError("dependency proposal refers to a missing or duplicate component")
    return names


def validate_revision(draft: dict, components: dict, failed: str) -> dict:
    if not isinstance(draft, dict) or set(draft) != {"parts", "rewire", "missing_requirements"}:
        raise ValueError("revision requires parts, rewire and missing_requirements")
    parts = draft["parts"]
    if not isinstance(parts, list) or not 1 <= len(parts) <= 4 or len(components) - 1 + len(parts) > 14:
        raise ValueError("revision exceeds the component budget")
    replacement = {}
    owned = [output.casefold() for name, row in components.items() if name != failed for output in row["outputs"]]
    for node in parts:
        if not isinstance(node, dict) or set(node) != {"id", "interface", "outputs", "needs"}:
            raise ValueError("new component requires id, interface, outputs and needs")
        name = label(node["id"])
        if name in replacement or (name in components and name != failed):
            raise ValueError("new component collides with existing authority")
        text_field(node["interface"], 1100)
        if not isinstance(node["outputs"], list) or not 1 <= len(node["outputs"]) <= 4:
            raise ValueError("new components must request explicit output paths")
        for value in node["outputs"]:
            if not isinstance(value, str) or any(ignore(part) or part.casefold() == ".handoff"
                                                 for part in value.split("/")):
                raise ValueError("proposed output path is not eligible")
            path = relative(value).casefold()
            if any(within(path, (other,)) or within(other, (path,)) for other in owned):
                raise ValueError("requested output overlaps an existing owner")
            owned.append(path)
        replacement[name] = node
    affected = {name for name, row in components.items() if failed in row.get("needs", []) and name != failed}
    rewire = draft["rewire"]
    if not isinstance(rewire, dict) or set(rewire) != affected:
        raise ValueError("revision must rewire exactly the direct dependents of the replaced component")
    changes = draft["missing_requirements"]
    if not isinstance(changes, list) or len(changes) > 8:
        raise ValueError("missing_requirements must be a bounded array")
    for requirement in changes:
        text_field(requirement, 500)
    unchanged = {name: row.get("needs", []) for name, row in components.items() if name != failed}
    for name, needs in rewire.items():
        inherited = set(unchanged[name]) - {failed}
        if not isinstance(needs, list) or not all(isinstance(item, str) for item in needs):
            raise ValueError("invalid rewire dependencies")
        new = set(needs) - inherited
        if not inherited <= set(needs) or not new or not new <= replacement.keys():
            raise ValueError("rewire must keep unrelated edges and connect a replacement")
    graph = {**unchanged, **rewire, **{name: node["needs"] for name, node in replacement.items()}}
    graph = {name: references(needs, set(graph)) for name, needs in graph.items()}
    pending = set(graph)
    while pending:
        ready = {name for name in pending if not (set(graph[name]) & pending)}
        if not ready:
            raise ValueError("proposed dependency cycle")
        pending -= ready
    return draft


def investigate(controller: Controller, project: str, run: str, component: str, proposal: str) -> dict:
    root, registration = load_registration(controller, project)
    status = inspect(controller, project, run)
    approval = json.loads((root / "plans" / label(run) / "approval.json").read_bytes())
    components = registration["policy"]["components"]
    if (status["current"].get(component) not in {"failed", "blocked", "partial"}
            or not components[component].get("public_cases")):
        raise ValueError("investigation requires a failed ranked component with a public corpus")
    attempts = controller.config.state / "runs" / status["jobs"][component]
    records = sorted(attempts.glob("attempt-*/checkpoint.json"), reverse=True)
    public = json.loads(records[0].read_bytes())["public"] if records else {}
    dependents = {name: row.get("needs", []) for name, row in components.items()
                  if component in row.get("needs", [])}
    context = {
        "failed": component, "interface": components[component]["interface"],
        "public_discrepancies": public.get("discrepancies", [])[:2],
        "build_diagnostic": public.get("build_diagnostic", "")[:700],
        "available_components": list(components), "direct_dependents": dependents,
    }
    example = {"parts": [
        {"id": f"{component[:24]}-parse", "interface": "First proposed interface.",
         "outputs": ["first.c"], "needs": components[component].get("needs", [])},
        {"id": f"{component[:24]}-validate", "interface": "Second proposed interface.",
         "outputs": ["second.c"], "needs": [f"{component[:24]}-parse"]}],
        "rewire": {name: [f"{component[:24]}-validate" if item == component else item for item in needs]
                   for name, needs in dependents.items()},
        "missing_requirements": ["Name a missing invariant or public check."],
    }
    prompt = (
        "You are a diagnostic planner. Split the failed component or propose a more precise replacement interface. "
        "Define specific inputs, outputs and responsibility in interface text. "
        "Use fresh component IDs and safe relative proposed paths. Keep existing unrelated dependency edges. "
        "Return JSON only. Propose no tools, commands or code. Your output is for operator review and cannot run. "
        f"Return this exact object shape with concrete project-specific values: {json.dumps(example)}"
    )
    folder = root / "plans" / run / "investigations" / label(proposal)
    folder.mkdir(parents=True, exist_ok=False)
    profile = local_profile(controller, approval["profile"])
    draft, _ = ask_planner(controller, profile, folder / "model.json", prompt, context,
                           "verification-driven diagnostic planner")
    validate_revision(draft, components, component)
    result = {"status": "review_required", "project": project, "run": run, "component": component,
              "revision": draft, "document": str(folder / "revision.json")}
    write_json(folder / "revision.json", result)
    return result
