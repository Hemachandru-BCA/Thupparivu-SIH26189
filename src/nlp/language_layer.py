"""
nlp/language_layer.py
---------------------
Multilingual architecture (Phase 3, requirement 8).

Do not hard-code a single language.  This module provides:

* :func:`detect_language` — script/heuristic language detection that works
  offline (does not depend on langdetect models) with Tamil/Hindi/English
  awareness;
* :func:`normalized_representation` — a language-agnostic normalized
  intermediate representation (NIR) for text: ISO date, normalized phone,
  transliteration folding, token canon.

The rest of the extraction pipeline can then operate on the NIR rather
than the raw surface string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.resolution.alias_normalizer import AliasNormalizer

# Unicode block ranges for Indian scripts
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"\d")


@dataclass
class LanguageResult:
    language: str = "en"        # en | ta | hi | unknown
    script: str = "latin"       # latin | tamil | devanagari | mixed
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {"language": self.language, "script": self.script,
                "confidence": round(self.confidence, 3)}


def detect_language(text: str) -> LanguageResult:
    """Offline language detection by script analysis."""
    if not text:
        return LanguageResult(language="unknown", script="unknown", confidence=0.0)

    tamil_chars = len(_TAMIL_RE.findall(text))
    deva_chars = len(_DEVANAGARI_RE.findall(text))
    latin_chars = len(_LATIN_RE.findall(text))

    total_alpha = tamil_chars + deva_chars + latin_chars
    if total_alpha == 0:
        return LanguageResult(language="unknown", script="digits", confidence=0.0)

    if tamil_chars > deva_chars and tamil_chars >= latin_chars * 0.5:
        return LanguageResult("ta", "tamil", round(tamil_chars / max(total_alpha, 1), 3))
    if deva_chars > tamil_chars and deva_chars >= latin_chars * 0.5:
        return LanguageResult("hi", "devanagari", round(deva_chars / max(total_alpha, 1), 3))
    if latin_chars > 0:
        return LanguageResult("en", "latin", round(latin_chars / max(total_alpha, 1), 3))
    return LanguageResult("unknown", "mixed", 0.0)


@dataclass
class NormalizedRepresentation:
    """Language-agnostic intermediate representation of a piece of text."""

    language: str = "en"
    script: str = "latin"
    iso_date: Optional[str] = None
    normalized_phone: Optional[str] = None
    transliteration_folded: str = ""       # canonical name key
    token_canon: List[str] = field(default_factory=list)
    contains_money: bool = False
    amount: Optional[float] = None
    currency: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "language": self.language,
            "script": self.script,
            "iso_date": self.iso_date,
            "normalized_phone": self.normalized_phone,
            "transliteration_folded": self.transliteration_folded,
            "token_canon": list(self.token_canon),
            "contains_money": self.contains_money,
            "amount": self.amount,
            "currency": self.currency,
        }


_MONEY_RE = re.compile(
    r"(?P<cur>rs\.?|inr|₹|usd|\$|€|£)?\s*(?P<amt>\d[\d,]*\.?\d*)\s*"
    r"(?P<unit>(?:crore|lakh|k|million|thousand)?)",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b"
    r"|\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b"
)

_CURRENCY_MAP = {
    "rs": "INR", "rs.": "INR", "inr": "INR", "₹": "INR",
    "usd": "USD", "$": "USD", "€": "EUR", "£": "GBP",
}


def normalized_representation(text: str) -> NormalizedRepresentation:
    """Produce the NIR for a text fragment."""
    lang = detect_language(text)
    normalizer = AliasNormalizer()
    result = NormalizedRepresentation(
        language=lang.language,
        script=lang.script,
    )

    date_match = _DATE_RE.search(text)
    if date_match and date_match.lastindex:
        if date_match.group(1):  # ISO-like yyyy-mm-dd
            result.iso_date = (
                f"{date_match.group(1)}-{int(date_match.group(2)):02d}-"
                f"{int(date_match.group(3)):02d}"
            )
        else:
            # DMY input: group 4 = day, group 5 = month, group 6 = year
            result.iso_date = (
                f"{date_match.group(6)}-{int(date_match.group(5)):02d}-"
                f"{int(date_match.group(4)):02d}"
            )

    # phone: 10-digit Indian mobile (spaces/dashes allowed), or +91 prefix
    phone_match = re.search(r"(?:\+?91[\s-]?)?[6-9][\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d", text)
    if phone_match:
        result.normalized_phone = normalizer.normalize_phone(phone_match.group(0))

    result.transliteration_folded = normalizer.transliteration_key(text)

    # token canon: normalized lowercase tokens with digits stripped
    raw_tokens = re.findall(r"[A-Za-z\u0B80-\u0BFF\u0900-\u097F]+", text)
    result.token_canon = [t.lower() for t in raw_tokens]

    # money — strip phone numbers first so "call +91 98400" isn't parsed as ₹91
    money_text = re.sub(r"(?:\+?91[\s-]?)?[6-9][\s-]?\d{9}", " PHONE ", text)
    money_match = _MONEY_RE.search(money_text)
    if money_match and money_match.group("amt"):
        raw_amount = money_match.group("amt").replace(",", "")
        amount = float(raw_amount)
        unit = (money_match.group("unit") or "").lower()
        if unit == "crore":
            amount *= 10_000_000
        elif unit == "lakh":
            amount *= 100_000
        elif unit == "thousand":
            amount *= 1000
        elif unit == "k":
            amount *= 1000
        elif unit == "million":
            amount *= 1_000_000
        result.amount = round(amount, 2)
        result.contains_money = True
        cur = (money_match.group("cur") or "").lower()
        result.currency = _CURRENCY_MAP.get(cur, "INR" if cur.startswith("rs") else None)

    return result