import unittest
from units import rounded_kib


class UnitTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual([rounded_kib(n) for n in (0, 1, 1024, 1025)], [0, 1, 1, 2])
