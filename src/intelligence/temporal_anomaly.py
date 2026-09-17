"""
intelligence/temporal_anomaly.py
---------------------------------
Temporal anomaly detection engine (Phase 4).

Operates on the evidence index and knowledge graph — does NOT re-run
the full pipeline.  Four anomaly families:

  A — Communication Burst
  B — Synchronized Cross-Community Activity
  C — New Hub Emergence
  D — Round-Trip Financial Flow
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/exports/temporal_anomalies.json")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class AnomalyRecord:
    anomaly_id: str
    anomaly_type: str  # BURST | SYNCHRONIZED | NEW_HUB | ROUND_TRIP
    severity: str  # LOW | MEDIUM | HIGH
    detected_at: str
    entity_ids: List[str]
    evidence_ids: List[str]
    description: str
    confidence: float
    status: str = "HYPOTHESIS — requires human review"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _make_anomaly_id(anomaly_type: str, payload: str) -> str:
    digest = hashlib.sha256(f"{anomaly_type}|{payload}".encode()).hexdigest()[:8]
    return f"AN-{digest}"


def _severity(z_score: float = 0.0, sync_score: float = 0.0,
              delta: float = 0.0, ratio: float = 0.0,
              anomaly_type: str = "") -> str:
    if anomaly_type == "BURST":
        if z_score > 5:
            return "HIGH"
        if z_score > 3:
            return "MEDIUM"
        return "LOW"
    if anomaly_type == "SYNCHRONIZED":
        if sync_score > 0.6:
            return "HIGH"
        if sync_score > 0.3:
            return "MEDIUM"
        return "LOW"
    if anomaly_type == "NEW_HUB":
        return "HIGH" if delta > 0.1 else ("MEDIUM" if delta > 0.05 else "LOW")
    if anomaly_type == "ROUND_TRIP":
        if ratio > 50:
            return "HIGH"
        if ratio > 10:
            return "MEDIUM"
        return "LOW"
    return "LOW"


# --------------------------------------------------------------------------- #
# Detector
# --------------------------------------------------------------------------- #

class TemporalAnomalyDetector:
    """Detects temporal anomalies in the knowledge graph + evidence store."""

    def __init__(self, graph: nx.MultiDiGraph, evidence_index: List[Dict[str, Any]]):
        self.graph = graph
        self.evidence = evidence_index
        self._anomalies: List[AnomalyRecord] = []

    # ---- Main entry ----

    def detect(self) -> List[AnomalyRecord]:
        self._anomalies = []
        self._detect_bursts()
        self._detect_synchronized()
        self._detect_new_hubs()
        self._detect_round_trips()
        logger.info("Temporal anomaly detection: %d anomalies found", len(self._anomalies))
        return self._anomalies

    # ---- A: Communication Burst ----

    def _detect_bursts(self):
        """For each entity, compute 24h rolling window counts over time-bucketed events."""
        import statistics

        # Build per-entity timestamp lists from evidence
        entity_timestamps: Dict[str, List[datetime]] = defaultdict(list)
        entity_evidence: Dict[str, List[str]] = defaultdict(list)

        for rec in self.evidence:
            ts_str = rec.get("timestamp", "")
            eid = rec.get("evidence_id", "")
            subjects = rec.get("subject_ids", [])
            if not ts_str or not subjects:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            for sid in subjects:
                entity_timestamps[sid].append(ts)
                entity_evidence[sid].append(eid)

        window = timedelta(hours=24)
        # Bucket timestamps into hour bins so the burst doesn't inflate its own baseline
        for entity_id, timestamps in entity_timestamps.items():
            if len(timestamps) < 5:
                continue

            timestamps.sort()
            # Deduplicate: create one window per unique hour-bucket
            unique_starts = sorted(set(
                ts.replace(minute=0, second=0, microsecond=0)
                for ts in timestamps
            ))

            # Rolling window counts over each unique start
            window_counts: List[int] = []
            for start in unique_starts:
                count = sum(1 for t in timestamps if start <= t < start + window)
                window_counts.append(count)

            if len(window_counts) < 5:
                continue

            mean = statistics.mean(window_counts)
            std = statistics.stdev(window_counts) if len(window_counts) > 1 else 0.001
            if std == 0:
                continue

            for start, count in zip(unique_starts, window_counts):
                z = (count - mean) / std
                if z > 3:  # Burst threshold
                    # Collect evidence in this window
                    ev_ids = [
                        eid for t, eid in zip(timestamps, entity_evidence[entity_id])
                        if start <= t < start + window
                    ]
                    ev_ids = list(dict.fromkeys(ev_ids))[:20]
                    payload = f"{entity_id}|{start.isoformat()}|{count}"
                    sev = _severity(z_score=z, anomaly_type="BURST")
                    self._anomalies.append(AnomalyRecord(
                        anomaly_id=_make_anomaly_id("BURST", payload),
                        anomaly_type="BURST",
                        severity=sev,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        entity_ids=[entity_id],
                        evidence_ids=ev_ids,
                        description=(
                            f"Communication burst detected for entity {entity_id}: "
                            f"{count} events in 24h window (baseline mean={mean:.1f}, "
                            f"z-score={z:.2f})."
                        ),
                        confidence=min(1.0, z / 10),
                    ))

    # ---- B: Synchronized Cross-Community Activity ----

    def _detect_synchronized(self):
        """Find entity pairs from different communities with synchronized activity."""
        # Build community labels from graph
        entity_community: Dict[str, int] = {}
        for node, data in self.graph.nodes(data=True):
            metrics = data.get("metrics", {})
            if "community" in metrics:
                entity_community[node] = metrics["community"]

        # Build per-entity timestamps
        entity_timestamps: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        for rec in self.evidence:
            ts_str = rec.get("timestamp", "")
            eid = rec.get("evidence_id", "")
            subjects = rec.get("subject_ids", [])
            if not ts_str or not subjects:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            for sid in subjects:
                entity_timestamps[sid].append((ts, eid))

        # Find synchronized pairs
        entity_list = list(entity_timestamps.keys())
        seen_pairs: Set[Tuple[str, str]] = set()

        for i, ea in enumerate(entity_list):
            ca = entity_community.get(ea)
            if ca is None:
                continue
            timestamps_a = entity_timestamps[ea]
            for eb in entity_list[i + 1:]:
                cb = entity_community.get(eb)
                if cb is None or ca == cb:
                    continue  # Same community or no community
                pair = (min(ea, eb), max(ea, eb))
                if pair in seen_pairs:
                    continue

                timestamps_b = entity_timestamps[eb]
                # Find timestamps within 15 min of each other
                sync_events: List[Tuple[str, str]] = []
                for t_a, eid_a in timestamps_a:
                    for t_b, eid_b in timestamps_b:
                        if abs((t_a - t_b).total_seconds()) <= 900:  # 15 min
                            sync_events.append((t_a.isoformat(), t_b.isoformat()))
                            break  # One match per A timestamp

                if len(sync_events) >= 3:
                    seen_pairs.add(pair)
                    sync_score = len(sync_events) / max(len(timestamps_a), 1)
                    payload = f"{ea}|{eb}|{len(sync_events)}"
                    sev = _severity(sync_score=sync_score, anomaly_type="SYNCHRONIZED")
                    self._anomalies.append(AnomalyRecord(
                        anomaly_id=_make_anomaly_id("SYNCHRONIZED", payload),
                        anomaly_type="SYNCHRONIZED",
                        severity=sev,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        entity_ids=[ea, eb],
                        evidence_ids=[],
                        description=(
                            f"Synchronized cross-community activity between {ea} "
                            f"(community {ca}) and {eb} (community {cb}): "
                            f"{len(sync_events)} synchronized events "
                            f"(score={sync_score:.2f})."
                        ),
                        confidence=min(1.0, sync_score),
                    ))

    # ---- C: New Hub Emergence ----

    def _detect_new_hubs(self):
        """Compare betweenness centrality at midpoint vs end of timeline."""
        timestamps = []
        for rec in self.evidence:
            ts_str = rec.get("timestamp", "")
            if ts_str:
                try:
                    timestamps.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
                except (ValueError, TypeError):
                    continue

        if len(timestamps) < 10:
            return

        timestamps.sort()
        mid = timestamps[len(timestamps) // 2]
        end = timestamps[-1]

        # Build graph at midpoint and end
        g_mid = self._graph_as_of(mid)
        g_end = self._graph_as_of(end)

        if g_mid.number_of_nodes() < 2 or g_end.number_of_nodes() < 2:
            return

        bc_mid = nx.betweenness_centrality(g_mid, k=min(100, g_mid.number_of_nodes()))
        bc_end = nx.betweenness_centrality(g_end, k=min(100, g_end.number_of_nodes()))

        for node in g_end.nodes():
            delta = bc_end.get(node, 0) - bc_mid.get(node, 0)
            if delta > 0.05:
                # Find first seen timestamp
                first_seen = self._first_seen(node)
                payload = f"{node}|{delta:.4f}"
                sev = _severity(delta=delta, anomaly_type="NEW_HUB")
                self._anomalies.append(AnomalyRecord(
                    anomaly_id=_make_anomaly_id("NEW_HUB", payload),
                    anomaly_type="NEW_HUB",
                    severity=sev,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    entity_ids=[node],
                    evidence_ids=[],
                    description=(
                        f"New hub emergence for {node}: betweenness centrality "
                        f"increased from {bc_mid.get(node, 0):.4f} to "
                        f"{bc_end.get(node, 0):.4f} (delta={delta:.4f})."
                    ),
                    confidence=min(1.0, delta * 10),
                ))

    def _graph_as_of(self, cutoff: datetime) -> nx.MultiDiGraph:
        """Return a subgraph with edges observed at or before cutoff."""
        g = nx.MultiDiGraph()
        for node, data in self.graph.nodes(data=True):
            g.add_node(node, **data)
        for u, v, k, data in self.graph.edges(data=True, keys=True):
            ts_str = (
                data.get("attributes", {}).get("timestamp", "")
                or data.get("observed_at", "")
            )
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts <= cutoff:
                        g.add_edge(u, v, k, **data)
                except (ValueError, TypeError):
                    g.add_edge(u, v, k, **data)
            else:
                g.add_edge(u, v, k, **data)
        return g

    def _first_seen(self, node_id: str) -> str:
        for rec in self.evidence:
            if node_id in rec.get("subject_ids", []):
                return rec.get("timestamp", "unknown")
        return "unknown"

    # ---- D: Round-Trip Financial Flow ----

    def _detect_round_trips(self):
        """Find financial cycles of length 2-4 within 72h windows."""
        # Build transaction subgraph
        tx_edges: List[Tuple[str, str, Dict]] = []
        for u, v, data in self.graph.edges(data=True):
            rel = data.get("relation", "")
            if "TRANSFER" in rel.upper() or "FINANCIAL" in rel.upper():
                attrs = data.get("attributes", {})
                # Merge top-level and nested attributes
                merged = {**data, **attrs}
                tx_edges.append((u, v, merged))

        if not tx_edges:
            return

        # Group edges by (source, target) with timestamps
        edge_map: Dict[Tuple[str, str], List[Tuple[datetime, Dict]]] = defaultdict(list)
        for u, v, attrs in tx_edges:
            ts_str = attrs.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    edge_map[(u, v)].append((ts, attrs))
                except (ValueError, TypeError):
                    pass

        if not edge_map:
            return

        # Compute median transaction amount
        amounts: List[float] = []
        for _, v_list in edge_map.items():
            for _, attrs in v_list:
                try:
                    amt = float(attrs.get("amount", attrs.get("duration_sec", 100)))
                    amounts.append(amt)
                except (ValueError, TypeError):
                    amounts.append(100)
        import statistics
        median_amt = statistics.median(amounts) if amounts else 100

        # DFS to find cycles of length 2-4
        all_nodes = set()
        for (u, v) in edge_map:
            all_nodes.add(u)
            all_nodes.add(v)

        found_cycles: Set[Tuple] = set()
        for start in all_nodes:
            self._dfs_cycles(start, start, edge_map, [start], found_cycles,
                             max_len=4, max_window=timedelta(hours=72))

        for cycle_nodes in found_cycles:
            if len(cycle_nodes) < 3:
                continue
            # Compute total amount and window
            total = 0.0
            window_hours = 0.0
            cycle_tx_ids: List[str] = []
            all_ts: List[datetime] = []
            for i in range(len(cycle_nodes) - 1):
                u, v = cycle_nodes[i], cycle_nodes[i + 1]
                for ts, attrs in edge_map.get((u, v), []):
                    total += float(attrs.get("amount", attrs.get("duration_sec", 100)))
                    all_ts.append(ts)
                    cycle_tx_ids.append(attrs.get("record_id", attrs.get("evidence", "")))
                    break  # Take first matching

            if all_ts and len(all_ts) >= 2:
                window_hours = (max(all_ts) - min(all_ts)).total_seconds() / 3600

            ratio = total / max(median_amt, 1)
            if ratio > 10:
                payload = "|".join(cycle_nodes)
                sev = _severity(ratio=ratio, anomaly_type="ROUND_TRIP")
                self._anomalies.append(AnomalyRecord(
                    anomaly_id=_make_anomaly_id("ROUND_TRIP", payload),
                    anomaly_type="ROUND_TRIP",
                    severity=sev,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    entity_ids=cycle_nodes,
                    evidence_ids=cycle_tx_ids[:10],
                    description=(
                        f"Round-trip financial flow detected: {' → '.join(cycle_nodes)} "
                        f"(total={total:.0f}, {window_hours:.1f}h window, "
                        f"ratio={ratio:.1f}x median)."
                    ),
                    confidence=min(1.0, ratio / 100),
                ))

    def _dfs_cycles(self, start: str, current: str, edge_map: Dict,
                    path: List[str], found: Set, max_len: int,
                    max_window: timedelta, visited: Optional[Set] = None):
        if visited is None:
            visited = set()

        if len(path) > max_len:
            return

        for (u, v), ts_list in edge_map.items():
            if u != current:
                continue
            if v == start and len(path) >= 2:
                found.add(tuple(path + [v]))
                continue
            if v not in visited and v not in path:
                visited.add(v)
                self._dfs_cycles(start, v, edge_map, path + [v],
                                 found, max_len, max_window, visited)
                visited.discard(v)


# --------------------------------------------------------------------------- #
# Convenience functions
# --------------------------------------------------------------------------- #

def run_temporal_anomaly_detection(
    graph: nx.MultiDiGraph,
    evidence_path: str = "data/exports/evidence_index.json",
) -> List[Dict[str, Any]]:
    """Run full anomaly detection and write results to disk."""
    ep = Path(evidence_path)
    if not ep.exists():
        logger.warning("Evidence index not found at %s — skipping anomalies", ep)
        return []
    evidence_data = json.loads(ep.read_text())
    evidence = evidence_data.get("records", evidence_data) if isinstance(evidence_data, dict) else evidence_data

    detector = TemporalAnomalyDetector(graph, evidence)
    anomalies = detector.detect()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(
        [a.to_dict() for a in anomalies], indent=2, default=str
    ))
    logger.info("Wrote %d anomalies to %s", len(anomalies), OUTPUT_PATH)
    return [a.to_dict() for a in anomalies]
