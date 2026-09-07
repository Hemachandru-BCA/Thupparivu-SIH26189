"""
translator.py
--------------
Language detection + translation for SentinelGraph AI.

Uses `langdetect` when installed for real statistical language ID; falls
back to a small stopword-overlap heuristic otherwise so the module keeps
working offline. Translation uses a pluggable `TranslationBackend` -- by
default a no-op/dictionary-based stub (since this environment has no
network access to call a real translation API), but a production backend
(e.g. Google Translate, DeepL, an internal LLM call) can be swapped in
without touching the rest of the pipeline.
"""

import re
from typing import Optional, Tuple, Dict, List, Protocol

try:
    from langdetect import detect_langs, DetectorFactory
    DetectorFactory.seed = 42  # deterministic results
    _HAS_LANGDETECT = True
except ImportError:  # pragma: no cover
    _HAS_LANGDETECT = False


# --------------------------------------------------------------------------- #
# Fallback heuristic detector (used only if langdetect isn't installed)
# --------------------------------------------------------------------------- #
_STOPWORDS: Dict[str, set] = {
    "en": {"the", "and", "is", "of", "to", "in", "was", "were", "on", "at", "a", "an", "he", "she", "they"},
    "es": {"el", "la", "de", "y", "es", "en", "un", "una", "que", "fue", "los", "las"},
    "fr": {"le", "la", "de", "et", "est", "en", "un", "une", "que", "des", "les"},
    "hi": {"aur", "hai", "ka", "ki", "ke", "mein", "ko", "se", "ek"},
}


class _HeuristicDetector:
    def detect(self, text: str) -> Tuple[str, float]:
        tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
        if not tokens:
            return "unknown", 0.0

        scores = {}
        for lang, stopwords in _STOPWORDS.items():
            overlap = len(tokens & stopwords)
            scores[lang] = overlap / max(len(stopwords), 1)

        best_lang = max(scores, key=scores.get)
        best_score = scores[best_lang]
        if best_score == 0:
            return "en", 0.4  # default assumption for this English-language dataset
        confidence = min(0.4 + best_score, 0.95)
        return best_lang, round(confidence, 2)


class LanguageDetector:
    """Facade used by both translator.py and cleaner.py."""

    def __init__(self):
        self._fallback = _HeuristicDetector()

    def detect(self, text: str) -> Tuple[str, float]:
        """Returns (language_code, confidence in [0,1])."""
        if not text or not text.strip():
            return "unknown", 0.0

        if _HAS_LANGDETECT:
            try:
                candidates = detect_langs(text)
                if candidates:
                    top = candidates[0]
                    return top.lang, round(float(top.prob), 2)
            except Exception:
                pass  # fall through to heuristic

        return self._fallback.detect(text)


# --------------------------------------------------------------------------- #
# Translation backends
# --------------------------------------------------------------------------- #
class TranslationBackend(Protocol):
    def translate(self, text: str, source_lang: str, target_lang: str = "en") -> str:
        ...


class NoOpTranslationBackend:
    """Returns text unchanged; used when translation isn't actually needed
    (e.g. record already in the target language) or as a safe default."""

    def translate(self, text: str, source_lang: str, target_lang: str = "en") -> str:
        return text


class StubDictionaryBackend:
    """
    Tiny illustrative dictionary-based backend for offline demos/tests.
    Swap for a real API-backed backend in production -- the rest of the
    pipeline only depends on the `TranslationBackend` protocol.
    """

    _DICTIONARIES: Dict[str, Dict[str, str]] = {
        "es": {"hola": "hello", "reunión": "meeting", "dinero": "money"},
        "fr": {"bonjour": "hello", "réunion": "meeting", "argent": "money"},
    }

    def translate(self, text: str, source_lang: str, target_lang: str = "en") -> str:
        if target_lang != "en" or source_lang not in self._DICTIONARIES:
            return text
        table = self._DICTIONARIES[source_lang]

        def _replace(match):
            word = match.group(0)
            return table.get(word.lower(), word)

        return re.sub(r"[^\W\d_]+", _replace, text, flags=re.UNICODE)


class Translator:
    """
    Facade: detect language, then translate to English if needed.
    """

    def __init__(self, backend: Optional[TranslationBackend] = None,
                 target_lang: str = "en"):
        self.detector = LanguageDetector()
        self.backend = backend or StubDictionaryBackend()
        self.target_lang = target_lang

    def process(self, text: str) -> Dict[str, object]:
        lang, confidence = self.detector.detect(text)
        if lang == self.target_lang or lang == "unknown":
            translated = text
        else:
            translated = self.backend.translate(text, source_lang=lang, target_lang=self.target_lang)

        return {
            "original_text": text,
            "detected_language": lang,
            "language_confidence": confidence,
            "translated_text": translated,
            "was_translated": translated != text,
        }
