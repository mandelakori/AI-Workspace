import unittest
from report import status


class ReportTests(unittest.TestCase):
    def test_report_integrates_both_components(self):
        self.assertEqual(status("west_hall", 68), "West Hall: 20.0 C")
