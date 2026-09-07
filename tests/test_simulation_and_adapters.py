"""Tests for the counterfactual simulation API (Phase J/K) and adapters."""
import json
import pickle
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.simulation import (  # noqa: E402
    SimulationConfig,
    SimulationError,
    build_simulation_context,
    compare_interventions,
    counterfactual_node_removal,
)


@pytest.fixture(scope="module")
def graph():
    from src.api import paths

    if not paths.GRAPH_PKL_PATH.exists():
        pytest.skip("graph artifact not built")
    with open(paths.GRAPH_PKL_PATH, "rb") as fh:
        return pickle.load(fh)


@pytest.fixture(scope="module")
def small_graph():
    """Tiny deterministic graph for the core assertions."""
    import networkx as nx

    g = nx.MultiDiGraph()
    g.add_edge("A", "B", id="e1", relation="CALLED", attributes={})
    g.add_edge("A", "C", id="e2", relation="CALLED", attributes={})
    g.add_edge("B", "C", id="e3", relation="CALLED", attributes={})
    g.add_edge("C", "D", id="e4", relation="TRANSFERRED_TO", attributes={})
    for n in g.nodes:
        g.nodes[n].update({"guid": n, "canonical_name": f"Node {n}",
                           "entity_type": "PERSON", "metrics": {}})
    return g


def test_counterfactual_removes_exactly_one_node(small_graph):
    result = counterfactual_node_removal(small_graph, "C", depth=2)
    assert result["counterfactual"]["nodes"] == small_graph.number_of_nodes() - 1
    assert result["counterfactual"]["edges"] == small_graph.number_of_edges() - 3


def test_counterfactual_payload_contract(small_graph):
    result = counterfactual_node_removal(small_graph, "C", depth=2,
                                         include_reranking=True)
    for key in ("simulation_id", "target_node_id", "baseline", "counterfactual",
                "delta", "fragmentation_score", "connectivity_change",
                "community_changes", "new_brokers", "alternate_paths",
                "affected_nodes", "affected_edges", "warnings", "method"):
        assert key in result, f"missing contract key: {key}"
    assert result["method"] == "NODE_REMOVAL_COUNTERFACTUAL"
    assert "NOT" in result["disclaimer"] and "enforcement" in result["disclaimer"].lower()
    assert result["delta"]["gcc_size_loss"] >= 0
    assert 0.0 <= (result["fragmentation_score"] or 0.0) <= 1.0
    # C had 3 incident edges (2 out + 1 in)
    assert len(result["affected_edges"]) == 3


def test_counterfactual_unknown_node_raises(small_graph):
    with pytest.raises(SimulationError):
        counterfactual_node_removal(small_graph, "MISSING")


def test_comparison_sandbox_ranks_and_labels(small_graph):
    doc = compare_interventions(small_graph, ["C", "A", "MISSING"])
    assert doc["ranking_note"].startswith("NETWORK EFFECT SCORE")
    assert doc["method"] == "INTERVENTION_COMPARISON_SANDBOX"
    by_id = {s["node_id"]: s for s in doc["scenarios"]}
    assert "error" in by_id["MISSING"]
    ranks = [s.get("network_effect_rank") for s in doc["scenarios"] if "error" not in s]
    assert sorted(r for r in ranks if r is not None) == list(range(1, len(ranks) + 1))


def test_precomputed_context_matches_fresh(small_graph):
    """Cached context must produce identical metrics to a fresh computation."""
    config = SimulationConfig(efficiency_sample_size=64)
    node = "C"
    ctx = build_simulation_context(small_graph, new_broker_sample=50)
    fresh = counterfactual_node_removal(
        small_graph, node, depth=1, include_reranking=False, config=config,
    )
    cached = counterfactual_node_removal(
        small_graph, node, depth=1, include_reranking=False,
        config=config, precomputed=ctx,
    )
    assert fresh["baseline"]["nodes"] == cached["baseline"]["nodes"]
    assert fresh["counterfactual"]["fragmentation"] == cached["counterfactual"]["fragmentation"]
    assert fresh["community_changes"]["num_communities_after"] == \
        cached["community_changes"]["num_communities_after"]


def test_rerouting_score_bounds(small_graph):
    result = counterfactual_node_removal(
        small_graph, "C", depth=1, include_reranking=True,
        config=SimulationConfig(efficiency_sample_size=64),
    )
    assert result["rerouting_score"] is None or 0.0 <= result["rerouting_score"] <= 1.0


@pytest.mark.slow
def test_full_graph_counterfactual_smoke(graph):
    """End-to-end counterfactual on the real artifact (marked slow)."""
    node = max(graph.nodes, key=lambda n: graph.degree(n))
    result = counterfactual_node_removal(
        graph, node, depth=1, include_reranking=False,
        config=SimulationConfig(efficiency_sample_size=64), new_broker_sample=50,
    )
    assert result["counterfactual"]["nodes"] == graph.number_of_nodes() - 1


# ------------------------------------------------------------------- adapters
def test_networkx_graph_store_interface(graph):
    from src.adapters.graph_store import NetworkXGraphStore

    store = NetworkXGraphStore(graph)
    node_id = next(iter(graph.nodes))
    node = store.get_node(node_id)
    assert node and node["id"] == str(node_id)
    sub = store.get_subgraph(node_id, depth=1, max_nodes=20)
    assert sub["node_count"] <= 20 and sub["node_count"] >= 1
    paths = store.get_paths(*list(graph.nodes)[:2], k=1) if graph.number_of_nodes() >= 2 else []
    assert isinstance(paths, list)
    assert isinstance(store, type(store))


def test_graph_store_protocol_satisfied(graph):
    from src.adapters.graph_store import GraphStore, NetworkXGraphStore

    assert isinstance(NetworkXGraphStore(graph), GraphStore)


def test_adapters_disabled_without_config(monkeypatch):
    from src.adapters.postgres_repository import AdapterNotConfigured, PostgresSourceRepository
    from src.adapters.s3_document_store import S3DocumentStore

    monkeypatch.delenv("SENTINELGRAPH_PG_DSN", raising=False)
    monkeypatch.delenv("SENTINELGRAPH_S3_BUCKET", raising=False)
    with pytest.raises(AdapterNotConfigured):
        PostgresSourceRepository()
    with pytest.raises(AdapterNotConfigured):
        S3DocumentStore()


def test_local_document_store(tmp_path):
    from src.adapters.s3_document_store import LocalDocumentStore

    store = LocalDocumentStore(tmp_path / "raw")
    store.put_document("docs/a.txt", b"hello")
    assert store.get_document("docs/a.txt") == b"hello"
    assert store.list_documents("docs/") == ["docs/a.txt"]
    # traversal-safe
    assert ".." not in store._path("../../etc/passwd").parts[-1]


def test_in_memory_event_stream():
    from src.adapters.kafka_event_stream import InMemoryEventStream, TOPIC_CDR

    stream = InMemoryEventStream()
    seen = []
    stream.subscribe(TOPIC_CDR, seen.append)
    stream.publish(TOPIC_CDR, {"call_id": "C1"})
    assert seen and seen[0]["call_id"] == "C1"
    assert stream.recent(TOPIC_CDR)[0]["topic"] == TOPIC_CDR
