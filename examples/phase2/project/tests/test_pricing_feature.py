import unittest

from parcel.model import QuoteRequest
from parcel.service import quote


class InsuranceAcceptance(unittest.TestCase):
    def test_insurance_adds_rounded_charge(self):
        self.assertEqual(quote(QuoteRequest(101, 5001)).total_cents, 356)

    def test_insurance_is_optional(self):
        self.assertEqual(quote(QuoteRequest(101)).total_cents, 280)
