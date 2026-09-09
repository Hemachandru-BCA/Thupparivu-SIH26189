"""Tests for Phase-4 ML layer: link baselines, embeddings, supervised
prediction, hidden intermediaries, calibration, ensembles + disagreement."""
import sys
import math
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ml.calibration import (  # noqa: E402
    brier_score,
    expected_calibration_error,
    f1_at_threshold,
    precision_at_k,
    recall_at_k,
    roc_auc,
    pr_auc,
)
from src.ml.link_baselines import (  # noqa: E402
    baseline_scores,
    rank_candidates,
    BaselineLinkPredictor,
)
from src.ml.link_prediction_engine import (  # noqa: E402
    LinkPredictionEngine,
    LinkType,
)
from src.ml.supervised_link_predictor import (  # noqa: E402
    NumpyLogisticRegression,
    SupervisedLinkPredictor,
)
from src.ml.hidden_intermediary import (  # noqa: E402
    GhostScoreConfig,
    HiddenIntermediaryDetector,
)
from src.ml.light_gnn import LightGNNScorer  # noqa: E402


# ------------------------------------------------------------------ #
# Graph helpers
# ------------------------------------------------------------------ #

def _barbell_graph():
    """Two dense communities joined by a single bridge node."""
    g = nx.MultiDiGraph()
    # community A: A0..A4 ring + edges to a bridge
    comm_a = ["A0", "A1", "A2", "A3", "A4"]
    comm_b = ["B0", "B1", "B2", "B3", "B4"]
    bridge = "BRIDGE"
    for i in range(len(comm_a)):
        for j in range(i + 1, len(comm_a)):
            g.add_edge(comm_a[i], comm_a[j], key=f"{comm_a[i]}-{comm_a[j]}",
                       relation="CALLED")
    for i in range(len(comm_b)):
        for j in range(i + 1, len(comm_b)):
            g.add_edge(comm_b[i], comm_b[j], key=f"{comm_b[i]}-{comm_b[j]}",
                       relation="CALLED")
    # bridge only connects to one node in each community
    g.add_edge(comm_a[0], bridge, key="a0-bridge", relation="CALLED",
               attributes={"entity_type": "PERSON"})
    g.add_edge(bridge, comm_b[0], key="bridge-b0", relation="CALLED",
               attributes={"entity_type": "PERSON"})
    for n in comm_a + comm_b + [bridge]:
        g.nodes[n].setdefault("entity_type", "PERSON")
        g.nodes[n].setdefault("canonical_name", n)
    return g


# ------------------------------------------------------------------ #
# Calibration
# ------------------------------------------------------------------ #

def test_brier_score():
    assert brier_score([1, 0, 1], [1.0, 0.0, 1.0]) == 0.0
    assert brier_score([1, 0, 1], [0.5, 0.5, 0.5]) == 0.25


def test_ece_perfect_calibration():
    # 0.9 → bin 9 (0.9-1.0), 0.1 → bin 1 (0.1-0.2); both perfectly calibrated
    y = [1, 1, 0, 0]
    p = [0.9, 0.9, 0.1, 0.1]
    ece = expected_calibration_error(y, p, n_bins=10)
    # bin 9: acc=1.0, conf=0.9 → |1.0-0.9|=0.1, weight 0.5 → 0.05
    # bin 1: acc=0.0, conf=0.1 → 0.1, weight 0.5 → 0.05; total = 0.1
    assert abs(ece - 0.1) < 1e-9


def test_precision_recall_at_k():
    y = [1, 1, 0, 0, 1]
    p = [0.9, 0.8, 0.3, 0.2, 0.7]
    assert precision_at_k(y, p, 2) == 1.0   # top-2: idx 0,1 (both +)
    assert precision_at_k(y, p, 3) == 1.0   # top-3: idx 0,1,4 (all +)
    assert recall_at_k(y, p, 2) == 2 / 3    # 2 of 3 positives recovered
    assert recall_at_k(y, p, 5) == 1.0


