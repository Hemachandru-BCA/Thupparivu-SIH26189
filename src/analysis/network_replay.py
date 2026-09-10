"""
network_replay.py
-----------------
Network Replay / Temporal Network Evolution engine (P1.1).

Provides precomputed temporal snapshots with delta updates for efficient
timeline replay.  Supports three timeline modes:
  - Snapshot: graph at a specific timestamp
  - Cumulative: everything up to timestamp T
  - Sliding window: only activity in [T-N, T]

Automatically identifies important temporal events:
  - first entity appearance
  - first relationship
  - sudden communication burst
  - new financial relationship
  - community merge/split
  - new bridge entity
  - disappearance of central entity
  - emergence of ghost candidate
  - cross-case connection
  - significant topology change
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TimelineEvent(BaseModel):
    event_id: str = ""
    timestamp: str
    event_type: str    # ENTITY_APPEAR | RELATIONSHIP_FORM | COMMUNITY_MERGE | BRIDGE_EMERGE | etc.
    description: str
    entities: List[Dict[str, str]] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    importance: float = 0.5   # 0-1


class NetworkDelta(BaseModel):
    timestamp: str
    nodes_added: int = 0
    nodes_removed: int = 0
    edges_added: int = 0
    edges_removed: int = 0
    community_changes: Dict[str, Any] = Field(default_factory=dict)
    centrality_changes: Dict[str, Any] = Field(default_factory=dict)
    bridge_changes: Dict[str, Any] = Field(default_factory=dict)
    added_node_ids: List[str] = Field(default_factory=list)
    removed_node_ids: List[str] = Field(default_factory=list)
    summary: str = ""


class ReplaySnapshot(BaseModel):
    timestamp: str
    node_count: int = 0
    edge_count: int = 0
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    communities: int = 0
    truncated: bool = False


class NetworkReplayEngine:
    """Precompute temporal snapshots for efficient timeline replay."""

    def __init__(self, graph: nx.MultiDiGraph, temporal_graph: Optional[Any] = None) -> None:
        self.graph = graph
        self.temporal_graph = temporal_graph
        self._snapshots: Dict[str, ReplaySnapshot] = {}
        self._deltas: Dict[str, NetworkDelta] = {}
        self._events: Optional[List[TimelineEvent]] = None
        self._bucket_timestamps: Optional[List[str]] = None

    # ------------------------------------------------------------------ #
    # Timestamp extraction
    # ------------------------------------------------------------------ #
    def _edge_timestamps(self) -> List[str]:
        """Extract all unique timestamps from edges, sorted."""
        timestamps = set()
        for _, _, d in self.graph.edges(data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")
            if ts:
                timestamps.add(str(ts)[:19])  # truncate microseconds
        return sorted(timestamps)

    def _temporal_edge_map(self) -> Dict[str, Set[Tuple[str, str, Any]]]:
        """Map timestamp → set of (source, target, edge_data)."""
        ts_map: Dict[str, Set[Tuple[str, str, Any]]] = defaultdict(set)
        for src, tgt, key, d in self.graph.edges(keys=True, data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")
            if ts:
                ts_map[str(ts)[:19]].add((src, tgt, key))
        return ts_map

    # ------------------------------------------------------------------ #
    # Bucket timestamps for replay
    # ------------------------------------------------------------------ #
    def get_bucket_timestamps(self, n_buckets: int = 12) -> List[str]:
        """Equally spaced timestamps covering the graph's temporal range."""
        if self._bucket_timestamps:
            return self._bucket_timestamps
        timestamps = self._edge_timestamps()
        if not timestamps:
            now = datetime.now(timezone.utc).isoformat()[:19]
            self._bucket_timestamps = [now]
            return self._bucket_timestamps
        if len(timestamps) <= n_buckets:
            self._bucket_timestamps = timestamps
            return self._bucket_timestamps
        # Sample evenly
        step = max(1, len(timestamps) // n_buckets)
        self._bucket_timestamps = [timestamps[i] for i in range(0, len(timestamps), step)][:n_buckets + 1]
        return self._bucket_timestamps

    # ------------------------------------------------------------------ #
    # Snapshot computation
    # ------------------------------------------------------------------ #
    def snapshot_at(self, timestamp: str, mode: str = "cumulative") -> ReplaySnapshot:
        """Get the graph state at a given timestamp.

        Modes:
          - cumulative: all edges observed up to timestamp
          - snapshot: only edges at exactly this timestamp
          - sliding_window: edges in [T - 30 days, T]
        """
        cache_key = f"{timestamp}|{mode}"
        if cache_key in self._snapshots:
            return self._snapshots[cache_key]

        if mode == "cumulative":
            nodes, edges = self._cumulative_state(timestamp)
        elif mode == "snapshot":
            nodes, edges = self._exact_snapshot(timestamp)
        elif mode == "sliding_window":
            window_start = (datetime.fromisoformat(timestamp) - timedelta(days=30)).isoformat()[:19]
            nodes, edges = self._window_state(window_start, timestamp)
        else:
            nodes, edges = self._cumulative_state(timestamp)

        # Community detection
        communities = 0
        if edges:
            try:
                temp_g = nx.MultiDiGraph()
                for n, d in nodes.items():
                    temp_g.add_node(n, **d)
                for src, tgt, d in edges.values():
                    temp_g.add_edge(src, tgt, **d)
                from networkx.algorithms.community import louvain_communities
                communities = len(louvain_communities(temp_g.to_undirected(), seed=42))
            except Exception:
                communities = 0

        # Serialize
        node_list = [
            {
                "id": n,
                "label": d.get("canonical_name") or d.get("label") or str(n),
                "type": d.get("entity_type") or "UNKNOWN",
                "metrics": d.get("metrics") or {},
            }
            for n, d in nodes.items()
        ]
        edge_list = []
        for (src, tgt, key), d in edges.items():
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            edge_list.append({
                "id": d.get("id") or str(key),
                "source": src,
                "target": tgt,
                "relation": d.get("relation", "ASSOCIATED_WITH"),
                "source_name": d.get("source_name", ""),
                "target_name": d.get("target_name", ""),
                "confidence": float(a.get("confidence", 1.0)),
                "timestamp": nested.get("timestamp") or a.get("timestamp"),
            })

        snap = ReplaySnapshot(
            timestamp=timestamp,
            node_count=len(node_list),
            edge_count=len(edge_list),
            nodes=node_list,
            edges=edge_list,
            communities=communities,
            truncated=len(edge_list) > 5000,
        )
        self._snapshots[cache_key] = snap
        return snap

    def _cumulative_state(self, ts: str) -> Tuple[Dict[str, dict], Dict[tuple, dict]]:
        nodes = {}
        edges = {}
        for src, tgt, key, d in self.graph.edges(keys=True, data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            edge_ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")
            if edge_ts and str(edge_ts)[:19] <= ts:
                edges[(src, tgt, key)] = d
                if src in self.graph:
                    nodes[src] = dict(self.graph.nodes[src])
                if tgt in self.graph:
                    nodes[tgt] = dict(self.graph.nodes[tgt])
        return nodes, edges

    def _exact_snapshot(self, ts: str) -> Tuple[Dict[str, dict], Dict[tuple, dict]]:
        nodes = {}
        edges = {}
        for src, tgt, key, d in self.graph.edges(keys=True, data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            edge_ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")
            if edge_ts and str(edge_ts)[:19] == ts[:19]:
                edges[(src, tgt, key)] = d
                if src in self.graph:
                    nodes[src] = dict(self.graph.nodes[src])
                if tgt in self.graph:
                    nodes[tgt] = dict(self.graph.nodes[tgt])
        return nodes, edges

    def _window_state(self, start: str, end: str) -> Tuple[Dict[str, dict], Dict[tuple, dict]]:
        nodes = {}
        edges = {}
        for src, tgt, key, d in self.graph.edges(keys=True, data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            edge_ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")
            if edge_ts:
                ets = str(edge_ts)[:19]
                if start <= ets <= end:
                    edges[(src, tgt, key)] = d
                    if src in self.graph:
                        nodes[src] = dict(self.graph.nodes[src])
                    if tgt in self.graph:
                        nodes[tgt] = dict(self.graph.nodes[tgt])
        return nodes, edges

    # ------------------------------------------------------------------ #
    # Delta computation
    # ------------------------------------------------------------------ #
    def compute_delta(self, from_ts: str, to_ts: str) -> NetworkDelta:
        """Compute structural diff between two timestamps."""
        cache_key = f"{from_ts}|{to_ts}"
        if cache_key in self._deltas:
            return self._deltas[cache_key]

        snap_from = self.snapshot_at(from_ts, "cumulative")
        snap_to = self.snapshot_at(to_ts, "cumulative")

        nodes_from = {n["id"] for n in snap_from.nodes}
        nodes_to = {n["id"] for n in snap_to.nodes}
        added_nodes = sorted(nodes_to - nodes_from)
        removed_nodes = sorted(nodes_from - nodes_to)

        edges_from = {(e["source"], e["target"]) for e in snap_from.edges}
        edges_to = {(e["source"], e["target"]) for e in snap_to.edges}
        added_edges = edges_to - edges_from
        removed_edges = edges_from - edges_to

        # Community changes
        community_delta = snap_to.communities - snap_from.communities

        summary_parts = []
        if added_nodes:
            summary_parts.append(f"+ {len(added_nodes)} entities")
        if removed_nodes:
            summary_parts.append(f"- {len(removed_nodes)} entities")
        if added_edges:
            summary_parts.append(f"+ {len(added_edges)} relationships")
        if removed_edges:
            summary_parts.append(f"- {len(removed_edges)} relationships")
        if community_delta != 0:
            summary_parts.append(f"Community count: {snap_from.communities} → {snap_to.communities}")

        delta = NetworkDelta(
            timestamp=to_ts,
            nodes_added=len(added_nodes),
            nodes_removed=len(removed_nodes),
            edges_added=len(added_edges),
            edges_removed=len(removed_edges),
            community_changes={
                "before": snap_from.communities,
                "after": snap_to.communities,
                "delta": community_delta,
            },
            added_node_ids=added_nodes[:50],
            removed_node_ids=removed_nodes[:50],
            summary="; ".join(summary_parts) if summary_parts else "No structural changes detected.",
        )
        self._deltas[cache_key] = delta
        return delta

    # ------------------------------------------------------------------ #
    # Important temporal events
    # ------------------------------------------------------------------ #
    def identify_events(self) -> List[TimelineEvent]:
        """Automatically identify important temporal events."""
        if self._events is not None:
            return self._events

        events: List[TimelineEvent] = []
        node_first_seen: Dict[str, str] = {}
        edge_first_seen: Dict[Tuple[str, str], str] = {}
        prev_node_count = 0
        prev_edge_count = 0
        event_idx = 0

        # Use fewer buckets to limit event count
        timestamps = self.get_bucket_timestamps(15)

        for ts in timestamps:
            snap = self.snapshot_at(ts, "cumulative")

            # New entities — only record significant ones (high degree or unique type)
            current_nodes = {n["id"] for n in snap.nodes}
            for n in snap.nodes:
                nid = n["id"]
                if nid not in node_first_seen:
                    node_first_seen[nid] = ts
                    # Only record entities with mentions > 3 or non-PERSON types
                    mention_count = n.get("metrics", {}).get("degree", 0)
                    if mention_count >= 3 or n.get("type") not in ("PERSON", "PHONE"):
                        event_idx += 1
                        events.append(TimelineEvent(
                            event_id=f"EVT-{event_idx:04d}",
                            timestamp=ts,
                            event_type="ENTITY_APPEAR",
                            description=f"Entity '{n['label']}' ({n['type']}) first appears",
                            entities=[{"id": nid, "label": n["label"]}],
                            importance=0.4,
                        ))

            # New edges
            for e in snap.edges:
                key = (e["source"], e["target"])
                if key not in edge_first_seen:
                    edge_first_seen[key] = ts
                    # Check for financial relationships
                    if e.get("relation") in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS"):
                        event_idx += 1
                        events.append(TimelineEvent(
                            event_id=f"EVT-{event_idx:04d}",
                            timestamp=ts,
                            event_type="FINANCIAL_RELATIONSHIP",
                            description=f"Financial relationship: {e.get('source_name', '')} → {e.get('target_name', '')}",
                            entities=[
                                {"id": e["source"], "label": e.get("source_name", "")},
                                {"id": e["target"], "label": e.get("target_name", "")},
                            ],
                            importance=0.6,
                        ))

            # Topology change
            node_delta = snap.node_count - prev_node_count
            edge_delta = snap.edge_count - prev_edge_count
            if prev_node_count > 0 and abs(node_delta) > prev_node_count * 0.1:
                event_idx += 1
                direction = "increase" if node_delta > 0 else "decrease"
                events.append(TimelineEvent(
                    event_id=f"EVT-{event_idx:04d}",
                    timestamp=ts,
                    event_type="TOPOLOGY_CHANGE",
                    description=f"Significant network {direction}: {abs(node_delta)} entities",
                    importance=0.7,
                ))

            prev_node_count = snap.node_count
            prev_edge_count = snap.edge_count

        self._events = sorted(events, key=lambda e: e.timestamp)
        return self._events
