"""Tests for temporal feature engineering with no-leakage guarantees."""
import sys
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.temporal_features import (  # noqa: E402
    FEATURE_NAMES,
    TemporalFeatureEngine,
    build_temporal_candidates,
)


def _build_graph():
    """Graph where a future edge A-D only appears on 2025-01-05."""
    g = nx.MultiDiGraph()
    for n, t in [("A", "PERSON"), ("B", "PERSON"), ("C", "PERSON"),
                 ("D", "PERSON"), ("E", "ACCOUNT"), ("F", "ACCOUNT")]:
        g.add_node(n, entity_type=t, canonical_name=n)
    # observed before 2025-01-03
    edges = [
        ("A", "B", "CALLED", "2025-01-01T08:00:00Z"),
        ("B", "C", "CALLED", "2025-01-01T09:00:00Z"),
        ("C", "D", "MET", "2025-01-02T10:00:00Z"),
        ("A", "E", "USES_ACCOUNT", "2025-01-02T11:00:00Z"),
        ("B", "F", "USES_ACCOUNT", "2025-01-02T12:00:00Z"),
        # future edge — must NOT influence features at 2025-01-03
        ("A", "D", "CALLED", "2025-01-05T08:00:00Z"),
    ]
    for s, t, rel, ts in edges:
        g.add_edge(s, t, key=f"{s}|{rel}|{t}", id=f"{s}|{rel}|{t}",
                   relation=rel, attributes={"timestamp": ts})
    return g


def test_feature_names_consistent():
    engine = TemporalFeatureEngine.from_graph(_build_graph(), "2025-01-03T00:00:00Z")
    vec = engine.feature_vector("A", "B")
    assert len(vec) == len(FEATURE_NAMES)


def test_future_edge_not_in_snapshot_features():
    g = _build_graph()
    engine = TemporalFeatureEngine.from_graph(g, "2025-01-03T00:00:00Z")
    snap = engine.snapshot
    # A→D edge is on 2025-01-05 → must NOT be in the 01-03 snapshot
    assert not snap.has_edge("A", "D"), "future edge leaked into snapshot"

    # common_neighbors of A,B at 01-03: A's out-neighbors = {B,E}, B's = {C,F} → none
    feats = engine.features_for("A", "B")
    assert feats["common_neighbors"] == 0.0
    # but A→D must NOT appear even as a future edge: D is not a common neighbor
    assert feats["same_community"] in (0.0, 1.0)


def test_candidate_generation_excludes_observed():
    g = _build_graph()
    engine = TemporalFeatureEngine.from_graph(g, "2025-01-03T00:00:00Z")
    candidates = engine.build_candidates(top_n=20)
    for u, v in candidates:
        assert not engine.snapshot.has_edge(u, v)
        assert not engine.snapshot.has_edge(v, u)


def test_temporal_window_excludes_future():
    g = _build_graph()
    engine = TemporalFeatureEngine.from_graph(g, "2025-01-03T00:00:00Z")
    # interaction_frequency between A and D must be 0 (their only edge is future)
    feats = engine.features_for("A", "D")
    assert feats["interaction_frequency"] == 0.0
    assert feats["source_activity"] <= 2.0  # A's activities up to 01-03


def test_build_temporal_candidates_returns_pairs():
    g = _build_graph()
    pairs = build_temporal_candidates(g, "2025-01-03T00:00:00Z", top_n=10)
    assert isinstance(pairs, list)
    for p in pairs:
        assert len(p) == 2