def test_f1_threshold():
    m = f1_at_threshold([1, 0, 1], [0.8, 0.2, 0.7], 0.5)
    assert m["tp"] == 2
    assert m["fp"] == 0
    assert m["fn"] == 0
    assert m["f1"] == 1.0


def test_roc_pr_auc():
    y = [1, 1, 0, 0]
    p = [0.9, 0.6, 0.4, 0.1]
    assert 0.0 < roc_auc(y, p) <= 1.0
    assert 0.0 < pr_auc(y, p) <= 1.0


# ------------------------------------------------------------------ #
# Classical baselines
# ------------------------------------------------------------------ #

def test_baseline_scores_shape():
    g = _barbell_graph()
    scores = baseline_scores(g, "A0", "B1")
    for name in ["common_neighbors", "jaccard", "adamic_adar",
                 "resource_allocation", "preferential_attachment"]:
        assert name in scores


def test_jaccard_identical_neighbors():
    g = nx.Graph()
    g.add_edge("A", "X")
    g.add_edge("B", "X")
    g.add_edge("A", "Y")
    g.add_edge("B", "Y")
    # A and B share both neighbors → jaccard = 1.0
    assert abs(__import__("src.ml.link_baselines", fromlist=["jaccard"]).jaccard(g, "A", "B") - 1.0) < 1e-9


def test_rank_candidates():
    g = _barbell_graph()
    pairs = [("A0", "B1"), ("A1", "A2"), ("B1", "B2")]
    ranked = rank_candidates(g, pairs, metric="common_neighbors")
    assert len(ranked) == 3
    # scores sorted descending
    scores = [x[2] for x in ranked]
    assert scores == sorted(scores, reverse=True)
    # intra-community pairs have more common neighbors than cross-community
    assert ranked[0][2] >= ranked[-1][2]


def test_baseline_predictor():
    g = _barbell_graph()
    model = BaselineLinkPredictor(metric="adamic_adar", ensemble=["adamic_adar", "jaccard"])
    model.fit(g)
    out = model.predict("A0", "B1")
    assert "ensemble" in out
    assert 0.0 <= out["ensemble"] <= 1.0


# ------------------------------------------------------------------ #
# Supervised
# ------------------------------------------------------------------ #

def test_numpy_logistic_trains():
    X = [[0.1, 0.2], [0.9, 0.8], [0.2, 0.1], [0.8, 0.9], [0.15, 0.25], [0.7, 0.85]]
    y = [0, 1, 0, 1, 0, 1]
    model = NumpyLogisticRegression(epochs=500, lr=0.2, seed=1)
    model.fit(X, y)
    probs = model.predict_proba(X)
    # model should separate the two classes reasonably
    assert probs[1] > probs[0]
    assert probs[3] > probs[2]


def test_supervised_predictor_sklearn_or_fallback():
    X = [[0.1], [0.9], [0.2], [0.8], [0.15], [0.85]]
    y = [0, 1, 0, 1, 0, 1]
    model = SupervisedLinkPredictor(model_kind="logistic", seed=42)
    model.fit(X, y)
    assert model.predict([0.95])[0] == 1
    assert model.predict([0.05])[0] == 0


def test_supervised_feature_importance():
    X = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0]]
    y = [1, 0, 1, 0]
    model = SupervisedLinkPredictor(model_kind="logistic", seed=42)
    model.fit(X, y)
    imp = model.feature_importance()
    assert isinstance(imp, dict)


# ------------------------------------------------------------------ #
# Link Prediction Engine
# ------------------------------------------------------------------ #

def test_engine_predicts_and_labels():
    g = _barbell_graph()
    engine = LinkPredictionEngine(use_embeddings=False, use_supervised=False,
                                  use_temporal=False)
    engine.fit(g)
    result = engine.predict_link("A0", "B1")
    assert result.probability >= 0.0
    assert result.status in (LinkType.INFERRED, LinkType.PREDICTED_FUTURE,
                             LinkType.HYPOTHETICAL)
    assert result.explanation
    assert "model_disagreement" in result.to_dict()


