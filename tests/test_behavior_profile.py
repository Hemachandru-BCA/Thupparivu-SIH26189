"""
tests/test_behavior_profile.py
------------------------------
Unit tests for the Behavioral Profile engine (Phase B) and Behavior
Change detection (Phase C).

Covers:
  - Profile structure (communications / financial / network / temporal /
    locations sections).
  - Call counting + unique contacts + average duration.
  - Financial incoming/outgoing + transaction count + account count.
  - Network metrics from the analytics pass.
  - Temporal incident overlaps.
  - Location counting.
  - Behavior change detection with period deltas + severity.
  - Deterministic output, no fabrication.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.behavior_profile import (
    BehaviorChangeDetector,
    BehaviorProfileBuilder,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_graph() -> nx.MultiDiGraph:
    """A small deterministic graph with one person having calls, transfers,
    locations, and an incident."""
    g = nx.MultiDiGraph()

    g.add_node("E-101", entity_type="PERSON", canonical_name="Ravi Kumar",
               metrics={"degree": 4, "betweenness_centrality": 0.5,
                        "pagerank": 0.02, "community": 1})
    g.add_node("E-102", entity_type="PERSON", canonical_name="Sita Devi",
               metrics={"degree": 2, "betweenness_centrality": 0.1,
                        "pagerank": 0.01, "community": 1})
    g.add_node("E-103", entity_type="PERSON", canonical_name="Ram",
               metrics={"degree": 1, "betweenness_centrality": 0.0,
                        "pagerank": 0.005, "community": 2})
    g.add_node("ACC-1", entity_type="ACCOUNT", canonical_name="ACC-1")
    g.add_node("LOC-1", entity_type="LOCATION", canonical_name="Chennai Central")
    g.add_node("LOC-2", entity_type="LOCATION", canonical_name="Guindy")
    g.add_node("INC-1", entity_type="INCIDENT", canonical_name="FIR-104",
               timestamp="2026-01-10T18:30:00")

    ts = "2026-01-10T18:00:00"
    g.add_edge("E-101", "E-102", relation="CALLED", id="E-C1",
               attributes={"attributes": {
                   "duration_sec": "120", "timestamp": ts}})
    g.add_edge("E-101", "E-103", relation="CALLED", id="E-C2",
               attributes={"attributes": {
                   "duration_sec": "60", "timestamp": ts}})
    g.add_edge("E-102", "E-101", relation="CALLED", id="E-C3",
               attributes={"attributes": {
                   "duration_sec": "30", "timestamp": ts}})
    g.add_edge("E-101", "ACC-1", relation="USES_ACCOUNT", id="E-U1",
               attributes={"attributes": {"account_id": "ACC-1", "timestamp": ts}})
    g.add_edge("E-101", "ACC-1", relation="TRANSFERRED_TO", id="E-T1",
               attributes={"attributes": {"amount": "1000", "timestamp": ts}})
    g.add_edge("E-102", "E-101", relation="TRANSFERRED_TO", id="E-T2",
               attributes={"attributes": {"amount": "500", "timestamp": ts}})
    g.add_edge("E-101", "LOC-1", relation="LOCATED_IN", id="E-L1",
               attributes={"attributes": {}})
    g.add_edge("E-101", "LOC-2", relation="LOCATED_IN", id="E-L2",
               attributes={"attributes": {}})
    g.add_edge("E-101", "INC-1", relation="ASSOCIATED_WITH", id="E-A1",
               attributes={"attributes": {"timestamp": ts}})
    return g


@pytest.fixture
def graph() -> nx.MultiDiGraph:
    return _make_graph()


@pytest.fixture
def builder(graph: nx.MultiDiGraph) -> BehaviorProfileBuilder:
    return BehaviorProfileBuilder(graph=graph)


# --------------------------------------------------------------------------- #
# Profile structure
# --------------------------------------------------------------------------- #

class TestProfileStructure:
    def test_profile_sections_present(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        assert p is not None
        assert p.communications is not None
        assert p.financial is not None
        assert p.network is not None
        assert p.temporal is not None
        assert p.locations is not None

    def test_entity_metadata(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        assert p.entity_id == "E-101"
        assert p.entity_name == "Ravi Kumar"
        assert p.entity_type == "PERSON"

    def test_unknown_entity_none(self, builder: BehaviorProfileBuilder):
        assert builder.build("NONEXISTENT") is None

    def test_deterministic(self, builder: BehaviorProfileBuilder):
        p1 = builder.build("E-101")
        p2 = builder.build("E-101")
        assert p1.model_dump() == p2.model_dump()


# --------------------------------------------------------------------------- #
# Communications
# --------------------------------------------------------------------------- #

class TestCommunications:
    def test_call_count(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        # E-101 -> E-102 (out), E-101 -> E-103 (out), E-102 -> E-101 (in)
        assert p.communications.total_calls == 3

    def test_unique_contacts(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        # Contacts: E-102 (×2: out+in), E-103 (out)
        assert p.communications.unique_contacts == 2

    def test_avg_duration(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        # Outgoing: 120 + 60; incoming: 30.  Average over all CALLED edges
        # touching the entity = (120+60+30)/3 = 70.0
        assert p.communications.avg_duration_sec == 70.0

    def test_met_count(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        assert p.communications.met_count == 0


# --------------------------------------------------------------------------- #
# Financial
# --------------------------------------------------------------------------- #

class TestFinancial:
    def test_incoming_outgoing(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        # Outgoing: 1000 (E-101 -> ACC-1 TRANSFERRED_TO)
        assert p.financial.outgoing_amount == 1000.0
        # Incoming: 500 (E-102 -> E-101 TRANSFERRED_TO)
        assert p.financial.incoming_amount == 500.0

    def test_transaction_count(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        assert p.financial.transaction_count == 2

    def test_account_count(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        assert p.financial.account_count == 1


# --------------------------------------------------------------------------- #
# Network / temporal / locations
# --------------------------------------------------------------------------- #

class TestNetworkTemporalLocations:
    def test_network_metrics(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        assert p.network.degree == 4
        assert p.network.betweenness == 0.5
        assert p.network.pagerank == 0.02

    def test_temporal_incident_overlap(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        # E-C1/C2/C3 at 18:00, incident at 18:30 - all within 24h window
        assert p.temporal.incident_overlaps >= 1

    def test_locations(self, builder: BehaviorProfileBuilder):
        p = builder.build("E-101")
        assert p.locations.unique_locations == 2


# --------------------------------------------------------------------------- #
# Behavior change
# --------------------------------------------------------------------------- #

class TestBehaviorChange:
    def test_detect_change_structure(self, graph: nx.MultiDiGraph):
        detector = BehaviorChangeDetector(graph=graph)
        # Edge timestamps are in the past relative to "now", so both periods
        # may be empty; structure must still return a valid object.
        change = detector.detect_change("E-101", window_days=30)
        assert change is not None
        assert change.entity_id == "E-101"
        assert isinstance(change.changes, list)
        assert len(change.changes) >= 1
        assert change.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATION")

    def test_pct_calculation(self):
        # _pct is a static private helper; test via detector instance
        d = BehaviorChangeDetector(graph=nx.MultiDiGraph())
        assert d._pct(10, 20) == 100.0
        assert d._pct(0, 10) is None  # undefined when previous == 0
        assert d._pct(20, 10) == -50.0

    def test_unknown_entity_none(self, graph: nx.MultiDiGraph):
        detector = BehaviorChangeDetector(graph=graph)
        assert detector.detect_change("NONEXISTENT") is None