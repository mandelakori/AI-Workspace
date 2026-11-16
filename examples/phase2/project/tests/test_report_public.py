import unittest

from parcel.report import page


class ReportSmokeTests(unittest.TestCase):
    def test_paging_has_no_duplicate_or_dropped_ids(self):
        entries = [{"timestamp": 20, "id": i} for i in range(5)]
        one, marker = page(entries, limit=3)
        two, marker = page(entries, after=marker, limit=3)
        self.assertEqual(one + two, entries)
        self.assertIsNone(marker)
