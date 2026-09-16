"""
tests/test_investigation_priority.py
------------------------------------
Unit tests for the Investigation Priority Score engine (Phase A).

Covers:
  - Component availability (network influence always present; optional
    components correctly marked unavailable when no signal exists).
  - Weight normalisation and renormalisation over available components.
  - Fallback for unknown entities.
  - Score boundary (0..100).
  - Priority components sum to priority_score.
  - Ranked entity output respects type filter and limit.
  - Deterministic IDs and no fabricated facts.
"""
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.investigation_priority import (
    DEFAULT_WEIGHTS,
    InvestigationPriorityEngine,
    PriorityComponent,
    PriorityResult,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_graph() -> nx.MultiDiGraph:
    """A small deterministic graph with 4 persons, 2 communities, 1 bridge."""
    g = nx.MultiDiGraph()
    persons = {
        "A": {"canonical_name": "Alice", "entity_type": "PERSON",
              "metrics": {"pagerank": 0.040, "degree_centrality": 0.80, "betweenness_centrality": 0.66}},
        "B": {"canonical_name": "Bob", "entity_type": "PERSON",
              "metrics": {"pagerank": 0.015, "degree_centrality": 0.40, "betweenness_centrality": 0.10}},
        "C": {"canonical_name": "Carol", "entity_type": "PERSON",
              "metrics": {"pagerank": 0.010, "degree_centrality": 0.30, "betweenness_centrality": 0.05}},
        "D": {"canonical_name": "Dave", "entity_type": "PERSON",
              "metrics": {"pagerank": 0.008, "degree_centrality": 0.20, "betweenness_centrality": 0.01}},
    }
    for nid, attrs in persons.items():
        g.add_node(nid, **attrs)
    # Two triangles + A bridges both
    g.add_edge("A", "B", relation="CALLED", attributes={})
    g.add_edge("A", "C", relation="CALLED", attributes={})
    g.add_edge("B", "C", relation="CALLED", attributes={})
    g.add_edge("A", "D", relation="CALLED", attributes={})
    g.add_edge("C", "D", relation="CALLED", attributes={})
    return g


@pytest.fixture
def engine() -> InvestigationPriorityEngine:
    return InvestigationPriorityEngine(graph=_make_graph())


@pytest.fixture
def engine_with_evidence() -> InvestigationPriorityEngine:
    """Engine with a mock evidence store that returns 10 records for node A."""
    g = _make_graph()

    class _MockEvidence:
        def get_evidence_for_node(self, node_id, limit=200):
            if node_id == "A":
                return [type("E", (), {"evidence_id": f"EV-{i}"})() for i in range(10)]
            return []

    return InvestigationPriorityEngine(graph=g, evidence_store=_MockEvidence())


# --------------------------------------------------------------------------- #
# Priority Result structure
# --------------------------------------------------------------------------- #

class TestPriorityStructure:
    def test_score_range(self, engine: InvestigationPriorityEngine):
        r = engine.score_entity("A")
        assert 0 <= r.priority_score <= 100

    def test_entity_metadata(self, engine: InvestigationPriorityEngine):
        r = engine.score_entity("A")
        assert r.entity_id == "A"
        assert r.entity_name == "Alice"
        assert r.entity_type == "PERSON"

    def test_components_present(self, engine: InvestigationPriorityEngine):
        r = engine.score_entity("A")
        component_names = {c.name for c in r.components}
        assert component_names == {
            "network_influence", "bridge_potential", "communication_anomaly",
            "financial_anomaly", "temporal_correlation", "cross_case_linkage",
            "evidence_strength",
        }

    def test_disclaimer_not_guilt(self, engine: InvestigationPriorityEngine):
        r = engine.score_entity("A")
        assert "probability of guilt" in r.disclaimer.lower()

    def test_unknown_entity_raises(self, engine: InvestigationPriorityEngine):
        with pytest.raises(KeyError):
            engine.score_entity("NONEXISTENT_NODE")

    def test_network_influence_always_available(self, engine: InvestigationPriorityEngine):
        r = engine.score_entity("A")
        ni = next(c for c in r.components if c.name == "network_influence")
        assert ni.available is True
        assert ni.score > 0.0


# --------------------------------------------------------------------------- #
# Component behaviour
# --------------------------------------------------------------------------- #

class TestComponents:
    def test_bridge_potential_picks_up_betweenness(self, engine: InvestigationPriorityEngine):
        r = engine.score_entity("A")
        bp = next(c for c in r.components if c.name == "bridge_potential")
        # A has betweenness=0.66, so bridge_potential score should be > 0
        assert bp.available is True
        assert bp.score > 0.0
        assert "Betweenness" in bp.reason

    def test_optional_component_unavailable(self, engine: InvestigationPriorityEngine):
        """With no ghost predictions, temporal anomalies, financial signals,
        cross-case links: those components are unavailable."""
        r = engine.score_entity("A")
        for name in ("communication_anomaly", "financial_anomaly",
                     "temporal_correlation", "cross_case_linkage"):
            c = next(c for c in r.components if c.name == name)
            assert c.available is False
            assert c.score == 0.0

    def test_evidence_strength_increases_with_records(self, engine_with_evidence):
        r = engine_with_evidence.score_entity("A")
        es = next(c for c in r.components if c.name == "evidence_strength")
        assert es.available is True
        assert es.score > 0.5
        assert "10" in es.reason

    def test_evidence_neutral_when_no_records(self, engine: InvestigationPriorityEngine):
        """Missing evidence = neutral 0.5, not 0.0 (missing ≠ negative)."""
        r = engine.score_entity("A")
        es = next(c for c in r.components if c.name == "evidence_strength")
        assert es.score == 0.5

    def test_components_contribute_to_score(self, engine: InvestigationPriorityEngine):
        """When components are available, their contributions must sum to priority_score / 100."""
        r = engine.score_entity("A")
        available = [c for c in r.components if c.available]
        if not available:
            pytest.skip("no available components")
        weight_total = sum(c.weight for c in available)
        score = sum(c.score * (c.weight / weight_total) for c in available)
        expected = int(round(score * 100))
        assert abs(r.priority_score - expected) <= 1


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #

class TestRanking:
    def test_ranked_limit(self, engine: InvestigationPriorityEngine):
        results = engine.ranked_entities(include_types=["PERSON"], limit=2)
        assert len(results) <= 2

    def test_ranked_sorted_descending(self, engine: InvestigationPriorityEngine):
        results = engine.ranked_entities(include_types=["PERSON"], limit=4)
        scores = [r.priority_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_type_filter(self, engine: InvestigationPriorityEngine):
        g = _make_graph()
        g.add_node("X1", canonical_name="Acme", entity_type="ORGANIZATION",
                    metrics={"pagerank": 0.099, "degree_centrality": 0.9, "betweenness_centrality": 0.5})
        eng = InvestigationPriorityEngine(graph=g)
        orgs = eng.ranked_entities(entity_type="ORGANIZATION", limit=10)
        assert all(r.entity_type == "ORGANIZATION" for r in orgs)
        assert len(orgs) >= 1


# --------------------------------------------------------------------------- #
# Weights
# --------------------------------------------------------------------------- #

class TestWeights:
    def test_default_weights_sum_to_one(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6

    def test_custom_weights(self, engine: InvestigationPriorityEngine):
        eng = InvestigationPriorityEngine(graph=_make_graph(), weights={
            "network_influence": 1.0,
            "bridge_potential": 0.0,
            "communication_anomaly": 0.0,
            "financial_anomaly": 0.0,
            "temporal_correlation": 0.0,
            "cross_case_linkage": 0.0,
            "evidence_strength": 0.0,
        })
        r = eng.score_entity("A")
        # When only network_influence weight is non-zero, renormalised to 1.0
        ni = next(c for c in r.components if c.name == "network_influence")
        assert abs(ni.weight - 1.0) < 1e-6
        assert abs(r.priority_score - round(ni.score * 100)) <= 1


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #

class TestDeterminism:
    def test_same_input_same_output(self, engine: InvestigationPriorityEngine):
        r1 = engine.score_entity("A")
        r2 = engine.score_entity("A")
        assert r1.priority_score == r2.priority_score
        assert r1.entity_id == r2.entity_id

    def test_ranked_deterministic(self, engine: InvestigationPriorityEngine):
        a1 = engine.ranked_entities(include_types=["PERSON"], limit=4)
        a2 = engine.ranked_entities(include_types=["PERSON"], limit=4)
        assert [r.entity_id for r in a1] == [r.entity_id for r in a2]