import unittest
from unittest.mock import patch
from report import label


class ReportTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(label(1025), "2 KiB")

    def test_delegates_to_units(self):
        with patch("report.rounded_kib", return_value=9) as convert:
            self.assertEqual(label(17), "9 KiB")
        convert.assert_called_once_with(17)
