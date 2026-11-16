import unittest

from parcel.model import QuoteRequest
from parcel.service import quote


class PricingTests(unittest.TestCase):
    def test_incremental_price(self):
        self.assertEqual(quote(QuoteRequest(100)).total_cents, 265)
        self.assertEqual(quote(QuoteRequest(101)).total_cents, 280)

    def test_rejects_zero(self):
        with self.assertRaises(ValueError):
            QuoteRequest(0)
