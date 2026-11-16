import unittest
from units import fahrenheit_to_celsius


class UnitsTests(unittest.TestCase):
    def test_freezing_and_boiling(self):
        self.assertEqual(fahrenheit_to_celsius(32), 0)
        self.assertEqual(fahrenheit_to_celsius(212), 100)

    def test_negative(self):
        self.assertEqual(fahrenheit_to_celsius(-40), -40)
