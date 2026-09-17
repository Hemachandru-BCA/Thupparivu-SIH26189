"""
tests/test_transliteration.py
-----------------------------
Unit tests for the Indian name transliteration module.
"""

import pytest

from src.resolution.transliteration import (
    detect_script,
    to_latin_fold,
    name_similarity,
)


class TestDetectScript:
    def test_tamil_script(self):
        assert detect_script("ராஜா") == "tamil"
        assert detect_script("ராஜகுமார்") == "tamil"
        assert detect_script("முருகன்") == "tamil"

    def test_devanagari_script(self):
        assert detect_script("राजा") == "devanagari"
        assert detect_script("सुब्रमण्यम") == "devanagari"
        assert detect_script("मुरुगन") == "devanagari"

    def test_latin_script(self):
        assert detect_script("Raja") == "latin"
        assert detect_script("Subramaniam") == "latin"
        assert detect_script("Kumar Rajan") == "latin"

    def test_unknown_script(self):
        assert detect_script("") == "unknown"
        assert detect_script("💥") == "unknown"
        assert detect_script("123") == "unknown"


class TestToLatinFold:
    def test_tamil_to_latin(self):
        # Tamil "ராஜா" -> produces some latin output
        result = to_latin_fold("ராஜா")
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == result.lower()

    def test_devanagari_to_latin(self):
        result = to_latin_fold("राजा")
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == result.lower()

    def test_latin_vowel_fold(self):
        # "aa" -> "a", "ii" -> "i", "uu" -> "u"
        # "Raaaja" has two "aa" sequences -> "raaja" (each aa -> a)
        assert to_latin_fold("Raaaja") == "raaja"
        # "Siiita" has two "ii" sequences -> "siita" (each ii -> i)
        assert to_latin_fold("Siiita") == "siita"
        assert to_latin_fold("Guruu") == "guru"   # single uu
        # "Shaan" -> "san" (sh -> s, aa -> a) - both folds apply
        assert to_latin_fold("Shaan") == "san"
        # "Rathna" -> "ratna" (th -> t)
        assert to_latin_fold("Rathna") == "ratna"

    def test_does_not_raise_on_invalid_unicode(self):
        # Emoji and invalid chars should not raise
        result = to_latin_fold("💥invalid")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_string(self):
        assert to_latin_fold("") == ""
        assert to_latin_fold("   ") == ""

    def test_whitespace_collapse(self):
        assert to_latin_fold("Raja   Kumar") == "raja kumar"
        assert to_latin_fold("  Raja  ") == "raja"


class TestNameSimilarity:
    def test_identical_names(self):
        assert name_similarity("Raja", "Raja") == 1.0
        assert name_similarity("Subramaniam", "Subramaniam") == 1.0

    def test_subramaniam_variants(self):
        # Classic Tamil variants
        sim = name_similarity("Subramaniam", "Subramanian")
        assert sim > 0.85, f"Expected > 0.85, got {sim}"

        sim = name_similarity("Subramaniam", "Subramanyam")
        assert sim > 0.85, f"Expected > 0.85, got {sim}"

    def test_raj_kumar_reordering(self):
        # Token sort ratio handles reordering
        sim = name_similarity("Rajan Kumar", "Kumar Rajan")
        assert sim > 0.90, f"Expected > 0.90, got {sim}"

    def test_murugesan_variants(self):
        sim = name_similarity("Murugesan", "Murugesh")
        assert sim > 0.75, f"Expected > 0.75, got {sim}"

    def test_mohammed_variants(self):
        sim = name_similarity("Mohammed", "Mohammad")
        assert sim > 0.85, f"Expected > 0.85, got {sim}"

    def test_krishnan_variants(self):
        sim = name_similarity("Krishnan", "Krishnan")  # Same
        assert sim == 1.0
        sim = name_similarity("Krishnan", "Krishnan")
        assert sim == 1.0

    def test_cross_script_same_name(self):
        # If indic-transliteration is available, these might match
        # At minimum, should not raise
        sim = name_similarity("ராஜா", "Raja")
        assert 0.0 <= sim <= 1.0

    def test_different_names_low_similarity(self):
        sim = name_similarity("Raja", "Kumar")
        assert sim < 0.5

    def test_unicode_emoji_no_raise(self):
        # Should never raise on any unicode input
        sim = name_similarity("Raja💥", "Raja")
        assert 0.0 <= sim <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])