from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from aiwork.controller import write_json
from aiwork.schema import Check


spec = importlib.util.spec_from_file_location(
    "component_grading", Path(__file__).resolve().parents[1] / "examples/phase52/grade_components.py")
grading = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grading)


class ComponentGradingTests(unittest.TestCase):
    def test_each_private_case_has_its_own_timeout_and_incomplete_suites_cannot_verify(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases.json"
            write_json(cases, [{"stdin": str(i), "stdout": "ok"} for i in range(4)])
            observed = {"cases": [{"verdict": "pass"}]}
            with patch.object(grading, "evaluate", return_value=observed) as evaluate:
                report = grading.evaluate_component(Check(("./probe",), timeout=1), root, cases,
                                                    root / "results", "offline", suite_timeout=30)
            self.assertTrue(report["complete"])
            self.assertEqual(report["completed"], 4)
            self.assertEqual(evaluate.call_count, 4)
            for call in evaluate.call_args_list:
                self.assertEqual(call.args[0].timeout, 1)
                self.assertEqual(call.args[5], 1)
            with patch.object(grading, "evaluate", return_value={"cases": []}):
                incomplete = grading.evaluate_component(Check(("./probe",), timeout=1), root, cases,
                                                        root / "incomplete", "offline")
            self.assertEqual(incomplete["status"], "inconclusive")
