import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aiwork.controller import Controller, write_json
from aiwork.hierarchy import digest
from aiwork.repair_benchmark import implementation_hashes, load_benchmark, remote_plan, run_a100
from aiwork.schema import Check, Config, Profile, Task
from aiwork.workspace import inventory


class RepairBenchmarkTests(unittest.TestCase):
    def test_approved_driver_bounds_requests_and_rolls_back_sanitizer_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root/"bundle"
            bundle.mkdir()
            ssh = {"alias": "aisak", "remote_port": 18080}
            profile = Profile("a100-existing", "fixture", "http://127.0.0.1:18882/v1", location="a100")
            write_json(bundle/"a100-prepared.json", {"profile": asdict(profile), "ssh": ssh})
            entries = {}
            for name in ("framing", "validation", "balance"):
                source = bundle/name/"start"
                source.mkdir(parents=True)
                (source/(name+".c")).write_text("preserved starting source", encoding="utf-8")
                (source/"contract.h").write_text("public contract", encoding="utf-8")
                write_json(source/"cases.json", [{"stdin": "public", "stdout": "ok"}])
                task = Task("Repair the component", source, "agent", "repair", (name+".c", "contract.h", "cases.json"),
                            (name+".c",), (Check(("gcc", name+".c", "-o", "probe")), Check(("./probe",))),
                            location="local", attempts=2, mode="engineering", write_roots=(name+".c",),
                            agent_role="debugging", source_context=("contract.h",), source_patch=True,
                            public_cases="cases.json", rank_public=True, attempt_limit=2)
                specification = asdict(task)
                specification["workspace"] = "."
                entries[name] = {"task": specification, "start": name+"/start"}
            manifest = {"runner": "offline", "components": entries, "inventory": inventory(bundle),
                        "implementation_sha256": implementation_hashes()}
            write_json(root/"manifest.json", manifest)
            (root/"manifest.sha256").write_text(digest(manifest), encoding="ascii")

            def measured(task, source, destination, image, deadline):
                initial = destination.name == "start"
                first = destination.parent.name == "attempt-001"
                return {"runner": image, "corpus_sha256": "same-public-corpus", "total": 2, "missing": [],
                        "compiled": True, "sanitizer_required": True, "sanitizer_passed": not first,
                        "public_passed": not initial and not first, "passed_cases": 1 if initial else 2,
                        "cases": [{"case": 1, "verdict": "pass"},
                                  {"case": 2, "verdict": "stdout" if initial else "pass"}],
                        "behavior": {"discrepancies": []}, "sanitizer": {"passed": not first}}

            def proposal(controller, task, profile, work, attempt, deadline, findings, **kwargs):
                self.assertTrue(kwargs["remote_authorized"])
                file = work/task.deliverables[0]
                # The first candidate passed ordinary behavior but failed sanitization.
                # Attempt two must start from the retained source, not that rejected candidate.
                self.assertEqual(file.read_text(), "preserved starting source")
                file.write_text("mock-model-"+attempt.name, encoding="utf-8")

            controller = Controller(Config(root/"original-state", ssh=ssh))
            with (patch("aiwork.repair_benchmark.pin_runner", return_value="offline"),
                  patch("aiwork.repair_benchmark.evaluate_candidate", side_effect=measured),
                  patch("aiwork.repair_benchmark.propose_source", side_effect=proposal) as model):
                report = run_a100(controller, root, root/"run", digest(manifest))
            self.assertEqual(model.call_count, 6)
            self.assertEqual(report["inference_requests"], 6)
            for name, outcome in report["components"].items():
                self.assertEqual(outcome["attempts"][0]["selection"]["reason"], "sanitizer_failure")
                self.assertTrue(outcome["attempts"][1]["selection"]["accepted"])
                self.assertEqual((Path(outcome["selected"])/(name+".c")).read_text(), "mock-model-attempt-002")
                self.assertEqual((bundle/name/"start"/(name+".c")).read_text(), "preserved starting source")

    def test_offline_plan_binds_frozen_inputs_and_remote_dispatch_requires_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root/"bundle"
            bundle.mkdir()
            write_json(bundle/"a100-prepared.json", {"execution_allowed": False})
            (bundle/"source.c").write_text("starting source", encoding="utf-8")
            manifest = {"runner": "offline", "components": {}, "inventory": inventory(bundle),
                        "implementation_sha256": implementation_hashes()}
            write_json(root/"manifest.json", manifest)
            (root/"manifest.sha256").write_text(digest(manifest), encoding="ascii")
            controller = Controller(Config(root/"state"))
            with (patch("aiwork.repair_benchmark.pin_runner") as runner,
                  patch("aiwork.repair_benchmark.propose_source") as propose):
                plan = remote_plan(root)
                self.assertEqual(plan["inference_requests_executed"], 0)
                self.assertFalse(plan["configuration"]["execution_allowed"])
                with self.assertRaisesRegex(ValueError, "explicit remote approval"):
                    run_a100(controller, root, root/"run", "unapproved")
                runner.assert_not_called()
                propose.assert_not_called()
            self.assertFalse((root/"run").exists())
            (bundle/"source.c").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frozen benchmark"):
                load_benchmark(root)
