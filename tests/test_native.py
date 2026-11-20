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
from aiwork.oracle import evaluate
from aiwork.rea_selection import exported_candidates
from aiwork.schema import Check, Config
from aiwork.selection import compare
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

    def test_exported_rounds_use_report_hashes_and_no_audit_artifacts(self):
        target, candidate = b"target", b"\x7fELFcandidate"
        target_digest = hashlib.sha256(target).hexdigest()
        run = "engine/runs/sample"
        remote = "/tmp/sample"
        member = f"{run}/round-1/{'a' * 64}.elf"
        state = {"config": {"target": remote + "/program"}, "input_hashes": {"target": target_digest},
                 "report": f"{remote}/{run}/reconstruction.json"}
        for correct in (True, False):
            with self.subTest(correct=correct):
                digest = hashlib.sha256(candidate).hexdigest() if correct else "0" * 64
                report = {"target_sha256": target_digest, "rounds": [
                    {"round": 1, "candidates": [{"candidate": f"{remote}/{member}", "sha256": digest}]}]}
                archive = self.root / f"archive-{correct}.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    for name, data in (
                        ("program", target), ("result/state.json", json.dumps(state).encode()),
                        (f"{run}/analysis/analysis.json", json.dumps({"target_sha256": target_digest}).encode()),
                        (f"{run}/reconstruction.json", json.dumps(report).encode()),
                        (member, candidate), ("result/audit.json", b"sealed-marker"),
                    ):
                        entry = tarfile.TarInfo(name)
                        entry.size = len(data)
                        bundle.addfile(entry, io.BytesIO(data))
                if correct:
                    exports = exported_candidates(archive, target_digest)
                    self.assertEqual(exports, [("round-1-1", {"member": member, "sha256": digest}, candidate)])
                else:
                    with self.assertRaisesRegex(ValueError, "digest or ELF"):
                        exported_candidates(archive, target_digest)

    def test_public_ties_and_incomplete_candidates_keep_incumbent(self):
        common = {"compiled": True, "missing": [], "corpus_sha256": "digest", "runner": "offline", "total": 2}
        incumbent = {**common, "cases": [{"case": 1, "verdict": "pass"}, {"case": 2, "verdict": "stdout"}]}
        self.assertEqual(compare(incumbent, incumbent, protect_passing=False)["reason"], "tie_keeps_incumbent")
        incomplete = {**common, "cases": incumbent["cases"][:1]}
        self.assertEqual(compare(incumbent, incomplete, protect_passing=True)["reason"], "incomplete_evaluation")
        with self.assertRaisesRegex(ValueError, "different public"):
            compare(incumbent, {**incumbent, "corpus_sha256": "changed"}, protect_passing=True)

    def test_public_case_timeouts_do_not_truncate_the_suite_budget(self):
        write_json(self.root / "examples.json", [{"stdin": str(i), "stdout": "ok"} for i in range(3)])
        observed = {"code": 0, "stdout": "ok", "stderr": "", "elapsed": 1,
                    "timed_out": False, "truncated": False}
        with (
            patch("aiwork.oracle.monotonic", side_effect=[0, 1, 2, 3]),
            patch("aiwork.oracle.invoke", return_value=observed) as invoke,
        ):
            check = Check(("./candidate",), timeout=1, oracle="examples.json")
            score = evaluate(check, self.root, self.root, self.root, "offline", 20, None, public=True)
        self.assertEqual(score["passed_cases"], 3)
        self.assertTrue(all(call.args[0].timeout == 1 for call in invoke.call_args_list))

    def test_public_traceback_retains_exception_without_exposing_sealed_feedback(self):
        write_json(self.root / "cases.json", [{"stdout": "ok", "stderr": ""}])
        diagnostic = "Traceback (most recent call last):\n" + "frame details\n" * 50 + "TypeError: missing datetime argument\n"
        observed = {"code": 1, "stdout": "", "stderr": diagnostic, "elapsed": 1,
                    "timed_out": False, "truncated": False}
        check = Check(("./candidate",), oracle="cases.json")
        with patch("aiwork.oracle.invoke", return_value=observed):
            public = evaluate(check, self.root, self.root, self.root, "offline", 20, None, public=True)
            sealed = evaluate(check, self.root, self.root, self.root, "offline", 20, None)
        excerpt = public["discrepancies"][0]["observed"]["stderr"]
        self.assertLessEqual(len(excerpt), 160)
        self.assertIn("Traceback", excerpt)
        self.assertIn("TypeError: missing datetime argument", excerpt)
        self.assertNotIn("discrepancies", sealed)
        self.assertNotIn("missing datetime argument", str(sealed))

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
