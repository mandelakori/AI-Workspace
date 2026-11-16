import contextlib
import io
import json
import unittest
from pathlib import Path

from parcel import policy
from parcel.cli import main
from parcel.model import Quote, QuoteRequest
from parcel.service import quote


class InsuranceTests(unittest.TestCase):
    def test_no_change_for_uninsured(self):
        self.assertEqual(quote(QuoteRequest(101)), Quote(280, 280))
        self.assertEqual(quote(QuoteRequest(101, 0)).insurance_cents, 0)

    def test_minimum_and_round_up(self):
        self.assertEqual(quote(QuoteRequest(101, 1)).insurance_cents, 75)
        self.assertEqual(quote(QuoteRequest(101, 5001)).insurance_cents, 76)
        self.assertEqual(quote(QuoteRequest(101, 1000000)).total_cents, 15280)

    def test_validates_bounds_and_type(self):
        for value in (-1, 1_000_001, True, 2.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                QuoteRequest(101, value)

    def test_policy_has_insurance_calculation(self):
        self.assertTrue(any(name != "base_rate_cents" and callable(fn) for name, fn in vars(policy).items()
                            if not name.startswith("_")))

    def test_cli_and_docs(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--grams", "101", "--insured-value-cents", "5001"]), 0)
        self.assertEqual(json.loads(out.getvalue()), {"base_cents": 280, "insurance_cents": 76,
                                                     "total_cents": 356})
        self.assertIn("--insured-value-cents", Path("docs/usage.md").read_text())
