import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from aiwork.native_recovery import recover
from aiwork.schema import Config


class NativeRecoveryTests(unittest.TestCase):
    def test_only_static_evidence_reaches_agent_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "static/attempt-001"
            output.mkdir(parents=True)
            program = b"self-authored test artifact"
            digest = hashlib.sha256(program).hexdigest()
            (output.parent / "intake.json").write_text(
                json.dumps({"inventory": {"toy.elf": {"sha256": digest}}}), encoding="utf-8")
            analysis = output / "analysis.json"
            analysis.write_text(json.dumps({"specialist": "ghidra", "binary": "toy.elf",
                                            "decompilation": "int main(void)"}), encoding="utf-8")
            archive = root / "evidence.tar.gz"
            state = {"status": "complete", "audit_total": 1, "input_hashes": {"target": digest}}
            case = {"case": {"stdin": "hidden\n"}, "original": {"status": "returned",
                      "stdout": "expected\n", "stderr": "", "returncode": 0, "files": {}}}
            with tarfile.open(archive, "w:gz") as bundle:
                for name, data in (("program", program),
                                   ("result/state.json", json.dumps(state).encode()),
                                   ("result/audit-0/00000.json", json.dumps(case).encode())):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    bundle.addfile(member, io.BytesIO(data))
            controller = Mock()
            controller.config = Config(root / "state")
            controller.submit_task.return_value = "sample"
            controller.run_submitted.return_value = {"status": "verified"}
            recover(controller, archive, analysis, "sample-profile")
            task = controller.submit_task.call_args.args[0]
            self.assertEqual([p.name for p in task.workspace.iterdir()], ["function-evidence.txt"])
            self.assertEqual(task.checks[0].argv[0], "gcc")
            self.assertEqual(task.checks[1].oracle, "cases.json")
            self.assertIn("expected", (task.verification_dir / "cases.json").read_text())
            self.assertEqual(controller.submit_task.call_args.kwargs["profile_id"], "sample-profile")
