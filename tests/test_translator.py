import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.preprocessing.translator import (
    LanguageDetector, Translator, NoOpTranslationBackend, StubDictionaryBackend
)


class TestLanguageDetector(unittest.TestCase):
    def setUp(self):
        self.detector = LanguageDetector()

    def test_detects_english(self):
        lang, conf = self.detector.detect("The quick brown fox jumps over the lazy dog.")
        self.assertEqual(lang, "en")
        self.assertGreater(conf, 0.0)

    def test_detects_french(self):
        lang, conf = self.detector.detect("Bonjour, ceci est une réunion importante pour le gang.")
        self.assertIn(lang, {"fr"})

    def test_empty_string_is_unknown(self):
        lang, conf = self.detector.detect("")
        self.assertEqual(lang, "unknown")
        self.assertEqual(conf, 0.0)

    def test_confidence_bounded_between_0_and_1(self):
        lang, conf = self.detector.detect("Somewhat ambiguous text 123 !!!")
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)


class TestTranslationBackends(unittest.TestCase):
    def test_noop_backend_returns_text_unchanged(self):
        backend = NoOpTranslationBackend()
        self.assertEqual(backend.translate("hola mundo", "es"), "hola mundo")

    def test_stub_dictionary_translates_known_words(self):
        backend = StubDictionaryBackend()
        result = backend.translate("Hola amigo", "es")
        self.assertIn("hello", result.lower())

    def test_stub_dictionary_passthrough_for_unsupported_language(self):
        backend = StubDictionaryBackend()
        result = backend.translate("hallo welt", "de")
        self.assertEqual(result, "hallo welt")


class TestTranslatorFacade(unittest.TestCase):
    def setUp(self):
        self.translator = Translator(backend=StubDictionaryBackend())

    def test_english_text_not_translated(self):
        result = self.translator.process("The suspect fled the scene.")
        self.assertEqual(result["detected_language"], "en")
        self.assertFalse(result["was_translated"])
        self.assertEqual(result["translated_text"], result["original_text"])

    def test_spanish_text_gets_translated(self):
        result = self.translator.process("Hola, hubo una reunión de dinero.")
        self.assertEqual(result["detected_language"], "es")
        self.assertTrue(result["was_translated"])
        self.assertIn("hello", result["translated_text"].lower())

    def test_result_contains_expected_keys(self):
        result = self.translator.process("Some text")
        expected_keys = {
            "original_text", "detected_language", "language_confidence",
            "translated_text", "was_translated",
        }
        self.assertEqual(expected_keys, set(result.keys()))


if __name__ == "__main__":
    unittest.main()
