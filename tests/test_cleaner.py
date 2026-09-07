import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from src.preprocessing.cleaner import RegexNormalizer, DuplicateDetector, TextCleaningPipeline


class TestRegexNormalizer(unittest.TestCase):
    def setUp(self):
        self.norm = RegexNormalizer()

    def test_collapses_whitespace(self):
        self.assertEqual(self.norm.normalize("hello    world\n\n\tfoo"), "hello world foo")

    def test_strips_leading_trailing_whitespace(self):
        self.assertEqual(self.norm.normalize("   hello   "), "hello")

    def test_collapses_repeated_punctuation(self):
        self.assertEqual(self.norm.normalize("wait what???!!"), "wait what?!")

    def test_masks_urls(self):
        self.assertEqual(
            self.norm.normalize("check http://example.com/path?q=1 now"),
            "check [URL] now",
        )

    def test_removes_control_characters(self):
        self.assertEqual(self.norm.normalize("hello\x00\x01world"), "helloworld")

    def test_none_input_returns_empty_string(self):
        self.assertEqual(self.norm.normalize(None), "")


class TestDuplicateDetector(unittest.TestCase):
    def setUp(self):
        self.dedup = DuplicateDetector()

    def test_exact_duplicates_detected(self):
        texts = ["hello world", "hello world", "goodbye world"]
        result = self.dedup.find_duplicates(texts)
        self.assertEqual(result, [None, 0, None])

    def test_near_duplicates_ignore_punctuation_and_case(self):
        texts = ["Hello, World!", "hello world"]
        result = self.dedup.find_duplicates(texts)
        self.assertEqual(result, [None, 0])

    def test_distinct_texts_none_flagged(self):
        texts = ["alpha", "beta", "gamma"]
        result = self.dedup.find_duplicates(texts)
        self.assertEqual(result, [None, None, None])

    def test_fingerprint_is_deterministic(self):
        fp1 = self.dedup.fingerprint("Hello, World!")
        fp2 = self.dedup.fingerprint("hello world")
        self.assertEqual(fp1, fp2)


class TestTextCleaningPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = TextCleaningPipeline(text_column="text")

    def test_run_adds_expected_columns(self):
        df = pd.DataFrame({"record_id": ["a", "b"], "text": ["Hello world.", "Hello   world."]})
        result = self.pipeline.run(df)
        for col in ["cleaned_text", "is_duplicate", "duplicate_of_index", "language", "language_confidence"]:
            self.assertIn(col, result.columns)

    def test_duplicate_rows_flagged_after_normalization(self):
        df = pd.DataFrame({
            "record_id": ["a", "b"],
            "text": ["Hello!!!   World.", "Hello! World."],
        })
        result = self.pipeline.run(df)
        self.assertFalse(result.iloc[0]["is_duplicate"])
        self.assertTrue(result.iloc[1]["is_duplicate"])
        self.assertEqual(result.iloc[1]["duplicate_of_index"], 0)

    def test_missing_column_raises(self):
        df = pd.DataFrame({"record_id": ["a"], "not_text": ["hi"]})
        with self.assertRaises(KeyError):
            self.pipeline.run(df)

    def test_language_detected_for_each_unique_row(self):
        df = pd.DataFrame({
            "record_id": ["a", "b"],
            "text": ["The gang was arrested at the scene.", "Bonjour, ceci est une réunion."],
        })
        result = self.pipeline.run(df)
        self.assertIn(result.iloc[0]["language"], {"en"})
        self.assertNotEqual(result.iloc[0]["language"], result.iloc[1]["language"])


if __name__ == "__main__":
    unittest.main()
