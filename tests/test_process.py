from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from time import monotonic, sleep
import unittest

from aiwork.lock import file_lock
from aiwork.process import OUTPUT_LIMIT, environment, kill_tree, owned_process, run


class OwnershipTests(unittest.TestCase):
    def test_bounded_large_trace_preserves_final_usage_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = ("import json; print(json.dumps({'tool':'read','output':'x'*"+str(OUTPUT_LIMIT+64)+"})); "
                      "print(json.dumps({'type':'step_finish','tokens':{'input':17,'output':9}}))")
            command = [sys.executable, "-c", script]
            bounded = run(command, root, 10, environment(root/"default-home"))
            self.assertTrue(bounded.truncated)
            self.assertLessEqual(len(bounded.stdout.encode()), OUTPUT_LIMIT)
            complete = run(command, root, 10, environment(root/"trace-home"), output_limit=2*OUTPUT_LIMIT)
            self.assertFalse(complete.truncated)
            self.assertEqual(complete.code, 0)
            rows = [json.loads(line) for line in complete.stdout.splitlines()]
            self.assertEqual(rows[-1]["tokens"], {"input":17,"output":9})

    def test_trace_limit_is_validated_before_process_launch(self):
        for limit in (0, -1, True, 17*OUTPUT_LIMIT):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, "output_limit"):
                run(["unavailable-program"], Path.cwd(), 1, {}, output_limit=limit)

    @unittest.skipUnless(os.name == "nt", "Windows launcher ownership")
    def test_killing_venv_worker_releases_descendant_lock_and_preserves_other_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = root / "owned.lock"
            ready = root / "child.json"
            child_script = (
                "import json,os,sys,time; from pathlib import Path; from aiwork.lock import file_lock; "
                "scope=file_lock(Path(sys.argv[1])); scope.__enter__(); "
                "Path(sys.argv[2]).write_text(json.dumps({'pid':os.getpid(),'parent':os.getppid()})); time.sleep(60)"
            )
            launch = (
                "import subprocess,sys,time; "
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],*sys.argv[2:]]); time.sleep(60)"
            )
            with owned_process([sys.executable, "-c", "import time; time.sleep(60)"]) as bystander:
                with owned_process([sys.executable, "-c", launch, child_script, str(lock), str(ready)]) as child:
                    deadline = monotonic() + 10
                    while not ready.exists() and child.poll() is None and monotonic() < deadline:
                        sleep(0.05)
                    self.assertTrue(ready.is_file())
                    identity = json.loads(ready.read_text())
                    self.assertNotEqual(identity["pid"], child.pid)
                    with self.assertRaises(TimeoutError), file_lock(lock):
                        pass
                    kill_tree(child)
                    child.wait(timeout=5)
                    with file_lock(lock, timeout=5):
                        pass
                    self.assertIsNone(bystander.poll())

    def test_timeout_drains_descendant_output_without_hanging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            code = (
                "import subprocess,sys,time; "
                "subprocess.Popen([sys.executable,'-c','import time; print(123,flush=True); time.sleep(60)']); "
                "time.sleep(60)"
            )
            result = run([sys.executable, "-c", code], root, 2, environment(root/"home"))
            self.assertTrue(result.timed_out)
            self.assertLess(result.elapsed, 9)
