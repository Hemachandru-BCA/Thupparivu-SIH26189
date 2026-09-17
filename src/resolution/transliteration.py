"""
transliteration.py
------------------
Indian name transliteration and similarity utilities.

Provides:
- detect_script(text) -> "tamil" | "devanagari" | "latin" | "unknown"
- to_latin_fold(text) -> str  (normalized, Latinized, vowel-folded)
- name_similarity(a, b) -> float [0.0, 1.0]  (Levenshtein + token-sort ratio)

All functions are deterministic, never raise on invalid unicode input,
and work with pure stdlib as fallback when indic-transliteration is missing.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Literal

ScriptType = Literal["tamil", "devanagari", "latin", "unknown"]

# Vowel/sound fold table for common Indian romanization variants
# Maps normalized transliteration forms to a canonical representation.
VOWEL_FOLD = {
    "aa": "a", "ā": "a", "a": "a",
    "ii": "i", "ī": "i", "i": "i",
    "uu": "u", "ū": "u", "u": "u",
    "ee": "e", "ē": "e", "e": "e",
    "oo": "o", "ō": "o", "o": "o",
    "ai": "ei", "ei": "ei",
    "au": "ou", "ou": "ou",
    "sh": "s", "ś": "s", "ṣ": "s", "ṡ": "s",
    "th": "t", "ṭ": "t", "t": "t",
    "dh": "d", "ḍ": "d", "d": "d",
    "ph": "f", "f": "f",
    "bh": "b", "b": "b",
    "gh": "g", "g": "g",
    "kh": "k", "k": "k",
    "ch": "c", "c": "c",
    "jh": "j", "j": "j",
    "zh": "l", "ḻ": "l", "l": "l",
    "ṅ": "n", "ñ": "n", "ṇ": "n", "n": "n",
    "ṃ": "m", "m": "m",
    "ṛ": "r", "r": "r",
    "y": "y", "v": "v", "w": "v",
    "x": "k", "q": "k",
}


def detect_script(text: str) -> ScriptType:
    """
    Detect the script of the input text using Unicode block ranges.
    Returns: "tamil", "devanagari", "latin", or "unknown"
    """
    if not text:
        return "unknown"
    tamil_count = 0
    devanagari_count = 0
    latin_count = 0
    other_count = 0

    for ch in text:
        code = ord(ch)
        if 0x0B80 <= code <= 0x0BFF:  # Tamil block
            tamil_count += 1
        elif 0x0900 <= code <= 0x097F:  # Devanagari block
            devanagari_count += 1
        elif (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):  # ASCII letters
            latin_count += 1
        else:
            other_count += 1

    if tamil_count > max(devanagari_count, latin_count):
        return "tamil"
    if devanagari_count > max(tamil_count, latin_count):
        return "devanagari"
    if latin_count > max(tamil_count, devanagari_count):
        return "latin"
    return "unknown"


def _to_itrans_latin(text: str) -> str:
    """
    Convert Tamil/Devanagari to ITRANS-style latin using indic-transliteration.
    Falls back to a basic character map if library missing.
    """
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
    except Exception:
        # Fallback: basic character map for common Tamil/Devanagari chars
        return _basic_indic_to_latin(text)

    script = detect_script(text)
    try:
        if script == "tamil":
            return transliterate(text, sanscript.TAMIL, sanscript.ITRANS).lower()
        elif script == "devanagari":
            return transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS).lower()
        else:
            return text.lower()
    except Exception:
        return _basic_indic_to_latin(text)


def _basic_indic_to_latin(text: str) -> str:
    """
    Basic character map for Tamil and Devanagari when indic-transliteration is unavailable.
    Covers common vowels and consonants for name-like text.
    """
    # Tamil basic map (partial)
    tamil_map = {
        'அ': 'a', 'ஆ': 'aa', 'இ': 'i', 'ஈ': 'ii', 'உ': 'u', 'ஊ': 'uu',
        'எ': 'e', 'ஏ': 'ee', 'ஐ': 'ai', 'ஒ': 'o', 'ஓ': 'oo', 'ஔ': 'au',
        'க': 'k', 'ங': 'ng', 'ச': 's', 'ஞ': 'ny', 'ட': 't', 'ண': 'n',
        'த': 'th', 'ந': 'n', 'ப': 'p', 'ம': 'm', 'ய': 'y', 'ர': 'r',
        'ல': 'l', 'வ': 'v', 'ழ': 'zh', 'ள': 'l', 'ற': 'r', 'ந': 'n',
        'ஃ': '', '்': '', 'ா': 'a', 'ி': 'i', 'ீ': 'ii', 'ு': 'u',
        'ூ': 'uu', 'ெ': 'e', 'ே': 'ee', 'ை': 'ai', 'ொ': 'o', 'ோ': 'oo',
        'ௌ': 'au',
    }
    
    # Devanagari basic map (partial)
    devanagari_map = {
        'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ii', 'उ': 'u', 'ऊ': 'uu',
        'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au',
        'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
        'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
        'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
        'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
        'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
        'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh',
        'ष': 'sh', 'स': 's', 'ह': 'h', 'ळ': 'l',
        'ा': 'a', 'ि': 'i', 'ी': 'ii', 'ु': 'u', 'ू': 'uu',
        'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ं': 'm', 'ः': 'h',
        '्': '',
    }
    
    # Determine script
    script = detect_script(text)
    if script == "tamil":
        char_map = tamil_map
    elif script == "devanagari":
        char_map = devanagari_map
    else:
        char_map = {}
    
    result = []
    for ch in text:
        if ch in char_map:
            result.append(char_map[ch])
        elif ord(ch) < 128:
            result.append(ch)
        else:
            # NFKD fallback for any remaining chars
            result.append(''.join(
                c for c in unicodedata.normalize('NFKD', ch)
                if ord(c) < 128
            ))
    return ''.join(result).lower()


def _apply_vowel_fold(text: str) -> str:
    """
    Apply vowel/sound fold table to collapse common Indian romanization variants.
    Scans left-to-right, matching longest keys first.
    """
    if not text:
        return text
    # Sort fold keys by length descending for longest-match-first
    fold_keys = sorted(VOWEL_FOLD.keys(), key=len, reverse=True)
    result = []
    i = 0
    text_lower = text.lower()
    while i < len(text_lower):
        matched = False
        for key in fold_keys:
            if text_lower.startswith(key, i):
                result.append(VOWEL_FOLD[key])
                i += len(key)
                matched = True
                break
        if not matched:
            result.append(text_lower[i])
            i += 1
    return ''.join(result)


def _strip_diacritics(text: str) -> str:
    """Remove combining diacritical marks."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _collapse_whitespace(text: str) -> str:
    """Collapse multiple whitespace chars to single space, strip ends."""
    return re.sub(r'\s+', ' ', text).strip()


