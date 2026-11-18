from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from aiwork.changes import checked_merge, save_patch
from aiwork.controller import Controller
from aiwork.planner import planned, validate_plan
from aiwork.schema import Check, Config, Profile, Task
from aiwork.verify import invoke, pipeline
from aiwork.workspace import inventory, snapshot


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        (self.source / "pkg").mkdir(parents=True)
        (self.source / "pkg" / "one.py").write_text("value = 0\n", encoding="utf-8")
        (self.source / "pkg" / "two.py").write_text("value = 0\n", encoding="utf-8")
        self.local = Profile("laptop", "fake", "http://127.0.0.1:8901/v1")
        self.remote = Profile("a100", "fake", "http://127.0.0.1:8902/v1", location="a100")
        self.controller = Controller(Config(self.root / "state", (self.local, self.remote)))
        self.check = Check(("{python}", "-c", "print('ok')"), stdout="ok\n")

    def task(self, **kwargs):
        return replace(Task("Implement an approved feature", self.source, "agent", "engineering", (), (),
                            (self.check,), mode="engineering", write_roots=("pkg",),
                            commands=(self.check,)), **kwargs)

    def test_rejects_unscoped_or_protected_writes(self):
        for roots in ((), ("pkg/.git",), ("../escape",)):
            with self.subTest(roots=roots), self.assertRaises(ValueError):
                self.task(write_roots=roots).validate()
        with self.assertRaises(ValueError):
            self.task(deliverables=("outside.py",)).validate()

    def test_subdirectory_argv_is_constrained(self):
        command = Check.read({"argv": ["{python}", "-c", "from pathlib import Path; print(Path.cwd().name)"],
                              "cwd": "pkg", "stdout": "pkg\n"})
        self.assertTrue(invoke(command, self.source, self.root / "env")["passed"])
        with self.assertRaises(ValueError):
            Check.read({"argv": ["{python}", "-V"], "cwd": "../outside"})

    def test_admission_rejects_declared_context_above_live_ollama_window(self):
        profile = replace(self.local, engine="ollama", context=8192)
        artifact = self.root / "admission"
        artifact.mkdir()
        with (
            patch("aiwork.controller.opencode_path", return_value="opencode"),
            patch("aiwork.controller.Inference.ready"),
            patch("aiwork.controller.ollama_residency", return_value={
                "resident": True, "configured_server_context": 4096,
            }),
            patch.object(Controller, "gpu_sample", return_value=[]),
            patch("aiwork.controller.OpenCode.execute") as execute,
            self.assertRaisesRegex(ValueError, "serving context 4096"),
        ):
            from time import monotonic
            self.controller.agent(self.task(min_context=8192), profile, self.source,
                                  artifact, monotonic() + 5, "", {}, "")
        execute.assert_not_called()
        record = json.loads((artifact / "admission.json").read_bytes())
        self.assertFalse(record["admitted"])
        self.assertEqual(record["effective_context"], 4096)

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_git_patch_includes_added_modified_and_deleted_files(self):
        stage = self.root / "candidate"
        snapshot(self.source, stage, ())
        (stage / "pkg/one.py").write_text("value = 1\n", encoding="utf-8")
        (stage / "pkg/two.py").unlink()
        (stage / "pkg/three.py").write_bytes(b"# coding: latin-1\nvalue = 'caf\xe9'\n")
        names = ["pkg/one.py", "pkg/three.py", "pkg/two.py"]
        patch_file = Path(save_patch(self.source, stage, names, self.root)["patch"])
        subprocess.run(["git", "apply", "--check", str(patch_file)], cwd=self.source, check=True)
        subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.whitespace=cr-at-eol",
                        "apply", str(patch_file)],
                       cwd=self.source, check=True)
        self.assertEqual(inventory(stage), inventory(self.source))

    def test_merge_rejects_conflict_and_stale_artifacts(self):
        candidate, combined = self.root / "candidate", self.root / "combined"
        snapshot(self.source, candidate, ())
        snapshot(self.source, combined, ())
        name = "pkg/one.py"
        (candidate / name).write_text("value = 1\n", encoding="utf-8")
        expected = inventory(candidate)
        (combined / name).write_text("value = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "integration conflict"):
            checked_merge(self.source, combined, candidate, [name], expected)
        (candidate / name).write_text("value = 9\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            checked_merge(self.source, combined, candidate, [name], expected)

    def test_planner_rejects_cycle_overlap_and_unapproved_commands(self):
        first = {"id": "one", "objective": "Modify one", "needs": [],
                 "write_roots": ["pkg/one.py"], "commands": [0]}
        second = {"id": "two", "objective": "Modify two", "needs": [],
                  "write_roots": ["pkg/two.py"], "commands": [0]}
        self.assertEqual(len(validate_plan({"steps": [first, second]}, self.task())), 2)
        with self.assertRaisesRegex(ValueError, "missing required command"):
            validate_plan({"steps": [first, second]}, self.task(commands=(self.check, self.check)),
                          cover_commands=True)
        for invalid in ({**second, "write_roots": ["pkg"]}, {**second, "commands": [1]},
                        {**second, "needs": ["two"]}, {**second, "write_roots": ["pkg/.git"]}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_plan({"steps": [first, invalid]}, self.task())

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_failed_attempt_carries_authorized_staged_work_to_retry(self):
        check = Check(("{python}", "-c", "from pkg.one import value; assert value == 2"))

        def agent(_, task, profile, work, artifact, deadline, previous, summary, findings):
            path = work / "pkg/one.py"
            value = path.read_text(encoding="utf-8")
            self.assertIn(value.strip(), findings)
            path.write_text(f"value = {int(value.rsplit(' ', 1)[-1]) + 1}\n", encoding="utf-8")

        with patch.object(Controller, "agent", agent):
            report = Check(("{python}", "-c", "from pathlib import Path; print(Path('pkg/one.py').read_text())"))
            job = self.controller.submit_task(self.task(checks=(check,), commands=(report,), baseline_check=True), True)
            result = self.controller.run_submitted(job)
        self.assertEqual(result["status"], "verified", self.controller.state.attempts(job))
        self.assertEqual([a["status"] for a in self.controller.state.attempts(job)], ["failed", "verified"])
        record = Path(result["artifacts"]) / "attempt-002" / "checkpoint.json"
        self.assertTrue(json.loads(record.read_text())["from"].endswith("workspace"))
        self.assertEqual((self.source / "pkg/one.py").read_text(), "value = 0\n")

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_retry_retains_scoped_edits_when_a_deliverable_is_missing(self):
        def agent(_, task, profile, work, *rest):
            first = work / "pkg" / "one.py"
            if first.read_text(encoding="utf-8") == "value = 0\n":
                first.write_text("value = 1\n", encoding="utf-8")
            else:
                (work / "pkg" / "three.py").write_text("value = 3\n", encoding="utf-8")

        with patch.object(Controller, "agent", agent):
            job = self.controller.submit_task(self.task(write_roots=("pkg",), deliverables=("pkg/three.py",)), True)
            result = self.controller.run_submitted(job)
        self.assertEqual(result["status"], "verified", self.controller.state.attempts(job))
        root = Path(result["artifacts"])
        self.assertTrue((root / "attempt-001/checkpoint.json").is_file())
        self.assertEqual((root / "attempt-002/workspace/pkg/one.py").read_text(), "value = 1\n")

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_ranked_public_candidate_rolls_back_to_incumbent_before_retry(self):
        seed = self.source / "pkg/one.py"
        seed.write_text("0", encoding="utf-8")
        examples = [{"name": f"public-{i}", "stdin": str(i), "stdout": "pass"} for i in range(1, 5)]
        (self.source / "examples.json").write_text(json.dumps(examples), encoding="utf-8")
        sealed = self.root / "sealed"
        sealed.mkdir()
        marker = "sealed-marker-never-send"
        (sealed / "cases.json").write_text(marker, encoding="utf-8")
        controller = Controller(replace(self.controller.config, verification_image="offline"))
        task = self.task(deliverables=("pkg/one.py",), checks=(self.check, self.check), attempts=3,
                         rank_public=True)
        with self.assertRaisesRegex(ValueError, "without private"):
            controller.submit_task(replace(task, verification_dir=sealed))
        columns = [{1}, {1, 2}, {2, 3, 4}, {1, 2, 3, 4}]

        def oracle_runner(_, workspace, _home, _image, *, stdin, **kwargs):
            self.assertTrue(kwargs["sealed"])
            self.assertIsNone(kwargs.get("private"))
            version = int((workspace / "pkg/one.py").read_text())
            return {"code": 0, "stdout": "pass" if int(stdin) in columns[version] else "fail",
                    "stderr": "", "timed_out": False, "truncated": False, "elapsed": 0}

        def agent(_, manifest, profile, work, artifact, deadline, previous, summary, findings):
            attempt = int(artifact.name.split("-")[-1])
            path = work / "pkg/one.py"
            self.assertEqual(path.read_text(), "0" if attempt == 1 else "1")
            self.assertIn(f"passes {1 if attempt == 1 else 2}/4 public cases", findings)
            if attempt == 3:
                self.assertIn("Rejected public proposal (public_regression)", previous)
                self.assertIn("indices lost: [1]", previous)
            else:
                self.assertEqual(previous, "")
            self.assertNotIn(marker, findings + previous)
            self.assertFalse((work / "cases.json").exists())
            path.write_text(str(attempt), encoding="utf-8")

        with (
            patch.object(Controller, "agent", agent),
            patch("aiwork.selection.invoke", return_value={"passed": True}),
            patch("aiwork.oracle.invoke", side_effect=oracle_runner),
        ):
            result = controller.run_submitted(controller.submit_task(task))
        self.assertEqual(result["status"], "verified", result)
        root = Path(result["artifacts"])
        regressed = json.loads((root / "attempt-002/checkpoint.json").read_bytes())
        self.assertEqual(regressed["public"]["passed_cases"], 3)
        self.assertEqual(regressed["selection"]["lost_cases"], [1])
        self.assertTrue(regressed["selection"]["rollback"])
        final = json.loads((root / "attempt-003/checkpoint.json").read_bytes())
        self.assertEqual(final["selection"]["previous"], "attempt-001")
        self.assertEqual(final["public"]["independent_verification"], "not_run")
        self.assertFalse((root / "private").exists())

    def test_ranked_attempt_limit_survives_resume(self):
        (self.source / "examples.json").write_text('[{"stdin":"","stdout":"pass"}]', encoding="utf-8")
        controller = Controller(replace(self.controller.config, verification_image="offline"))
        task = self.task(deliverables=("pkg/one.py",), checks=(self.check, self.check), attempts=2,
                         rank_public=True, attempt_limit=2)

        def agent(_, manifest, profile, work, artifact, deadline, previous, summary, findings):
            (work/"pkg/one.py").write_text(artifact.name, encoding="utf-8")

        observed = {"code":0, "stdout":"fail", "stderr":"", "timed_out":False, "truncated":False, "elapsed":0}
        with (
            patch.object(Controller, "agent", agent),
            patch("aiwork.selection.invoke", return_value={"passed":True}),
            patch("aiwork.oracle.invoke", return_value=observed),
        ):
            job = controller.submit_task(task)
            first = controller.run_submitted(job)
            self.assertEqual(first["status"], "failed")
            controller.resume(job)
            second = controller.run_submitted(job)
        self.assertEqual(second["detail"], "ranked attempt budget exhausted")
        self.assertEqual(len(controller.state.attempts(job)), 2)

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_checkpoint_verification_replays_checks_without_an_agent(self):
        def agent(_, task, profile, work, *rest):
            (work / "pkg" / "one.py").write_text("value = 1\n", encoding="utf-8")

        controller = Controller(replace(self.controller.config, verification_image="offline"))
        outcome = {"passed": True, "code": 0, "stdout": "ok\n", "stderr": ""}
        with (
            patch("aiwork.controller.invoke", return_value=outcome),
            patch("aiwork.controller.runner_status", return_value={"image_id": "sha256:abc"}),
            patch.object(Controller, "agent", side_effect=agent, autospec=True) as invocation,
        ):
            job = controller.submit_task(self.task(deliverables=("pkg/one.py",)))
            initial = controller.run_submitted(job)
            replay = controller.verify_checkpoint(job, 1)
            invocation.assert_called_once()
            self.assertEqual(replay["status"], "verified")
            self.assertNotEqual(initial["job"], replay["job"])
            source = Path(initial["artifacts"]) / "attempt-001" / "workspace" / "pkg" / "one.py"
            source.write_text("value = 9\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inventory changed"):
                controller.verify_checkpoint(job, 1)

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_reset_preserves_evidence_but_skips_old_checkpoint(self):
        def agent(_, task, profile, work, *rest):
            path = work / "pkg/one.py"
            self.assertEqual(path.read_text(), "value = 0\n")
            path.write_text("value = 1\n", encoding="utf-8")

        fail = Check(("{python}", "-c", "raise SystemExit(1)"))
        with patch.object(Controller, "agent", agent):
            job = self.controller.submit_task(self.task(attempts=1, checks=(fail,)), True)
            first = self.controller.run_submitted(job)
            self.controller.resume(job, reset=True)
            second = self.controller.run_submitted(job)
        self.assertEqual([first["status"], second["status"]], ["failed", "failed"])
        root = Path(first["artifacts"])
        self.assertTrue((root / "attempt-001/proposed.patch").is_file())
        latest = json.loads((root / "attempt-002/checkpoint.json").read_text())
        self.assertEqual(latest["from"], "")

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_validated_plan_runs_workers_and_integrates(self):
        source = self.root / "objective.toml"
        source.write_text("""
objective = "Implement independent two-file feature"
workspace = "source"
kind = "agent"
mode = "engineering"
category = "integration"
write_roots = ["pkg"]
attempts = 1
[[commands]]
argv = ["{python}", "-c", "from pkg.one import value; assert value == 1"]
[[commands]]
argv = ["{python}", "-c", "from pkg.two import value; assert value == 2"]
[[commands]]
argv = ["{python}", "-c", "from pkg.one import value as x; from pkg.two import value as y; from pkg.three import value as z; assert (x, y, z) == (1, 2, 3)"]
[[checks]]
argv = ["{python}", "-c", "from pkg.one import value as x; from pkg.two import value as y; from pkg.three import value as z; assert (x, y, z) == (1, 2, 3)"]
""", encoding="utf-8")
        plan = {"steps": [
            {"id": "one", "objective": "Provide value 1", "needs": [],
             "write_roots": ["pkg/one.py"], "commands": [0]},
            {"id": "two", "objective": "Provide value 2", "needs": [],
             "write_roots": ["pkg/two.py"], "commands": [1]},
            {"id": "three", "objective": "Provide value 3", "needs": ["one", "two"],
             "write_roots": ["pkg/three.py"], "commands": [2]},
        ]}

        def agent(_, task, profile, work, *unused):
            value = int(task.objective.splitlines()[0].split()[-1])
            (work / task.write_roots[0]).write_text(f"value = {value}\n", encoding="utf-8")

        with (patch("aiwork.planner.propose", return_value=plan) as proposal,
              patch.object(Controller, "agent", agent)):
            result = planned(self.controller, source, "test-plan", 2, True)
            again = planned(self.controller, source, "test-plan", 2, True)
        proposal.assert_called_once()
        self.assertEqual(result["status"], "verified",
                         [self.controller.state.attempts(job) for job in result["jobs"].values()])
        self.assertEqual(result["jobs"], again["jobs"])
        self.assertEqual(set(result["assignments"].values()), {"laptop", "a100"})
        self.assertTrue(Path(result["patch"]).is_file())

    def test_setup_runs_in_same_disposable_command_workspace(self):
        spec = self.root / "tool.json"
        stage = self.root / "worker"
        snapshot(self.source, stage, ())
        spec.write_text(json.dumps({
            "workspace": str(stage), "baseline": str(self.source),
            "engineering": True, "write_roots": ["pkg"], "image": "",
            "setup": [{"argv": ["{python}", "-c", "open('installed', 'w').write('yes')"]}],
            "checks": [{"argv": ["{python}", "-c", "assert open('installed').read() == 'yes'"]}],
        }), encoding="utf-8")
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "check", "arguments": {"index": 0}}}
        outcome = subprocess.run([sys.executable, "-m", "aiwork.mcp", str(spec)],
                                 input=json.dumps(message) + "\n", text=True, capture_output=True,
                                 check=True, timeout=15)
        self.assertFalse(json.loads(outcome.stdout)["result"]["isError"])
        self.assertFalse((stage / "installed").exists())

    @unittest.skipUnless(os.getenv("AIWORK_TEST_DOCKER_IMAGE"), "set AIWORK_TEST_DOCKER_IMAGE")
    def test_docker_installs_approved_offline_wheel(self):
        wheel = self.source / "parcel_demo-1.0-py3-none-any.whl"
        meta = "parcel_demo-1.0.dist-info"
        with ZipFile(wheel, "w") as package:
            entries = {
                "parcel_demo.py": "value = 37\n",
                f"{meta}/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
                f"{meta}/METADATA": "Metadata-Version: 2.1\nName: parcel-demo\nVersion: 1.0\n",
                f"{meta}/RECORD": "",
            }
            for name, value in entries.items():
                package.writestr(name, value or "".join(f"{item},,\n" for item in entries))
        install = Check(("{python}", "-m", "pip", "install", "--no-index", "--no-deps",
                         "--target", ".deps", wheel.name), timeout=45)
        check = Check(("{python}", "-c",
                       "import sys; from pathlib import Path; sys.path.insert(0, '.deps'); "
                       "import parcel_demo; assert parcel_demo.value == 37; "
                       "assert {p.name for p in Path('/sys/class/net').iterdir()} == {'lo'}"))
        stage = self.root / "sandbox"
        snapshot(self.source, stage, ())
        result = pipeline((install,), check, stage, self.root / "env",
                          os.environ["AIWORK_TEST_DOCKER_IMAGE"], timeout=60)
        self.assertTrue(result["passed"], result)
        self.assertFalse((self.source / ".deps").exists())
