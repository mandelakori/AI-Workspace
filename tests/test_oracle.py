import json
import os
import tempfile
import unittest
from pathlib import Path

from aiwork.oracle import evaluate, load_cases
from aiwork.schema import Check


class OracleTests(unittest.TestCase):
    def test_rejects_private_path_in_candidate_command(self):
        with self.assertRaises(ValueError):
            Check.read({"argv": ["{python}", "{verification}/private.py"], "oracle": "cases.json"})

    def test_rejects_noninteger_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            cases = Path(temporary) / "cases.json"
            cases.write_text('[{"code":true,"stdout":"ok"}]', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_cases(cases)

    @unittest.skipUnless(os.getenv("AIWORK_TEST_DOCKER_IMAGE"), "requires Linux Docker")
    def test_candidate_cannot_read_private_files_and_outputs_are_redacted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "work"
            private = root / "private"
            work.mkdir()
            private.mkdir()
            (private / "cases.json").write_text(json.dumps([
                {"stdin": "5", "stdout": "isolated 10\n"}, {"stdin": "6", "stdout": "isolated 12\n"}
            ]), encoding="utf-8")
            (private / "secret.txt").write_text("verifier-only", encoding="utf-8")
            (work / "candidate.py").write_text(
                "from pathlib import Path\n"
                "assert not Path('/verification').exists()\n"
                "assert not Path('/private').exists()\n"
                "assert not Path('/var/run/docker.sock').exists()\n"
                "assert {p.name for p in Path('/sys/class/net').iterdir()} == {'lo'}\n"
                "try:\n"
                "    Path('changed').write_text('unexpected write')\n"
                "except OSError:\n"
                "    pass\n"
                "else:\n"
                "    raise AssertionError('writable candidate mount')\n"
                "print('isolated', int(input()) * 2)\n", encoding="utf-8")
            check = Check(("{python}", "candidate.py"), 25, oracle="cases.json")
            outcome = evaluate(check, work, root / "home", private,
                               os.environ["AIWORK_TEST_DOCKER_IMAGE"], 25, None)
            self.assertTrue(outcome["passed"], outcome)
            self.assertEqual(outcome["passed_cases"], 2)
            self.assertNotIn("isolated 10", json.dumps(outcome))
            self.assertNotIn("verifier-only", json.dumps(outcome))
            self.assertFalse((work / "changed").exists())
