"""
test_p2_analytics.py
--------------------
Deterministic tests for the P2 analytical intelligence layer:

  - Geospatial intelligence (extraction, clustering, proximity)
  - Natural-language analyst query (parse → execute, ambiguity)
  - Next-best analytical action (scored recommendations, safety)
  - Case Similarity / Network DNA (fingerprints, similarity, comparison)
"""

from __future__ import annotations

import networkx as nx

from src.analysis.case_dna import CaseDNAEngine, compute_similarity, compare_cases
from src.analysis.geospatial import GeospatialEngine
from src.analysis.next_best_action import NextBestActionEngine
from src.analysis.nl_query import MockAnalystQueryProvider, NLQueryEngine


def _edge(ts="2025-01-01T00:00:00", relation="CALLED", record_id="R1", amount=None):
    attrs = {"timestamp": ts, "record_id": record_id, "confidence": 0.9}
    if amount is not None:
        attrs["amount"] = amount
    return {"relation": relation, "attributes": attrs}


def _rich_graph():
    """A graph with locations, financial edges, and temporal structure."""
    g = nx.MultiDiGraph()
    for n in "ABCDE":
        g.add_node(n, canonical_name=f"Entity {n}", entity_type="PERSON", mention_count=3)
    # Two locations
    g.add_node("LOC1", canonical_name="Chennai Central", entity_type="LOCATION")
    g.add_node("LOC2", canonical_name="Madurai North", entity_type="LOCATION")

    g.add_edge("A", "B", key="ab", **_edge("2025-01-01T00:00:00", "CALLED", "C1"))
    g.add_edge("B", "C", key="bc", **_edge("2025-01-02T00:00:00", "TRANSFERRED_TO", record_id="T1", amount=1000))
    g.add_edge("C", "D", key="cd", **_edge("2025-01-03T00:00:00", "TRANSFERRED_TO", record_id="T2", amount=800))
    g.add_edge("D", "E", key="de", **_edge("2025-01-04T00:00:00", "TRANSFERRED_TO", record_id="T3", amount=600))
    g.add_edge("E", "B", key="eb", **_edge("2025-01-05T00:00:00", "TRANSFERRED_TO", record_id="T4", amount=500))
    g.add_edge("A", "C", key="ac", **_edge("2025-01-06T00:00:00", "CALLED", "C2"))
    # Location associations
    g.add_edge("A", "LOC1", key="a_loc1", **_edge("2025-01-07T00:00:00", "LOCATED_AT", "L1"))
    g.add_edge("B", "LOC1", key="b_loc1", **_edge("2025-01-08T00:00:00", "LOCATED_AT", "L2"))
    g.add_edge("C", "LOC2", key="c_loc2", **_edge("2025-01-09T00:00:00", "LOCATED_AT", "L3"))
    return g


# --------------------------------------------------------------------------- #
# Geospatial
# --------------------------------------------------------------------------- #

def test_geospatial_extracts_observations():
    engine = GeospatialEngine(_rich_graph())
    report = engine.analyze()
    assert len(report.observations) >= 2  # A/B at LOC1, C at LOC2
    observed = [o for o in report.observations if o.location_id == "LOC1"]
    assert observed
    assert {o.entity_id for o in observed} >= {"A", "B"}
    # Evidence linkage preserved
    assert any(o.evidence_ids for o in report.observations)


def test_geospatial_clustering_is_deterministic():
    engine = GeospatialEngine(_rich_graph())
    clusters_a = engine.cluster_observations(grid_size_km=5.0)
    clusters_b = engine.cluster_observations(grid_size_km=5.0)
    assert clusters_a == clusters_b
    assert all(c.observation_count > 0 for c in clusters_a)


def test_geospatial_proximity_returns_explainable_relations():
    engine = GeospatialEngine(_rich_graph())
    relations = engine.spatial_proximity(max_distance_km=1000.0)  # large distance for deterministic coords
    # A and B are both at LOC1 → at least 1 co-occurrence (their LOC1 observations overlap)
    assert relations
    rel = relations[0]
    assert rel.entity_a != rel.entity_b
    assert rel.co_location_count >= 1
    assert rel.median_distance_m is not None


# --------------------------------------------------------------------------- #
# Natural-language query
# --------------------------------------------------------------------------- #

