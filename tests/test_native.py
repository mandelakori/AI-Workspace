import hashlib
import contextlib
import io
import json
import tarfile
import tempfile
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from aiwork.campaign import allocation_receipt, stage_fixture, static_evidence
from aiwork.controller import Controller, write_json
from aiwork.native import grade, read_inputs
from aiwork.native_feedback import run_public_checks
from aiwork.schema import Check, Config
from aiwork.workspace import inventory


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_public_feedback_shows_at_most_three_reproducers(self):
        public = self.root / "examples.json"
        write_json(public, [
            {"name": f"public-{i}", "stdin": f"input-{i}", "argv": [], "code": 0,
             "stdout": f"expected-{i}\n", "stderr": ""}
            for i in range(1, 6)
        ])
        build = {"argv": [sys.executable, "-c", "pass"], "cwd": "", "timeout": 5}
        run = {**build, "argv": [sys.executable, "-c", "print('observed')"]}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(run_public_checks(public, build, run), 1)
        summary = output.getvalue()
        self.assertIn("expected-1", summary)
        self.assertIn("observed", summary)
        self.assertIn("input-3", summary)
        self.assertNotIn("input-4", summary)
        self.assertIn("passed: 0/5", summary)

    def test_campaign_receipt_binds_a_private_phase_four_directory(self):
        record = allocation_receipt("/tmp/aiwork-p4.Ab12CD34\nubuntu 1000 700 29 418")
        self.assertEqual(record["remote_owner"], "ubuntu")
        self.assertEqual(record["remote_uid"], 1000)
        self.assertEqual(record["remote_inode"], 418)
        for unexpected in ("/tmp/aiwork-p3.Ab12CD34\nubuntu 1000 700 29 418",
                           "/tmp/aiwork-p4.Ab12CD34\nubuntu 1000 755 29 418"):
            with self.assertRaises(ValueError):
                allocation_receipt(unexpected)

    def test_target_descriptor_supports_pinned_elf_and_fixed_file_arguments(self):
        (self.root / "target.elf").write_bytes(b"\x7fELFdata")
        for name in ("dev", "audit"):
            (self.root / f"{name}.jsonl").write_text("{}", encoding="utf-8")
        policy = self.root / "fixture.toml"
        policy.write_text(
            'artifact = "target.elf"\ndevelopment = "dev.jsonl"\naudit = "audit.jsonl"\n'
            '[input]\nmode = "file"\nfilename = "example.txt"\nargs = ["example.txt"]\n', encoding="utf-8")
        stage = self.root / "stage"
        stage.mkdir()
        compile_argv, transport = stage_fixture(policy, stage)
        self.assertEqual(compile_argv, ())
        self.assertEqual(transport["args"], ["example.txt"])
        self.assertEqual((stage / "program").read_bytes(), (self.root / "target.elf").read_bytes())

    def test_campaign_import_binds_static_artifacts_and_excludes_audit(self):
        program, listing = b"toy program", b"static listing"
        digest = hashlib.sha256(program).hexdigest()
        metadata = {"target_sha256": digest, "format": "ELF", "unexpected": "ignore me",
                    "tools": {"objdump": {"sha256": hashlib.sha256(listing).hexdigest()}}}
        archive = self.root / "campaign.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name, value in [
                ("program", program),
                ("engine/runs/sample/analysis/analysis.json", json.dumps(metadata).encode()),
                ("engine/runs/sample/analysis/objdump.txt", listing),
                ("result/input-holdout", b"audit-only"),
            ]:
                member = tarfile.TarInfo(name)
                member.size = len(value)
                bundle.addfile(member, io.BytesIO(value))
        findings = static_evidence(archive, digest)
        self.assertEqual(findings[0]["listings"]["objdump"]["text"], listing.decode())
        self.assertNotIn("audit-only", str(findings))
        self.assertNotIn("unexpected", str(findings))
        with self.assertRaisesRegex(ValueError, "target digest"):
            static_evidence(archive, "0" * 64)

    def prepare_grade(self):
        for name in ("frozen", "target", "development"):
            (self.root / name).mkdir()
        (self.root / "frozen" / "candidate.c").write_text("candidate", encoding="utf-8")
        (self.root / "target" / "program").write_bytes(b"target")
        write_json(self.root / "development" / "cases.json", [{"stdin": "dev", "argv": [], "stdout": ""}])
        write_json(self.root / "frozen.json", inventory(self.root / "frozen"))
        write_json(self.root / "run.json", {
            "image": "offline", "target": inventory(self.root / "target"),
            "development": inventory(self.root / "development"),
            "build_candidate": asdict(Check(("gcc", "candidate.c"))),
            "candidate": asdict(Check(("./candidate",))), "reference": asdict(Check(("./program",))),
        })
        return Controller(Config(self.root / "queue"))

    def test_final_rejects_audit_overlap_before_candidate_runs(self):
        controller = self.prepare_grade()
        cases, audit = self.root / "final-inputs.json", self.root / "audit.json"
        write_json(cases, [{"name": "final", "argv": ["{python}"]}])
        write_json(audit, [{"name": "audit", "argv": ["{python}"]}])
        with patch("aiwork.native.invoke") as invoke, self.assertRaisesRegex(ValueError, "overlap"):
            grade(controller, self.root, cases, [audit], 1)
        invoke.assert_not_called()

    def test_final_uses_exact_stream_bytes_and_keeps_case_args_literal(self):
        controller = self.prepare_grade()
        cases = self.root / "final-inputs.json"
        write_json(cases, [{"name": "final", "group": "argv", "argv": ["{python}", ""]}])
        response = {"code": 0, "stdout": "ok\n", "stderr": "", "timed_out": False, "truncated": False}
        with patch("aiwork.native.invoke", side_effect=[{"passed": True}, response,
                                                       {**response, "stdout": "ok\r\n"}]) as invoke:
            result = grade(controller, self.root, cases, [], 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["counts"], {"pass": 0, "mismatch": 1, "inconclusive": 0})
        self.assertEqual(invoke.call_args.kwargs["extra_args"], ("{python}", ""))
        self.assertTrue(invoke.call_args.kwargs["sealed"])
        record = Path(result["artifacts"]) / "observations" / "0000.json"
        self.assertEqual(json.loads(record.read_bytes())["candidate"]["stdout"], "ok\r\n")

    def test_duplicate_invocations_fail_even_when_named_differently(self):
        path = self.root / "cases.json"
        write_json(path, [{"name": "one"}, {"name": "two", "argv": [], "stdin": ""}])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            read_inputs(path, 32)
