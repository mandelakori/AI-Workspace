"""Bounded local recovery experiment using existing source workers and public ranking.

Controller-authored assembly only: all replacement text comes from saved model responses.
Never reads private evaluation material. Existing experiment roots are not overwritten.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import textwrap
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aiwork.component_source import propose_source
from aiwork.controller import Controller, write_json
from aiwork.schema import Check, Config, Task
from aiwork.selection import compare, score
from aiwork.workspace import inventory, snapshot


def class_span(source, class_name="ISODateTime"):
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.ClassDef) and node.name == class_name]
    node, = nodes
    return node.lineno - 1, node.end_lineno


def assemble(name, source, work, documentation_base=None):
    if name == "docs-text":
        parts = source.split("<!-- AIWORK-API -->")
        if len(parts) != 2:
            raise ValueError("documentation must contain exactly one API section separator")
        return assemble("docs", json.dumps(dict(zip(("parameter-types", "api"), parts))), work, documentation_base)
    if name in {"api", "api-method", "test-method"}:
        tree = ast.parse(source)
        expected = {"api": "ISODateTime", "api-method": "_handle_datetime", "test-method": "test_cli_integration"}[name]
        node_type = ast.ClassDef if name == "api" else ast.FunctionDef
        if len(tree.body) != 1 or not isinstance(tree.body[0], node_type) or tree.body[0].name != expected:
            raise ValueError("replacement must contain only " + expected)
        target = work / ("tests/test_iso_datetime.py" if name == "test-method" else "src/click/types.py")
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        class_name = "TestISODateTime" if name == "test-method" else "ISODateTime"
        first, last = class_span("".join(lines), class_name)
        if name in {"api-method", "test-method"}:
            cls = next(node for node in ast.parse("".join(lines)).body
                       if isinstance(node, ast.ClassDef) and node.name == class_name)
            method, = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == expected]
            def signature(args):
                return ([arg.arg for arg in (*args.posonlyargs, *args.args)],
                        [arg.arg for arg in args.kwonlyargs], bool(args.vararg), bool(args.kwarg),
                        len(args.defaults), [value is None for value in args.kw_defaults])
            if signature(tree.body[0].args) != signature(method.args):
                raise ValueError("method replacement changed its calling signature")
            first, last = method.lineno - 1, method.end_lineno
            source = textwrap.indent(source, "    ")
        target.write_text("".join(lines[:first]) + source.rstrip() + "\n" + "".join(lines[last:]), encoding="utf-8")
    elif name == "tests":
        ast.parse(source)
        (work / "tests/test_iso_datetime.py").write_text(source, encoding="utf-8")
    else:
        sections = json.loads(source)
        if set(sections) != {"parameter-types", "api"} or not all(isinstance(x, str) and x.strip() for x in sections.values()):
            raise ValueError("documentation requires two nonempty sections")
        for section, addition in sections.items():
            path = work / f"docs/{section}.md"
            if documentation_base:
                base = (documentation_base / f"docs/{section}.md").read_text(encoding="utf-8")
                if not path.read_text(encoding="utf-8").startswith(base):
                    raise ValueError("documentation predecessor is not an unchanged upstream prefix")
                path.write_text(base, encoding="utf-8")
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n\n" + addition.strip() + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--start", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--components", default="api,tests,docs", choices=("api,tests,docs", "api-method", "api-method,tests,docs", "test-method", "docs-text"))
    parser.add_argument("--review-artifacts", action="store_true")
    parser.add_argument("--documentation-base", type=Path)
    parser.add_argument("--public-diagnostic", type=Path)
    parser.add_argument("--interface", type=Path)
    parser.add_argument("--attempts", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    controller = Controller(Config.load(args.config.resolve()))
    profile, = controller.config.profiles
    if profile.location != "local" or profile.model != "aiwork-qwen35-phase4:8k":
        raise ValueError("only the reviewed existing local profile is allowed")
    selected = root / "selected"
    snapshot(args.start.resolve(), selected, ())
    probe = selected / "_aiwork_probe.py"
    text = probe.read_text(encoding="utf-8")
    insertion = '''    if kind == "feature-tests":
        result = subprocess.run([sys.executable, "_aiwork_verify.py", "feature"], capture_output=True, timeout=45)
        return {"complete": result.returncode == 0}
    if kind == "documentation":
        docs = Path("docs/parameter-types.md").read_text()+Path("docs/api.md").read_text()
        return {"complete": all(word in docs for word in ("ISODateTime", "require_timezone", "normalize_to_utc"))}
'''
    if 'if kind == "feature-tests":' not in text:
        probe.write_text(text.replace('    if kind == "repository":', insertion + '    if kind == "repository":'), encoding="utf-8")
    corpus = selected / "_aiwork_public_cases.json"
    cases = json.loads(corpus.read_bytes())
    for name in ("feature-tests", "documentation"):
        if not any(row.get("name") == name for row in cases):
            cases.append({"name": name, "stdin": json.dumps({"kind": name}), "stdout": '{"complete":true}\n'})
    write_json(corpus, cases)
    if args.review_artifacts:
        import shutil
        shutil.copyfile(Path(__file__).with_name("authored_checks.py"), selected / "_aiwork_authored_checks.py")
        text = probe.read_text(encoding="utf-8")
        insertion = '''    if kind in {"authored-cli", "authored-docs"}:
        result = subprocess.run([sys.executable, "_aiwork_authored_checks.py", kind.split("-")[1]], capture_output=True, timeout=45)
        return {"complete": result.returncode == 0}
'''
        if 'if kind in {"authored-cli", "authored-docs"}:' not in text:
            probe.write_text(text.replace('    if kind == "repository":', insertion + '    if kind == "repository":'), encoding="utf-8")
        for name in ("authored-cli", "authored-docs"):
            if not any(row.get("name") == name for row in cases):
                cases.append({"name": name, "stdin": json.dumps({"kind": name}), "stdout": '{"complete":true}\n'})
        write_json(corpus, cases)
    write_json(root / "public-corpus-review.json", {"sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
               "cases": len(cases), "policy": "same frozen public corpus for all proposals; no sealed access",
               "budget": {"attempts_per_component": args.attempts,
                          "inference_requests": args.attempts * len(args.components.split(","))}})
    build = Check(("python", "_aiwork_verify.py", "upstream"), timeout=120)
    run = Check(("python", "_aiwork_probe.py"), timeout=90)
    image = controller.config.verification_image
    stop = root / "STOP"

    def grade(work, path):
        path.mkdir()
        receipt = score(build, run, work / corpus.name, work, path / "home", image, monotonic()+240, stop, [])
        receipt["inventory"] = inventory(work)
        write_json(path / "receipt.json", receipt)
        return receipt

    incumbent = grade(selected, root / "baseline")
    if not incumbent["compiled"]:
        raise RuntimeError("baseline regression gate unavailable; no inference permitted")
    history = []
    started = monotonic()
    spec = (selected / "FEATURE.md").read_text(encoding="utf-8")
    for name in args.components.split(","):
        findings = (args.public_diagnostic.read_text(encoding="utf-8")[:1800] if args.public_diagnostic
                    else json.dumps(incumbent.get("discrepancies", []))[:1800])
        previous = ""
        if name == "docs-text":
            task_objective = 'Write Markdown documentation, not a nested JSON document. The source string must contain two sections separated by exactly one <!-- AIWORK-API --> marker. Before the marker: heading # ISODateTime, a working Python CLI example using @click.command, @click.option and click.ISODateTime, both flags, naive rejection, UTC normalization, errors and compatibility with existing DateTime. After the marker: the fenced Sphinx autoclass directive for ISODateTime following existing docs/api.md syntax under currentmodule click. No :module: option. Use unmodified upstream examples in INTERFACE.md for syntax. Do not use an undefined cli/app or annotations as option definitions. Use click.echo for visible command output. Return the normal source field containing this Markdown text.'
        elif name == "test-method":
            task_objective = "Replace only TestISODateTime.test_cli_integration(self). Preserve other tests. Locally import CliRunner inside the method. Define your own decorated Click command accepting ISODateTime and actually invoke it for valid and invalid inputs. Check exit codes and visible output. The callback parameter must match the option destination, and returning a value alone does not print output. Follow the existing upstream CLI test pattern in INTERFACE.md. Do not use any undefined app, verifier JSON output or external fixture. Return only the complete method at module indentation; controller will indent it."
        elif name == "api-method":
            task_objective = "Replace only the _handle_datetime method of ISODateTime. Preserve the signature and datetime identity unless normalization requested. The public reproduction uses a datetime with non-None tzinfo whose UTC offset is None: all three timezone-policy combinations must raise Click BadParameter with ISO 8601 and timezone hints; default mode must preserve identity. Follow FEATURE.md. Existing parser is outside scope and must not change. Available globals: datetime, timezone, t, ParamType, Parameter, Context."
        elif name == "api":
            task_objective = "Replace only ISODateTime class. Globals available: datetime, timezone, t, ParamType, Parameter, Context. Follow FEATURE.md. Fix the public object-offset policy failure. Preserve passing parsing and metadata. Remove redundant parser iterations if useful."
        elif name == "tests":
            task_objective = "Write a concise complete tests/test_iso_datetime.py with >=6 meaningful pytest cases for FEATURE.md including CLI integration. Import click canonically, never src.click. Use actual conversion calls in raises blocks. Base metadata keys are param_type and name. Avoid incorrect assertions. The previous test only defined a command but never invoked it. Your CLI integration test MUST call CliRunner.invoke and check the resulting exit code and visible output for valid and invalid inputs."
        else:
            task_objective = 'Write a source string containing JSON with exactly two string fields: parameter-types and api. These are complete documentation additions for existing Click docs. Begin the parameter-types section with heading # ISODateTime. Include a fenced Python example using click.option and click.ISODateTime, both flags, errors and compatibility with legacy DateTime. The api section uses the existing Sphinx currentmodule click and autoclass syntax. Do not add a :module: option: autodoc does not support it. No implementation code.'
        for number in range(1, args.attempts + 1):
            attempt = root / f"{name}-{number}"
            attempt.mkdir()
            context = attempt / "worker"
            context.mkdir()
            (context / "FEATURE.md").write_text(spec, encoding="utf-8")
            types = (selected / "src/click/types.py").read_text(encoding="utf-8")
            first, last = class_span(types)
            current = "".join(types.splitlines(keepends=True)[first:last])
            if name in {"api-method", "test-method"}:
                source = ((selected / "tests/test_iso_datetime.py").read_text(encoding="utf-8") if name == "test-method" else types)
                class_name = "TestISODateTime" if name == "test-method" else "ISODateTime"
                method_name = "test_cli_integration" if name == "test-method" else "_handle_datetime"
                cls = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == class_name)
                method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
                current = textwrap.dedent("".join(source.splitlines(keepends=True)[method.lineno-1:method.end_lineno]))
            interface = current[:1500]
            if name == "docs-text":
                basic = (selected / "tests/test_basic.py").read_text(encoding="utf-8")
                node = next(node for node in ast.parse(basic).body if isinstance(node, ast.FunctionDef) and node.name == "test_datetime_option_default")
                interface = "Unmodified upstream CLI example:\n" + "".join(basic.splitlines(keepends=True)[node.lineno-1:node.end_lineno])[:1400]
                api = (selected / "docs/api.md").read_text(encoding="utf-8")
                index = api.index(".. autoclass:: DateTime")
                interface += "\nUnmodified upstream Markdown API syntax:\n" + api[index-15:index+50]
            if name == "test-method":
                original = (selected / "tests/test_basic.py").read_text(encoding="utf-8")
                node = next(node for node in ast.parse(original).body if isinstance(node, ast.FunctionDef) and node.name == "test_datetime_option_default")
                interface = "Unmodified upstream example, not an operator solution:\n" + "".join(original.splitlines(keepends=True)[node.lineno-1:node.end_lineno])[:1800]
            if args.interface:
                interface = args.interface.read_text(encoding="utf-8")[:1000] + "\n" + interface
            (context / "INTERFACE.md").write_text(
                "Existing metadata returns {param_type: class name, name: type.name}. Use canonical click imports in tests. "
                "Public diagnostics: tzinfo with utcoffset() None is naive even when tzinfo is not None. "
                "Current source is worker-authored. No operator implementation is supplied.\n" +
                ((selected / "docs/api.md").read_text(encoding="utf-8")[-1300:] if name == "docs" else interface), encoding="utf-8")
            filename = {"api": "ISODateTime.py", "api-method": "_handle_datetime.py",
                        "tests": "tests/test_iso_datetime.py", "docs": "documentation.json",
                        "test-method": "test_cli_integration.py", "docs-text": "ISODateTime-documentation.md"}[name]
            if name in {"api", "api-method", "test-method"}:
                (context / filename).write_text(current, encoding="utf-8")
            task = Task(objective=task_objective, workspace=context, category="phase6-click-source-repair",
                        checks=(build,), kind="agent", mode="engineering",
                        location="local", profile=profile.id, agent_role="debugging", timeout=120,
                        inputs=("FEATURE.md", "INTERFACE.md"), source_context=("FEATURE.md", "INTERFACE.md"),
                        deliverables=(filename,), write_roots=(filename,))
            task.validate()
            write_json(attempt / "task.json", {"objective": task_objective, "source_scope": name})
            try:
                propose_source(controller, task, profile, context, attempt, monotonic()+120,
                               findings, previous=previous)
                previous = (context / filename).read_text(encoding="utf-8")[:700]
                candidate = attempt / "candidate"
                snapshot(selected, candidate, ())
                assemble(name, (context / filename).read_text(encoding="utf-8"), candidate, args.documentation_base)
                receipt = grade(candidate, attempt / "verification")
                decision = compare(incumbent, receipt, protect_passing=True)
                findings = json.dumps(receipt.get("discrepancies", []))[:1800]
                if decision["accepted"]:
                    selected.rename(attempt / "predecessor")
                    snapshot(candidate, selected, ())
                    incumbent = receipt
            except (ValueError, OSError, RuntimeError) as error:
                decision = {"accepted": False, "reason": str(error)}
            write_json(attempt / "selection.json", decision)
            history.append({"component": name, "attempt": number, **decision})
            write_json(root / "report.json", {"history": history, "passed": incumbent["passed_cases"],
                       "total": incumbent["total"], "elapsed": round(monotonic()-started, 3)})
            print(name, number, decision, flush=True)
            if decision["accepted"]:
                break


if __name__ == "__main__":
    main()
