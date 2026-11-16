import unittest

from units import fahrenheit_to_celsius


class ConversionTests(unittest.TestCase):
    def test_freezing(self):
        self.assertAlmostEqual(fahrenheit_to_celsius(32), 0)

    def test_boiling(self):
        self.assertAlmostEqual(fahrenheit_to_celsius(212), 100)

    def test_negative(self):
        self.assertAlmostEqual(fahrenheit_to_celsius(-40), -40)

    def test_fraction(self):
        self.assertAlmostEqual(fahrenheit_to_celsius(98.6), 37)


if __name__ == "__main__":
    unittest.main()
