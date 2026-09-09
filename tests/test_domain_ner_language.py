"""Tests for Phase-3 NLP: domain NER + multilingual language layer."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.extraction.domain_ner import (  # noqa: E402
    extract_domain_mentions,
    merge_with_spacy,
)
from src.nlp.language_layer import (  # noqa: E402
    detect_language,
    normalized_representation,
)


# ------------------------------------------------------------------ #
# Domain NER
# ------------------------------------------------------------------ #

def test_email_extraction():
    mentions = extract_domain_mentions("Contact ravi.kumar@gmail.com for details")
    labels = [m.label for m in mentions]
    assert "EMAIL" in labels


def test_phone_extraction():
    mentions = extract_domain_mentions("Call 9840012345 immediately")
    labels = [m.label for m in mentions]
    assert "PHONE" in labels


def test_upi_extraction():
    mentions = extract_domain_mentions("Send to ravi@upi")
    assert any(m.label == "UPI" for m in mentions)


def test_account_extraction():
    mentions = extract_domain_mentions("Account 123456789012 was used")
    assert any(m.label == "ACCOUNT" for m in mentions)


def test_crime_type_extraction():
    mentions = extract_domain_mentions("Charged with money laundering")
    assert any(m.label == "CRIME_TYPE" for m in mentions)


def test_case_extraction():
    mentions = extract_domain_mentions("Refer to FIR 112/2025")
    assert any(m.label == "CASE" for m in mentions)


def test_date_extraction():
    mentions = extract_domain_mentions("On 15-08-2025 they met")
    assert any(m.label == "DATE" for m in mentions)


def test_no_overlap_double_count():
    """Phone digits inside a vehicle pattern must not double-count."""
    mentions = extract_domain_mentions("Vehicle TN01AB1234 was spotted")
    types = [m.label for m in mentions]
    assert types.count("VEHICLE") == 1


def test_merge_with_spacy():
    combined = merge_with_spacy(
        [("PERSON", "Ravi Kumar", 0, 10)],
        "Ravi Kumar at ravi@example.com",
    )
    labels = [e["label"] for e in combined]
    assert "PERSON" in labels
    assert "EMAIL" in labels


# ------------------------------------------------------------------ #
# Language layer
# ------------------------------------------------------------------ #

def test_detect_language_tamil():
    r = detect_language("ரவி குமார்")
    assert r.language == "ta"
    assert r.script == "tamil"


def test_detect_language_hindi():
    r = detect_language("रवि कुमार")
    assert r.language == "hi"


def test_detect_language_english():
    r = detect_language("Ravi Kumar transferred money")
    assert r.language == "en"


def test_nir_date_iso():
    nir = normalized_representation("transaction on 15/08/2025")
    assert nir.iso_date == "2025-08-15"


def test_nir_phone():
    nir = normalized_representation("call +91 98400 12345")
    assert nir.normalized_phone == "9840012345"


def test_nir_money():
    nir = normalized_representation("transferred Rs. 5,00,000")
    assert nir.contains_money
    assert nir.amount == 500000.0
    assert nir.currency == "INR"


def test_nir_no_money():
    nir = normalized_representation("they met at the docks")
    assert not nir.contains_money