def test_nl_parse_financial_query():
    engine = NLQueryEngine(_rich_graph())
    interp = engine.parse("trace money transfers from B")
    assert interp.structured.intent == "financial_flow"
    assert "B" in interp.structured.entities
    assert "TRANSFERRED_TO" in interp.structured.relationship_types


def test_nl_ambiguous_query_notes_ambiguity():
    engine = NLQueryEngine(_rich_graph())
    # A query without any entity references or clear patterns
    interp = engine.parse("show me the network")
    assert interp.structured.intent == "general_search"
    assert interp.ambiguity_notes  # ambiguity documented when no specific intent found
    # No specific entity found
    assert not interp.structured.entities


def test_nl_execution_returns_structured_results():
    engine = NLQueryEngine(_rich_graph())
    result = engine.execute(engine.parse("trace money transfers from B"))
    assert result.total >= 1
    assert result.results[0].item_id  # QueryResultItem has item_id


def test_mock_provider_has_deterministic_demo_queries():
    queries = MockAnalystQueryProvider.available_queries()
    assert queries
    assert any("financial" in q["query"] for q in queries)


# --------------------------------------------------------------------------- #
# Next-best analytical action
# --------------------------------------------------------------------------- #

def test_recommendations_are_analytical_only():
    engine = NextBestActionEngine(_rich_graph())
    report = engine.generate_recommendations({"entity_id": "B"})
    assert report.recommendations
    forbidden = {"arrest", "surveill", "guilt", "mastermind", "detain", "search warrant"}
    for rec in report.recommendations:
        assert not any(word in rec.title.lower() for word in forbidden)
        assert not any(word in rec.reason.lower() for word in forbidden)
        # Every recommendation carries an explainable score
        assert rec.score.total >= 0
        assert rec.action_type in {
            "INSPECT_ENTITY", "EXPAND_NETWORK", "INSPECT_EVIDENCE",
            "REVIEW_CONTRADICTION", "REPLAY_TIMELINE", "TRACE_FINANCIAL",
            "INSPECT_MOTIF", "COMPARE_CASE", "INSPECT_LOCATION",
            "REVIEW_DATA_QUALITY", "COMPARE_METHODS",
        }


def test_recommendation_scores_are_explainable():
    engine = NextBestActionEngine(_rich_graph())
    report = engine.generate_recommendations({"entity_id": "B"})
    for rec in report.recommendations[:3]:
        # Score components present
        assert hasattr(rec.score, "evidence_value")
        assert hasattr(rec.score, "information_gain")
        assert hasattr(rec.score, "cross_case_relevance")
        assert hasattr(rec.score, "temporal_relevance")
        assert hasattr(rec.score, "unresolved_uncertainty")
        assert hasattr(rec.score, "investigator_context")
        assert rec.score.total >= 0


# --------------------------------------------------------------------------- #
# Case similarity / Network DNA
# --------------------------------------------------------------------------- #

def test_case_dna_fingerprint_is_compact_and_structural():
    engine = CaseDNAEngine(_rich_graph(), case_id="CASE-0421")
    fp = engine.generate_fingerprint()
    assert fp.case_id == "CASE-0421"
    assert fp.entity_count == 7  # A–E + LOC1 + LOC2
    assert fp.community_count >= 1
    assert fp.network_density > 0
    assert fp.financial_edge_count == 4
    assert fp.features  # flat vector present


def test_case_dna_similarity_prefers_identical_fingerprints():
    a = CaseDNAEngine(_rich_graph(), case_id="CASE-A").generate_fingerprint()
    b = CaseDNAEngine(_rich_graph(), case_id="CASE-B").generate_fingerprint()
    # Clone with slight perturbation
    perturbed = _rich_graph()
    perturbed.remove_edge("A", "B")
    c = CaseDNAEngine(perturbed, case_id="CASE-C").generate_fingerprint()
    sim_ab = compute_similarity(a, b).similarity
    sim_ac = compute_similarity(a, c).similarity
    assert sim_ab > sim_ac


def test_case_dna_comparison_is_explainable():
    a = CaseDNAEngine(_rich_graph(), case_id="CASE-A").generate_fingerprint()
    b = CaseDNAEngine(_rich_graph(), case_id="CASE-B").generate_fingerprint()
    comparison = compare_cases(a, b)
    assert comparison.case_a == "CASE-A"
    assert comparison.case_b == "CASE-B"
    assert comparison.why_similar  # explanations present
    assert comparison.dimensions  # per-metric scores
    assert comparison.limitations  # never a bare number