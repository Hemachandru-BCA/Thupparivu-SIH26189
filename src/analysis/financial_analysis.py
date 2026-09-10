"""
financial_analysis.py
---------------------
Enhanced financial flow analysis (P1.2).

Extends the existing financial router with advanced analytical signals:
  - High-volume intermediary detection
  - Multi-hop layering pattern detection
  - Circular flow detection
  - Dormant-to-active transitions
  - Transaction burst detection
  - Aggregated flow computation
  - Upstream/downstream expansion
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FinancialSignal(BaseModel):
    signal_type: str    # HIGH_VOLUME_INTERMEDIARY | FAN_IN | FAN_OUT | LAYERING | CIRCULAR | DORMANT_ACTIVE | BURST
    description: str
    entities: List[Dict[str, str]] = Field(default_factory=list)
    transactions_involved: int = 0
    time_range: Optional[Dict[str, str]] = None
    confidence: float = 0.0
    evidence_ids: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class FinancialFlowPath(BaseModel):
    path_id: str = ""
    hops: List[Dict[str, Any]] = Field(default_factory=list)
    total_amount: float = 0.0
    currency: str = "INR"
    hop_count: int = 0
    evidence_ids: List[str] = Field(default_factory=list)


class AggregatedFlow(BaseModel):
    source: str
    source_label: str = ""
    target: str
    target_label: str = ""
    total_amount: float = 0.0
    transaction_count: int = 0
    time_range: Optional[Dict[str, str]] = None
    confidence: float = 0.0
    evidence_ids: List[str] = Field(default_factory=list)


class EnhancedFinancialReport(BaseModel):
    paths: List[FinancialFlowPath] = Field(default_factory=list)
    aggregated_flows: List[AggregatedFlow] = Field(default_factory=list)
    signals: List[FinancialSignal] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class FinancialAnalyzer:
    """Enhanced financial flow analysis on the account subgraph."""

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self.account_graph = self._build_account_graph()

    def _build_account_graph(self) -> nx.MultiDiGraph:
        sub = nx.MultiDiGraph()
        for n, d in self.graph.nodes(data=True):
            if d.get("entity_type") == "ACCOUNT":
                sub.add_node(n, **d)
        for src, tgt, key, d in self.graph.edges(keys=True, data=True):
            if d.get("relation") in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS", "USES_ACCOUNT"):
                if src in sub and tgt in sub:
                    sub.add_edge(src, tgt, key=key, **d)
        return sub

    def _label(self, node: str) -> str:
        d = self.graph.nodes.get(node, {})
        return d.get("canonical_name") or d.get("label") or str(node)

    def _amount(self, edge_data: dict) -> float:
        a = edge_data.get("attributes") or {}
        nested = a.get("attributes") or {}
        raw = a.get("amount") or nested.get("amount")
        if raw is None:
            return 0.0
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    def _timestamp(self, edge_data: dict) -> Optional[str]:
        a = edge_data.get("attributes") or {}
        nested = a.get("attributes") or {}
        return nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")

    # ------------------------------------------------------------------ #
    # High-volume intermediary
    # ------------------------------------------------------------------ #
    def detect_high_volume_intermediaries(self, threshold_percentile: float = 0.9) -> List[FinancialSignal]:
        """Entities passing large amounts relative to neighbors."""
        if self.account_graph.number_of_nodes() == 0:
            return []

        pass_through: Dict[str, float] = {}
        for n in self.account_graph.nodes():
            in_total = sum(self._amount(d) for _, _, d in self.account_graph.in_edges(n, data=True))
            out_total = sum(self._amount(d) for _, _, d in self.account_graph.out_edges(n, data=True))
            if in_total > 0 and out_total > 0:
                pass_through[n] = min(in_total, out_total)

        if not pass_through:
            return []

        values = sorted(pass_through.values())
        threshold_idx = int(len(values) * threshold_percentile)
        threshold = values[min(threshold_idx, len(values) - 1)]

        signals = []
        for node, amt in sorted(pass_through.items(), key=lambda x: -x[1]):
            if amt < threshold:
                break
            signals.append(FinancialSignal(
                signal_type="HIGH_VOLUME_INTERMEDIARY",
                description=(
                    f"Entity '{self._label(node)}' passes ₹{amt:,.0f} through "
                    f"(above {threshold_percentile:.0%} threshold)"
                ),
                entities=[{"id": node, "label": self._label(node), "role": "intermediary"}],
                confidence=min(1.0, amt / max(threshold * 2, 1)),
                limitations=["High pass-through is structural; does not indicate intent."],
            ))
        return signals

    # ------------------------------------------------------------------ #
    # Layering detection
    # ------------------------------------------------------------------ #
    def detect_layering(self, min_hops: int = 3, max_hops: int = 5) -> List[FinancialSignal]:
        """Multi-hop sequential transfers."""
        signals = []
        visited = set()

        for source in self.account_graph.nodes():
            if self.account_graph.in_degree(source) > 0:
                continue  # Only start from source nodes
            frontier = [(source, [source], 0.0)]
            for hop in range(max_hops):
                next_frontier = []
                for node, path, total in frontier:
                    for _, tgt, d in self.account_graph.out_edges(node, data=True):
                        if tgt in path:
                            continue
                        amt = self._amount(d)
                        new_path = path + [tgt]
                        new_total = total + amt
                        if len(new_path) >= min_hops:
                            key = tuple(new_path)
                            if key not in visited:
                                visited.add(key)
                                signals.append(FinancialSignal(
                                    signal_type="LAYERING",
                                    description=(
                                        f"Multi-hop transfer pattern: {' → '.join(self._label(n) for n in new_path)} "
                                        f"({len(new_path)-1} hops, total ₹{new_total:,.0f})"
                                    ),
                                    entities=[{"id": n, "label": self._label(n), "role": "layer"} for n in new_path],
                                    transactions_involved=len(new_path) - 1,
                                    confidence=min(1.0, len(new_path) / max_hops),
                                    limitations=["Sequential transfers do not imply layering intent."],
                                ))
                        if hop < max_hops - 1:
                            next_frontier.append((tgt, new_path, new_total))
                frontier = next_frontier
                if not frontier:
                    break
        return signals[:30]

    # ------------------------------------------------------------------ #
    # Circular flow
    # ------------------------------------------------------------------ #
    def detect_circular_flows(self, max_cycle_length: int = 5) -> List[FinancialSignal]:
        """Circular fund flows A → B → C → A."""
        try:
            cycles = list(nx.simple_cycles(self.account_graph))
        except Exception:
            cycles = []
        cycles = [c for c in cycles if 2 <= len(c) <= max_cycle_length]

        signals = []
        for cycle in cycles[:20]:
            total = 0.0
            for i in range(len(cycle)):
                for _, _, d in self.account_graph.edges(cycle[i], data=True):
                    if d.get("target") == cycle[(i + 1) % len(cycle)]:
                        total += self._amount(d)
            signals.append(FinancialSignal(
                signal_type="CIRCULAR",
                description=(
                    f"Circular flow: {' → '.join(self._label(n) for n in cycle)} → {self._label(cycle[0])} "
                    f"(₹{total:,.0f})"
                ),
                entities=[{"id": n, "label": self._label(n), "role": "cycle_node"} for n in cycle],
                transactions_involved=len(cycle),
                confidence=min(1.0, len(cycle) / max_cycle_length),
                limitations=["Circular flow is topological; does not indicate circular trading."],
            ))
        return signals

    # ------------------------------------------------------------------ #
    # Transaction burst
    # ------------------------------------------------------------------ #
    def detect_bursts(self, window_days: int = 7, min_transactions: int = 5) -> List[FinancialSignal]:
        """Periods with unusually high transaction activity."""
        # Group edges by date
        daily: Dict[str, int] = defaultdict(int)
        for _, _, d in self.account_graph.edges(data=True):
            ts = self._timestamp(d)
            if ts:
                try:
                    date_str = ts[:10]
                    daily[date_str] += 1
                except Exception:
                    pass

        if not daily:
            return []

        # Sliding window burst detection
        sorted_dates = sorted(daily.keys())
        signals = []
        for i in range(len(sorted_dates)):
            window_start = sorted_dates[i]
            window_count = 0
            window_entities: Set[str] = set()
            for j in range(i, min(i + window_days, len(sorted_dates))):
                window_count += daily[sorted_dates[j]]
            if window_count >= min_transactions:
                avg = len(self.account_graph.edges()) / max(len(sorted_dates), 1)
                if window_count > avg * 3:
                    signals.append(FinancialSignal(
                        signal_type="BURST",
                        description=(
                            f"Transaction burst: {window_count} transactions in window "
                            f"starting {window_start} ({window_days}-day window)"
                        ),
                        transactions_involved=window_count,
                        time_range={"start": window_start, "end": sorted_dates[min(i + window_days, len(sorted_dates) - 1)]},
                        confidence=min(1.0, window_count / (avg * 5)),
                        limitations=["Bursts are statistical anomalies; context may explain them."],
                    ))
        return signals[:10]

    # ------------------------------------------------------------------ #
    # Aggregated flows
    # ------------------------------------------------------------------ #
    def aggregated_flows(
        self,
        min_amount: float = 0,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> List[AggregatedFlow]:
        """Aggregate multiple transactions between the same pair."""
        pair_data: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {
            "total": 0.0, "count": 0, "evidence": [], "amounts": [],
            "timestamps": [],
        })

        for src, tgt, d in self.account_graph.edges(data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            ts = nested.get("timestamp") or a.get("timestamp")
            amt = self._amount(d)
            eid = a.get("record_id", "")

            if date_range and ts:
                try:
                    if ts < date_range[0] or ts > date_range[1]:
                        continue
                except Exception:
                    pass

            key = (src, tgt)
            pair_data[key]["total"] += amt
            pair_data[key]["count"] += 1
            if eid:
                pair_data[key]["evidence"].append(eid)
            if ts:
                pair_data[key]["timestamps"].append(ts)

        flows = []
        for (src, tgt), data in sorted(pair_data.items(), key=lambda x: -x[1]["total"]):
            if data["total"] < min_amount:
                continue
            timestamps = sorted(data["timestamps"]) if data["timestamps"] else None
            flows.append(AggregatedFlow(
                source=src,
                source_label=self._label(src),
                target=tgt,
                target_label=self._label(tgt),
                total_amount=round(data["total"], 2),
                transaction_count=data["count"],
                time_range={"start": timestamps[0], "end": timestamps[-1]} if timestamps else None,
                confidence=1.0,
                evidence_ids=data["evidence"][:10],
            ))
        return flows[:200]

    # ------------------------------------------------------------------ #
    # Multi-hop path finding
    # ------------------------------------------------------------------ #
    def find_paths(
        self,
        source: str,
        max_hops: int = 4,
        min_amount: float = 0,
        destination: Optional[str] = None,
    ) -> List[FinancialFlowPath]:
        """Find all paths from source within hop limit."""
        if source not in self.account_graph:
            return []

        paths = []
        frontier = [(source, [], 0.0)]
        for hop in range(max_hops):
            next_frontier = []
            for node, path, total in frontier:
                for _, tgt, d in self.account_graph.out_edges(node, data=True):
                    amt = self._amount(d)
                    if amt < min_amount:
                        continue
                    if destination and tgt != destination:
                        if hop < max_hops - 1:
                            next_frontier.append((tgt, path + [{"from": node, "to": tgt, "amount": amt}], total + amt))
                        continue
                    new_path = path + [{
                        "from": node,
                        "from_label": self._label(node),
                        "to": tgt,
                        "to_label": self._label(tgt),
                        "amount": amt,
                        "confidence": float((d.get("attributes") or {}).get("confidence", 1.0)),
                        "edge_id": d.get("id", ""),
                    }]
                    paths.append(FinancialFlowPath(
                        hops=new_path,
                        total_amount=round(total + amt, 2),
                        hop_count=len(new_path),
                    ))
                    if hop < max_hops - 1:
                        next_frontier.append((tgt, new_path, total + amt))
            frontier = next_frontier
            if not frontier:
                break

        paths.sort(key=lambda p: -p.total_amount)
        return paths[:200]

    # ------------------------------------------------------------------ #
    # Full analysis
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        source: Optional[str] = None,
        max_hops: int = 4,
        min_amount: float = 0,
    ) -> EnhancedFinancialReport:
        """Run all financial analyses."""
        signals = []
        signals.extend(self.detect_high_volume_intermediaries())
        signals.extend(self.detect_layering())
        signals.extend(self.detect_circular_flows())
        signals.extend(self.detect_bursts())

        paths = []
        if source:
            paths = self.find_paths(source, max_hops=max_hops, min_amount=min_amount)

        agg = self.aggregated_flows(min_amount=min_amount)

        return EnhancedFinancialReport(
            paths=paths,
            aggregated_flows=agg,
            signals=signals,
            summary={
                "total_accounts": self.account_graph.number_of_nodes(),
                "total_transfers": self.account_graph.number_of_edges(),
                "signals_detected": len(signals),
                "aggregated_flows": len(agg),
            },
            limitations=[
                "Financial analysis is derived from observed transaction records.",
                "Patterns are structural indicators, not evidence of financial crime.",
                "Amounts are from synthetic data; real-world interpretation requires additional verification.",
            ],
        )
