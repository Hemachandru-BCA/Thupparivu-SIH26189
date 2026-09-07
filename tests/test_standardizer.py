import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.preprocessing.standardizer import (
    PhoneStandardizer, DateStandardizer, LocationStandardizer, RecordStandardizer
)


class TestPhoneStandardizer(unittest.TestCase):
    def setUp(self):
        self.std = PhoneStandardizer(default_country_code="1")

    def test_dashed_us_format(self):
        result = self.std.standardize("+1-9231067245")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.e164, "+19231067245")
        self.assertEqual(result.country_code, "1")

    def test_bare_digits_no_plus(self):
        result = self.std.standardize("923-106-7245")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.e164, "+19231067245")

    def test_parenthesized_format(self):
        result = self.std.standardize("(923) 106-7245")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.e164, "+19231067245")

    def test_empty_input_is_invalid(self):
        result = self.std.standardize("")
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.e164)

    def test_too_short_is_invalid(self):
        result = self.std.standardize("12345")
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.e164)

    def test_international_prefix_preserved(self):
        result = self.std.standardize("+44-7911123456")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.country_code, "44")
        self.assertEqual(result.e164, "+447911123456")


class TestDateStandardizer(unittest.TestCase):
    def setUp(self):
        self.std = DateStandardizer()

    def test_slash_format(self):
        self.assertEqual(self.std.standardize("15/03/2025", assume_date_only=True), "2025-03-15")

    def test_iso_format_passthrough(self):
        self.assertEqual(self.std.standardize("2025-03-15", assume_date_only=True), "2025-03-15")

    def test_full_timestamp(self):
        result = self.std.standardize("2025-03-15T10:30:00")
        self.assertTrue(result.startswith("2025-03-15"))

    def test_natural_language_date(self):
        result = self.std.standardize("March 15, 2025", assume_date_only=True)
        self.assertEqual(result, "2025-03-15")

    def test_invalid_date_returns_none(self):
        self.assertIsNone(self.std.standardize("not a date at all!!"))

    def test_empty_returns_none(self):
        self.assertIsNone(self.std.standardize(""))


class TestLocationStandardizer(unittest.TestCase):
    def setUp(self):
        self.std = LocationStandardizer()

    def test_known_city_resolves_region_country(self):
        loc = self.std.standardize("3241 Main St, Grantville")
        self.assertEqual(loc.city, "Grantville")
        self.assertEqual(loc.region, "Central Province")
        self.assertEqual(loc.country, "USA")
        self.assertEqual(loc.normalized, "Grantville, Central Province, USA")

    def test_unknown_city_falls_back_gracefully(self):
        loc = self.std.standardize("1 Nowhere Rd, Atlantis")
        self.assertEqual(loc.city, "Atlantis")
        self.assertEqual(loc.region, "UNKNOWN")
        self.assertEqual(loc.country, "UNKNOWN")

    def test_empty_address(self):
        loc = self.std.standardize("")
        self.assertEqual(loc.normalized, "UNKNOWN")

    def test_single_component_address(self):
        loc = self.std.standardize("Riverport")
        self.assertEqual(loc.city, "Riverport")
        self.assertEqual(loc.region, "Coastal Province")


class TestRecordStandardizerFacade(unittest.TestCase):
    def test_bundles_all_three(self):
        facade = RecordStandardizer()
        self.assertIsInstance(facade.phone, PhoneStandardizer)
        self.assertIsInstance(facade.date, DateStandardizer)
        self.assertIsInstance(facade.location, LocationStandardizer)


if __name__ == "__main__":
    unittest.main()
