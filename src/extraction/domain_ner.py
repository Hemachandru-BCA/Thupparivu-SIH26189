"""
extraction/domain_ner.py
------------------------
Extensible rule + regex entity extraction (Phase 3).

The existing :mod:`src.extraction.ner` covers PERSON / LOCATION /
ORGANIZATION / VEHICLE / PHONE via spaCy + gazetteer + a small regex layer.
This module adds a **plug-in regex suite** for the extended taxonomy:

    EMAIL, ACCOUNT, BANK, UPI, DEVICE, SOCIAL_HANDLE,
    DATE, TIME, CASE, CRIME_TYPE, ADDRESS, IDENTIFIER

and exposes a pure-function API (no spaCy required) so the entity types can
be used standalone, in notebooks, or merged into the existing spaCy
pipeline output.

Design goal: **extensibility**.  Adding a new entity type is one regex
entry in :data:`DOMAIN_PATTERNS`, plus an optional postprocessor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Canonical extended labels
# --------------------------------------------------------------------------- #

EXTENDED_LABELS = [
    "EMAIL",
    "ACCOUNT",
    "BANK",
    "UPI",
    "DEVICE",
    "SOCIAL_HANDLE",
    "DATE",
    "TIME",
    "CASE",
    "CRIME_TYPE",
    "ADDRESS",
    "IDENTIFIER",
    "PHONE",
    "VEHICLE",
]

#: Priority order: unambiguous closed patterns beat open patterns.
_PRIORITY = {
    "PHONE": 0,
    "EMAIL": 0,
    "UPI": 0,
    "VEHICLE": 1,
    "ACCOUNT": 1,
    "BANK": 1,
    "DEVICE": 2,
    "SOCIAL_HANDLE": 2,
    "DATE": 2,
    "TIME": 2,
    "IDENTIFIER": 2,
    "CRIME_TYPE": 3,
    "ADDRESS": 3,
    "CASE": 3,
}

# --------------------------------------------------------------------------- #
# Pattern table (extensible)
# --------------------------------------------------------------------------- #

CRIME_TYPES = (
    "extortion", "assault", "narcotics", "smuggling", "theft", "fraud",
    "money laundering", "illegal weapons", "unlawful assembly", "kidnapping",
    "robbery", "cybercrime", "dacoity", "homicide", "forgery",
)

BANKS = (
    "state bank of india", "hdfc bank", "icici bank", "axis bank",
    "punjab national bank", "bank of baroda", "canara bank", "kotak mahindra",
)

DOMAIN_PATTERNS: List[Tuple[str, str, str]] = [
    # (label, name, regex)
    ("EMAIL", "EMAIL", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("UPI", "UPI_ID", r"[A-Za-z0-9._-]{2,}@(?:upi|ybl|paytm|okaxis|oksbi|okhdfcbank|apl|pockets|ibl|axl|upi)"),
    ("ACCOUNT", "BANK_ACCOUNT", r"(?:account|a/c|acc(?:ount)?)[\s:#-]*([A-Z0-9]{6,18})"),
    ("PHONE", "PHONE", r"(?:\+?91[\s-]?)?[6-9]\d{9}"),
    ("VEHICLE", "VEHICLE", r"\b[A-Z]{2}[\s-]?[0-9]{2}[\s-]?[A-Z]{1,2}[\s-]?[0-9]{1,4}\b"),
    ("SOCIAL_HANDLE", "SOCIAL_HANDLE", r"@[a-zA-Z0-9_]{3,20}"),
    ("DEVICE", "DEVICE_ID", r"(?:imei|sim|device)[\s:#-]*(\d{10,16})"),
    ("IDENTIFIER", "AADHAAR", r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"),
    ("CRIME_TYPE", "CRIME_TYPE", r"\b(" + "|".join(CRIME_TYPES) + r")\b"),
    ("BANK", "BANK", r"\b(" + "|".join(BANKS) + r")\b"),
    ("DATE", "DATE", r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"),
    ("TIME", "TIME", r"\b\d{1,2}:\d{2}\s?(?:am|pm|hrs)?\b"),
    ("ADDRESS", "ADDRESS", r"\b\d{1,4}[\s,]+[A-Za-z][A-Za-z\s,]{5,40}(?:road|street|lane|nagar|colony|street|salai)\b",),
]

#: Case references like "Case No. 234 /2025", "FIR 112/2025"
CASE_PATTERN = re.compile(r"\b(?:case|fir|crime)\s*(?:no\.?|number)?\s*[\s#:-]*(\d{1,6}(?:[/-]\d{2,4})?)", re.IGNORECASE)


@dataclass
class DomainMention:
    """A single entity mention found by the regex suite."""

    text: str
    label: str
    start: int
    end: int
    confidence: float = 0.9
    attributes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "text": self.text,
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "attributes": dict(self.attributes),
        }


def _compile_patterns() -> List[Tuple[str, str, re.Pattern]]:
    out = []
    for label, name, pattern in DOMAIN_PATTERNS:
        try:
            out.append((label, name, re.compile(pattern, re.IGNORECASE)))
        except re.error:  # pragma: no cover - guard against bad patterns
            continue
    return out


_COMPILED = _compile_patterns()


def extract_domain_mentions(text: str) -> List[DomainMention]:
    """Run every pattern over *text* and return non-overlapping mentions.

    Overlap resolution: the higher-priority label wins; within the same
    priority, the longer span wins.
    """
    raw: List[DomainMention] = []
    for label, name, pattern in _COMPILED:
        for match in pattern.finditer(text):
            if match.lastindex:  # capture group present → use it
                group = match.group(1)
                start = match.start(1)
                end = match.end(1)
            else:
                group = match.group(0)
                start = match.start(0)
                end = match.end(0)
            raw.append(DomainMention(text=group, label=label, start=start, end=end))

    # case references (separate since they have a different output shape)
    for match in CASE_PATTERN.finditer(text):
        raw.append(DomainMention(
            text=match.group(0).strip(),
            label="CASE",
            start=match.start(),
            end=match.end(),
            attributes={"case_number": match.group(1)},
        ))

    if not raw:
        return []
    return _resolve_overlaps(raw)


def _resolve_overlaps(mentions: List[DomainMention]) -> List[DomainMention]:
    """Greedy non-overlapping selection by (priority, length)."""
    ordered = sorted(
        mentions,
        key=lambda m: (_PRIORITY.get(m.label, 5), -(m.end - m.start), m.start),
    )
    picked: List[DomainMention] = []
    occupied: List[Tuple[int, int]] = []
    for mention in ordered:
        span = (mention.start, mention.end)
        if any(not (span[1] <= s or span[0] >= e) for s, e in occupied):
            continue
        picked.append(mention)
        occupied.append(span)
    picked.sort(key=lambda m: m.start)
    return picked


def domain_mentions_to_dicts(text: str) -> List[Dict[str, object]]:
    return [m.to_dict() for m in extract_domain_mentions(text)]


# --------------------------------------------------------------------------- #
# Merge with spaCy-style output
# --------------------------------------------------------------------------- #

def merge_with_spacy(spacy_entities: List[Tuple[str, str, int, int]],
                     text: str) -> List[Dict[str, object]]:
    """Merge spaCy entities with domain mentions.

    ``spacy_entities`` is a list of ``(label, text, start, end)`` tuples.
    Domain mentions win on overlap (they are more precise for the
    closed-world types).
    """
    domain = extract_domain_mentions(text)
    combined = [
        {"text": t, "label": l, "start": s, "end": e} for l, t, s, e in spacy_entities
    ]
    for mention in domain:
        m = mention.to_dict()
        overlap = any(
            not (m["end"] <= other["start"] or m["start"] >= other["end"])
            for other in combined
        )
        if not overlap:
            combined.append(m)
        else:
            # domain wins: remove overlapping spaCy entities
            combined = [
                other for other in combined
                if other["end"] <= m["start"] or other["start"] >= m["end"]
            ]
            combined.append(m)
    combined.sort(key=lambda e: e["start"])
    return combined