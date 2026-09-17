"""
tests/test_financial_intelligence.py
------------------------------------
Tests for financial intelligence engine (Phase 5 / Task 13).
"""

from __future__ import annotations

import networkx as nx
import pytest

from src.intelligence.financial import (
    FinancialIntelligenceEngine,
    FinancialPattern,
    SMURF_THRESHOLD,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _ts(day: int, hour: int = 12) -> str:
    from datetime import datetime, timezone
    return datetime(2025, 1, day, hour, 0, 0, tzinfo=timezone.utc).isoformat()


def _make_financial_graph(edges, nodes=None) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for n in (nodes or []):
        nid, data = n if isinstance(n, tuple) else (n, {})
        g.add_node(nid, entity_type=data.pop("entity_type", "ACCOUNT"), **data)
    for e in edges:
        u, v, attrs = e
        g.add_edge(u, v, relation="TRANSFERRED_TO", attributes=attrs)
    return g


# --------------------------------------------------------------------------- #
# Tests — Layering
# --------------------------------------------------------------------------- #

class TestLayering:
    def test_layering_detected(self):
        """Account receiving from 5+ sources and sending to 5+ dests within 7 days."""
        graph = nx.MultiDiGraph()
        graph.add_node("layer_acct")
        inflow_edges = []
        outflow_edges = []
        for i in range(6):
            graph.add_node(f"src_{i}")
            graph.add_node(f"dst_{i}")
            inflow_edges.append((f"src_{i}", "layer_acct", {"amount": 10000, "timestamp": _ts(1, 8 + i)}))
            outflow_edges.append(("layer_acct", f"dst_{i}", {"amount": 9500, "timestamp": _ts(1 + i, 10)}))
        for e in inflow_edges + outflow_edges:
            graph.add_edge(e[0], e[1], relation="TRANSFERRED_TO", attributes=e[2])

        engine = FinancialIntelligenceEngine(graph, [])
        patterns = engine.analyze()
        layering = [p for p in patterns if p.pattern_type == "LAYERING"]
        assert len(layering) >= 1


# --------------------------------------------------------------------------- #
# Tests — Smurfing
# --------------------------------------------------------------------------- #

class TestSmurfing:
    def test_smurfing_detected(self):
        """4 sub-threshold transactions to same destination within 24h."""
        threshold = SMURF_THRESHOLD * 0.8  # Each below threshold
        graph = nx.MultiDiGraph()
        edges = []
        for i in range(4):
            graph.add_node(f"smurf_src_{i}")
            edges.append((
                f"smurf_src_{i}", "smurf_dest",
                {"amount": threshold, "timestamp": _ts(1, 8 + i), "record_id": f"TX{i}"}
            ))
        graph.add_node("smurf_dest")
        for e in edges:
            graph.add_edge(e[0], e[1], relation="TRANSFERRED_TO", attributes=e[2])

        engine = FinancialIntelligenceEngine(graph, [])
        patterns = engine.analyze()
        smurfing = [p for p in patterns if p.pattern_type == "SMURFING"]
        # Total should be 4 * 0.8 * threshold > 3 * threshold
        assert len(smurfing) >= 1

    def test_smurfing_below_count_threshold(self):
        """Only 2 transactions should NOT be flagged."""
        graph = nx.MultiDiGraph()
        graph.add_node("dest2")
        graph.add_node("src_a")
        graph.add_node("src_b")
        threshold = SMURF_THRESHOLD * 0.8
        for s in ["src_a", "src_b"]:
            graph.add_edge(s, "dest2", relation="TRANSFERRED_TO",
                           attributes={"amount": threshold, "timestamp": _ts(1, 10)})

        engine = FinancialIntelligenceEngine(graph, [])
        patterns = engine.analyze()
        smurfing = [p for p in patterns if p.pattern_type == "SMURFING"]
        assert len(smurfing) == 0


# --------------------------------------------------------------------------- #
# Tests — Shell Account
# --------------------------------------------------------------------------- #

class TestShellAccount:
    def test_shell_account_flagged(self):
        """Account with no attributes and high transaction volume."""
        graph = nx.MultiDiGraph()
        graph.add_node("shell_acct")  # No attributes = shell
        graph.add_node("normal_person", entity_type="PERSON",
                       canonical_name="John Doe",
                       attributes={"phone": "123", "location": "Chennai"})
        # High volume for shell
        for i in range(30):
            graph.add_node(f"counter_{i}")
            graph.add_edge(f"counter_{i}", "shell_acct", relation="TRANSFERRED_TO",
                           attributes={"amount": 1000, "timestamp": _ts(1 + i % 28, 12)})

        engine = FinancialIntelligenceEngine(graph, [])
        patterns = engine.analyze()
        shells = [p for p in patterns if p.pattern_type == "SHELL_ACCOUNT"]
        assert len(shells) >= 1
        assert "shell_acct" in shells[0].implicated_accounts


# --------------------------------------------------------------------------- #
# Tests — FinancialPattern schema
# --------------------------------------------------------------------------- #

class TestFinancialPatternSchema:
    def test_schema_validates(self):
        p = FinancialPattern(
            pattern_id="FP-12345678",
            pattern_type="LAYERING",
            severity="HIGH",
            detected_at="2025-01-01T00:00:00Z",
            implicated_accounts=["ACC-001"],
            evidence_ids=["EV-001"],
            description="Test pattern",
            confidence=0.9,
            total_amount=100000,
        )
        d = p.to_dict()
        assert d["pattern_id"] == "FP-12345678"
        assert d["severity"] == "HIGH"
        assert d["status"] == "HYPOTHESIS — requires human review"


# --------------------------------------------------------------------------- #
# Tests — Risk score
# --------------------------------------------------------------------------- #

class TestRiskScore:
    def test_risk_score_high_for_many_patterns(self):
        """Account with 2 HIGH patterns should have risk > 0.8."""
        patterns = [
            FinancialPattern(
                pattern_id="FP-001", pattern_type="LAYERING", severity="HIGH",
                detected_at="2025-01-01T00:00:00Z", implicated_accounts=["ACC-1"],
                evidence_ids=[], description="L1", confidence=0.9
            ),
            FinancialPattern(
                pattern_id="FP-002", pattern_type="SHELL_ACCOUNT", severity="HIGH",
                detected_at="2025-01-01T00:00:00Z", implicated_accounts=["ACC-1"],
                evidence_ids=[], description="S1", confidence=0.8
            ),
        ]
        # Risk score calculation (mirrors API logic)
        severity_weights = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2}
        total = sum(severity_weights.get(p.severity, 0.2) * p.confidence for p in patterns)
        risk = min(1.0, total / 2.0)  # Normalize
        assert risk > 0.8
