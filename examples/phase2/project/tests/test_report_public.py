import unittest

from parcel.report import page


class ReportSmokeTests(unittest.TestCase):
    def test_paging_has_no_duplicate_or_dropped_ids(self):
        entries = [{"timestamp": 20, "id": i} for i in range(5)]
        one, marker = page(entries, limit=3)
        two, marker = page(entries, after=marker, limit=3)
        self.assertEqual(one + two, entries)
        self.assertIsNone(marker)

    def test_no_cursor_when_final_page_is_full(self):
        entries = [{"timestamp": 20, "id": 1}, {"timestamp": 21, "id": 2}]
        visible, marker = page(entries, limit=2)
        self.assertEqual(visible, entries)
        self.assertIsNone(marker)

    def test_zero_size_page(self):
        self.assertEqual(page([{"timestamp": 30, "id": 2}], limit=0), ([], None))
