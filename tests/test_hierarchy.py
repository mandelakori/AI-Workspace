from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from aiwork.controller import Controller, write_json
from aiwork.component_source import propose_source
from aiwork.hierarchy import execute, graph_tasks, inspect, leaves, prepare, register
from aiwork.schema import Config, Profile


DRIVER = """import sys
from pathlib import Path
role = sys.argv[1]
if role == "analysis":
    Path("public.json").write_text('{"contract": 7}')
    Path("extra.txt").write_text("unrelated")
elif role in ("first", "second"):
    assert Path(".handoff/analysis/public.json").is_file()
    assert not Path(".handoff/analysis/extra.txt").exists()
    assert Path(role + ".txt").read_text() == role
else:
    first = Path(".handoff/first/first.txt").read_text()
    second = Path(".handoff/second/second.txt").read_text()
    Path("joined.txt").write_text(first + second)
"""


class HierarchyTests(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        self.root = Path(context.name)
        self.workspace = self.root / "public"
        self.workspace.mkdir()
        (self.workspace / "driver.py").write_text(DRIVER, encoding="utf-8")
        (self.workspace / "outside.txt").write_text("fixture private marker", encoding="utf-8")
        self.tree = {"id": "objective", "children": [
            {"id": "evidence-and-build", "children": [
                {"component": "analysis"}, {"component": "first"}, {"component": "second"}]},
            {"component": "integration"},
        ]}
        self.reviewed = self.root / "tree.json"
        write_json(self.reviewed, self.tree)
        self.policy = self.root / "project.json"

        def component(role, name, outputs, needs=(), imports=None):
            row = {"role": role, "interface": f"Produce {name} from approved evidence.", "inputs": ["driver.py"],
                   "outputs": outputs, "checks": [{"argv": ["{python}", "driver.py", name]}],
                   "needs": list(needs), "timeout": 40}
            if imports:
                row["imports"] = imports
            return row

        self.components = {
            "analysis": component("analysis", "analysis", ["public.json", "extra.txt"]),
            "first": component("implementation", "first", ["first.txt"], ("analysis",),
                               {"analysis": ["public.json"]}),
            "second": component("implementation", "second", ["second.txt"], ("analysis",),
                                {"analysis": ["public.json"]}),
            "integration": component("integration", "integration", ["joined.txt"], ("first", "second")),
        }
        self.save_policy()
        self.controller = Controller(Config(self.root / "state", (
            Profile("local-p", "fixture", "http://127.0.0.1:11434/v1"),),
            verification_image=os.environ.get("AIWORK_TEST_DOCKER_IMAGE", "offline")))
        image = patch("aiwork.hierarchy.pin_runner", return_value=self.controller.config.verification_image)
        image.start()
        self.addCleanup(image.stop)

    def save_policy(self):
        write_json(self.policy, {"workspace": "public", "components": self.components, "max_attempts": 2})

    def test_tree_cannot_introduce_authority_or_duplicate_work(self):
        allowed = set(self.components)
        self.assertEqual(set(leaves(self.tree, allowed)), allowed)
        bad = {"id": "root", "children": [{"component": "first", "tools": ["shell"]}]}
        with self.assertRaises(ValueError):
            leaves(bad, allowed)
        with self.assertRaises(ValueError):
            leaves({"id": "root", "children": [{"component": "first"}, {"component": "first"}]}, allowed)
        self.components["first"]["imports"] = {"analysis": ["secret.json"]}
        self.save_policy()
        with self.assertRaisesRegex(ValueError, "exceed the dependency interface"):
            register(self.controller, "fixture", self.policy)

    def test_specialist_only_revises_group_and_requires_new_approval(self):
        register(self.controller, "fixture", self.policy)
        first = prepare(self.controller, "fixture", "original", "Objective", "local-p", self.reviewed)
        refined = {"id": "evidence-and-build", "children": [
            {"component": "analysis"}, {"id": "build", "children": [
                {"component": "first"}, {"component": "second"}]}]}
        with patch("aiwork.hierarchy.propose", return_value=(refined, {})) as propose:
            second = prepare(self.controller, "fixture", "refinement", "Refine build", "local-p",
                             from_run="original", group="evidence-and-build")
        self.assertEqual(set(propose.call_args.args[4]), {"analysis", "first", "second"})
        self.assertEqual(first["permissions"], second["permissions"])
        self.assertEqual(first["tree"]["children"][1], second["tree"]["children"][1])
        self.assertNotEqual(first["approval"], second["approval"])
        with self.assertRaisesRegex(ValueError, "approval digest"):
            execute(self.controller, "fixture", "refinement", first["approval"], 1)

    def test_source_proposal_cannot_choose_files_or_send_unapproved_context(self):
        self.components["first"]["source_context"] = ["driver.py"]
        self.save_policy()
        policy = json.loads(self.policy.read_bytes())
        task = graph_tasks(policy, self.workspace, "local-p")["first"].task
        profile = self.controller.config.profiles[0]
        attempt = self.root / "attempt"
        attempt.mkdir()
        candidate = {"choices": [{"message": {"content": '{"source":"first","path":"outside.txt"}'}}]}
        with (patch("aiwork.component_source.Inference.ready"),
              patch("aiwork.component_source.request", return_value=candidate) as request):
            with self.assertRaisesRegex(ValueError, "bounded source file"):
                propose_source(self.controller, task, profile, self.workspace, attempt, monotonic()+30, "")
        request_text = str(request.call_args.args[2]["messages"])
        self.assertIn("driver.py", request_text)
        self.assertNotIn("fixture private marker", request_text)
        self.assertEqual((self.workspace / "outside.txt").read_text(), "fixture private marker")
        self.assertFalse((self.workspace / "first.txt").exists())

    @unittest.skipUnless(os.environ.get("AIWORK_TEST_DOCKER_IMAGE"), "requires offline Docker")
    def test_failed_component_retry_reuses_verified_artifacts_and_integrates(self):
        register(self.controller, "fixture", self.policy)
        plan = prepare(self.controller, "fixture", "run", "Objective", "local-p", self.reviewed)

        def agent(_, task, profile, work, attempt, deadline, previous, summary, findings):
            name = task.deliverables[0]
            self.assertFalse((work / "outside.txt").exists())
            self.assertFalse((work / ".handoff/analysis/extra.txt").exists())
            self.assertTrue((work / ".handoff/analysis/public.json").exists())
            value = Path(name).stem
            if value == "second" and attempt.name == "attempt-001":
                self.assertEqual(task.agent_role, "implementation")
                value = "wrong"
            if attempt.name == "attempt-002":
                self.assertEqual(task.agent_role, "debugging")
                self.assertEqual((work / name).read_text(), "wrong")
            (work / name).write_text(value, encoding="utf-8")

        with patch.object(Controller, "agent", agent):
            partial = execute(self.controller, "fixture", "run", plan["approval"], 1)
            self.assertEqual(partial["steps"]["first"], "verified")
            self.assertEqual(partial["steps"]["second"], "failed")
            self.assertEqual(partial["steps"]["integration"], "waiting_for_dependencies")
            complete = execute(self.controller, "fixture", "run", plan["approval"], 1, "second")
        self.assertEqual(complete["status"], "verified")
        self.assertEqual(partial["jobs"]["first"], complete["jobs"]["first"])
        self.assertEqual(len(self.controller.state.attempts(complete["jobs"]["first"])), 1)
        outputs = inspect(self.controller, "fixture", "run")["outputs"]
        self.assertEqual(Path(outputs["integration"]["joined.txt"]["path"]).read_text(), "firstsecond")