def to_latin_fold(text: str) -> str:
    """
    Normalize any name-like string to folded latin form.
    Pipeline: detect_script -> ITRANS transliteration -> vowel fold ->
    diacritic strip -> lowercase -> whitespace collapse.
    Never raises on any unicode input.
    """
    if not text:
        return ""
    try:
        # Step 1: Script-aware transliteration to ITRANS latin
        latin = _to_itrans_latin(text)
        # Step 2: Apply vowel/sound fold
        folded = _apply_vowel_fold(latin)
        # Step 3: Strip diacritics
        stripped = _strip_diacritics(folded)
        # Step 4: Lowercase + whitespace collapse
        return _collapse_whitespace(stripped.lower())
    except Exception:
        # Ultimate fallback: simple lower + strip
        return text.strip().lower()


def _levenshtein_ratio(a: str, b: str) -> float:
    """Levenshtein ratio using difflib.SequenceMatcher (stdlib)."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _token_sort_ratio(a: str, b: str) -> float:
    """
    Token-sort ratio: split on whitespace, sort tokens alphabetically,
    join, then compute Levenshtein ratio.
    Handles "Kumar Rajan" vs "Rajan Kumar".
    """
    tokens_a = sorted(a.split())
    tokens_b = sorted(b.split())
    joined_a = ' '.join(tokens_a)
    joined_b = ' '.join(tokens_b)
    return _levenshtein_ratio(joined_a, joined_b)


def name_similarity(a: str, b: str) -> float:
    """
    Compute similarity between two names [0.0, 1.0].
    1. Fold both via to_latin_fold()
    2. If folded identical: return 1.0
    3. Levenshtein ratio on folded strings
    4. Token-sort ratio on folded strings
    5. Return max(lev, token_sort)
    """
    folded_a = to_latin_fold(a)
    folded_b = to_latin_fold(b)

    if folded_a == folded_b:
        return 1.0

    lev = _levenshtein_ratio(folded_a, folded_b)
    tok = _token_sort_ratio(folded_a, folded_b)
    return max(lev, tok)