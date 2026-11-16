import unittest
from reading import reading
from summary import summarize


class ReadingTests(unittest.TestCase):
    def test_invalid(self):
        with self.assertRaises(ValueError):
            reading(True)

    def test_nonempty(self):
        self.assertEqual(summarize([2, 4]), {"count": 2, "total": 6, "mean": 3})
