from __future__ import annotations

import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from aiwork.adaptive import validate_revision
from aiwork.controller import Controller, write_json
from aiwork.component_source import apply_edits, propose_source
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

    def test_adaptive_proposal_can_split_and_rewire_but_cannot_expand_existing_ownership(self):
        draft = {"parts": [
            {"id": "tokenize", "interface": "Tokenize the input.", "outputs": ["tokens.txt"],
             "needs": ["analysis"]},
            {"id": "validate", "interface": "Validate the tokens.", "outputs": ["checked.txt"],
             "needs": ["tokenize"]}],
            "rewire": {"integration": ["first", "validate"]},
            "missing_requirements": ["Test malformed tokens."]}
        self.assertEqual(validate_revision(draft, self.components, "second"), draft)
        draft["rewire"]["integration"] = ["validate"]
        with self.assertRaisesRegex(ValueError, "unrelated"):
            validate_revision(draft, self.components, "second")
        draft["rewire"]["integration"] = ["first", "validate"]
        draft["parts"][1]["outputs"] = ["first.txt"]
        with self.assertRaisesRegex(ValueError, "overlaps"):
            validate_revision(draft, self.components, "second")
        draft["parts"][1]["outputs"] = ["checked.txt"]
        draft["parts"][0]["needs"] = ["validate"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_revision(draft, self.components, "second")

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

    def test_source_repair_receives_complete_current_component(self):
        self.components["first"]["source_context"] = ["driver.py"]
        write_json(self.workspace/"public-cases.json", [
            {"name":"grammar-case", "stdin":"malformed", "stdout":"error\n", "code":0, "stderr":""},
        ])
        self.components["first"]["inputs"].append("public-cases.json")
        self.components["first"]["public_cases"] = "public-cases.json"
        self.components["first"]["checks"] *= 2
        self.save_policy()
        task = graph_tasks(json.loads(self.policy.read_bytes()), self.workspace, "local-p")["first"].task
        current = "/*" + "existing implementation " * 150 + "*/"
        (self.workspace/"first.txt").write_text(current, encoding="utf-8")
        attempt = self.root/"source-repair"
        attempt.mkdir()
        response = {"choices":[{"message":{"content":'{"source":"repaired"}'},"finish_reason":"stop"}]}
        with (patch("aiwork.component_source.Inference.ready"),
              patch("aiwork.component_source.request", return_value=response) as request):
            propose_source(self.controller, task, self.controller.config.profiles[0], self.workspace, attempt,
                           monotonic()+30, "approved public discrepancy")
        sent = json.loads(request.call_args.args[2]["messages"][1]["content"])
        self.assertEqual(sent["current_source"], current)
        self.assertEqual(sent["public_cases"][0]["case"], "grammar-case")
        self.assertEqual(sent["public_cases"][0]["expected"]["stdout"], "error\n")
        self.assertEqual(sent["public_cases_omitted"], 0)
        self.assertNotIn("fixture private marker", json.dumps(sent))
        self.assertEqual((self.workspace/"first.txt").read_text(), "repaired")

    def test_targeted_patch_requires_unique_bounded_edits(self):
        self.assertEqual(apply_edits("before\nkeep\n", {"edits": [
            {"old": "before", "new": "after"}]}), "after\nkeep\n")
        for proposal in (
            {"edits": [{"old": "absent", "new": "x"}]},
            {"edits": [{"old": "e", "new": "x"}]},
            {"edits": [{"old": "before", "new": "before"}]},
            {"edits": [{"old": "before", "new": "\0"}]},
            {"edits": [{"old": "before", "new": "x", "path": "outside.txt"}]},
            {"edits": []},
        ):
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                apply_edits("before\nkeep\n", proposal)

    def test_patch_worker_preserves_source_on_invalid_edits_and_records_valid_provenance(self):
        self.components["first"].update(source_context=["driver.py"], source_patch=True)
        self.save_policy()
        task = graph_tasks(json.loads(self.policy.read_bytes()), self.workspace, "local-p")["first"].task
        target = self.workspace/"first.txt"
        original = b"before\r\n"
        target.write_bytes(original)
        for number, edit in enumerate(({"old": "missing", "new": "after"},
                                      {"old": "before", "new": "after"})):
            attempt = self.root/f"patch-{number}"
            attempt.mkdir()
            response = {"choices": [{"message": {"content": json.dumps({"edits": [edit]})},
                                      "finish_reason": "stop"}]}
            with (patch("aiwork.component_source.Inference.ready"),
                  patch("aiwork.component_source.request", return_value=response) as request):
                if number == 0:
                    with self.assertRaisesRegex(ValueError, "exactly once"):
                        propose_source(self.controller, task, self.controller.config.profiles[0],
                                       self.workspace, attempt, monotonic()+30, "public failure")
                    self.assertEqual(target.read_text(), "before\n")
                else:
                    propose_source(self.controller, task, self.controller.config.profiles[0], self.workspace,
                                   attempt, monotonic()+30, "public failure", previous="patch mismatch")
                    sent = json.loads(request.call_args.args[2]["messages"][1]["content"])
                    self.assertEqual(sent["previous_public_attempt"], "patch mismatch")
                    receipt = json.loads((attempt/"applied-edits.json").read_bytes())
                    self.assertEqual(receipt["filename"], "first.txt")
                    self.assertEqual(receipt["before_sha256"], hashlib.sha256(original).hexdigest())
                    self.assertEqual(receipt["after_sha256"], hashlib.sha256(target.read_bytes()).hexdigest())
                    self.assertNotEqual(receipt["before_sha256"], receipt["after_sha256"])
        self.assertEqual(target.read_text(), "after\n")
        self.assertEqual((self.workspace/"outside.txt").read_text(), "fixture private marker")

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

    @unittest.skipUnless(os.environ.get("AIWORK_TEST_DOCKER_IMAGE"), "requires offline Docker")
    def test_ranked_component_uses_public_diagnostics_and_reuses_only_compatible_revision_jobs(self):
        file = self.workspace / "named-corpus.json"
        write_json(file, [{"name": "named-case", "stdin": "probe", "stdout": "second"}])
        self.components["second"].update(inputs=["driver.py", file.name], public_cases=file.name, checks=[
            {"argv": ["{python}", "-c", "pass"]},
            {"argv": ["{python}", "-c", "from pathlib import Path; print(Path('second.txt').read_text(),end='')"]},
        ])
        self.save_policy()
        register(self.controller, "fixture", self.policy)
        first = prepare(self.controller, "fixture", "initial", "Objective", "local-p", self.reviewed)

        def worker(_, task, profile, work, attempt, deadline, previous, summary, findings):
            name = task.deliverables[0]
            self.assertFalse((work / "outside.txt").exists())
            if name == "second.txt" and "Clarified" not in task.objective:
                if task.agent_role == "implementation":
                    (work/name).write_text("wrong", encoding="utf-8")
                    return
                self.assertIn("named-case", findings)
                self.assertIn('"differences": ["stdout"]', findings)
                self.assertIn('"stdout": "wrong"', findings)
                self.assertIn('"stdout": "second"', findings)
            (work/name).write_text(Path(name).stem, encoding="utf-8")

        with patch.object(Controller, "agent", worker):
            baseline = execute(self.controller, "fixture", "initial", first["approval"], 1)
            self.assertEqual(baseline["status"], "verified")
            second = baseline["jobs"]["second"]
            self.assertEqual(len(self.controller.state.attempts(second)), 2)
            self.components["second"]["interface"] += " Clarified."
            self.save_policy()
            register(self.controller, "revision", self.policy)
            plan = prepare(self.controller, "revision", "with-reuse", "Objective", "local-p", self.reviewed,
                           reuse_from="fixture/initial")
            revised = execute(self.controller, "revision", "with-reuse", plan["approval"], 1)
        self.assertEqual(revised["status"], "verified")
        self.assertEqual(revised["reused"], {name: baseline["jobs"][name] for name in ("analysis", "first")})
        self.assertNotEqual(revised["jobs"]["integration"], baseline["jobs"]["integration"])
