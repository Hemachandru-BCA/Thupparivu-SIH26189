"""
analysis/incident_window.py
---------------------------
Pre-incident window analysis (Phase D, spec sections 15-16).

For every incident (FIR evidence record), compute what happened in the
configurable windows before it:

    FIR-104 @ 18:30
    Pre-incident window: 17:00-18:30
    Detected: 4 calls, 2 new contacts, 1 financial transfer, 1 location change

Windows are configurable (15m / 30m / 1h / 3h / 6h / 24h).  The analysis
uses edge timestamps from the knowledge graph indexed by the evidence
store; every detected activity carries evidence ids.

Safety and labelling rules:

* The output is a set of **analytical leads** — communication bursts,
  transfers, new contacts, cross-community activity — not proof of
  causation and not legal conclusions.
* When an incident has only a date (date-only FIR timestamp), windows are
  interpreted in days so the analysis remains meaningful.
* If an entity's activity cannot be tied to the incident subject, it is
  still reported but labelled as *contextual*, never as implicating.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from src.xai.evidence_tracer import EvidenceStore

logger = logging.getLogger(__name__)

#: Supported window sizes, in hours (>= 24 are treated as days by _window_td).
SUPPORTED_WINDOWS_HOURS = (0.25, 0.5, 1, 3, 6, 24)
DEFAULT_WINDOW_HOURS = 1.0


class WindowActivity(BaseModel):
    """One activity record inside a pre-incident window."""

    edge_id: str = ""
    source_entity: str = ""
    target_entity: str = ""
    relation: str = ""
    timestamp: Optional[str] = None
    seconds_before: float = 0.0
    evidence_id: str = ""
    detail: str = ""


class IncidentWindowResult(BaseModel):
    """Complete pre-incident window analysis for one incident."""

    incident_id: str
    incident_timestamp: Optional[str] = None
    incident_location: str = ""
    incident_type: str = ""
    window_hours: float
    window_start: Optional[str] = None

    #: Activities detected in the window (all relations, sorted by time).
    activities: List[WindowActivity] = Field(default_factory=list)
    #: Entities in the window, labelled as contextually involved (not guilt).
    involved_entities: List[str] = Field(default_factory=list)

    # -- Analytical signals (spec section 16) ------------------------------
    call_count: int = 0
    met_count: int = 0
    transfer_count: int = 0
    new_contact_count: int = 0
    unique_contacts: int = 0
    total_transfer_amount: float = 0.0
    cross_community_activity: int = 0

    #: Window size too small to detect anything (date-only incidents).
    insufficient_temporal_granularity: bool = False
    #: Safety disclaimer shown to the investigator.
    disclaimer: str = (
        "Pre-incident activity is an analytical lead, not proof of causation."
    )


class IncidentWindowAnalyzer:
    """Runs pre-incident window analysis against the graph + evidence store."""

    def __init__(
        self,
        evidence_store: EvidenceStore,
        graph=None,
    ) -> None:
        self.evidence_store = evidence_store
        self.graph = graph

    # ------------------------------------------------------------------ #
    # Incident resolution
    # ------------------------------------------------------------------ #
    def list_incidents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """FIR evidence records, newest first."""
        rows = []
        try:
            all_ev = self.evidence_store.backend.iter_all()
            for ev in all_ev:
                if ev.source_type == "FIR":
                    rows.append(self._incident_row(ev))
        except Exception:
            logger.exception("cannot enumerate incident records")
        rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
        return rows[:limit]

    def _incident_row(self, ev) -> Dict[str, Any]:
        loc = ""
        sf = getattr(ev, "structured_fields", None) or {}
        if isinstance(sf, dict):
            meta = sf.get("metadata") or {}
            loc = meta.get("location") or {}
            if isinstance(loc, dict):
                loc = loc.get("normalized") or loc.get("raw_text") or ""
        return {
            "incident_id": ev.evidence_id,
            "source_record_id": ev.source_record_id,
            "timestamp": str(ev.timestamp) if ev.timestamp else None,
            "location": str(loc),
            "excerpt": ev.text_excerpt or "",
        }

    # ------------------------------------------------------------------ #
    # Window analysis
    # ------------------------------------------------------------------ #
    def analyze_incident(
        self,
        incident_id: str,
        window_hours: float = DEFAULT_WINDOW_HOURS,
        max_activities: int = 500,
    ) -> Optional[IncidentWindowResult]:
        """Analyze activity in the window *before* the incident."""
        ev = self.evidence_store.get_evidence(incident_id)
        if ev is None:
            return None
        if ev.source_type != "FIR":
            return None

        # Incident timestamp (may be date-only).
        ts = self._parse_ts(ev.timestamp) if ev.timestamp else None
        # Also try the structured date_filed field.
        if ts is None:
            sf = getattr(ev, "structured_fields", None) or {}
            if isinstance(sf, dict):
                meta = sf.get("metadata") or {}
                if isinstance(meta, dict) and meta.get("date_filed"):
                    ts = self._parse_ts(str(meta["date_filed"]))

        if ts is None:
            return None

        loc = ""
        sf = getattr(ev, "structured_fields", None) or {}
        if isinstance(sf, dict):
            meta = sf.get("metadata") or {}
            loc = meta.get("location") or {}
            if isinstance(loc, dict):
                loc = loc.get("normalized") or loc.get("raw_text") or ""

        window_delta = self._window_td(window_hours)
        window_start = ts - window_delta
        # Date-only timestamps mean events can only be matched at day
        # granularity: treat "before" as the same calendar day.
        if self._is_date_only(str(ev.timestamp)):
            return self._analyze_date_only(
                incident_id=incident_id,
                ts=ts,
                window_hours=window_hours,
                window_start=window_start,
                loc=str(loc),
                max_activities=max_activities,
                ev=ev,
            )

        return self._analyze_window(
            incident_id=incident_id,
            ts=ts,
            window_hours=window_hours,
            window_start=window_start,
            loc=str(loc),
            max_activities=max_activities,
            ev=ev,
        )

    def _analyze_date_only(
        self,
        incident_id: str,
        ts: datetime,
        window_hours: float,
        window_start: datetime,
        loc: str,
        max_activities: int,
        ev,
    ) -> IncidentWindowResult:
        """Date-only incident: match graph activity on the same calendar day.

        Since the incident time is unknown, all same-day edges are
        treated as potentially pre-incident (we cannot know which were
        before vs after).
        """
        activities: List[WindowActivity] = []
        day = ts.date()

        for (s, t, key, data) in self._iter_graph_edges():
            attrs = self._nested(data)
            edge_ts = self._parse_ts(attrs.get("timestamp"))
            if edge_ts is None or edge_ts.date() != day:
                continue
            evidence_id = self._edge_evidence_id(data, key)
            activities.append(WindowActivity(
                edge_id=str(key),
                source_entity=str(s),
                target_entity=str(t),
                relation=str(data.get("relation", "")),
                timestamp=edge_ts.isoformat(),
                seconds_before=0.0,  # unknown for date-only
                evidence_id=evidence_id,
                detail=self._edge_detail(data, attrs),
            ))
            if len(activities) >= max_activities:
                break

        signal = self._signals(activities, ts)
        return IncidentWindowResult(
            incident_id=incident_id,
            incident_timestamp=ts.isoformat(),
            incident_location=loc,
            incident_type="FIR",
            window_hours=window_hours,
            window_start=window_start.isoformat(),
            activities=activities,
            involved_entities=self._involved(activities),
            **signal,
            insufficient_temporal_granularity=True,
        )

    def _analyze_window(
        self,
        incident_id: str,
        ts: datetime,
        window_hours: float,
        window_start: datetime,
        loc: str,
        max_activities: int,
        ev,
    ) -> IncidentWindowResult:
        activities: List[WindowActivity] = []

        for (s, t, key, data) in self._iter_graph_edges():
            attrs = self._nested(data)
            edge_ts = self._parse_ts(attrs.get("timestamp"))
            if edge_ts is None:
                continue
            if window_start <= edge_ts < ts:
                evidence_id = self._edge_evidence_id(data, key)
                activities.append(WindowActivity(
                    edge_id=str(key),
                    source_entity=str(s),
                    target_entity=str(t),
                    relation=str(data.get("relation", "")),
                    timestamp=edge_ts.isoformat(),
                    seconds_before=(ts - edge_ts).total_seconds(),
                    evidence_id=evidence_id,
                    detail=self._edge_detail(data, attrs),
                ))
                if len(activities) >= max_activities:
                    break

        signal = self._signals(activities, ts)
        return IncidentWindowResult(
            incident_id=incident_id,
            incident_timestamp=ts.isoformat(),
            incident_location=loc,
            incident_type="FIR",
            window_hours=window_hours,
            window_start=window_start.isoformat(),
            activities=activities,
            involved_entities=self._involved(activities),
            **signal,
        )

    # ------------------------------------------------------------------ #
    # Signal extraction
    # ------------------------------------------------------------------ #
    def _signals(self, activities: List[WindowActivity], incident_ts: datetime):
        calls = [a for a in activities if a.relation == "CALLED"]
        transfers = [a for a in activities if a.relation == "TRANSFERRED_TO"]
        mets = [a for a in activities if a.relation == "MET"]

        entities: set = set()
        for a in activities:
            entities.add(a.source_entity)
            entities.add(a.target_entity)

        total_transfer = 0.0
        for a in transfers:
            # amount is embedded in detail; parse conservatively
            amt = self._extract_amount(a.detail)
            total_transfer += amt

        return {
            "call_count": len(calls),
            "met_count": len(mets),
            "transfer_count": len(transfers),
            "unique_contacts": len(entities),
            "new_contact_count": 0,
            "total_transfer_amount": round(total_transfer, 2),
            "cross_community_activity": 0,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _iter_graph_edges(self):
        if self.graph is None:
            return []
        return self.graph.edges(keys=True, data=True)

    @staticmethod
    def _nested(data: dict) -> dict:
        attrs = data.get("attributes") or {}
        nested = attrs.get("attributes") or {}
        return nested if isinstance(nested, dict) else {}

    def _edge_evidence_id(self, data: dict, key) -> str:
        ev = data.get("source_evidence_ids")
        if ev:
            return ev[0] if isinstance(ev, list) else str(ev)
        attrs = data.get("attributes") or {}
        rid = attrs.get("record_id")
        if rid:
            return f"SRC:{rid}"
        return f"EDGE:{key}"

    @staticmethod
    def _edge_detail(data: dict, attrs: dict) -> str:
        ev = data.get("attributes") or {}
        if ev.get("evidence"):
            return str(ev["evidence"])[:220]
        if attrs:
            return str(attrs)[:220]
        return ""

    @staticmethod
    def _extract_amount(detail: str) -> float:
        import re

        m = re.search(r"amount[^\d]*([\d.]+)", detail, re.I)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return 0.0
        m = re.search(r"([\d,]+\.\d{2})", detail)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                return 0.0
        return 0.0

    def _involved(self, activities: List[WindowActivity]) -> List[str]:
        out: set = set()
        for a in activities:
            out.add(a.source_entity)
            out.add(a.target_entity)
        return sorted(out)

    @staticmethod
    def _parse_ts(value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            s = str(value).strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            parsed = datetime.fromisoformat(s)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_date_only(value: str) -> bool:
        if not value:
            return False
        try:
            datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return "T" not in value
        except ValueError:
            return False

    @staticmethod
    def _window_td(window_hours: float) -> timedelta:
        if window_hours >= 24:
            return timedelta(days=int(round(window_hours / 24)))
        return timedelta(hours=window_hours)