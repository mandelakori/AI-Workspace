import unittest

from parcel.report import page


class ReportTests(unittest.TestCase):
    def test_equal_timestamps_across_pages(self):
        rows = [{"timestamp": 10, "id": i} for i in reversed(range(4))]
        rows.append({"timestamp": 11, "id": 0})
        first, cursor = page(rows, limit=2)
        second, next_cursor = page(rows, after=cursor, limit=2)
        third, final_cursor = page(rows, after=next_cursor, limit=2)
        self.assertEqual([r["id"] for r in first + second + third], [0, 1, 2, 3, 0])
        self.assertIsNone(final_cursor)

    def test_exact_last_page_has_no_cursor(self):
        rows = [{"timestamp": 10, "id": 1}, {"timestamp": 10, "id": 2}]
        visible, cursor = page(rows, limit=2)
        self.assertEqual(visible, rows)
        self.assertIsNone(cursor)