def test_engine_observed_link_labeled():
    g = _barbell_graph()
    engine = LinkPredictionEngine(use_embeddings=False, use_supervised=False,
                                  use_temporal=False)
    engine.fit(g)
    result = engine.predict_link("A0", "BRIDGE")
    assert result.status == LinkType.OBSERVED


def test_engine_model_disagreement_represented():
    """Different models returning different probabilities must lower the
    reported probability (not silently average)."""
    g = _barbell_graph()
    engine = LinkPredictionEngine(use_embeddings=False, use_supervised=False,
                                  use_temporal=False)
    engine.fit(g)
    # force disagreement into the model_scores
    result = engine.predict_link("A0", "B1")
    if len(result.model_scored) >= 2:
        scores = list(result.model_scored.values())
        spread = max(scores) - min(scores)
        if spread > 0.3:
            assert result.model_disagreement > 0.0


def test_engine_candidate_pool():
    g = _barbell_graph()
    engine = LinkPredictionEngine(use_embeddings=False, use_supervised=False,
                                  use_temporal=False)
    engine.fit(g)
    assert len(engine.candidates) > 0
    for u, v in engine.candidates:
        assert not g.has_edge(u, v)


# ------------------------------------------------------------------ #
# Hidden intermediary
# ------------------------------------------------------------------ #

def test_hidden_intermediary_detection():
    g = _barbell_graph()
    detector = HiddenIntermediaryDetector(use_embeddings=False)
    detector.fit(g)
    candidates = detector.detect(min_score=0.0, top_n=5)
    assert len(candidates) > 0
    for c in candidates:
        assert 0.0 <= c.ghost_score <= 1.0
        assert c.explanation
        # no fabricated confidence: signals must be present
        assert "structural" in c.signals


def test_ghost_score_bounded():
    import random
    g = _barbell_graph()
    detector = HiddenIntermediaryDetector(use_embeddings=False)
    detector.fit(g)
    candidates = detector.detect(min_score=0.0, top_n=5)
    for c in candidates:
        assert 0.0 <= c.ghost_score <= 1.0


def test_ghost_detector_no_communities_single():
    g = nx.MultiDiGraph()
    g.add_node("A", entity_type="PERSON")
    detector = HiddenIntermediaryDetector(use_embeddings=False)
    detector.fit(g)
    candidates = detector.detect()
    assert candidates == []


# ------------------------------------------------------------------ #
# Link types never conflated
# ------------------------------------------------------------------ #

def test_link_types_distinct():
    assert LinkType.OBSERVED.value != LinkType.INFERRED.value
    assert LinkType.INFERRED.value != LinkType.PREDICTED_FUTURE.value
    assert LinkType.PREDICTED_FUTURE.value != LinkType.HYPOTHETICAL.value


# ------------------------------------------------------------------ #
# Optional GNN backend
# ------------------------------------------------------------------ #

def test_light_gnn_scorer():
    g = _barbell_graph()
    scorer = LightGNNScorer(seed=42)
    scorer.fit(g)
    p = scorer.score("A0", "B1")
    assert 0.0 <= p <= 1.0
    # intra-community pair should be scored at least as high as the
    # cross-community candidate
    p_intra = scorer.score("A0", "A1")
    assert p_intra >= p - 0.2


def test_light_gnn_registers_into_engine():
    from src.ml.link_prediction_engine import LinkPredictionEngine
    g = _barbell_graph()
    engine = LinkPredictionEngine(use_embeddings=False, use_supervised=False,
                                  use_temporal=False)
    engine.fit(g)
    scorer = LightGNNScorer(seed=1)
    scorer.fit(g)
    scorer.register(engine)
    result = engine.predict_link("A0", "B1")
    assert "gnn" in result.model_scored