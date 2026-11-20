"""Public specification review for datetime objects whose timezone has no UTC offset."""
from datetime import date, datetime, tzinfo
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path("src").resolve()))
import click


class NoOffset(tzinfo):
    def utcoffset(self, value):
        return None

    def dst(self, value):
        return None


class PublicObjectPolicyTests(unittest.TestCase):
    def test_require_rejects_no_offset_object(self):
        value = datetime(2024, 7, 19, 8, 31, tzinfo=NoOffset())
        with self.assertRaises(click.BadParameter):
            click.ISODateTime(require_timezone=True).convert(value, None, None)

    def test_normalize_rejects_no_offset_object(self):
        value = datetime(2024, 7, 20, 8, 32, tzinfo=NoOffset())
        with self.assertRaises(click.BadParameter):
            click.ISODateTime(normalize_to_utc=True).convert(value, None, None)

    def test_combined_policy_rejects_no_offset_object(self):
        value = datetime(2024, 7, 21, 8, 33, tzinfo=NoOffset())
        with self.assertRaises(click.BadParameter):
            click.ISODateTime(require_timezone=True, normalize_to_utc=True).convert(value, None, None)

    def test_default_preserves_naive_object_identity(self):
        value = datetime(2024, 7, 22, 8, 34, tzinfo=NoOffset())
        self.assertIs(click.ISODateTime().convert(value, None, None), value)

    def test_date_object_is_not_a_datetime(self):
        with self.assertRaises(click.BadParameter):
            click.ISODateTime().convert(date(2024, 7, 23), None, None)


if __name__ == "__main__":
    unittest.main()
