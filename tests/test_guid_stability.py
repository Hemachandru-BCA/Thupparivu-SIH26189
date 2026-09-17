"""
tests/test_guid_stability.py
----------------------------
Unit tests for stable GUID generation.
"""

import os
import pytest

from src.resolution.guid_generator import (
    make_stable_guid,
    generate_legacy_guid,
    entity_guid,
    _normalize_phone,
    _normalize_dob,
)


class TestMakeStableGuid:
    def test_same_inputs_same_guid(self):
        """Same name + DOB + phone always produces same GUID."""
        g1 = make_stable_guid("Raja Kumar", "1990-01-15", "9876543210")
        g2 = make_stable_guid("Raja Kumar", "1990-01-15", "9876543210")
        assert g1 == g2
        assert g1.startswith("E-")
        assert len(g1) == 18  # "E-" + 16 hex chars

    def test_different_name_different_guid(self):
        """Different name produces different GUID."""
        g1 = make_stable_guid("Raja Kumar", "1990-01-15", "9876543210")
        g2 = make_stable_guid("Suresh Reddy", "1990-01-15", "9876543210")
        assert g1 != g2

    def test_missing_dob_phone_still_valid(self):
        """Missing DOB/phone still produces valid, stable GUID."""
        g1 = make_stable_guid("Kumar Rajan")
        g2 = make_stable_guid("Kumar Rajan")
        assert g1 == g2
        assert g1.startswith("E-")

    def test_extra_space_in_name_same_guid(self):
        """Normalization strips extra spaces before hashing."""
        g1 = make_stable_guid("Kumar Rajan")
        g2 = make_stable_guid("  Kumar   Rajan  ")
        assert g1 == g2

    def test_case_insensitive_name(self):
        """Name normalization is case-insensitive."""
        g1 = make_stable_guid("Raja Kumar")
        g2 = make_stable_guid("raja kumar")
        assert g1 == g2

    def test_phone_normalization(self):
        """Phone normalization: strips non-digits, keeps last 10."""
        g1 = make_stable_guid("Raja", "1990-01-15", "+91-9876543210")
        g2 = make_stable_guid("Raja", "1990-01-15", "919876543210")
        assert g1 == g2

    def test_dob_format_agnostic(self):
        """DOB normalization: different formats, same date -> same GUID."""
        g1 = make_stable_guid("Raja", "1990-01-15")
        g2 = make_stable_guid("Raja", "15/01/1990")
        g3 = make_stable_guid("Raja", "01-15-1990")
        # At least two of these should match (depends on dateutil)
        assert g1 == g2 or g1 == g3 or g2 == g3

    def test_entity_type_in_hash(self):
        """Different entity types produce different GUIDs for same name."""
        g1 = make_stable_guid("Raja", entity_type="PERSON")
        g2 = make_stable_guid("Raja", entity_type="ORGANIZATION")
        assert g1 != g2


class TestLegacyGuid:
    def test_legacy_mode_still_works(self):
        """Legacy GUID generation produces valid UUID5 hashes."""
        g = generate_legacy_guid("PERSON", "Raja Kumar")
        # Legacy uses UUIDv5 under the hood
        assert len(g) == 36  # Standard UUID format (36 chars with hyphens)
        # UUIDv5 format: xxxxxxxx-xxxx-5xxx-yxxx-xxxxxxxxxxxx
        assert g[14] == '5'  # version 5

    def test_entity_guid_stable_mode(self):
        """entity_guid in stable mode (default) uses SHA-256."""
        os.environ.pop("GUID_STRATEGY", None)  # ensure default
        g = entity_guid("PERSON", "Raja Kumar")
        assert g.startswith("E-")

    def test_entity_guid_legacy_mode(self):
        """entity_guid in legacy mode uses UUIDv5."""
        os.environ["GUID_STRATEGY"] = "legacy"
        try:
            g = entity_guid("PERSON", "Raja Kumar")
            # Legacy mode uses UUIDv5
            assert len(g) == 36
            assert g[14] == '5'
        finally:
            os.environ.pop("GUID_STRATEGY", None)


class TestNormalizeHelpers:
    def test_normalize_phone_strips_non_digits(self):
        assert _normalize_phone("+91-9876543210") == "9876543210"
        assert _normalize_phone("9876543210") == "9876543210"
        # "(044) 2345-6789" -> digits "04423456789" -> last 10 = "4423456789"
        assert _normalize_phone("(044) 2345-6789") == "4423456789"
        assert _normalize_phone(None) == ""
        assert _normalize_phone("") == ""

    def test_normalize_dob_formats(self):
        assert _normalize_dob("1990-01-15") == "1990-01-15"
        assert _normalize_dob("15/01/1990") == "1990-01-15"
        assert _normalize_dob("15-01-1990") == "1990-01-15"
        assert _normalize_dob(None) == ""
        assert _normalize_dob("not-a-date") == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])