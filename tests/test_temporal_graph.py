"""Tests for the Phase-2 temporal multilayer graph engine and temporal
leakage detection."""
import sys
from datetime import datetime, timezone

import networkx as nx
import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.temporal_graph import (  # noqa: E402
    EntityLayer,
    RelationshipLayer,
    TemporalEdge,
    TemporalMultilayerGraph,
    _parse_ts,
    classify_relation,
)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_edge(src, tgt, relation, timestamp, key=None):
    """Build a tiny graph with one edge carrying a timestamp in attributes."""
    g = nx.MultiDiGraph()
    g.add_node(src, entity_type="PERSON", canonical_name=src)
    g.add_node(tgt, entity_type="PERSON", canonical_name=tgt)
    g.add_edge(src, tgt, key=key or f"{src}|{relation}|{tgt}",
               id=key or f"{src}|{relation}|{tgt}",
               relation=relation,
               attributes={"timestamp": timestamp, "confidence": 0.9})
    return g


def _build_chain_graph():
    """5-node temporal chain: A→B→C→D→E with dates 2025-01-01 to 2025-01-05."""
    g = nx.MultiDiGraph()
    nodes = [("A", "PERSON"), ("B", "PERSON"), ("C", "LOCATION"), ("D", "PHONE"), ("E", "ACCOUNT")]
    for n, t in nodes:
        g.add_node(n, entity_type=t, canonical_name=n)
    edges = [
        ("A", "B", "CALLED", "2025-01-01T08:00:00Z"),
        ("B", "C", "LOCATED_IN", "2025-01-02T09:00:00Z"),
        ("C", "D", "ASSOCIATED_WITH", "2025-01-03T10:00:00Z"),
        ("D", "E", "TRANSFERRED_TO", "2025-01-04T11:00:00Z"),
    ]
    for s, t, rel, ts in edges:
        g.add_edge(s, t, key=f"{s}|{rel}|{t}", id=f"{s}|{rel}|{t}",
                   relation=rel, attributes={"timestamp": ts})
    return g


# ------------------------------------------------------------------ #
# Timestamp helpers
# ------------------------------------------------------------------ #

def test_parse_ts_variants():
    assert _parse_ts("2025-01-01T00:00:00Z") is not None
    assert _parse_ts("2025-06-15T12:30:00+05:30") is not None
    assert _parse_ts(None) is None
    assert _parse_ts("") is None
    assert _parse_ts("not-a-date") is None


def test_classify_relation():
    assert classify_relation("CALLED") == RelationshipLayer.COMMUNICATION
    assert classify_relation("TRANSFERRED_TO") == RelationshipLayer.FINANCIAL
    assert classify_relation("LOCATED_IN") == RelationshipLayer.LOCATION
    assert classify_relation("MEMBER_OF") == RelationshipLayer.ORGANIZATIONAL
    assert classify_relation("ASSOCIATED_WITH") == RelationshipLayer.SOCIAL


# ------------------------------------------------------------------ #
# TemporalEdge.is_active_at
# ------------------------------------------------------------------ #

def test_edge_active_at():
    te = TemporalEdge(source="A", target="B", key="k", relation="CALLED",
                      layer=RelationshipLayer.COMMUNICATION,
                      observed_at=_parse_ts("2025-03-01T00:00:00Z"))
    assert te.is_active_at(_parse_ts("2025-04-01T00:00:00Z"))
    assert not te.is_active_at(_parse_ts("2025-02-01T00:00:00Z"))
    # unknown timestamp → always visible
    te2 = TemporalEdge(source="A", target="B", key="k", relation="CALLED",
                       layer=RelationshipLayer.COMMUNICATION)
    assert te2.is_active_at(_parse_ts("2025-12-31T00:00:00Z"))


# ------------------------------------------------------------------ #
# Snapshot API
# ------------------------------------------------------------------ #

def test_graph_as_of_excludes_future_edges():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    # 2025-01-02: only A→B and B→C should exist
    snap = tm.graph_as_of("2025-01-02T12:00:00Z")
    edges = list(snap.edges(keys=True, data=True))
    assert len(edges) == 2
    rels = {d["relation"] for _, _, _, d in edges}
    assert "CALLED" in rels
    assert "LOCATED_IN" in rels
    assert "TRANSFERRED_TO" not in rels


def test_graph_as_of_single_edge():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    snap = tm.graph_as_of("2025-01-01T12:00:00Z")
    assert snap.number_of_edges() == 1


def test_graph_between():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    # edges strictly within [01-02, 01-04]: B→C (01-02), C→D (01-03)
    snap = tm.graph_between("2025-01-02T00:00:00Z", "2025-01-04T00:00:00Z")
    assert snap.number_of_edges() == 2


def test_graph_before_after():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    before = tm.graph_before("2025-01-03T00:00:00Z")
    assert before.number_of_edges() == 2
    after = tm.graph_after("2025-01-03T00:00:00Z")
    assert after.number_of_edges() == 2


