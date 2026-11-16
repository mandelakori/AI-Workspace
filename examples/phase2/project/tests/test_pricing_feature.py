import unittest

from parcel.model import Quote, QuoteRequest
from parcel.service import quote


class InsuranceAcceptance(unittest.TestCase):
    def test_insurance_adds_rounded_charge(self):
        self.assertEqual(quote(QuoteRequest(101, 5001)).total_cents, 356)

    def test_insurance_is_optional(self):
        self.assertEqual(quote(QuoteRequest(101)), Quote(280, 280))
        self.assertEqual(quote(QuoteRequest(101)).insurance_cents, 0)

    def test_minimum_and_larger_coverage(self):
        self.assertEqual(quote(QuoteRequest(101, 11)).insurance_cents, 75)
        self.assertEqual(quote(QuoteRequest(101, 6000)).insurance_cents, 90)

    def test_rejects_invalid_declared_values(self):
        for value in (-7, 1_000_005, "12"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                QuoteRequest(101, value)
