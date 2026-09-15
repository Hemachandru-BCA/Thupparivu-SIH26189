"""Tests for Indian name entity resolution (Task 4).

Evaluates the ``compare_names`` matcher (with n-gram augmentation) against
the labeled ``tests/fixtures/entity_resolution/indian_name_pairs.json``
fixture.  Reports P/R/F1 and ensures a minimum F1 threshold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.resolution.entity_matcher import (
    MatchConfig,
    char_ngram_overlap,
    compare_names,
)

FIXTURE = ROOT / "tests" / "fixtures" / "entity_resolution" / "indian_name_pairs.json"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def labeled_pairs():
    data = json.loads(FIXTURE.read_text())
    return data.get("pairs", data)


# --------------------------------------------------------------------------- #
# char n-gram overlap unit tests
# --------------------------------------------------------------------------- #

def test_char_ngram_identical():
    assert char_ngram_overlap("Gupta", "Gupta") == 1.0


def test_char_ngram_empty():
    assert char_ngram_overlap("", "Gupta") == 0.0


def test_char_ngram_high_for_transliteration():
    score = char_ngram_overlap("Banerjee", "Banerji")
    assert score > 0.4  # substantial overlap despite spelling difference


def test_char_ngram_low_for_unrelated():
    score = char_ngram_overlap("Ramesh", "Priya")
    assert score < 0.3


# --------------------------------------------------------------------------- #
# compare_names integration (with n-gram enabled)
# --------------------------------------------------------------------------- #

class TestCompareNamesWithNgram:
    """Verify that the n-gram component improves Indian transliteration
    matches without degrading standard Levenshtein / Soundex paths."""

    def test_same_person_reorder(self):
        r = compare_names("Ramesh Kumar", "Kumar Ramesh")
        assert r.matched

    def test_same_person_initial(self):
        r = compare_names("Ramesh Kumar", "R. Kumar")
        assert r.matched

    def test_same_person_double_consonant(self):
        r = compare_names("Ramesh Kumarr", "Ramesh Kumar")
        assert r.matched

    def test_same_person_spelling_gupta(self):
        r = compare_names("Sanjay Gupta", "Sanjay Guptha")
        assert r.matched

    def test_same_person_spelling_reddy(self):
        r = compare_names("Arjun Reddy", "Arjun Reddi")
        assert r.matched

    def test_different_persons_same_surname(self):
        r = compare_names("Ramesh Kumar", "Rajesh Kumar")
        assert not r.matched

    def test_different_persons_completely(self):
        r = compare_names("Ramesh Kumar", "Rahul Sharma")
        assert not r.matched

    def test_ngram_present_in_components(self):
        r = compare_names("Gupta", "Guptha")
        assert "ngram" in r.components


# --------------------------------------------------------------------------- #
# fixture-based evaluation
# --------------------------------------------------------------------------- #

def test_indian_name_pairs_min_f1(labeled_pairs):
    """The matcher must achieve F1 >= 0.70 on the 76 labeled pairs
    (41 positive, 35 negative) to meet the Tier-1 Task 4 threshold."""
    config = MatchConfig(
        combined_threshold=0.75,
        use_first_letter_prefilter=False,  # needed for Iyer/Aiyyer etc.
    )
    tp = fp = tn = fn = 0
    for pair in labeled_pairs:
        r = compare_names(pair["a"], pair["b"], config)
        pred = 1 if r.matched else 0
        truth = pair["label"]
        if pred == 1 and truth == 1:
            tp += 1
        elif pred == 1 and truth == 0:
            fp += 1
        elif pred == 0 and truth == 0:
            tn += 1
        else:
            fn += 1
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    assert f1 >= 0.70, (
        f"Indian name resolution F1={f1:.3f} < 0.70 threshold  "
        f"(tp={tp} fp={fp} tn={tn} fn={fn} precision={precision:.3f} recall={recall:.3f})"
    )
