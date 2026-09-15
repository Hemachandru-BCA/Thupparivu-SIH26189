"""Tests for confidence calibration (Task 2 of Tier-1 accuracy directive)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.xai.calibration import (
    ConfidenceCalibrator,
    _isotonic_fit,
    _platt_fit,
    ece,
    reliability_diagram_ascii,
)
from src.xai.findings import FindingBuilder, Finding


def _synthetic_miscalibrated(n: int = 4000, seed: int = 1):
    rng = np.random.RandomState(seed)
    raw = np.clip(rng.beta(2, 4, n) * 1.3, 0, 1)
    outcome = (rng.rand(n) < raw * 0.55).astype(int)
    return raw, outcome


def test_isotonic_is_monotone():
    x, y = _synthetic_miscalibrated(2000)
    xs, ys = _isotonic_fit(x, y)
    assert np.all(np.diff(ys) >= -1e-9)


def test_isotonic_improves_ece():
    x, y = _synthetic_miscalibrated(4000)
    cal = ConfidenceCalibrator(method="isotonic").fit(x, y)
    # raw scores are over-optimistic; calibration must reduce ECE
    assert cal.ece_after < cal.ece_before
    assert cal.ece_after < 0.1


def test_platt_improves_ece():
    x, y = _synthetic_miscalibrated(4000)
    cal = ConfidenceCalibrator(method="platt").fit(x, y)
    assert cal.ece_after < cal.ece_before
    assert cal.ece_after < 0.2


def test_calibration_maps_to_probability_range():
    x, y = _synthetic_miscalibrated(1000)
    cal = ConfidenceCalibrator(method="isotonic").fit(x, y)
    out = cal.apply(np.array([0.0, 0.3, 0.5, 0.8, 1.0]))
    assert bool(np.all(out >= 0.0))
    assert bool(np.all(out <= 1.0))
    assert bool(np.all(np.isfinite(out)))


def test_calibration_save_load_roundtrip(tmp_path):
    x, y = _synthetic_miscalibrated(500)
    cal = ConfidenceCalibrator(method="isotonic").fit(x, y)
    p = tmp_path / "cal.pkl"
    cal.save(p)
    loaded = ConfidenceCalibrator.load(p)
    assert loaded is not None
    np.testing.assert_allclose(loaded.apply(x[:10]), cal.apply(x[:10]), atol=1e-9)
    assert loaded.ece_before == cal.ece_before


def test_calibration_load_missing_returns_none(tmp_path):
    assert ConfidenceCalibrator.load(tmp_path / "nope.pkl") is None


def test_reliability_diagram_has_buckets():
    x, y = _synthetic_miscalibrated(2000)
    cal = ConfidenceCalibrator(method="isotonic").fit(x, y)
    rows = cal.reliability(x, y, n_bins=5)
    assert len(rows) > 0
    for r in rows:
        assert 0.0 <= r["mean_predicted"] <= 1.0
        assert 0.0 <= r["observed_accuracy"] <= 1.0
        assert r["n"] > 0
    art = reliability_diagram_ascii(rows)
    assert "Reliability" in art


def test_finding_builder_calibrates_with_artifact(tmp_path):
    """When a calibrator artifact exists, Finding confidence gets mapped."""
    x, y = _synthetic_miscalibrated(500)
    cal = ConfidenceCalibrator(method="isotonic").fit(x, y)
    path = tmp_path / "cal.pkl"
    cal.save(path)

    # a deliberately over-optimistic raw ghost confidence
    raw_conf = 0.9
    from src.xai.evidence_tracer import EvidenceStore
    store = EvidenceStore()
    builder = FindingBuilder(store, calibrator_path=str(path))
    ghost = {
        "ghost_id": "G1",
        "confidence": raw_conf,
        "confidence_breakdown": {"weights": {}, "components": []},
        "community_pair": [0, 1],
        "label": "Ghost A",
    }
    finding = builder.from_ghost(ghost)
    mapped = float(cal.apply([raw_conf])[0])
    assert abs(finding.confidence - min(round(mapped, 4), 0.999)) < 1e-6
    assert finding.confidence <= 0.999


def test_finding_builder_without_calibrator_keeps_raw(tmp_path):
    from src.xai.evidence_tracer import EvidenceStore
    store = EvidenceStore()
    builder = FindingBuilder(store, calibrator_path=str(tmp_path / "missing.pkl"))
    assert builder._calibrator is None
    ghost = {"ghost_id": "G2", "confidence": 0.73, "community_pair": [0, 1]}
    finding = builder.from_ghost(ghost)
    assert finding.confidence == 0.73


def test_ece_helper():
    pred = np.array([0.1, 0.1, 0.9, 0.9])
    y = np.array([0, 0, 1, 1])
    assert 0.0 <= ece(pred, y) <= 1.0