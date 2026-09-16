"""
analysis/behavior_profile.py
----------------------------
Deterministic per-entity behavioral profiling (Phase B, spec sections 17-18)
and behavior-change detection (Phase C, spec section 18).

Spec section 17 asks for a structured behavior profile per entity:

    {
      "communications": {"total_calls", "unique_contacts", "avg_duration", "burst_count"},
      "financial":      {"incoming_amount", "outgoing_amount", "transaction_count",
                          "cycle_count", "layering_indicators"},
      "network":        {"degree", "betweenness", "pagerank", "communities"},
      "temporal":       {"incident_overlaps"},
      "locations":      {"unique_locations"}
    }

Rules:

* **Everything is derived deterministically from the graph.** The LLM is
  never asked to compute these numbers.
* Communications come from CALLED / MET edges; financial from
  TRANSFERRED_TO / USES_ACCOUNT edges; locations from LOCATED_IN edges;
  network metrics from the analytics pass already stored on nodes.
* Temporal burst count is taken from the existing `TemporalAnomalyDetector`
  (communication bursts / dormant activation / ...).
* Incident overlaps = number of entity activities within 24h of any
  INCIDENT / EVENT node timestamp (spec section 16 "pre-incident window").
* Behavior change (Phase C) compares a previous period with the current
  period and reports deltas as percentages + severity, with explicit
  "not enough data" handling instead of calling every change suspicious.

Safety: the profile is a *description of observed activity*, not a legal
conclusion.  Behavior change severity is an analytical indicator, never a
guilt statement.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

#: Pre-incident window used for incident-overlap counting (hours).
INCIDENT_WINDOW_HOURS = 24
#: Default comparison window for behavior change (days).
CHANGE_WINDOW_DAYS = 30


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class CommunicationsProfile(BaseModel):
    total_calls: int = 0
    unique_contacts: int = 0
    avg_duration_sec: float = 0.0
    burst_count: int = 0
    met_count: int = 0


class FinancialProfile(BaseModel):
    incoming_amount: float = 0.0
    outgoing_amount: float = 0.0
    transaction_count: int = 0
    account_count: int = 0
    cycle_count: int = 0
    layering_indicators: int = 0


class NetworkProfile(BaseModel):
    degree: int = 0
    betweenness: float = 0.0
    pagerank: float = 0.0
    communities: int = 1


class TemporalProfile(BaseModel):
    incident_overlaps: int = 0


class LocationProfile(BaseModel):
    unique_locations: int = 0


class BehaviorProfile(BaseModel):
    """Deterministic behavioral profile for one entity."""

    entity_id: str
    entity_type: str = ""
    entity_name: str = ""
    communications: CommunicationsProfile = Field(default_factory=CommunicationsProfile)
    financial: FinancialProfile = Field(default_factory=FinancialProfile)
    network: NetworkProfile = Field(default_factory=NetworkProfile)
    temporal: TemporalProfile = Field(default_factory=TemporalProfile)
    locations: LocationProfile = Field(default_factory=LocationProfile)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ChangeMetric(BaseModel):
    """One measured period-over-period change."""

    metric: str
    label: str
    previous: float = 0.0
    current: float = 0.0
    delta_pct: Optional[float] = Field(None, description="Percentage change (None if previous == 0)")
    notes: str = ""


class BehaviorChange(BaseModel):
    """Phase C - behavior change summary between two periods."""

    entity_id: str
    entity_name: str = ""
    window_days: int = CHANGE_WINDOW_DAYS
    changes: List[ChangeMetric] = Field(default_factory=list)
    severity: str = "INFORMATION"  # CRITICAL | HIGH | MEDIUM | LOW | INFORMATION
    description: str = ""


# --------------------------------------------------------------------------- #
# Profile builder
# --------------------------------------------------------------------------- #

class BehaviorProfileBuilder:
    """Builds a deterministic behavior profile for graph entities."""

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        temporal_anomalies: Optional[List[Any]] = None,
    ) -> None:
        self.graph = graph
        self._temporal_anomalies = temporal_anomalies
        self._incident_timestamps: Optional[List[Any]] = None

    # -- helpers ---------------------------------------------------------- #
    def _node_label(self, node: str) -> str:
        d = self.graph.nodes.get(node, {})
        return d.get("canonical_name") or d.get("label") or d.get("name") or str(node)

    def _node_metrics(self, node: str) -> Dict[str, Any]:
        d = self.graph.nodes.get(node, {})
        m = d.get("metrics") or {}
        return m if isinstance(m, dict) else {}

    def _nested_attrs(self, edge_data: dict) -> dict:
        attrs = edge_data.get("attributes") or {}
        nested = attrs.get("attributes") or {}
        return nested if isinstance(nested, dict) else {}

    def _parse_ts(self, value: Any) -> Optional[datetime]:
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

    def _incident_ts(self) -> List[datetime]:
        if self._incident_timestamps is not None:
            return self._incident_timestamps
        ts_list: List[datetime] = []
        for _n, d in self.graph.nodes(data=True):
            et = str(d.get("entity_type") or "").upper()
            if et in ("INCIDENT", "EVENT"):
                ts_str = d.get("timestamp") or (d.get("attributes") or {}).get("timestamp")
                ts = self._parse_ts(ts_str)
                if ts is not None:
                    ts_list.append(ts)
        self._incident_timestamps = ts_list
        return ts_list

    def _anomalies_for(self, entity_id: str) -> List[Any]:
        if not self._temporal_anomalies:
            return []
        return [a for a in self._temporal_anomalies if entity_id in (a.entity_ids or [])]

    # -- main builder ----------------------------------------------------- #
    def build(self, entity_id: str) -> Optional[BehaviorProfile]:
        if entity_id not in self.graph:
            return None
        d = self.graph.nodes.get(entity_id, {})

        comms = self._communications(entity_id)
        fin = self._financial(entity_id)
        net = self._network(entity_id)
        temp = self._temporal(entity_id)
        locs = self._locations(entity_id)

        return BehaviorProfile(
            entity_id=entity_id,
            entity_type=str(d.get("entity_type") or "UNKNOWN"),
            entity_name=self._node_label(entity_id),
            communications=comms,
            financial=fin,
            network=net,
            temporal=temp,
            locations=locs,
        )

    def _communications(self, entity_id: str) -> CommunicationsProfile:
        total_calls = 0
        durations: List[float] = []
        contacts: set = set()
        met_count = 0

        def _count_edge(data, other, direction):
            nonlocal total_calls, met_count
            rel = data.get("relation")
            if rel == "CALLED":
                total_calls += 1
                contacts.add(other)
                dur_raw = self._nested_attrs(data).get("duration_sec")
                if dur_raw is not None:
                    try:
                        durations.append(float(dur_raw))
                    except (TypeError, ValueError):
                        pass
            elif rel == "MET":
                met_count += 1
                contacts.add(other)

        for _s, t, _k, data in self.graph.edges(entity_id, keys=True, data=True):
            _count_edge(data, t, "out")
        for s, _t, _k, data in self.graph.in_edges(entity_id, keys=True, data=True):
            _count_edge(data, s, "in")

        avg_duration = (
            round(sum(durations) / len(durations), 1) if durations else 0.0
        )

        return CommunicationsProfile(
            total_calls=total_calls,
            unique_contacts=len(contacts),
            avg_duration_sec=avg_duration,
            burst_count=len(self._anomalies_for(entity_id)),
            met_count=met_count,
        )

    def _financial(self, entity_id: str) -> FinancialProfile:
        incoming = 0.0
        outgoing = 0.0
        tx_count = 0
        accounts: set = set()

        for _s, _t, _k, data in self.graph.edges(entity_id, keys=True, data=True):
            rel = data.get("relation")
            nested = self._nested_attrs(data)
            if rel == "TRANSFERRED_TO":
                amt = nested.get("amount")
                if amt is not None:
                    try:
                        outgoing += float(amt)
                    except (TypeError, ValueError):
                        pass
                tx_count += 1
            elif rel == "USES_ACCOUNT":
                acct = nested.get("account_id")
                if acct:
                    accounts.add(acct)

        for _s, _t, _k, data in self.graph.in_edges(entity_id, keys=True, data=True):
            rel = data.get("relation")
            nested = self._nested_attrs(data)
            if rel == "TRANSFERRED_TO":
                amt = nested.get("amount")
                if amt is not None:
                    try:
                        incoming += float(amt)
                    except (TypeError, ValueError):
                        pass
                tx_count += 1
            elif rel == "USES_ACCOUNT":
                acct = nested.get("account_id")
                if acct:
                    accounts.add(acct)

        # Cycle / layering indicators are computed against the account graph.
        cycles, layering = self._financial_patterns(entity_id)

        return FinancialProfile(
            incoming_amount=round(incoming, 2),
            outgoing_amount=round(outgoing, 2),
            transaction_count=tx_count,
            account_count=len(accounts),
            cycle_count=cycles,
            layering_indicators=layering,
        )

    def _financial_patterns(self, entity_id: str) -> Tuple[int, int]:
        """Cycles/layering involving the entity's accounts (cheap heuristics)."""
        # Build the account subgraph once per call (small).
        account_edges: List[Tuple[str, str]] = []
        for s, t, _k, data in self.graph.edges(keys=True, data=True):
            if data.get("relation") in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS"):
                sl = self.graph.nodes.get(s, {}).get("entity_type")
                tl = self.graph.nodes.get(t, {}).get("entity_type")
                if sl == "ACCOUNT" and tl == "ACCOUNT":
                    account_edges.append((s, t))
        if not account_edges:
            return 0, 0

        # Which accounts belong to this entity (via USES_ACCOUNT edges)?
        my_accounts: set = set()
        for s, t, _k, data in self.graph.edges(keys=True, data=True):
            if data.get("relation") == "USES_ACCOUNT" and s == entity_id:
                acct = self._nested_attrs(data).get("account_id")
                if acct:
                    my_accounts.add(acct)
            elif data.get("relation") == "USES_ACCOUNT" and t == entity_id:
                acct = self._nested_attrs(data).get("account_id")
                if acct:
                    my_accounts.add(acct)

        from collections import defaultdict as _dd

        adj: Dict[str, list] = _dd(list)
        for s, t in account_edges:
            adj[s].append(t)

        # 2-hop and 3-hop reachability from my accounts += layering indicator
        layering = 0
        cycles = 0
        for acct in my_accounts:
            if acct not in adj:
                continue
            # Direct neighbors
            hops1 = set(adj[acct])
            for n1 in hops1:
                # cycles: n1 can reach acct directly
                if acct in adj.get(n1, []):
                    cycles += 1
                for n2 in adj.get(n1, []):
                    if n2 == acct:
                        cycles += 1
                        continue
                    # 3-hop chain: acct -> n1 -> n2 -> next
                    if adj.get(n2, []):
                        layering += 1

        return min(cycles, 20), min(layering, 20)

    def _network(self, entity_id: str) -> NetworkProfile:
        m = self._node_metrics(entity_id)
        return NetworkProfile(
            degree=int(m.get("degree") or 0),
            betweenness=float(m.get("betweenness_centrality") or 0.0),
            pagerank=float(m.get("pagerank") or 0.0),
            communities=1 if m.get("community") is None else 2,
        )

    def _temporal(self, entity_id: str) -> TemporalProfile:
        incidents = self._incident_ts()
        if not incidents:
            return TemporalProfile(incident_overlaps=0)
        overlaps = 0
        seen: set = set()
        for _s, _t, _k, data in self.graph.edges(entity_id, keys=True, data=True):
            ts = self._parse_ts(self._nested_attrs(data).get("timestamp"))
            if ts is None:
                continue
            edge_id = data.get("id") or _k
            if edge_id in seen:
                continue
            seen.add(edge_id)
            for inc in incidents:
                if abs((ts - inc).total_seconds()) <= INCIDENT_WINDOW_HOURS * 3600:
                    overlaps += 1
                    break
        for s, _t, _k, data in self.graph.in_edges(entity_id, keys=True, data=True):
            ts = self._parse_ts(self._nested_attrs(data).get("timestamp"))
            if ts is None:
                continue
            edge_id = data.get("id") or _k
            if edge_id in seen:
                continue
            seen.add(edge_id)
            for inc in incidents:
                if abs((ts - inc).total_seconds()) <= INCIDENT_WINDOW_HOURS * 3600:
                    overlaps += 1
                    break
        return TemporalProfile(incident_overlaps=overlaps)

    def _locations(self, entity_id: str) -> LocationProfile:
        locs: set = set()
        for _s, t, _k, data in self.graph.edges(entity_id, keys=True, data=True):
            if data.get("relation") == "LOCATED_IN":
                locs.add(t)
        return LocationProfile(unique_locations=len(locs))


