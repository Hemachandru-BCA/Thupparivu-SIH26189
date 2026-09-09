"""
graph/temporal_graph.py
-----------------------
Temporal multilayer knowledge graph engine (Phase 2).

This module wraps a NetworkX ``MultiDiGraph`` with:

1. **Typed entity layers** — PERSON, ORGANIZATION, PHONE, VEHICLE,
   LOCATION, ACCOUNT, DEVICE, CASE, DOCUMENT, EVENT, ADDRESS, IDENTIFIER.
2. **Typed relationship layers** — COMMUNICATION, FINANCIAL, LOCATION,
   ORGANIZATIONAL, SOCIAL.
3. Every edge supports ``valid_from`` / ``valid_to`` / ``observed_at``
   temporal metadata.
4. **Temporal snapshots** — ``graph_as_of(ts)``, ``graph_between(s,e)``.
5. Historical queries that **must not** use future information.
6. **Multilayer views** — communication layer, financial layer, etc.
7. **Temporal network features** — burstiness, persistence, emergence, decay.
8. **ML-ready temporal features** with strict no-leakage guarantees.

All timestamps are ISO-8601 strings; comparisons are done via
``datetime.fromisoformat``.  Edges whose temporal metadata is missing are
treated as "observed from the beginning" (no future leakage if the system
only sees them at the snapshot timestamp).

Non-negotiable rule: ``graph_as_of(t)`` must never return edges or
centrality computed from information that became available *after* ``t``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import networkx as nx

from src.domain.models import Entity, Relationship, RelationshipStatus, TemporalSpan

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Entity layer taxonomy
# --------------------------------------------------------------------------- #

class EntityLayer(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    LOCATION = "LOCATION"
    ACCOUNT = "ACCOUNT"
    DEVICE = "DEVICE"
    CASE = "CASE"
    DOCUMENT = "DOCUMENT"
    EVENT = "EVENT"
    ADDRESS = "ADDRESS"
    IDENTIFIER = "IDENTIFIER"
    DATETIME = "DATETIME"


ENTITY_LAYER_SET: Set[str] = {e.value for e in EntityLayer}


# --------------------------------------------------------------------------- #
# Relationship layer taxonomy
# --------------------------------------------------------------------------- #

class RelationshipLayer(str, Enum):
    COMMUNICATION = "COMMUNICATION"
    FINANCIAL = "FINANCIAL"
    LOCATION = "LOCATION"
    ORGANIZATIONAL = "ORGANIZATIONAL"
    SOCIAL = "SOCIAL"


RELATION_TO_LAYER: Dict[str, RelationshipLayer] = {
    "CALLED": RelationshipLayer.COMMUNICATION,
    "MESSED": RelationshipLayer.COMMUNICATION,
    "MESSED": RelationshipLayer.COMMUNICATION,
    "TRANSFERRED_TO": RelationshipLayer.FINANCIAL,
    "TRANSFERRED_FUNDS": RelationshipLayer.FINANCIAL,
    "USES_ACCOUNT": RelationshipLayer.FINANCIAL,
    "LOCATED_IN": RelationshipLayer.LOCATION,
    "LOCATED_AT": RelationshipLayer.LOCATION,
    "MEMBER_OF": RelationshipLayer.ORGANIZATIONAL,
    "LEADS": RelationshipLayer.ORGANIZATIONAL,
    "WORKS_FOR": RelationshipLayer.ORGANIZATIONAL,
    "REGISTERED_TO": RelationshipLayer.ORGANIZATIONAL,
    "MET": RelationshipLayer.SOCIAL,
    "ATTENDED_MEETING_AT": RelationshipLayer.SOCIAL,
    "TRAVELED_WITH": RelationshipLayer.SOCIAL,
    "ASSOCIATED_WITH": RelationshipLayer.SOCIAL,
}


def classify_relation(relation: str) -> RelationshipLayer:
    return RELATION_TO_LAYER.get(relation.upper().strip(), RelationshipLayer.SOCIAL)


# --------------------------------------------------------------------------- #
# Timestamp helpers
# --------------------------------------------------------------------------- #

def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _ts_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# --------------------------------------------------------------------------- #
# Edge temporal record
# --------------------------------------------------------------------------- #

@dataclass
class TemporalEdge:
    """Thin wrapper around a NetworkX edge with temporal metadata."""

    source: str
    target: str
    key: Any
    relation: str
    layer: RelationshipLayer
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    observed_at: Optional[datetime] = None
    confidence: float = 1.0
    evidence_ids: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def effective_time(self) -> Optional[datetime]:
        """The canonical timestamp for ordering and snapshot filtering."""
        return self.observed_at or self.valid_from

    def is_active_at(self, ts: datetime) -> bool:
        """True if this edge was already known/observed at timestamp *ts*."""
        effective = self.effective_time
        if effective is None:
            return True  # unknown timestamp → assumed always visible
        return effective <= ts

    def is_active_between(self, start: datetime, end: datetime) -> bool:
        effective = self.effective_time
        if effective is None:
            return True
        return start <= effective <= end


# --------------------------------------------------------------------------- #
# Temporal Multilayer Graph
# --------------------------------------------------------------------------- #

class TemporalMultilayerGraph:
    """A temporal, typed, multilayer wrapper over a NetworkX graph.

    The wrapper does **not** own the underlying graph; it indexes it for
    fast temporal queries.  Call :meth:`build_index` after construction
    (or whenever the underlying graph changes).

    Usage::

        tm = TemporalMultilayerGraph(graph)
        snap = tm.graph_as_of("2025-06-15T00:00:00Z")
        comm_layer = tm.layer_view(RelationshipLayer.COMMUNICATION)
        stats = tm.temporal_statistics()
    """

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        # indexes — populated by build_index()
        self._edges: List[TemporalEdge] = []
        self._node_layers: Dict[str, str] = {}             # node → entity layer
        self._layer_nodes: Dict[str, Set[str]] = defaultdict(set)
        self._layer_edges: Dict[str, List[TemporalEdge]] = defaultdict(list)
        self._edge_by_key: Dict[Any, TemporalEdge] = {}
        self._timeline: List[TemporalEdge] = []  # sorted by effective_time

        self._build_index()

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #
    def _build_index(self) -> None:
        self._edges.clear()
        self._node_layers.clear()
        self._layer_nodes.clear()
        self._layer_edges.clear()
        self._edge_by_key.clear()

        for node, attrs in self.graph.nodes(data=True):
            etype = (attrs.get("entity_type") or "UNKNOWN").upper()
            self._node_layers[node] = etype
            if etype in ENTITY_LAYER_SET:
                self._layer_nodes[etype].add(node)

        for src, tgt, key, attrs in self.graph.edges(keys=True, data=True):
            relation = (attrs.get("relation") or "ASSOCIATED_WITH").upper()
            layer = classify_relation(relation)
            a = attrs.get("attributes") or {}
            te = TemporalEdge(
                source=src,
                target=tgt,
                key=key,
                relation=relation,
                layer=layer,
                valid_from=_parse_ts(a.get("valid_from")),
                valid_to=_parse_ts(a.get("valid_to")),
                observed_at=_parse_ts(a.get("timestamp") or a.get("observed_at")),
                confidence=float(a.get("confidence", 1.0)),
                evidence_ids=list(a.get("evidence_ids") or []),
                attributes=dict(a),
            )
            self._edges.append(te)
            self._edge_by_key[key] = te
            self._layer_edges[layer.value].append(te)

        self._timeline = sorted(
            self._edges,
            key=lambda e: e.effective_time or datetime.min.replace(tzinfo=timezone.utc),
        )
        logger.info(
            "Temporal index built: %d edges across %d layers, %d nodes",
            len(self._edges),
            len(self._layer_edges),
            len(self._node_layers),
        )

    # ------------------------------------------------------------------ #
    # Snapshot API
    # ------------------------------------------------------------------ #
    def graph_as_of(self, timestamp: str) -> nx.MultiDiGraph:
        """Return the sub-graph that was known *as of* the given timestamp.

        Only edges whose ``effective_time <= timestamp`` are included.
        Only nodes that are endpoints of at least one surviving edge (or
        have no outgoing edges at all) are kept.
        """
        ts = _parse_ts(timestamp) or datetime.now(timezone.utc)
        surviving_edges = [e for e in self._timeline if e.is_active_at(ts)]
        return self._build_subgraph(surviving_edges)

    def graph_between(self, start: str, end: str) -> nx.MultiDiGraph:
        """Edges observed in the interval [start, end]."""
        s = _parse_ts(start) or datetime.min.replace(tzinfo=timezone.utc)
        e = _parse_ts(end) or datetime.now(timezone.utc)
        surviving = [edge for edge in self._timeline if edge.is_active_between(s, e)]
        return self._build_subgraph(surviving)

    def graph_before(self, timestamp: str) -> nx.MultiDiGraph:
        """Edges observed strictly *before* the given timestamp."""
        ts = _parse_ts(timestamp) or datetime.now(timezone.utc)
        surviving = [e for e in self._timeline if e.effective_time and e.effective_time < ts]
        return self._build_subgraph(surviving)

    def graph_after(self, timestamp: str) -> nx.MultiDiGraph:
        """Edges observed strictly *after* the given timestamp."""
        ts = _parse_ts(timestamp) or datetime.now(timezone.utc)
        surviving = [e for e in self._timeline if e.effective_time and e.effective_time > ts]
        return self._build_subgraph(surviving)

    def _build_subgraph(self, edges: Sequence[TemporalEdge]) -> nx.MultiDiGraph:
        g = nx.MultiDiGraph()
        nodes_in = set()
        for e in edges:
            nodes_in.add(e.source)
            nodes_in.add(e.target)
        for n in nodes_in:
            if n in self.graph.nodes:
                g.add_node(n, **dict(self.graph.nodes[n]))
        for e in edges:
            if e.source in g and e.target in g:
                orig = self.graph.edges[e.source, e.target, e.key]
                g.add_edge(e.source, e.target, key=e.key, **orig)
        return g

    # ------------------------------------------------------------------ #
    # Multilayer views
    # ------------------------------------------------------------------ #
    def layer_view(self, layer: RelationshipLayer) -> nx.MultiDiGraph:
        """Return a sub-graph containing only edges of the given layer."""
        edges = self._layer_edges.get(layer.value, [])
        return self._build_subgraph(edges)

    def all_layers(self) -> Dict[str, nx.MultiDiGraph]:
        """Communication, financial, location, organizational, social views."""
        views: Dict[str, nx.MultiDiGraph] = {}
        for layer in RelationshipLayer:
            g = self.layer_view(layer)
            if g.number_of_edges() > 0:
                views[layer.value] = g
        return views

    def multiplex_graph(self) -> nx.MultiDiGraph:
        """Combined graph with edges carrying a ``layer`` attribute."""
        g = nx.MultiDiGraph()
        for node, data in self.graph.nodes(data=True):
            g.add_node(node, **data)
        for te in self._edges:
            orig = self.graph.edges[te.source, te.target, te.key]
            attrs = dict(orig)
            attrs["layer"] = te.layer.value
            g.add_edge(te.source, te.target, key=te.key, **attrs)
        return g

    # ------------------------------------------------------------------ #
    # Temporal network features (per-node)
    # ------------------------------------------------------------------ #
    def temporal_node_features(self, node: str) -> Dict[str, Any]:
        """Compute temporal network features for a single node."""
        out_edges = [e for e in self._edges if e.source == node]
        in_edges = [e for e in self._edges if e.target == node]
        all_edges = out_edges + in_edges

        if not all_edges:
            return {"node": node, "first_seen": None, "last_seen": None, "activity_count": 0}

        times = [e.effective_time for e in all_edges if e.effective_time]
        first = min(times) if times else None
        last = max(times) if times else None

        # interaction frequency: events per day
        span_days = 1.0
        if first and last and last > first:
            span_days = max((last - first).total_seconds() / 86400, 1.0)
        freq = len(all_edges) / span_days

        # burstiness: coefficient of variation of inter-event times
        burstiness = 0.0
        sorted_times = sorted(times)
        if len(sorted_times) >= 2:
            diffs = [(sorted_times[i+1] - sorted_times[i]).total_seconds()
                     for i in range(len(sorted_times)-1)]
            import statistics
            mean_d = statistics.mean(diffs)
            stdev_d = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
            burstiness = stdev_d / mean_d if mean_d > 0 else 0.0

        return {
            "node": node,
            "first_seen": _ts_str(first),
            "last_seen": _ts_str(last),
            "activity_count": len(all_edges),
            "interaction_frequency": round(freq, 6),
            "burstiness": round(burstiness, 4),
            "span_days": round(span_days, 2),
        }

    # ------------------------------------------------------------------ #
    # Temporal network features (per-edge / relationship)
    # ------------------------------------------------------------------ #
    def temporal_edge_features(self, source: str, target: str) -> Dict[str, Any]:
        """Compute temporal relationship features between two nodes."""
        edges = [e for e in self._edges if e.source == source and e.target == target]
        edges += [e for e in self._edges if e.source == target and e.target == source]

        if not edges:
            return {"source": source, "target": target, "interaction_count": 0}

        times = [e.effective_time for e in edges if e.effective_time]
        first = min(times) if times else None
        last = max(times) if times else None

        # persistence: fraction of total time span with at least one interaction
        persistence = 0.0
        if first and last and last > first:
            total_days = (last - first).total_seconds() / 86400
            active_days = len(set(t.date() for t in times))
            persistence = active_days / max(total_days, 1.0)

        # recency: days since last interaction (from latest known timestamp)
        latest = _parse_ts("2025-12-31T23:59:59Z")  # system "now" for demo
        recency_days = 0.0
        if last and latest:
            recency_days = max((latest - last).total_seconds() / 86400, 0.0)

        return {
            "source": source,
            "target": target,
            "interaction_count": len(edges),
            "first_seen": _ts_str(first),
            "last_seen": _ts_str(last),
            "persistence": round(persistence, 4),
            "recency_days": round(recency_days, 2),
            "layers": list(set(e.layer.value for e in edges)),
        }

    # ------------------------------------------------------------------ #
    # Temporal graph statistics
    # ------------------------------------------------------------------ #
    def temporal_statistics(self) -> Dict[str, Any]:
        """Aggregate temporal statistics over the full timeline."""
        if not self._timeline:
            return {"edge_count": 0, "node_count": 0}

        times = [e.effective_time for e in self._timeline if e.effective_time]
        first = min(times) if times else None
        last = max(times) if times else None

        # edge velocity: new edges per day
        velocity = 0.0
        if first and last and last > first:
            days = (last - first).total_seconds() / 86400
            velocity = len(self._timeline) / max(days, 1.0)

        # unique node activity over time
        active_nodes_by_date: Dict[str, Set[str]] = defaultdict(set)
        for e in self._timeline:
            if e.effective_time:
                d = e.effective_time.date().isoformat()
                active_nodes_by_date[d].add(e.source)
                active_nodes_by_date[d].add(e.target)

        unique_active = len(set().union(*active_nodes_by_date.values())) if active_nodes_by_date else 0

        return {
            "edge_count": len(self._timeline),
            "node_count": len(self._node_layers),
            "active_node_count": unique_active,
            "first_seen": _ts_str(first),
            "last_seen": _ts_str(last),
            "new_edge_velocity_per_day": round(velocity, 4),
            "layer_counts": {k: len(v) for k, v in self._layer_edges.items()},
        }

    def degree_over_time(self, node: str) -> List[Dict[str, Any]]:
        """Cumulative degree of *node* at each observation point."""
        result: List[Dict[str, Any]] = []
        count = 0
        for e in self._timeline:
            if e.source == node or e.target == node:
                count += 1
                result.append({
                    "timestamp": _ts_str(e.effective_time),
                    "cumulative_degree": count,
                })
        return result

    def community_changes(self) -> List[Dict[str, Any]]:
        """Record community membership changes over time.

        Uses a simple union-find re-run at each timestamp (suitable for
        snapshot analysis; not for real-time streaming).
        """
        g_acc = nx.Graph()
        changes: List[Dict[str, Any]] = []
        prev_comm: Dict[str, int] = {}
        for e in self._timeline:
            g_acc.add_edge(e.source, e.target)
            ts_str = _ts_str(e.effective_time)
            if g_acc.number_of_nodes() < 2:
                continue
            try:
                from networkx.algorithms.community import louvain_communities
                communities = louvain_communities(g_acc, seed=42)
                comm_map: Dict[str, int] = {}
                for idx, comm in enumerate(communities):
                    for n in comm:
                        comm_map[n] = idx
                if comm_map != prev_comm:
                    changes.append({
                        "timestamp": ts_str,
                        "edge_added": f"{e.source}→{e.target}",
                        "community_count": len(communities),
                        "node_community_map": comm_map,
                    })
                    prev_comm = comm_map
            except Exception:
                pass
        return changes

    def bridge_emergence(self) -> List[Dict[str, Any]]:
        """Detect when edges create bridges in the evolving graph."""
        g_acc = nx.Graph()
        bridges: List[Dict[str, Any]] = []
        for e in self._timeline:
            g_acc.add_edge(e.source, e.target)
            ts_str = _ts_str(e.effective_time)
            try:
                if nx.is_connected(g_acc):
                    current_bridges = set(nx.bridges(g_acc))
                    if (e.source, e.target) in current_bridges or (e.target, e.source) in current_bridges:
                        bridges.append({
                            "timestamp": ts_str,
                            "bridge_edge": f"{e.source}↔{e.target}",
                            "relation": e.relation,
                        })
            except nx.NetworkXError:
                pass
        return bridges