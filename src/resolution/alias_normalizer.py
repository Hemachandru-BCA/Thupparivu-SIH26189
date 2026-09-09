"""
resolution/alias_normalizer.py
------------------------------
Alias normalization and multilingual-name handling (Phase 3).

Handles:

* name variations / initials          ("J. Doe" ~ "John Doe")
* spelling variants                  ("Mohammed" ~ "Mohammad")
* Tamil/Hindi/English transliterations
* phone formatting                   (E.164-ish + local forms)
* vehicle formatting                 (TN-01-AB-1234 variants)
* address variations

The module is deterministic and dependency-free (stdlib + the existing
:mod:`src.resolution.entity_matcher` utilities).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Sequence, Set, Tuple

from src.resolution.entity_matcher import normalize_name, soundex

# --------------------------------------------------------------------------- #
# Transliteration tables (Tamil / Hindi common variants)
# --------------------------------------------------------------------------- #

#: Common English↔regional transliteration vowel/sound substitutions.
TRANSLITERATION_VARIANTS = {
    "sh": {"s", "sh", "sa"},
    "s": {"sh", "s", "sa", "ss"},
    "v": {"v", "w"},
    "w": {"v", "w"},
    "j": {"j", "z"},
    "z": {"j", "z"},
    "ph": {"ph", "f"},
    "f": {"ph", "f"},
    "th": {"t", "th", "d"},
    "d": {"d", "th"},
    "bh": {"b", "bh"},
    "gh": {"g", "gh"},
    "ch": {"ch", "c"},
    "k": {"k", "c", "q"},
    "q": {"q", "k"},
    "aa": {"a", "aa", "ah"},
    "ee": {"i", "ee", "e"},
    "oo": {"u", "oo", "o"},
    "iyan": {"iyan", "ian", "iyan"},
    "an": {"an", "en", "in"},
    "hammed": {"hammad"},
}

_DIGITS_RE = re.compile(r"\d+")
_VEHICLE_PREFIX_RE = re.compile(r"^[A-Z]{2}\d{2}")
_VEHICLE_FULL_RE = re.compile(r"^[A-Z]{2}[ -]?\d{2}[ -]?[A-Z]{1,2}[ -]?\d{1,4}$")


class AliasNormalizer:
    """Normalizes raw strings into comparable canonical keys per type."""

    # ------------------------------------------------------------------ #
    def normalize_phone(self, phone: str) -> str:
        digits = re.sub(r"\D", "", str(phone))
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        return digits

    def normalize_email(self, email: str) -> str:
        return str(email).strip().lower()

    def normalize_vehicle(self, vehicle: str) -> str:
        """TN-01-AB-1234, TN01AB1234, TN 01 AB 1234 → TN01AB1234."""
        raw = str(vehicle).upper()
        raw = re.sub(r"[^A-Z0-9]", "", raw)
        # if a state prefix exists, keep it; otherwise keep digits+letters
        return raw

    def normalize_address(self, address: str) -> str:
        """Lowercase, strip punctuation, drop street suffixes & stop words."""
        raw = str(address).lower()
        raw = re.sub(r"[,.;:#]", " ", raw)
        tokens = []
        stop = {"street", "st", "road", "rd", "lane", "ln", "avenue", "ave",
                "nagar", "colony", "block", "bhk", "floor"}
        for tok in raw.split():
            tok = tok.strip()
            if tok in stop or not tok:
                continue
            if tok.isdigit():  # house numbers are not discriminating
                continue
            tokens.append(tok)
        return " ".join(sorted(set(tokens)))

    def transliteration_key(self, name: str) -> str:
        """A canonical key robust to common transliteration substitutions.

        The key maps each token through TRANSLITERATION_VARIANTS, keeping
        the *first* canonical variant so 'Mohammed' and 'Mohammad' collide.
        """
        tokens = normalize_name(name).split()
        out = []
        for tok in tokens:
            lowered = tok.lower()
            subs = TRANSLITERATION_VARIANTS.get(lowered)
            if subs:
                out.append(sorted(subs)[0])
            else:
                # substring variants (e.g. "sharma" → "sarma")
                canonical = lowered
                for variant_key in sorted(TRANSLITERATION_VARIANTS, key=len, reverse=True):
                    if variant_key in canonical:
                        canonical = canonical.replace(
                            variant_key, sorted(TRANSLITERATION_VARIANTS[variant_key])[0], 1
                        )
                out.append(canonical)
        return " ".join(out)

    def soundex_key(self, name: str) -> str:
        """Phonetic key for initials / spelling variants."""
        tokens = normalize_name(name).split()
        if not tokens:
            return ""
        return "".join(soundex(tok) for tok in tokens)

    def initials_key(self, name: str) -> str:
        """First-initial + surname key: 'J. Doe' → 'j doe'."""
        tokens = normalize_name(name).split()
        if not tokens:
            return ""
        if len(tokens) == 1:
            return tokens[0]
        return f"{tokens[0][0]} {tokens[-1]}"

    # ------------------------------------------------------------------ #
    def all_keys(self, name: str) -> Set[str]:
        """All comparable keys for a name (any of them matching is a hit)."""
        return {
            self.transliteration_key(name),
            self.soundex_key(name),
            self.initials_key(name),
            normalize_name(name),
        }

    def normalize_by_type(self, value: str, value_type: str) -> Optional[str]:
        """Dispatch normalization by attribute type."""
        t = value_type.upper()
        if t in ("PHONE", "MOBILE", "TEL"):
            return self.normalize_phone(value)
        if t in ("EMAIL", "EMAIL_ADDRESS"):
            return self.normalize_email(value)
        if t in ("VEHICLE", "VEHICLE_NO", "LICENSE_PLATE"):
            return self.normalize_vehicle(value)
        if t in ("ADDRESS", "LOCATION"):
            return self.normalize_address(value)
        if t in ("NAME", "PERSON", "ORGANIZATION"):
            return self.transliteration_key(value)
        return str(value).strip().lower()


def compare_aliases(a: str, b: str, alias_type: str = "NAME") -> float:
    """0..1 similarity between two alias strings of the same type."""
    if alias_type.upper() in ("PHONE", "MOBILE", "TEL"):
        na, nb = AliasNormalizer().normalize_phone(a), AliasNormalizer().normalize_phone(b)
        return 1.0 if na == nb and na else 0.0
    if alias_type.upper() in ("VEHICLE", "LICENSE_PLATE"):
        na, nb = AliasNormalizer().normalize_vehicle(a), AliasNormalizer().normalize_vehicle(b)
        return 1.0 if na == nb and na else 0.0
    normalizer = AliasNormalizer()
    keys_a, keys_b = normalizer.all_keys(a), normalizer.all_keys(b)
    if keys_a & keys_b:
        return 1.0
    return 0.0