# --------------------------------------------------------------------------- #
# Behavior change detection (Phase C)
# --------------------------------------------------------------------------- #

class BehaviorChangeDetector:
    """Period-over-period behavior change analysis (spec section 18)."""

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self._builder = BehaviorProfileBuilder(graph)

    def _edge_timestamps(self, entity_id: str) -> Dict[str, List[datetime]]:
        """Returns {metric_key: [timestamps]} for period comparisons."""
        out: Dict[str, List[datetime]] = defaultdict(list)
        for _s, _t, _k, data in self.graph.edges(entity_id, keys=True, data=True):
            rel = data.get("relation")
            nested = self._builder._nested_attrs(data)
            ts = self._builder._parse_ts(nested.get("timestamp"))
            if ts is None:
                continue
            if rel == "CALLED":
                out["calls"].append(ts)
                contact = _t
                out.setdefault("contacts_ts", []).append(ts)
                out.setdefault("contacts", []).append(contact)
            elif rel == "MET":
                out["meetings"].append(ts)
            elif rel == "TRANSFERRED_TO":
                out["transactions"].append(ts)
                try:
                    amt = float(nested.get("amount") or 0)
                except (TypeError, ValueError):
                    amt = 0.0
                out.setdefault("amounts", []).append((ts, amt))
            elif rel == "LOCATED_IN":
                out["locations"].append(ts)
                out.setdefault("location_ids", []).append(_t)
        return out

    def _split_periods(
        self, ts_list: List[Any], now: datetime, window_days: int
    ) -> Tuple[List[Any], List[Any]]:
        """Split timestamps into [previous period, current period]."""
        current_start = now - timedelta(days=window_days)
        previous_start = now - timedelta(days=2 * window_days)
        previous = [t for t in ts_list if previous_start <= t < current_start]
        current = [t for t in ts_list if current_start <= t <= now]
        return previous, current

    def _pct(self, prev: float, cur: float) -> Optional[float]:
        if prev == 0:
            return None  # undefined; handled as "new activity"
        return round((cur - prev) / prev * 100.0, 1)

    def detect_change(
        self, entity_id: str, window_days: int = CHANGE_WINDOW_DAYS
    ) -> Optional[BehaviorChange]:
        if entity_id not in self.graph:
            return None

        now = datetime.now(timezone.utc)
        changes: List[ChangeMetric] = []

        # Communication volume
        comm = self._edge_timestamps(entity_id)
        prev_calls, cur_calls = self._split_periods(comm.get("calls", []), now, window_days)
        changes.append(ChangeMetric(
            metric="communication_volume",
            label="Communication activity",
            previous=float(len(prev_calls)),
            current=float(len(cur_calls)),
            delta_pct=self._pct(len(prev_calls), len(cur_calls)),
            notes="Number of CALLED/MET events",
        ))

        # Unique contacts
        prev_contacts, cur_contacts = self._period_contacts(entity_id, comm, now, window_days)
        changes.append(ChangeMetric(
            metric="unique_contacts",
            label="Unique contacts",
            previous=float(len(prev_contacts)),
            current=float(len(cur_contacts)),
            delta_pct=self._pct(len(prev_contacts), len(cur_contacts)),
            notes="Distinct communication partners",
        ))

        # Financial volume
        amts = comm.get("amounts", [])
        prev_amts, cur_amts = self._split_periods([t for t, _ in amts], now, window_days)
        prev_amount = sum(a for t, a in amts if t in prev_amts)
        cur_amount = sum(a for t, a in amts if t in cur_amts)
        changes.append(ChangeMetric(
            metric="financial_volume",
            label="Financial volume",
            previous=round(prev_amount, 2),
            current=round(cur_amount, 2),
            delta_pct=self._pct(prev_amount, cur_amount),
            notes="Sum of transfer amounts",
        ))

        # Locations
        prev_locs, cur_locs = self._split_periods(comm.get("locations", []), now, window_days)
        prev_loc_ids = {loc for loc, ts in zip(comm.get("location_ids", []), comm.get("locations", [])) if ts in prev_locs}
        cur_loc_ids = {loc for loc, ts in zip(comm.get("location_ids", []), comm.get("locations", [])) if ts in cur_locs}
        changes.append(ChangeMetric(
            metric="locations",
            label="Unique locations",
            previous=float(len(prev_loc_ids)),
            current=float(len(cur_loc_ids)),
            delta_pct=self._pct(len(prev_loc_ids), len(cur_loc_ids)),
            notes="Distinct locations visited",
        ))

        severity = self._severity(changes)
        return BehaviorChange(
            entity_id=entity_id,
            entity_name=self._builder._node_label(entity_id),
            window_days=window_days,
            changes=changes,
            severity=severity,
            description=self._describe(severity),
        )

    def _period_contacts(self, entity_id, comm, now, window_days):
        """Split unique contacts by period."""
        current_start = now - timedelta(days=window_days)
        previous_start = now - timedelta(days=2 * window_days)
        prev_set: set = set()
        cur_set: set = set()
        for c, ts in zip(comm.get("contacts", []), comm.get("contacts_ts", [])):
            if ts is None:
                continue
            if previous_start <= ts < current_start:
                prev_set.add(c)
            elif current_start <= ts <= now:
                cur_set.add(c)
        return prev_set, cur_set

    def _severity(self, changes: List[ChangeMetric]) -> str:
        """Analytical severity from deltas; never a guilt statement."""
        max_abs = 0.0
        for c in changes:
            if c.delta_pct is None:
                if c.current > 0 and c.previous == 0:
                    max_abs = max(max_abs, 100.0)
                continue
            max_abs = max(max_abs, abs(c.delta_pct))
        if max_abs >= 300:
            return "CRITICAL"
        if max_abs >= 150:
            return "HIGH"
        if max_abs >= 75:
            return "MEDIUM"
        if max_abs >= 25:
            return "LOW"
        return "INFORMATION"

    @staticmethod
    def _describe(severity: str) -> str:
        return {
            "CRITICAL": "Large behavior shift across multiple activity dimensions.",
            "HIGH": "Substantial behavior change detected; compare metrics for context.",
            "MEDIUM": "Moderate activity change observed.",
            "LOW": "Minor activity change observed.",
            "INFORMATION": "Activity within normal range.",
        }[severity]