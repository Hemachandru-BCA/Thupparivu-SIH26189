"""
cleaner.py
----------
Text cleaning pipeline for SentinelGraph AI:

  1. Regex normalization  - whitespace, punctuation, casing, control chars
  2. Duplicate removal    - exact + near-duplicate (normalized-text) detection
  3. Language detection   - tags every record with (language, confidence)

Operates on pandas DataFrames so it composes naturally with the rest of a
tabular NLP pipeline, but also exposes a single-string `clean_text()` method
for ad-hoc use (e.g. inside ocr.py or fir_simulator.py).
"""

import re
import hashlib
import unicodedata
from typing import List, Optional

import pandas as pd

from .translator import LanguageDetector


class RegexNormalizer:
    """Pure regex/string based text normalization."""

    _CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    _MULTI_SPACE_RE = re.compile(r"\s+")
    _REPEATED_PUNCT_RE = re.compile(r"([!?.,])\1{1,}")
    _URL_RE = re.compile(r"https?://\S+|www\.\S+")
    _NON_PRINTABLE_RE = re.compile(r"[^\x20-\x7E\u00A0-\uFFFF]")

    def normalize(self, text: str) -> str:
        if text is None:
            return ""

        text = unicodedata.normalize("NFKC", text)
        text = self._CONTROL_CHARS_RE.sub("", text)
        text = self._URL_RE.sub("[URL]", text)
        text = self._REPEATED_PUNCT_RE.sub(r"\1", text)
        text = self._MULTI_SPACE_RE.sub(" ", text)
        return text.strip()


class DuplicateDetector:
    """
    Flags exact and near-duplicate text records.
    Near-duplicates are found by hashing a heavily normalized ("fingerprint")
    version of the text: lowercased, punctuation stripped, whitespace
    collapsed. Two records with the same fingerprint are considered
    duplicates of whichever one appeared first.
    """

    _NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
    _SPACE_RE = re.compile(r"\s+")

    def fingerprint(self, text: str) -> str:
        cleaned = (text or "").lower()
        cleaned = self._NON_ALNUM_RE.sub("", cleaned)
        cleaned = self._SPACE_RE.sub(" ", cleaned).strip()
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def find_duplicates(self, texts: List[str]) -> List[Optional[int]]:
        """
        Returns a list the same length as `texts`, where entry i is:
          - None if texts[i] is the first occurrence of its fingerprint
          - the index of the first occurrence, if texts[i] is a duplicate
        """
        seen = {}
        result: List[Optional[int]] = []
        for i, text in enumerate(texts):
            fp = self.fingerprint(text)
            if fp in seen:
                result.append(seen[fp])
            else:
                seen[fp] = i
                result.append(None)
        return result


class TextCleaningPipeline:
    """
    Orchestrates regex normalization + duplicate removal + language
    detection over a pandas DataFrame with a designated text column.
    """

    def __init__(self, text_column: str = "text"):
        self.text_column = text_column
        self.normalizer = RegexNormalizer()
        self.dedup = DuplicateDetector()
        self.lang_detector = LanguageDetector()

    def clean_text(self, text: str) -> str:
        """Single-string convenience method (used by ocr.py, etc.)."""
        return self.normalizer.normalize(text)

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.text_column not in df.columns:
            raise KeyError(f"Column '{self.text_column}' not found in DataFrame")

        df = df.copy()

        # 1) Regex normalization
        df["cleaned_text"] = df[self.text_column].apply(self.normalizer.normalize)

        # 2) Duplicate detection (on the *cleaned* text)
        dup_of = self.dedup.find_duplicates(df["cleaned_text"].tolist())
        df["is_duplicate"] = [d is not None for d in dup_of]
        df["duplicate_of_index"] = dup_of

        # 3) Language detection (skip for rows already flagged as duplicates
        #    to save work -- they'll inherit the original's language)
        languages, confidences = [], []
        lang_cache = {}
        for i, row in df.iterrows():
            if row["is_duplicate"]:
                orig_idx = row["duplicate_of_index"]
                lang, conf = lang_cache.get(orig_idx, ("unknown", 0.0))
            else:
                lang, conf = self.lang_detector.detect(row["cleaned_text"])
                lang_cache[i] = (lang, conf)
            languages.append(lang)
            confidences.append(conf)

        df["language"] = languages
        df["language_confidence"] = confidences

        return df
