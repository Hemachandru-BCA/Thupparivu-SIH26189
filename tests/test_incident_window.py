"""
tests/test_incident_window.py
-----------------------------
Unit tests for pre-incident window analysis (Phase D, spec section 16).

Covers:
  - Incident listing returns FIR records only.
  - Window analysis returns activities strictly BEFORE the incident.
  - Analytical signals (calls / transfers / involved entities).
  - Date-only incidents fall back to same-day matching.
  - Configurable window sizes.
  - Unknown / non-FIR incident returns None.
  - Disclaimer present (not causation).
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.incident_window import (
    DEFAULT_WINDOW_HOURS,
    SUPPORTED_WINDOWS_HOURS,
    IncidentWindowAnalyzer,
)
from src.xai.evidence_tracer import EvidenceRecord, EvidenceStore, InMemoryEvidenceBackend


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    g.add_node("E-1", entity_type="PERSON", canonical_name="Alice")
    g.add_node("E-2", entity_type="PERSON", canonical_name="Bob")
    g.add_node("E-3", entity_type="PERSON", canonical_name="Carol")
    g.add_node("ACC-1", entity_type="ACCOUNT", canonical_name="ACC-1")

    # Incident at 18:30: two calls at 18:00 (1h before), one at 17:38 (1h22m
    # before), a transfer at 18:10, a MET at 19:00 (AFTER, must be excluded).
    ts = "2026-08-21T18:00:00"
    g.add_edge("E-1", "E-2", relation="CALLED", id="C1",
               attributes={"record_id": "C0001",
                           "attributes": {"timestamp": ts}})
    g.add_edge("E-2", "E-3", relation="CALLED", id="C2",
               attributes={"record_id": "C0002",
                           "attributes": {"timestamp": "2026-08-21T17:38:00"}})
    g.add_edge("E-1", "ACC-1", relation="TRANSFERRED_TO", id="T1",
               attributes={"attributes": {"amount": 5000, "timestamp": "2026-08-21T18:10:00"}})
    g.add_edge("E-2", "E-3", relation="MET", id="M1",
               attributes={"attributes": {"timestamp": "2026-08-21T19:00:00"}})
    return g


def _make_store() -> EvidenceStore:
    backend = InMemoryEvidenceBackend()
    backend.upsert(EvidenceRecord(
        evidence_id="INC-001",
        source_type="FIR",
        source_record_id="FIR000001",
        timestamp="2026-08-21T18:30:00",
        text_excerpt="Incident reported at 18:30.",
        structured_fields={"metadata": {"location": {"normalized": "Chennai"}}},
    ))
    backend.upsert(EvidenceRecord(
        evidence_id="INC-DATE-ONLY",
        source_type="FIR",
        source_record_id="FIR000002",
        timestamp="2026-08-21",  # date only
        text_excerpt="Another incident.",
    ))
    backend.upsert(EvidenceRecord(
        evidence_id="REC-001",
        source_type="CALL",
        source_record_id="C0001",
        timestamp="2026-08-21T18:00:00",
        text_excerpt="Alice called Bob.",
    ))
    return EvidenceStore(backend=backend)


@pytest.fixture
def analyzer() -> IncidentWindowAnalyzer:
    return IncidentWindowAnalyzer(
        evidence_store=_make_store(),
        graph=_make_graph(),
    )


# --------------------------------------------------------------------------- #
# Incident listing
# --------------------------------------------------------------------------- #

class TestIncidentListing:
    def test_lists_only_firs(self, analyzer: IncidentWindowAnalyzer):
        incidents = analyzer.list_incidents()
        assert len(incidents) == 2
        for inc in incidents:
            assert inc["incident_id"].startswith("INC-")

    def test_incident_row_has_timestamp_and_location(self, analyzer: IncidentWindowAnalyzer):
        incidents = analyzer.list_incidents()
        by_id = {i["incident_id"]: i for i in incidents}
        assert by_id["INC-001"]["timestamp"] == "2026-08-21T18:30:00"
        assert "Chennai" in by_id["INC-001"]["location"]


# --------------------------------------------------------------------------- #
# Window analysis
# --------------------------------------------------------------------------- #

class TestWindowAnalysis:
    def test_unknown_incident_returns_none(self, analyzer: IncidentWindowAnalyzer):
        assert analyzer.analyze_incident("DOES-NOT-EXIST") is None

    def test_non_fir_returns_none(self, analyzer: IncidentWindowAnalyzer):
        # REC-001 is a CALL record, not an FIR
        assert analyzer.analyze_incident("REC-001") is None

    def test_activities_strictly_before_incident(self, analyzer: IncidentWindowAnalyzer):
        r = analyzer.analyze_incident("INC-001", window_hours=1.0)
        assert r is not None
        # All activities within [17:30, 18:30)
        for a in r.activities:
            assert 0 <= a.seconds_before <= 3600 + 1
        # The MET at 19:00 must NOT appear
        assert not any(a.relation == "MET" for a in r.activities)
        # The transfer at 18:10 must appear
        assert any(a.relation == "TRANSFERRED_TO" for a in r.activities)

    def test_call_signal_counts(self, analyzer: IncidentWindowAnalyzer):
        r = analyzer.analyze_incident("INC-001", window_hours=2.0)
        # 2 calls at 18:00 and 17:38 (both within 2h window)
        assert r.call_count == 2
        assert r.transfer_count == 1
        assert r.unique_contacts >= 2

    def test_involved_entities(self, analyzer: IncidentWindowAnalyzer):
        r = analyzer.analyze_incident("INC-001", window_hours=2.0)
        assert "E-1" in r.involved_entities
        assert "E-2" in r.involved_entities

    def test_date_only_incident(self, analyzer: IncidentWindowAnalyzer):
        """Date-only FIR: edges on same calendar day are included as
        potentially pre-incident (time unknown -> insufficient granularity)."""
        r = analyzer.analyze_incident("INC-DATE-ONLY", window_hours=24)
        assert r is not None
        assert "2026-08-21" in r.incident_timestamp
        # All graph edges are on 2026-08-21, so they count
        assert r.call_count >= 2
        assert r.insufficient_temporal_granularity is True

    def test_window_sizes(self, analyzer: IncidentWindowAnalyzer):
        for w in SUPPORTED_WINDOWS_HOURS:
            r = analyzer.analyze_incident("INC-001", window_hours=w)
            assert r is not None
            # Small windows (0.25h = 15m) will filter tighter than 24h
            assert isinstance(r.window_hours, float)

    def test_disclaimer_present(self, analyzer: IncidentWindowAnalyzer):
        r = analyzer.analyze_incident("INC-001", window_hours=1.0)
        assert "not proof of causation" in r.disclaimer.lower()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class TestHelpers:
    def test_window_td_days_for_large_hours(self):
        td = IncidentWindowAnalyzer._window_td(48)
        assert td == timedelta(days=2)

    def test_window_td_hours_for_small(self):
        td = IncidentWindowAnalyzer._window_td(0.5)
        assert td == timedelta(hours=0.5)

    def test_date_only_detection(self):
        assert IncidentWindowAnalyzer._is_date_only("2026-08-21") is True
        assert IncidentWindowAnalyzer._is_date_only("2026-08-21T18:30:00") is False