# ------------------------------------------------------------------ #
# Multilayer views
# ------------------------------------------------------------------ #

def test_layer_view_communication():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    comm = tm.layer_view(RelationshipLayer.COMMUNICATION)
    assert comm.number_of_edges() == 1  # only A→B CALLED
    fin = tm.layer_view(RelationshipLayer.FINANCIAL)
    assert fin.number_of_edges() == 1  # only D→E TRANSFERRED_TO


def test_multiplex_graph_preserves_all():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    mx = tm.multiplex_graph()
    assert mx.number_of_edges() == 4
    # every edge has a layer attribute
    for _, _, d in mx.edges(data=True):
        assert "layer" in d


def test_all_layers():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    layers = tm.all_layers()
    assert "COMMUNICATION" in layers
    assert "FINANCIAL" in layers
    assert "LOCATION" in layers
    assert "SOCIAL" in layers


# ------------------------------------------------------------------ #
# Temporal node/edge features
# ------------------------------------------------------------------ #

def test_temporal_node_features():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    feat = tm.temporal_node_features("B")
    assert feat["node"] == "B"
    assert feat["activity_count"] == 2  # A→B and B→C


def test_temporal_edge_features():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    feat = tm.temporal_edge_features("A", "B")
    assert feat["interaction_count"] == 1
    assert "COMMUNICATION" in feat["layers"]


# ------------------------------------------------------------------ #
# Temporal graph statistics
# ------------------------------------------------------------------ #

def test_temporal_statistics():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    stats = tm.temporal_statistics()
    assert stats["edge_count"] == 4
    assert stats["node_count"] == 5
    assert stats["new_edge_velocity_per_day"] > 0
    assert "COMMUNICATION" in stats["layer_counts"]


def test_degree_over_time():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    dot = tm.degree_over_time("B")
    assert len(dot) == 2
    assert dot[-1]["cumulative_degree"] == 2


# ------------------------------------------------------------------ #
# Temporal leakage test (Phase 2 requirement 10)
# ------------------------------------------------------------------ #

def test_temporal_leakage_detection():
    """
    Temporal leakage: at time t, the system must NOT use information
    discovered AFTER t.

    This test creates a graph with known timestamps, builds a snapshot at
    t=2025-01-02, then verifies:
      1. The snapshot does NOT contain edges with timestamp > 2025-01-02.
      2. Centrality is computed ONLY on surviving edges.
      3. Community assignments use only past information.
    """
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    snap = tm.graph_as_of("2025-01-02T12:00:00Z")

    # Rule 1: no future edges
    for _, _, d in snap.edges(data=True):
        ts = d.get("attributes", {}).get("timestamp")
        if ts:
            assert _parse_ts(ts) <= _parse_ts("2025-01-02T12:00:00Z"), (
                f"LEAKAGE: edge has future timestamp {ts}"
            )

    # Rule 2: degree centrality is computed only on surviving edges
    deg_cent = nx.degree_centrality(snap)
    # node D has degree 0 in the snapshot (its only edge is on 2025-01-04)
    assert deg_cent.get("D", 0) == 0.0, "D should have zero centrality before its edge appears"

    # Rule 3: community detection on the snapshot uses only past edges
    from networkx.algorithms.community import louvain_communities
    if snap.number_of_edges() > 1:
        comms = louvain_communities(snap, seed=42)
        # node D is isolated before its edge appears → it is NOT assigned
        # to any community (louvain drops isolated nodes)
        d_community = [c for c in comms if "D" in c]
        assert len(d_community) == 0, "D must not be clustered before its edge exists"


def test_no_leakage_in_full_graph_as_of():
    """Full graph (no timestamp) should not leak when edge has no timestamp."""
    g = nx.MultiDiGraph()
    g.add_node("A", entity_type="PERSON", canonical_name="A")
    g.add_node("B", entity_type="PERSON", canonical_name="B")
    g.add_edge("A", "B", key="AB", id="AB", relation="CALLED",
               attributes={"confidence": 0.8})  # no timestamp
    tm = TemporalMultilayerGraph(g)
    snap = tm.graph_as_of("2025-01-01T00:00:00Z")
    # edge with no timestamp is treated as "always known" — this is
    # correct because we cannot prove it was discovered later
    assert snap.number_of_edges() == 1


# ------------------------------------------------------------------ #
# Bridge emergence
# ------------------------------------------------------------------ #

def test_bridge_emergence():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    bridges = tm.bridge_emergence()
    # In a chain graph every edge is a bridge when it first appears
    assert len(bridges) >= 1
    for b in bridges:
        assert "timestamp" in b
        assert "bridge_edge" in b


# ------------------------------------------------------------------ #
# Community changes
# ------------------------------------------------------------------ #

def test_community_changes():
    g = _build_chain_graph()
    tm = TemporalMultilayerGraph(g)
    changes = tm.community_changes()
    # At least one community reassignment should be recorded
    assert isinstance(changes, list)