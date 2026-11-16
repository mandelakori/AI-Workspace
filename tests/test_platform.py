from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from threading import Timer
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch

from aiwork.benchmark import aggregate
from aiwork.controller import Controller
from aiwork.lock import file_lock
from aiwork.process import Result, environment, run
from aiwork.router import routes
from aiwork.schema import Config, Profile, Task, relative
from aiwork.workflow import execute


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        project = self.root / "project"
        project.mkdir()
        (project / "answer.py").write_text("answer = 1\n", encoding="utf-8")
        (project / ".env").write_text("EXAMPLE_SECRET=should-never-copy\n", encoding="utf-8")
        self.manifest = self.root / "task.toml"
        self.profile = Profile("local", "test-model", "http://127.0.0.1:9998/v1")
        self.remote = Profile("remote", "test-model", "http://127.0.0.1:9999/v1", location="a100")
        self.controller = Controller(Config(self.root / "state", (self.profile, self.remote)))

    def task(self, *, kind="agent", check='["{python}", "-c", "from answer import answer; assert answer == 2"]',
             extras="", deliverables='["answer.py"]'):
        self.manifest.write_text(f"""
objective = "Fix the reviewed test fixture"
workspace = "project"
kind = "{kind}"
category = "fixture"
deliverables = {deliverables}
{extras}
[[checks]]
argv = {check}
""", encoding="utf-8")
        return self.manifest

    def test_direct_queue_and_snapshot(self):
        task = self.task(kind="direct", check='["{python}", "-c", "from answer import answer; assert answer == 1"]')
        job = self.controller.submit(task, True)
        (self.root / "project" / "answer.py").write_text("answer = 9", encoding="utf-8")
        value = self.controller.work(job)
        self.assertEqual(value["status"], "verified")
        root = Path(value["artifacts"])
        self.assertFalse((root / "baseline/.env").exists())
        self.assertTrue((root / "attempt-001/check-00.json").is_file())
        self.assertEqual(self.controller.state.jobs(job)[0]["status"], "verified")
        self.assertEqual(self.controller.run_submitted(job), value)

    def test_trust_required_without_container(self):
        with self.assertRaisesRegex(ValueError, "reviewed task"):
            self.controller.submit(self.task())

    def test_mock_agent_retry_escalates_and_verifies(self):
        attempted = []

        def fixture(_, profile, task, work, attempt, prompt, timeout, tool_spec, stop):
            attempted.append(profile.id)
            (work / "answer.py").write_text(f"answer = {len(attempted)}\n", encoding="utf-8")
            return Result(0, 0.02, "", "", False, False)

        with (patch("aiwork.controller.opencode_path", return_value="mock-opencode"),
              patch("aiwork.controller.Inference.ready"),
              patch("aiwork.controller.OpenCode.execute", new=fixture)):
            job = self.controller.submit(self.task(), True)
            result = self.controller.work(job)
        self.assertEqual(attempted, ["local", "remote"])
        self.assertEqual(result["status"], "verified")
        self.assertEqual([a["status"] for a in self.controller.state.attempts(job)], ["failed", "verified"])
        self.assertEqual((self.root / "project/answer.py").read_text(), "answer = 1\n")

    def test_unauthorized_edit_rejected(self):
        def fixture(_, task, profile, work, *args):
            (work / "injected.py").write_text("", encoding="utf-8")

        with patch.object(Controller, "agent", new=fixture):
            job = self.controller.submit(self.task(extras="attempts = 1"), True)
            self.assertEqual(self.controller.work(job)["status"], "failed")

    def test_parallel_claim_has_one_winner(self):
        job = self.controller.submit(self.task(), True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda _: self.controller.state.claim(job), range(4)))
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        self.controller.resume(job, interrupted=True)
        self.assertEqual(self.controller.state.jobs(job)[0]["status"], "queued")

    def test_resume_skips_existing_attempt_directory(self):
        task = self.task(kind="direct", check='["{python}", "-c", "print(1)"]')
        job = self.controller.submit(task, True)
        row = self.controller.state.claim(job)
        root = Path(row["spec"]).parent
        (root / "attempt-001").mkdir()
        self.controller.resume(job, interrupted=True)
        self.assertEqual(self.controller.work(job)["status"], "verified")
        self.assertTrue((root / "attempt-002/evidence.json").is_file())

    def test_worker_kill_releases_claim_without_overwriting_partial_artifacts(self):
        task = self.task(kind="direct", check='["{python}", "-c", "print(1)"]')
        job = self.controller.submit(task, True)
        root = self.root / "state" / "runs" / job
        script = """
from pathlib import Path
from sys import argv
from time import sleep
from aiwork.controller import Controller
from aiwork.schema import Config
def hold(self, row, root):
    attempt = root / "attempt-001"
    attempt.mkdir()
    (attempt / "partial.txt").write_text("preserve this attempt")
    sleep(60)
Controller._work = hold
Controller(Config(Path(argv[1]), ())).work(argv[2])
"""
        child = subprocess.Popen([sys.executable, "-c", script, str(self.root / "state"), job])
        partial = root / "attempt-001" / "partial.txt"
        try:
            deadline = monotonic() + 10
            while not partial.exists() and child.poll() is None and monotonic() < deadline:
                sleep(0.05)
            self.assertTrue(partial.is_file())
            with self.assertRaises(TimeoutError):
                self.controller.resume(job, interrupted=True)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
        self.controller.resume(job, interrupted=True)
        self.assertEqual(self.controller.work(job)["status"], "verified")
        self.assertEqual(partial.read_text(), "preserve this attempt")
        self.assertTrue((root / "attempt-002/evidence.json").is_file())

    def test_paths_and_override(self):
        for name in ("../test", "a\\..\\secret", "x:stream", "CON", "x/", "x.*", "C:/x"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relative(name)
        task = Task.load(self.task(extras='profile = "remote"'))
        chosen = routes(task, (self.profile, self.remote), {"local": (10, 10, 1)})
        self.assertEqual([r.profile.id for r in chosen], ["remote"])
        self.assertEqual(routes(replace(task, location="local"), (self.profile, self.remote), {}), [])

    def test_private_failure_not_fed_to_retry(self):
        secret_dir = self.root / "private"
        secret_dir.mkdir()
        (secret_dir / "verify.py").write_text('print("hidden sentinel")\nraise SystemExit(1)', encoding="utf-8")
        spec = self.task(extras='verification_dir = "private"', check='["{python}", "{verification}/verify.py"]')
        feedback = []

        def fixture(_, task, profile, work, attempt, deadline, previous, summary, findings):
            self.assertFalse((work / "verify.py").exists())
            (work / "answer.py").write_text("answer = 2\n", encoding="utf-8")
            feedback.append(previous)

        with patch.object(Controller, "agent", new=fixture):
            job = self.controller.submit(spec, True)
            self.assertEqual(self.controller.work(job)["status"], "failed")
        self.assertEqual(feedback, ["", "private verification failed"])

    def test_workflow_handoff_is_verified_and_resume_is_idempotent(self):
        seed = self.task(kind="direct", check='["{python}", "-c", "open(\'data.txt\', \'w\').write(\'ready\')"]',
                         deliverables='["data.txt"]')
        second = self.root / "check.toml"
        second.write_text("""
objective = "Read a verified dependency artifact"
workspace = "project"
kind = "direct"
category = "fixture"
[[checks]]
argv = ["{python}", "-c", "from pathlib import Path; assert Path('.handoff/seed/data.txt').read_text() == 'ready'"]
""", encoding="utf-8")
        plan = self.root / "workflow.toml"
        plan.write_text(f'[steps.seed]\nmanifest = "{seed.name}"\n[steps.consume]\n'
                        'manifest = "check.toml"\nneeds = ["seed"]\n', encoding="utf-8")
        first = execute(self.controller, plan, 2, True, "fixture")
        again = execute(self.controller, plan, 2, True, "fixture")
        self.assertEqual(first["status"], "verified")
        self.assertEqual(first["jobs"], again["jobs"])

    def test_mcp_cannot_select_arbitrary_command(self):
        spec = self.root / "tool.json"
        spec.write_text(json.dumps({"workspace": str(self.root / "project"), "image": "",
                                    "checks": [{"argv": ["{python}", "-c", "print(7)"]}]}),
                        encoding="utf-8")
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "check", "arguments": {"index": 0, "argv": ["illegal"]}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "check", "arguments": {"index": 0}}},
        ]
        result = subprocess.run([sys.executable, "-m", "aiwork.mcp", str(spec)],
                                input="\n".join(map(json.dumps, messages)) + "\n",
                                text=True, capture_output=True, timeout=15, check=True)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertTrue(replies[1]["result"]["isError"])
        self.assertFalse(replies[2]["result"]["isError"])

    def test_success_rate_uses_attempted_samples(self):
        report = aggregate([
            {"profile": "small", "elapsed": 1, "status": "verified", "first_pass": True},
            {"profile": "small", "elapsed": 3, "status": "blocked", "first_pass": False},
        ])
        self.assertEqual(report["small"]["verified"], 1)
        self.assertEqual(report["small"]["p50_seconds"], 2)

    def test_stop_marker_interrupts_active_subprocess(self):
        marker = self.root / "STOP"
        timer = Timer(0.3, marker.touch)
        timer.start()
        try:
            result = run([sys.executable, "-c", "import time; time.sleep(20)"],
                         self.root, 20, environment(self.root / "temp"), marker)
        finally:
            timer.cancel()
            timer.join()
        self.assertTrue(result.timed_out)
        self.assertLess(result.elapsed, 8)

    def test_allocated_job_id_recovers_journal_gap(self):
        task = self.task()
        allocated = "1" * 32
        first = self.controller.submit(task, True, job_id=allocated)
        second = self.controller.submit(task, True, job_id=allocated)
        self.assertEqual(first, second)
        self.assertEqual(len(self.controller.state.jobs()), 1)

    def test_contended_file_lock_reports_busy(self):
        lock = self.root / "lane.lock"
        with file_lock(lock), self.assertRaises(TimeoutError), file_lock(lock):
            self.fail("second lock unexpectedly acquired")
        with file_lock(lock):
            self.assertTrue(lock.exists())

    @patch.dict("os.environ", {"LAMBDA_API_KEY": "credential"})
    def test_child_environment_omits_credential(self):
        self.assertNotIn("LAMBDA_API_KEY", environment(self.root / "temp"))


if __name__ == "__main__":
    unittest.main()
