"""
intelligence/financial.py
-------------------------
Enhanced financial intelligence engine (Phase 5 / Task 13).

Operates on the knowledge graph and evidence store to detect:

  A — Layering (Structuring Detection)
  B — Smurfing (Sub-threshold Structuring)
  C — Shell Account Detection
  D — Velocity Anomaly
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/exports/financial_patterns.json")
SMURF_THRESHOLD = float(os.environ.get("FINANCIAL_SMURF_THRESHOLD", "50000"))


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class FinancialPattern:
    pattern_id: str
    pattern_type: str  # LAYERING | SMURFING | SHELL_ACCOUNT | VELOCITY
    severity: str  # LOW | MEDIUM | HIGH
    detected_at: str
    implicated_accounts: List[str]
    evidence_ids: List[str]
    description: str
    confidence: float
    total_amount: float = 0.0
    flow_graph: Dict[str, Any] = field(default_factory=dict)
    status: str = "HYPOTHESIS — requires human review"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _make_pattern_id(ptype: str, payload: str) -> str:
    digest = hashlib.sha256(f"{ptype}|{payload}".encode()).hexdigest()[:8]
    return f"FP-{digest}"


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

class FinancialIntelligenceEngine:
    """Detects structured financial crime patterns."""

    def __init__(self, graph: nx.MultiDiGraph, evidence_index: List[Dict[str, Any]]):
        self.graph = graph
        self.evidence = evidence_index
        self._patterns: List[FinancialPattern] = []

    def analyze(self) -> List[FinancialPattern]:
        self._patterns = []
        self._detect_layering()
        self._detect_smurfing()
        self._detect_shell_accounts()
        self._detect_velocity()
        logger.info("Financial intelligence: %d patterns found", len(self._patterns))
        return self._patterns

    # ---- Helper: extract financial edges ----

    def _tx_edges(self) -> List[Tuple[str, str, Dict]]:
        edges = []
        for u, v, data in self.graph.edges(data=True):
            rel = data.get("relation", "")
            if "TRANSFER" in rel.upper() or "FINANCIAL" in rel.upper() or "PAID" in rel.upper():
                attrs = data.get("attributes", {})
                edges.append((u, v, attrs))
        return edges

    def _tx_amount(self, attrs: Dict) -> float:
        for key in ("amount", "transaction_amount", "total_amount"):
            try:
                return float(attrs.get(key, 0))
            except (ValueError, TypeError):
                pass
        try:
            return float(attrs.get("duration_sec", 100))
        except (ValueError, TypeError):
            return 100.0

    def _tx_timestamp(self, attrs: Dict) -> Optional[datetime]:
        ts_str = attrs.get("timestamp", "")
        if ts_str:
            try:
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None

    # ---- A: Layering ----

    def _detect_layering(self):
        """Accounts that receive from ≥5 sources and send to ≥5 destinations in 7-day windows."""
        tx_edges = self._tx_edges()
        if not tx_edges:
            return

        # Build per-account inflow/outflow with timestamps
        inflows: Dict[str, List[Tuple[str, float, datetime]]] = defaultdict(list)
        outflows: Dict[str, List[Tuple[str, float, datetime]]] = defaultdict(list)

        for u, v, attrs in tx_edges:
            ts = self._tx_timestamp(attrs)
            amt = self._tx_amount(attrs)
            if ts:
                inflows[v].append((u, amt, ts))
                outflows[u].append((v, amt, ts))

        for account, sources in inflows.items():
            if len(sources) < 5:
                continue
            destinations = outflows.get(account, [])
            if len(destinations) < 5:
                continue

            # Find 7-day windows where both conditions hold
            all_timestamps = [ts for _, _, ts in sources] + [ts for _, _, ts in destinations]
            all_timestamps.sort()

            window = timedelta(days=7)
            for start in all_timestamps:
                end = start + window
                inflow_in_window = [(s, a, t) for s, a, t in sources if start <= t <= end]
                outflow_in_window = [(d, a, t) for d, a, t in destinations if start <= t <= end]

                if len(inflow_in_window) >= 5 and len(outflow_in_window) >= 5:
                    total_in = sum(a for _, a, _ in inflow_in_window)
                    total_out = sum(a for _, a, _ in outflow_in_window)
                    retention = total_out / max(total_in, 1)

                    payload = f"{account}|{start.isoformat()}"
                    sev = "HIGH" if retention < 0.05 else ("MEDIUM" if retention < 0.2 else "LOW")

                    self._patterns.append(FinancialPattern(
                        pattern_id=_make_pattern_id("LAYERING", payload),
                        pattern_type="LAYERING",
                        severity=sev,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        implicated_accounts=[account],
                        evidence_ids=[],
                        description=(
                            f"Layering pattern for {account}: "
                            f"{len(inflow_in_window)} inflow sources → "
                            f"{len(outflow_in_window)} outflow destinations "
                            f"(retention={retention:.3f})."
                        ),
                        confidence=min(1.0, retention * -5 + 1),
                        total_amount=total_in + total_out,
                        flow_graph={
                            account: {
                                "inflow": total_in, "outflow": total_out,
                                "sources": list(set(s for s, _, _ in inflow_in_window)),
                                "destinations": list(set(d for d, _, _ in outflow_in_window)),
                            }
                        },
                    ))
                    break  # One window per account

    # ---- B: Smurfing ----

    def _detect_smurfing(self):
        """Groups of 3+ sub-threshold transactions to same destination within 24h."""
        tx_edges = self._tx_edges()
        if not tx_edges:
            return

        # Group by destination
        by_dest: Dict[str, List[Tuple[str, float, datetime, str]]] = defaultdict(list)
        for u, v, attrs in tx_edges:
            ts = self._tx_timestamp(attrs)
            amt = self._tx_amount(attrs)
            rid = attrs.get("record_id", attrs.get("evidence", ""))
            if ts and amt < SMURF_THRESHOLD:
                by_dest[v].append((u, amt, ts, rid))

        for dest, txns in by_dest.items():
            if len(txns) < 3:
                continue

            txns.sort(key=lambda x: x[2])
            # Sliding window of 24h
            for i, (src0, amt0, ts0, rid0) in enumerate(txns):
                window_end = ts0 + timedelta(hours=24)
                group = [(s, a, t, r) for s, a, t, r in txns if ts0 <= t <= window_end]
                if len(group) >= 3:
                    total = sum(a for _, a, _, _ in group)
                    if total > 3 * SMURF_THRESHOLD:
                        sources = list(set(s for s, _, _, _ in group))
                        payload = f"{dest}|{ts0.isoformat()}"
                        self._patterns.append(FinancialPattern(
                            pattern_id=_make_pattern_id("SMURFING", payload),
                            pattern_type="SMURFING",
                            severity="HIGH" if total > 5 * SMURF_THRESHOLD else "MEDIUM",
                            detected_at=datetime.now(timezone.utc).isoformat(),
                            implicated_accounts=[dest] + sources,
                            evidence_ids=[r for _, _, _, r in group],
                            description=(
                                f"Smurfing pattern targeting {dest}: "
                                f"{len(group)} transactions from {len(sources)} sources "
                                f"(total={total:.0f}, threshold={SMURF_THRESHOLD:.0f})."
                            ),
                            confidence=min(1.0, total / (3 * SMURF_THRESHOLD)),
                            total_amount=total,
                        ))
                        break  # One window per destination

    # ---- C: Shell Account Detection ----

    def _detect_shell_accounts(self):
        """Accounts with zero identifying attributes but high transaction volume."""
        # Build attribute completeness scores
        person_attrs: Dict[str, Dict] = {}
        for node, data in self.graph.nodes(data=True):
            if data.get("entity_type") == "PERSON":
                person_attrs[node] = data

        # Count transactions per account
        tx_counts: Dict[str, int] = defaultdict(int)
        tx_volumes: Dict[str, float] = defaultdict(float)
        for u, v, attrs in self._tx_edges():
            tx_counts[u] += 1
            tx_volumes[u] += self._tx_amount(attrs)
            tx_counts[v] += 1
            tx_volumes[v] += self._tx_amount(attrs)

        if not tx_counts:
            return

        # Median transaction count
        counts = list(tx_counts.values())
        median_count = statistics.median(counts) if counts else 1
        threshold = max(median_count * 3, 10)

        for account, count in tx_counts.items():
            if count < threshold:
                continue

            # Compute attribute completeness
            attrs = person_attrs.get(account, {})
            has_name = bool(attrs.get("canonical_name", ""))
            has_phone = bool(attrs.get("attributes", {}).get("phone", ""))
            has_location = bool(attrs.get("attributes", {}).get("location", ""))

            completeness = sum([has_name, has_phone, has_location]) / 3.0

            if completeness < 0.5:  # Mostly anonymous
                payload = f"{account}|{count}"
                sev = "HIGH" if completeness == 0 else "MEDIUM"
                self._patterns.append(FinancialPattern(
                    pattern_id=_make_pattern_id("SHELL_ACCOUNT", payload),
                    pattern_type="SHELL_ACCOUNT",
                    severity=sev,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    implicated_accounts=[account],
                    evidence_ids=[],
                    description=(
                        f"Shell account {account}: {count} transactions "
                        f"(volume={tx_volumes[account]:.0f}), "
                        f"attribute completeness={completeness:.2f}."
                    ),
                    confidence=1.0 - completeness,
                    total_amount=tx_volumes.get(account, 0),
                ))

    # ---- D: Velocity Anomaly ----

    def _detect_velocity(self):
        """Accounts whose recent 7-day velocity exceeds their 30-day median by > 5x."""
        tx_edges = self._tx_edges()
        if not tx_edges:
            return

        # Collect timestamps per account
        account_ts: Dict[str, List[datetime]] = defaultdict(list)
        for u, v, attrs in tx_edges:
            ts = self._tx_timestamp(attrs)
            if ts:
                account_ts[u].append(ts)
                account_ts[v].append(ts)

        if not account_ts:
            return

        # Find latest timestamp in evidence
        all_ts = [ts for tss in account_ts.values() for ts in tss]
        if not all_ts:
            return
        latest = max(all_ts)

        window_7d = timedelta(days=7)
        window_30d = timedelta(days=30)

        for account, timestamps in account_ts.items():
            recent = [t for t in timestamps if latest - window_7d <= t <= latest]
            baseline = [t for t in timestamps if latest - window_30d <= t <= latest - window_7d]

            if len(baseline) < 3 or len(recent) < 1:
                continue

            # Velocity = transactions per day
            recent_velocity = len(recent) / 7.0
            baseline_velocity = len(baseline) / 23.0  # 30 - 7 = 23 days

            if baseline_velocity > 0 and recent_velocity > 5 * baseline_velocity:
                payload = f"{account}|{recent_velocity:.2f}"
                self._patterns.append(FinancialPattern(
                    pattern_id=_make_pattern_id("VELOCITY", payload),
                    pattern_type="VELOCITY",
                    severity="HIGH" if recent_velocity > 20 * baseline_velocity else "MEDIUM",
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    implicated_accounts=[account],
                    evidence_ids=[],
                    description=(
                        f"Velocity anomaly for {account}: "
                        f"{recent_velocity:.1f} tx/day (recent 7d) vs "
                        f"{baseline_velocity:.1f} tx/day (baseline 30d), "
                        f"ratio={recent_velocity / baseline_velocity:.1f}x."
                    ),
                    confidence=min(1.0, recent_velocity / (5 * baseline_velocity)),
                ))


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #

def run_financial_intelligence(
    graph: nx.MultiDiGraph,
    evidence_path: str = "data/exports/evidence_index.json",
) -> List[Dict[str, Any]]:
    """Run full financial intelligence and write results to disk."""
    ep = Path(evidence_path)
    evidence: List[Dict] = []
    if ep.exists():
        data = json.loads(ep.read_text())
        evidence = data.get("records", data) if isinstance(data, dict) else data

    engine = FinancialIntelligenceEngine(graph, evidence)
    patterns = engine.analyze()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(
        [p.to_dict() for p in patterns], indent=2, default=str
    ))
    logger.info("Wrote %d patterns to %s", len(patterns), OUTPUT_PATH)
    return [p.to_dict() for p in patterns]
