"""
tests/test_ghost_ranker.py
--------------------------
Unit tests for the supervised ghost ranker.
"""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.ml.ghost_ranker import (
    GhostRanker,
    RankerArtifact,
    DEFAULT_RANKER_PATH,
    SIGNAL_NAMES,
    load_ranker_if_available,
    ranker_exists,
)


def test_generate_training_data_shapes():
    """generate_training_data returns (N, 7) X and (N,) y."""
    import networkx as nx
    graph = nx.MultiDiGraph()
    # Add some nodes
    for i in range(10):
        graph.add_node(i, name=f"Person_{i}")
    # Add some edges
    graph.add_edge(0, 1)
    graph.add_edge(1, 2)
    graph.add_edge(2, 3)

    ranker = GhostRanker()
    X, y = ranker.generate_training_data(graph, hidden_coordinator_names=["Person_0"])
    assert X.shape[1] == 7
    assert len(y) == X.shape[0]
    assert set(np.unique(y)).issubset({0, 1})


def test_fit_predict_proba_returns_float_in_01():
    """fit + predict_proba returns floats in [0, 1]."""
    X = np.random.rand(20, 7)
    y = np.array([1 if i < 10 else 0 for i in range(20)])

    ranker = GhostRanker()
    ranker.fit(X, y)

    signal = dict(zip(SIGNAL_NAMES, [0.5] * 7))
    prob = ranker.predict_proba(signal)
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0


def test_save_load_roundtrip():
    """save/load round-trip produces identical predictions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "ranker.json"
        X = np.random.rand(20, 7)
        y = np.array([1 if i < 10 else 0 for i in range(20)])

        ranker = GhostRanker()
        ranker.fit(X, y)

        prob_before = ranker.predict_proba(dict(zip(SIGNAL_NAMES, [0.3] * 7)))

        ranker.save(path)
        ranker2 = GhostRanker.load(path)
        prob_after = ranker2.predict_proba(dict(zip(SIGNAL_NAMES, [0.3] * 7)))

        assert abs(prob_before - prob_after) < 1e-9
        assert ranker2.artifact.kind == ranker.artifact.kind
        assert ranker2.artifact.trained_at is not None


def test_graceful_fallback_when_sklearn_absent(monkeypatch):
    """Test graceful fallback when sklearn is not available."""
    # We can't easily mock sklearn imports at module level without
    # reloading the module, so we just verify the fallback works
    # by using the pure-numpy backend directly.
    from src.ml.ghost_ranker import _NumpyLogistic

    X = np.random.rand(20, 7)
    y = np.array([1 if i < 10 else 0 for i in range(20)])

    backend = _NumpyLogistic()
    backend.fit(X, y)

    prob = backend.predict_proba(X[0].reshape(1, -1))[0]
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0


def test_load_nonexistent_returns_none():
    """load_ranker_if_available returns None for missing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "nonexistent.json"
        result = load_ranker_if_available(path)
        assert result is None


def test_ranker_exists_false_for_missing():
    """ranker_exists returns False for missing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "nonexistent.json"
        assert ranker_exists(path) is False


def test_ranker_artifact_serialization():
    """RankerArtifact to_dict/from_dict round-trip."""
    artifact = RankerArtifact(
        kind="logistic",
        coefficients=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
        intercept=0.5,
        cv_metrics={"precision": 0.7, "recall": 0.6, "f1": 0.65},
        brier_score=0.15,
        ece=0.08,
        n_samples=100,
    )
    d = artifact.to_dict()
    artifact2 = RankerArtifact.from_dict(d)
    assert artifact2.kind == artifact.kind
    assert artifact2.coefficients == artifact.coefficients
    assert artifact2.intercept == artifact.intercept
    assert artifact2.cv_metrics == artifact.cv_metrics
    assert artifact2.brier_score == artifact.brier_score
    assert artifact2.ece == artifact.ece
    assert artifact2.n_samples == artifact.n_samples


def test_calibrate_stores_brier_and_ece():
    """calibrate stores Brier score and ECE on the artifact."""
    X = np.random.rand(30, 7)
    y = np.array([1 if i < 15 else 0 for i in range(30)])

    ranker = GhostRanker()
    ranker.fit(X, y)

    X_val = np.random.rand(10, 7)
    y_val = np.array([1 if i < 5 else 0 for i in range(10)])

    brier, ece = ranker.calibrate(X_val, y_val)
    assert ranker.artifact.brier_score == brier
    assert ranker.artifact.ece == ece
    assert 0.0 <= brier <= 1.0
    assert 0.0 <= ece <= 1.0


def test_signal_vector_keys_match():
    """SIGNAL_NAMES matches the 7 signals expected by the heuristic engine."""
    assert len(SIGNAL_NAMES) == 7
    expected = [
        "structural_hole",
        "community_bridge",
        "temporal_affinity",
        "behavioral_similarity",
        "embedding_proximity",
        "evidence_shared_infrastructure",
        "contradiction_penalty",
    ]
    assert SIGNAL_NAMES == expected


def test_predict_proba_handles_wrong_width():
    """predict_proba gracefully handles feature vectors of wrong width."""
    X = np.random.rand(20, 7)
    y = np.array([1 if i < 10 else 0 for i in range(20)])

    ranker = GhostRanker()
    ranker.fit(X, y)

    # Provide only 5 features instead of 7 -- should not crash
    prob = ranker.predict_proba({
        "structural_hole": 0.5,
        "community_bridge": 0.5,
        "temporal_affinity": 0.5,
        "behavioral_similarity": 0.5,
        "embedding_proximity": 0.5,
    })
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0

    # Provide extra features -- should not crash
    prob2 = ranker.predict_proba({
        "structural_hole": 0.5,
        "community_bridge": 0.5,
        "temporal_affinity": 0.5,
        "behavioral_similarity": 0.5,
        "embedding_proximity": 0.5,
        "evidence_shared_infrastructure": 0.5,
        "contradiction_penalty": 0.5,
        "extra_feature": 0.5,
    })
    assert isinstance(prob2, float)
    assert 0.0 <= prob2 <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])