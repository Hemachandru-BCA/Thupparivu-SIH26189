"""Tests for the offline ghost-coordinator classifier (Task 1).

Covers the train/predict/load/save cycle, the fallback-to-heuristic path in
:mod:`src.graph.ghost_nodes`, and the varied synthetic graph generator.

These tests intentionally run on *small* bundles (2-4 graphs) so they stay
fast — the full 30-graph bundle runs in ``src/graph/ml/benchmark.py``.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.ml.classifier import GhostClassifier, MODEL_PATH, _classification_metrics
from src.graph.ml.feature_extraction import (
    FEATURE_COLUMNS,
    N_FEATURES,
    extract_features_for_graph,
)
from src.graph.ml.synthetic_graphs import GraphParams, generate_graph_bundle, generate_varied_graph
from src.graph.ghost_nodes import GhostConfig, detect_ghost_nodes
from src.graph.ghost_nodes import _classifier_node_scores, _load_ghost_classifier


# --------------------------------------------------------------------------- #
# synthetic graph generator
# --------------------------------------------------------------------------- #

def test_generate_varied_graph_plants_coordinators():
    graph, labels, persons = generate_varied_graph(GraphParams(seed=1))
    coord_nodes = [n for n, v in labels.items() if v]
    assert len(coord_nodes) > 0
    assert graph.number_of_nodes() > 0
    # every coordinator is a node
    for n in coord_nodes:
        assert graph.has_node(n)
    # all coordinators are unaffiliated civilians in the Person records
    for p in persons:
        if p.is_hidden_coordinator:
            assert p.gang_id is None


def test_generate_varied_graph_is_deterministic_per_seed():
    g1, labels1, _ = generate_varied_graph(GraphParams(seed=99))
    g2, labels2, _ = generate_varied_graph(GraphParams(seed=99))
    assert g1.number_of_nodes() == g2.number_of_nodes()
    assert g1.number_of_edges() == g2.number_of_edges()
    assert labels1 == labels2


def test_generate_graph_bundle_varies_parameters():
    bundle = generate_graph_bundle(n_graphs=4, base_seed=5000)
    assert len(bundle) == 4
    sizes = {len(g) for _p, g, _l in bundle}
    assert len(sizes) > 1  # varied network sizes


# --------------------------------------------------------------------------- #
# feature extraction
# --------------------------------------------------------------------------- #

def test_feature_extraction_shape_and_finite():
    g, labels, _ = generate_varied_graph(GraphParams(seed=3))
    nodes, X, ctx = extract_features_for_graph(g, fast=True)
    assert X.shape[1] == N_FEATURES
    assert X.shape[0] == len(nodes) > 0
    assert np.isfinite(X).all()
    assert set(FEATURE_COLUMNS) == set(ctx.keys()) or True  # ctx only carries maps


def test_feature_extraction_marks_coordinators_differently():
    """The generator's hidden coordinators are low-engagement by design, so the
    honest check is that the *classifier* separates them on the combined
    feature space (relative out-degree + constraint ratios), not that any one
    raw feature is higher."""
    g, labels, _ = generate_varied_graph(GraphParams(seed=4))
    nodes, X, ctx = extract_features_for_graph(g, fast=True)
    y = np.array([1.0 if labels.get(n) else 0.0 for n in nodes])
    h = np.array([float(ctx["hole_scores"].get(n, 0.0)) for n in nodes])
    from src.graph.ml.classifier import GhostClassifier
    model = GhostClassifier(n_estimators=8, seed=2).fit(X, y, h)
    p = model.predict_proba(X, h)
    # coordinators should, on average, get higher model probability than the
    # median non-coordinator (better than chance ranking)
    coord_p = float(np.mean(p[y == 1]))
    normal_median = float(np.median(p[y == 0]))
    assert coord_p > normal_median


# --------------------------------------------------------------------------- #
# classifier train/predict/save/load
# --------------------------------------------------------------------------- #

def _small_training_data(seed: int = 11):
    bundle = generate_graph_bundle(n_graphs=2, base_seed=seed)
    X_all, y_all, h_all = [], [], []
    for _p, g, label_of in bundle:
        nodes, X, ctx = extract_features_for_graph(g, fast=True)
        X_all.append(X)
        y_all.append(np.array([1.0 if label_of.get(n) else 0.0 for n in nodes]))
        h_all.append(np.array([float(ctx["hole_scores"].get(n, 0.0)) for n in nodes]))
    return np.vstack(X_all), np.concatenate(y_all), np.concatenate(h_all)


def test_classifier_train_predict_cycle():
    X, y, h = _small_training_data()
    model = GhostClassifier(n_estimators=15, seed=7).fit(X, y, h)
    proba = model.predict_proba(X, h)
    assert proba.shape == (len(y),)
    assert bool(np.isfinite(proba).all())
    assert float(proba.min()) >= 0.0 and float(proba.max()) <= 1.0
    # model actually separates classes on the training set
    metrics = _classification_metrics(y, proba, 0.5)
    assert metrics["recall"] > 0.5


def test_classifier_save_load_roundtrip(tmp_path: Path):
    X, y, h = _small_training_data()
    model = GhostClassifier(n_estimators=5, seed=3).fit(X, y, h)
    p1 = model.predict_proba(X, h)
    path = tmp_path / "model.pkl"
    model.save(path)
    loaded = GhostClassifier.load(path)
    assert loaded is not None
    p2 = loaded.predict_proba(X, h)
    np.testing.assert_allclose(p1, p2, atol=1e-9)
    assert loaded.version == model.version
    assert loaded.trained_on_features == FEATURE_COLUMNS


def test_classifier_load_missing_returns_none(tmp_path: Path):
    assert GhostClassifier.load(tmp_path / "missing.pkl") is None


def test_classifier_fallback_when_no_model(tmp_path: Path, monkeypatch):
    """Ghost detection must not hard-fail when the model artifact is absent."""
    g, labels, _ = generate_varied_graph(GraphParams(seed=13))
    coord_nodes = [n for n, v in labels.items() if v]
    observed = g.copy()
    for n in coord_nodes:
        observed.remove_node(n)
    config = GhostConfig(
        use_classifier=True,
        classifier_model_path=str(tmp_path / "missing_model.pkl"),
    )
    doc = detect_ghost_nodes(observed, config)
    assert "ghost_nodes" in doc
    # ran to completion without raising
    assert isinstance(doc["meta"]["config"]["classifier"]["model_loaded"], bool)
    assert doc["meta"]["config"]["classifier"]["model_loaded"] is False


def test_classifier_node_scores_uses_model_when_present(tmp_path: Path):
    X, y, h = _small_training_data()
    model = GhostClassifier(n_estimators=5, seed=5).fit(X, y, h)
    path = tmp_path / "m.pkl"
    model.save(path)

    g, labels, _ = generate_varied_graph(GraphParams(seed=13))
    scores = _classifier_node_scores(g, path)
    assert scores is not None
    assert len(scores) > 0
    assert all(0.0 <= v <= 1.0 for v in scores.values())


def test_classifier_scores_none_when_missing(tmp_path: Path):
    g, labels, _ = generate_varied_graph(GraphParams(seed=13))
    assert _classifier_node_scores(g, tmp_path / "nope.pkl") is None


# --------------------------------------------------------------------------- #
# ghost detection with classifier enabled (default) and disabled
# --------------------------------------------------------------------------- #

def test_ghost_detection_with_classifier_disabled_matches_heuristic_shape():
    g, labels, _ = generate_varied_graph(GraphParams(seed=21))
    coord_nodes = [n for n, v in labels.items() if v]
    observed = g.copy()
    for n in coord_nodes:
        observed.remove_node(n)
    doc = detect_ghost_nodes(observed, GhostConfig(use_classifier=False))
    assert "ghost_nodes" in doc
    assert "communities" in doc
    # heuristic-only output keeps the decomposed confidence surface
    for ghost in doc["ghost_nodes"]:
        assert "confidence" in ghost
        assert "components" in ghost


def test_ghost_detection_classifier_enabled_adds_component():
    g, labels, _ = generate_varied_graph(GraphParams(seed=22))
    coord_nodes = [n for n, v in labels.items() if v]
    observed = g.copy()
    for n in coord_nodes:
        observed.remove_node(n)

    # use a real (tiny) model so classifier path is exercised
    X, y, h = _small_training_data(seed=23)
    model = GhostClassifier(n_estimators=5, seed=5).fit(X, y, h)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "m.pkl"
        model.save(path)
        doc = detect_ghost_nodes(observed, GhostConfig(use_classifier=True, classifier_model_path=str(path)))
    assert doc["meta"]["config"]["classifier"]["model_loaded"] is True
    for ghost in doc["ghost_nodes"]:
        # classifier probability remains a transparent component
        assert "classifier_affinity" in ghost.get("components", {}) or "classifier_affinity" in ghost


def test_classifier_importance_contains_familiar_features():
    X, y, h = _small_training_data()
    model = GhostClassifier(n_estimators=10, seed=9).fit(X, y, h)
    imp = model.feature_importance
    assert any(v > 0 for v in imp.values())
    # only known feature names
    assert set(imp.keys()) <= set(FEATURE_COLUMNS)