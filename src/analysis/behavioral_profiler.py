"""
analysis/behavioral_profiler.py
-------------------------------
Behavioral Profiling and Change Detection Engine for Thupparivu.

Computes entity behavioral profiles across:
  - Communications (frequency, burst count, night activity, unique contacts)
  - Financials (volume, transaction count, velocity, cycles, layering)
  - Locations (unique locations, entropy, movement)
  - Network role (centrality, bridge score, community shifts)

Detects statistically significant changes between a baseline period
and an active/incident window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import networkx as nx

logger = logging.getLogger(__name__)

@dataclass
class BehavioralProfile:
    """Structured behavioral representation of an entity."""
    entity_id: str
    period_label: str = "all_time"
    period_start: str = ""
    period_end: str = ""
    
    # Communication metrics
    total_calls: int = 0
    unique_contacts: int = 0
    avg_call_duration_sec: float = 0.0
    night_call_ratio: float = 0.0
    burst_count: int = 0
    call_frequency_per_day: float = 0.0
    
    # Financial metrics
    total_inflow: float = 0.0
    total_outflow: float = 0.0
    transaction_count: int = 0
    rapid_transfer_count: int = 0
    new_counterparties: int = 0       # counterparties not seen in baseline
    unusual_amount_count: int = 0     # amounts outside historical distribution
    circular_transfer_count: int = 0  # A->B->C->A style cycles
    
    # Spatial metrics
    unique_locations: int = 0
    new_locations: int = 0
    location_entropy: float = 0.0
    
    # Graph / Network metrics
    degree: int = 0
    betweenness: float = 0.0
    bridge_score: float = 0.0
    new_connections: int = 0
    dropped_connections: int = 0
    
    # Evidence
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "period": self.period_label,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "communications": {
                "total_calls": self.total_calls,
                "unique_contacts": self.unique_contacts,
                "avg_duration_sec": round(self.avg_call_duration_sec, 1),
                "night_ratio": round(self.night_call_ratio, 3),
                "burst_count": self.burst_count,
                "frequency_per_day": round(self.call_frequency_per_day, 3),
            },
            "financial": {
                "total_inflow": self.total_inflow,
                "total_outflow": self.total_outflow,
                "transaction_count": self.transaction_count,
                "new_counterparties": self.new_counterparties,
                "unusual_amounts": self.unusual_amount_count,
                "circular_transfers": self.circular_transfer_count,
            },
            "network": {
                "degree": self.degree,
                "betweenness": round(self.betweenness, 4),
                "bridge_score": round(self.bridge_score, 4),
                "new_connections": self.new_connections,
                "dropped_connections": self.dropped_connections,
            },
            "locations": {
                "unique_locations": self.unique_locations,
                "new_locations": self.new_locations,
                "entropy": round(self.location_entropy, 3),
            },
            "evidence_count": len(self.evidence_ids),
        }


@dataclass
class BehaviorChangeReport:
    """Explains detected shift from baseline to active period.

    Every change is a normalized delta with an explanation, plus a
    statutory Evidence list.  The overall ``overall_change_score`` is an
    analytical relevance indicator - never a guilt score.
    """
    entity_id: str
    baseline: BehavioralProfile
    recent: BehavioralProfile
    
    # Normalized deltas (0 to 1 scale)
    communication_change: float = 0.0
    financial_change: float = 0.0
    location_change: float = 0.0
    network_change: float = 0.0
    
    overall_change_score: float = 0.0
    explanation: str = ""
    
    # Per-signal "WHAT CHANGED?" findings (structured, LLM-narratable)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    method: str = "behavioral_baseline_comparison"
    model_version: str = "behavior_profiler_v2"

    def add_finding(self, signal: str, change: str, before: float, after: float, severity: str = "INFO") -> None:
        """Append a structured WHAT-CHANGED finding."""
        self.findings.append({
            "signal": signal,
            "change": change,
            "before": round(float(before), 4),
            "after": round(float(after), 4),
            "severity": severity,   # INFO | OBSERVED | STATISTICAL_FINDING
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "change_score": round(self.overall_change_score, 4),
            "components": {
                "communication": round(self.communication_change, 3),
                "financial": round(self.financial_change, 3),
                "location": round(self.location_change, 3),
                "network": round(self.network_change, 3),
            },
            "method": self.method,
            "model_version": self.model_version,
            "findings": self.findings,
            "baseline": self.baseline.to_dict(),
            "recent": self.recent.to_dict(),
            "evidence_ids": self.evidence_ids,
            "explanation": self.explanation,
        }


def _normalized_delta(before: float, after: float) -> float:
    """Normalized percentage-style change mapped into [0, 1].

    Uses relative change capped at 1.0; protects against division by zero.
    """
    before = float(before or 0.0)
    after = float(after or 0.0)
    if before == 0 and after == 0:
        return 0.0
    if before == 0:
        return min(1.0, after / (after + 1.0))
    return min(1.0, abs(after - before) / max(before, after))


def compare_profiles(baseline: BehavioralProfile, recent: BehavioralProfile) -> BehaviorChangeReport:
    """Detect and explain behavioral change between two periods.

    The report's findings are structured facts (WHAT CHANGED) - the LLM may
    narrate them but never invent additional ones.
    """
    report = BehaviorChangeReport(
        entity_id=baseline.entity_id,
        baseline=baseline,
        recent=recent,
        evidence_ids=list(recent.evidence_ids),
    )

    # --- Communication ---------------------------------------------------
    comm_changes = []
    if recent.total_calls != baseline.total_calls:
        report.add_finding(
            "communication_volume",
            "increased" if recent.total_calls > baseline.total_calls else "decreased",
            baseline.total_calls, recent.total_calls,
            "OBSERVED",
        )
        comm_changes.append(_normalized_delta(baseline.total_calls, recent.total_calls))
    if recent.unique_contacts != baseline.unique_contacts:
        report.add_finding(
            "unique_contacts",
            "expanded" if recent.unique_contacts > baseline.unique_contacts else "contracted",
            baseline.unique_contacts, recent.unique_contacts,
            "OBSERVED",
        )
        comm_changes.append(_normalized_delta(baseline.unique_contacts, recent.unique_contacts))
    if recent.burst_count > baseline.burst_count:
        report.add_finding(
            "communication_burst",
            f"burst activity increased from {baseline.burst_count} to {recent.burst_count}",
            baseline.burst_count, recent.burst_count,
            "STATISTICAL_FINDING",
        )
        comm_changes.append(_normalized_delta(baseline.burst_count, recent.burst_count))
    if recent.night_call_ratio > baseline.night_call_ratio + 0.05:
        report.add_finding(
            "night_call_ratio",
            "night-time communication ratio increased",
            baseline.night_call_ratio, recent.night_call_ratio,
            "STATISTICAL_FINDING",
        )
        comm_changes.append(_normalized_delta(baseline.night_call_ratio, recent.night_call_ratio))
    if comm_changes:
        report.communication_change = round(min(1.0, sum(comm_changes) / len(comm_changes)), 4)

    # --- Financial ---------------------------------------------------------
    fin_changes = []
    if recent.new_counterparties > 0:
        report.add_finding(
            "new_financial_counterparties",
            f"{recent.new_counterparties} new counterparties appeared",
            baseline.new_counterparties, recent.new_counterparties,
            "STATISTICAL_FINDING",
        )
        fin_changes.append(min(1.0, recent.new_counterparties / 5.0))
    if recent.unusual_amount_count > 0:
        report.add_finding(
            "unusual_amounts",
            f"{recent.unusual_amount_count} transactions outside the historical amount distribution",
            baseline.unusual_amount_count, recent.unusual_amount_count,
            "STATISTICAL_FINDING",
        )
        fin_changes.append(min(1.0, recent.unusual_amount_count / 5.0))
    if recent.rapid_transfer_count > baseline.rapid_transfer_count:
        report.add_finding(
            "rapid_transfers",
            f"rapid transfers rose from {baseline.rapid_transfer_count} to {recent.rapid_transfer_count}",
            baseline.rapid_transfer_count, recent.rapid_transfer_count,
            "STATISTICAL_FINDING",
        )
        fin_changes.append(_normalized_delta(baseline.rapid_transfer_count, recent.rapid_transfer_count))
    if recent.transaction_count != baseline.transaction_count:
        report.add_finding(
            "transaction_volume",
            "increased" if recent.transaction_count > baseline.transaction_count else "decreased",
            baseline.transaction_count, recent.transaction_count,
            "OBSERVED",
        )
        fin_changes.append(_normalized_delta(baseline.transaction_count, recent.transaction_count))
    if recent.circular_transfer_count > 0:
        report.add_finding(
            "circular_transfers",
            f"{recent.circular_transfer_count} circular/pathological transfer cycles detected",
            baseline.circular_transfer_count, recent.circular_transfer_count,
            "STATISTICAL_FINDING",
        )
        fin_changes.append(min(1.0, recent.circular_transfer_count / 3.0))
    if fin_changes:
        report.financial_change = round(min(1.0, sum(fin_changes) / len(fin_changes)), 4)

    # --- Location -----------------------------------------------------------
    loc_changes = []
    if recent.new_locations > 0:
        report.add_finding(
            "new_locations",
            f"{recent.new_locations} new locations appeared",
            baseline.unique_locations, recent.unique_locations,
            "OBSERVED",
        )
        loc_changes.append(min(1.0, recent.new_locations / 3.0))
    if recent.unique_locations != baseline.unique_locations:
        loc_changes.append(_normalized_delta(baseline.unique_locations, recent.unique_locations))
    if loc_changes:
        report.location_change = round(min(1.0, sum(loc_changes) / len(loc_changes)), 4)

    # --- Network -------------------------------------------------------------
    net_changes = []
    if recent.new_connections > 0:
        report.add_finding(
            "new_connections",
            f"{recent.new_connections} new network connections established",
            baseline.degree, recent.degree,
            "OBSERVED",
        )
        net_changes.append(min(1.0, recent.new_connections / 5.0))
    if recent.dropped_connections > 0:
        report.add_finding(
            "dropped_connections",
            f"{recent.dropped_connections} prior connections no longer observed",
            baseline.degree, recent.degree,
            "OBSERVED",
        )
        net_changes.append(min(1.0, recent.dropped_connections / 5.0))
    if recent.bridge_score != baseline.bridge_score:
        report.add_finding(
            "brokerage_position",
            "increased" if recent.bridge_score > baseline.bridge_score else "decreased",
            baseline.bridge_score, recent.bridge_score,
            "INFERRED",
        )
        net_changes.append(_normalized_delta(baseline.bridge_score, recent.bridge_score))
    if recent.degree != baseline.degree:
        net_changes.append(_normalized_delta(baseline.degree, recent.degree))
    if net_changes:
        report.network_change = round(min(1.0, sum(net_changes) / len(net_changes)), 4)

    # --- Overall (equal-weight blend of the four families) -------------------
    components = [
        report.communication_change,
        report.financial_change,
        report.location_change,
        report.network_change,
    ]
    active = [c for c in components if c > 0]
    if active:
        report.overall_change_score = round(min(1.0, sum(active) / len(active)), 4)

    # --- Explanation (boring is better than hallucinated) ---------------------
    highlights = [f["change"] for f in report.findings[:3]]
    report.explanation = (
        f"Baseline vs recent comparison for {baseline.entity_id}. "
        f"Structured findings: {'; '.join(highlights) if highlights else 'no significant change detected across profiled signals'}. "
        f"Change score {report.overall_change_score:.2f} is an analytical relevance indicator, not a guilt assessment."
    )

    return report
