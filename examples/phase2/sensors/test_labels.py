import unittest
from labels import zone_label


class LabelsTests(unittest.TestCase):
    def test_trims_and_formats(self):
        self.assertEqual(zone_label("  roof_sensor  "), "Roof Sensor")
        self.assertEqual(zone_label("north_wing"), "North Wing")
