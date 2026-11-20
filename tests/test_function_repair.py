import json
from dataclasses import asdict
from pathlib import Path
import tempfile
from time import monotonic
import unittest
from unittest.mock import patch

from aiwork.controller import Controller, write_json
from aiwork.function_repair import feedback, fully_passed, function_span, integrate, propose, replace_function, run
from aiwork.hierarchy import digest
from aiwork.repair_benchmark import implementation_hashes
from aiwork.schema import Check, Config, Profile, Task
from aiwork.workspace import inventory


class FunctionRepairTests(unittest.TestCase):
    signature = "int target(int value)"
    source = '#include <stdio.h>\nint helper(void) {return 2;}\nint target(int value) {\n/* } */ puts("{"); return value;\n}\n/* tail */\n'

    def test_replacement_changes_only_function_and_handles_literals_and_comments(self):
        start, end = function_span(self.source, self.signature)
        replacement = 'int target(int value) { char brace = \'}\'; return value + brace; }'
        result, receipt = replace_function(self.source, self.signature, {"function": replacement})
        self.assertEqual(result[:start], self.source[:start])
        self.assertEqual(result[start+len(replacement):], self.source[end:])
        self.assertNotEqual(receipt["before_sha256"], receipt["after_sha256"])
        self.assertIn("int helper(void) {return 2;}", result)

    def test_replacement_rejects_signature_changes_extra_scope_and_unbounded_source(self):
        original = self.source
        begin, end = function_span(original, self.signature)
        for function in (
            "int target(int renamed) { return renamed; }",
            "long target(int value) {return value;}",
            "int target(int value) {return value;} int helper2(void) {return 3;}",
            "#include <stdlib.h>\nint target(int value) {return value;}",
            "int target(int value) {\n#define X 1\nreturn X;}",
            "int target(int value) {return value;", original[begin:end],
            "int target(int value) {return value;}\0", "x"*8001,
            "int target(int value) {return value;}\\\nint extra;",
        ):
            with self.subTest(function=function[:60]), self.assertRaises(ValueError):
                replace_function(original, self.signature, {"function": function})
        self.assertEqual(self.source, original)
        with self.assertRaises(ValueError):
            function_span(original+original, self.signature)
        with self.assertRaises(ValueError):
            replace_function(original, self.signature, {"function": "x", "path": "other.c"})

    def test_compiler_diagnostics_survive_into_retry_feedback(self):
        candidate = {"compilation": {"stderr": "public compiler error: missing declaration"},
                     "behavior": None, "sanitized_behavior": None}
        result = feedback(candidate, {"accepted": False, "reason": "build_regression"})
        self.assertIn("missing declaration", result["compiler_stderr"])
        self.assertEqual(result["public_discrepancies"], [])

    def test_remote_worker_and_unqualified_integration_are_blocked_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            controller = Controller(Config(root/"state"))
            profile = Profile("remote", "fixture", "http://127.0.0.1:18882/v1", location="a100")
            task = Task("repair", root, "agent", "fixture", (), (), ())
            with patch("aiwork.function_repair.request") as request:
                with self.assertRaisesRegex(ValueError, "local only"):
                    propose(controller, profile, task, self.signature, root, root, {}, {}, monotonic()+5)
                request.assert_not_called()
            (root/"execution").mkdir()
            write_json(root/"execution/report.json", {"components": {"framing": {"public": {"public_passed": False}}}})
            with self.assertRaisesRegex(ValueError, "blocked"):
                integrate(controller, root)
            self.assertFalse((root/"integration-inputs").exists())
            self.assertFalse(fully_passed({"public_passed": True, "compiled": False, "sanitizer_passed": True}))

    def test_request_budget_is_reserved_and_failed_candidates_do_not_replace_seeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = Profile("fixture", "fixture", "http://127.0.0.1:11434/v1")
            controller = Controller(Config(root/"state", (profile,)))
            entries = {}
            tasks = {}
            for name in ("framing", "validation", "balance"):
                source = root/"seeds"/name
                source.mkdir(parents=True)
                (source/(name+".c")).write_text("seed", encoding="utf-8")
                (source/"contract.h").write_text("public contract", encoding="utf-8")
                write_json(source/"cases.json", [{"stdin": "public", "stdout": "ok"}])
                task = Task("Repair", source, "agent", "repair", (name+".c", "contract.h", "cases.json"),
                            (name+".c",), (Check(("gcc", name+".c", "-o", "probe")), Check(("./probe",))),
                            location="local", attempts=2, mode="engineering", write_roots=(name+".c",),
                            agent_role="debugging", source_context=("contract.h",), public_cases="cases.json",
                            rank_public=True, attempt_limit=2)
                specification = asdict(task)
                specification["workspace"] = "."
                entries[name] = {"task": specification, "signature": self.signature}
                tasks[name] = task

            def receipt(task, source, count, safe=True):
                total = 10 if task.deliverables == ("balance.c",) else 2
                passed = count == total
                return {"runner": "offline", "corpus_sha256": "public", "total": total, "missing": [],
                        "inventory": inventory(source), "compiled": True, "compilation": {"stderr": ""},
                        "sanitizer_required": True, "sanitizer_passed": safe, "sanitizer": {"passed": safe},
                        "public_passed": passed and safe, "passed_cases": count,
                        "behavior": {"passed": passed, "discrepancies": []},
                        "sanitized_behavior": {"passed": passed, "discrepancies": []},
                        "cases": [{"case": i, "verdict": "pass" if i <= count else "stdout"}
                                  for i in range(1, total+1)]}

            (root/"balance-import-verification").mkdir()
            write_json(root/"balance-import-verification/receipt.json",
                       receipt(tasks["balance"], root/"seeds/balance", 9))
            plan = {"profile": asdict(profile), "runner": "offline", "entries": entries,
                    "seed_inventory": inventory(root/"seeds"), "implementation_sha256": implementation_hashes()}
            write_json(root/"campaign.json", plan)
            calls = []

            def worker(controller, profile, task, signature, work, attempt, incumbent, previous, deadline):
                calls.append(attempt)
                reserved = json.loads((root/"execution/report.json").read_bytes())["requests"]
                self.assertEqual(reserved, len(calls))
                target = work/task.deliverables[0]
                self.assertEqual(target.read_text(), "seed")
                target.write_text("mock-model-"+attempt.name, encoding="utf-8")

            def measured(task, source, destination, image, deadline):
                if destination.name == "initial":
                    return receipt(task, source, 1)
                total = 10 if task.deliverables == ("balance.c",) else 2
                return receipt(task, source, total, destination.parent.name != "attempt-001")

            with (patch("aiwork.function_repair.pin_runner", return_value="offline"),
                  patch("aiwork.function_repair.propose", side_effect=worker) as model,
                  patch("aiwork.function_repair.evaluate_candidate", side_effect=measured)):
                result = run(controller, root, digest(plan))
                self.assertEqual(result["requests"], 6)
                self.assertEqual(model.call_count, 6)
                for name, row in result["components"].items():
                    self.assertEqual(row["attempts"][0]["selection"]["reason"], "sanitizer_failure")
                    self.assertTrue(row["attempts"][1]["selection"]["accepted"])
                    self.assertEqual((root/"seeds"/name/(name+".c")).read_text(), "seed")
                with self.assertRaises(FileExistsError):
                    run(controller, root, digest(plan))
                self.assertEqual(model.call_count, 6)
