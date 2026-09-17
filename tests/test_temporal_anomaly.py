"""
tests/test_temporal_anomaly.py
-------------------------------
Tests for temporal anomaly detection (Phase 4 / Task 12).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import networkx as nx
import pytest

from src.intelligence.temporal_anomaly import (
    AnomalyRecord,
    TemporalAnomalyDetector,
    _severity,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _ts(day: int, hour: int = 12) -> str:
    from datetime import timedelta
    base = datetime(2025, 1, 1, hour, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(days=day)).isoformat()


def _make_graph(nodes=None, edges=None) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for n in (nodes or []):
        nid, data = n if isinstance(n, tuple) else (n, {})
        g.add_node(nid, **data)
    for e in (edges or []):
        if len(e) == 2:
            g.add_edge(e[0], e[1], attributes={})
        else:
            g.add_edge(e[0], e[1], attributes=e[2] if isinstance(e[2], dict) else {})
    return g


def _evidence_record(eid: str, subjects: list, ts: str, **kw):
    return {
        "evidence_id": eid,
        "subject_ids": subjects,
        "timestamp": ts,
        "source_type": "call_observation",
        "text_excerpt": f"Record {eid}",
        **kw,
    }


# --------------------------------------------------------------------------- #
# Tests — Burst detection
# --------------------------------------------------------------------------- #

class TestBurstDetection:
    def test_burst_detected_in_spike(self):
        """A known burst of events within 24h should be detected."""
        records = []
        # 150 regular events (1/day) for a strong, flat baseline
        for i in range(150):
            records.append(_evidence_record(
                f"E{i:04d}", ["entity_A"], _ts(1 + i, 12)
            ))
        # Burst: 40 events spread across 6 hours on day 400 (far from regulars)
        for i in range(40):
            records.append(_evidence_record(
                f"BURST{i:04d}", ["entity_A"], _ts(400, 8 + i // 8)
            ))

        graph = _make_graph(nodes=[("entity_A", {"metrics": {"community": 0}})])
        detector = TemporalAnomalyDetector(graph, records)
        anomalies = detector.detect()
        bursts = [a for a in anomalies if a.anomaly_type == "BURST"]
        assert len(bursts) >= 1
        assert "entity_A" in bursts[0].entity_ids

    def test_no_burst_in_uniform_series(self):
        """Uniform events should produce no false-positive bursts."""
        records = []
        for i in range(20):
            records.append(_evidence_record(f"E{i:04d}", ["entity_B"], _ts(1 + i, 12)))

        graph = _make_graph(nodes=[("entity_B", {"metrics": {"community": 0}})])
        detector = TemporalAnomalyDetector(graph, records)
        anomalies = detector.detect()
        bursts = [a for a in anomalies if a.anomaly_type == "BURST"]
        assert len(bursts) == 0

    def test_skips_entities_with_few_windows(self):
        """Entities with < 5 windows should be skipped, not flagged."""
        records = [_evidence_record(f"E{i}", ["entity_C"], _ts(1 + i)) for i in range(3)]
        graph = _make_graph(nodes=[("entity_C", {"metrics": {"community": 0}})])
        detector = TemporalAnomalyDetector(graph, records)
        anomalies = detector.detect()
        bursts = [a for a in anomalies if a.anomaly_type == "BURST"]
        assert len(bursts) == 0


# --------------------------------------------------------------------------- #
# Tests — Synchronized activity
# --------------------------------------------------------------------------- #

class TestSynchronizedDetection:
    def test_synchronized_detected(self):
        """Pairs from different communities with 3+ events within 15 min."""
        records = []
        for i in range(5):
            # Both entities active within 10 minutes of each other
            records.append(_evidence_record(f"SA{i}", ["ent_X", "ent_Y"], _ts(10, 10 + i * 3)))
            records.append(_evidence_record(f"SB{i}", ["ent_Y"], _ts(10, 10 + i * 3 + 1)))

        graph = _make_graph(nodes=[
            ("ent_X", {"metrics": {"community": 1}}),
            ("ent_Y", {"metrics": {"community": 2}}),
        ])
        detector = TemporalAnomalyDetector(graph, records)
        anomalies = detector.detect()
        syncs = [a for a in anomalies if a.anomaly_type == "SYNCHRONIZED"]
        assert len(syncs) >= 1

    def test_no_sync_for_distant_pairs(self):
        """Pairs 60 min apart should NOT be flagged."""
        records = []
        for i in range(5):
            records.append(_evidence_record(f"DA{i}", ["ent_P"], _ts(10, 8)))
            records.append(_evidence_record(f"DB{i}", ["ent_Q"], _ts(10, 9)))  # 60 min later

        graph = _make_graph(nodes=[
            ("ent_P", {"metrics": {"community": 1}}),
            ("ent_Q", {"metrics": {"community": 2}}),
        ])
        detector = TemporalAnomalyDetector(graph, records)
        anomalies = detector.detect()
        syncs = [a for a in anomalies if a.anomaly_type == "SYNCHRONIZED"]
        assert len(syncs) == 0


# --------------------------------------------------------------------------- #
# Tests — Round-trip financial flow
# --------------------------------------------------------------------------- #

class TestRoundTripDetection:
    def test_round_trip_detected(self):
        """A→B→A within 72h where total >> median should be detected."""
        graph = nx.MultiDiGraph()
        graph.add_node("A", metrics={"community": 0})
        graph.add_node("B", metrics={"community": 1})
        # A→B and B→A with large amounts in a cycle
        # Also add some small "noise" edges so the median stays low
        graph.add_edge("A", "B", relation="TRANSFERRED_TO",
                       attributes={"amount": 100000, "timestamp": _ts(1, 10)})
        graph.add_edge("B", "A", relation="TRANSFERRED_TO",
                       attributes={"amount": 100000, "timestamp": _ts(1, 14)})
        # Noise: other small transactions to keep median low
        for i in range(5):
            graph.add_node(f"n{i}")
            graph.add_edge(f"n{i}", "A", relation="TRANSFERRED_TO",
                           attributes={"amount": 100, "timestamp": _ts(2 + i, 10)})

        records = [_evidence_record("EF1", ["A", "B"], _ts(1, 10))]
        detector = TemporalAnomalyDetector(graph, records)
        anomalies = detector.detect()
        cycles = [a for a in anomalies if a.anomaly_type == "ROUND_TRIP"]
        assert any("A" in c.entity_ids and "B" in c.entity_ids for c in cycles)


# --------------------------------------------------------------------------- #
# Tests — AnomalyRecord schema
# --------------------------------------------------------------------------- #

class TestAnomalyRecord:
    def test_schema_validates(self):
        record = AnomalyRecord(
            anomaly_id="AN-12345678",
            anomaly_type="BURST",
            severity="HIGH",
            detected_at="2025-01-01T00:00:00Z",
            entity_ids=["E-001"],
            evidence_ids=["EV-001"],
            description="Test burst",
            confidence=0.85,
        )
        d = record.to_dict()
        assert d["anomaly_id"] == "AN-12345678"
        assert d["anomaly_type"] == "BURST"
        assert d["status"] == "HYPOTHESIS — requires human review"
        assert 0 <= d["confidence"] <= 1

    def test_severity_thresholds(self):
        assert _severity(z_score=6, anomaly_type="BURST") == "HIGH"
        assert _severity(z_score=4, anomaly_type="BURST") == "MEDIUM"
        assert _severity(z_score=2, anomaly_type="BURST") == "LOW"
        assert _severity(sync_score=0.7, anomaly_type="SYNCHRONIZED") == "HIGH"
        assert _severity(delta=0.15, anomaly_type="NEW_HUB") == "HIGH"
        assert _severity(ratio=60, anomaly_type="ROUND_TRIP") == "HIGH"
