"""
graph/temporal_features.py
--------------------------
Temporal feature engineering for ML (Phase 2, requirement 9).

**No-leakage contract:**

Training features for event *t* must ONLY use information observed before
*t*.  In practice:

* edge features (common neighbours, Jaccard, Adamic-Adar, ...) are computed
  on the graph snapshot ``as_of(t)`` — never the full graph;
* temporal window features (interaction frequency in the last *W* days)
  only count events with ``effective_time < t``;
* centrality / community features are computed on the snapshot, so no
  future edges influence them.

This module exposes:

* :func:`snapshot_features` — feature vector for a candidate edge at time t;
* :class:`TemporalFeatureEngine` — batch feature generation for candidate
  edge sets with an explicit evaluation time;
* :func:`build_temporal_candidates` — candidate generation from a snapshot.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import networkx as nx

from src.graph.temporal_graph import TemporalMultilayerGraph, _parse_ts

logger = logging.getLogger(__name__)

#: All feature names produced by :func:`snapshot_features` (order matters).
FEATURE_NAMES = [
    # --- structural (on snapshot) ---
    "common_neighbors",
    "jaccard",
    "adamic_adar",
    "resource_allocation",
    "preferential_attachment",
    "shortest_path_length",
    "source_degree",
    "target_degree",
    "source_betweenness",
    "target_betweenness",
    "source_pagerank",
    "target_pagerank",
    "source_community",
    "target_community",
    "same_community",
    # --- temporal (window before t) ---
    "interaction_frequency",
    "source_activity",
    "target_activity",
    "recency_days",
    "temporal_overlap",
    "temporal_burstiness",
    # --- evidence ---
    "shared_evidence_count",
    # --- entity resolution ---
    "name_similarity",
]


def _safe_log1p(x: float) -> float:
    return math.log1p(max(0.0, x))


@dataclass
class TemporalFeatureEngine:
    """Batch temporal feature generation with an evaluation timestamp."""

    tm_graph: TemporalMultilayerGraph
    snapshot: nx.MultiDiGraph
    as_of: str
    window_days: int = 30
    name_lookup: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------ #
    @classmethod
    def from_graph(cls, graph: nx.MultiDiGraph,
                   as_of: str, window_days: int = 30) -> "TemporalFeatureEngine":
        tm = TemporalMultilayerGraph(graph)
        snap = tm.graph_as_of(as_of)
        # build name → guid lookup from canonical_name attributes
        name_lookup: Dict[str, str] = {}
        for node, data in graph.nodes(data=True):
            cn = data.get("canonical_name")
            if cn:
                name_lookup[str(cn)] = str(node)
        return cls(tm_graph=tm, snapshot=snap, as_of=as_of,
                   window_days=window_days, name_lookup=name_lookup)

    # ------------------------------------------------------------------ #
    def _snapshot_metrics(self) -> Dict[str, Any]:
        """Compute snapshot centrality/community once for reuse."""
        g = self.snapshot
        out: Dict[str, Any] = {}
        try:
            out["betweenness"] = nx.betweenness_centrality(g, k=min(256, g.number_of_nodes()),
                                                           seed=42, normalized=True)
        except Exception:
            out["betweenness"] = {}
        try:
            out["pagerank"] = nx.pagerank(g, alpha=0.85, max_iter=200, tol=1e-4)
        except Exception:
            out["pagerank"] = {}
        try:
            from networkx.algorithms.community import louvain_communities
            comms = louvain_communities(g, seed=42)
            comm_map: Dict[Any, int] = {}
            for i, c in enumerate(comms):
                for n in c:
                    comm_map[n] = i
            out["community"] = comm_map
        except Exception:
            out["community"] = {}
        return out

    def _window_edge_count(self, source: str, target: str,
                           before: datetime) -> float:
        """Count interactions between source/target in the window before t."""
        window_start = before - timedelta(days=self.window_days)
        count = 0
        for e in self.tm_graph._timeline:
            if e.effective_time is None:
                continue
            if not (window_start <= e.effective_time < before):
                continue
            if {e.source, e.target} == {source, target}:
                count += 1
        return float(count)

    # ------------------------------------------------------------------ #
    def features_for(self, source: str, target: str) -> Dict[str, float]:
        """Compute the no-leakage feature vector for (source, target)."""
        snap = self.snapshot
        metrics = self._snapshot_metrics()
        before = _parse_ts(self.as_of) or datetime.now(timezone.utc)

        # --- structural ---
        common = set(snap.neighbors(source)) & set(snap.neighbors(target)) \
            if source in snap and target in snap else set()
        cn = float(len(common))
        union = (set(snap.neighbors(source)) | set(snap.neighbors(target))) \
            if source in snap and target in snap else set()
        jaccard = cn / len(union) if union else 0.0

        adamic_adar = 0.0
        for n in common:
            deg = snap.degree(n)
            adamic_adar += 1.0 / max(math.log(deg), 1e-9) if deg > 1 else 0.0

        ra = 0.0
        for n in common:
            ra += 1.0 / max(snap.degree(n), 1e-9)

        pa = float(snap.degree(source) * snap.degree(target)) \
            if source in snap and target in snap else 0.0

        spl = nx.shortest_path_length(snap, source, target) \
            if source in snap and target in snap and nx.has_path(snap, source, target) else -1.0

        src_deg = float(snap.degree(source)) if source in snap else 0.0
        tgt_deg = float(snap.degree(target)) if target in snap else 0.0

        src_btw = metrics["betweenness"].get(source, 0.0)
        tgt_btw = metrics["betweenness"].get(target, 0.0)
        src_pr = metrics["pagerank"].get(source, 0.0)
        tgt_pr = metrics["pagerank"].get(target, 0.0)

        src_comm = metrics["community"].get(source, -1)
        tgt_comm = metrics["community"].get(target, -1)
        same_comm = 1.0 if (src_comm >= 0 and src_comm == tgt_comm) else 0.0

        # --- temporal (window strictly before t — no future edges) ---
        win_count = self._window_edge_count(source, target, before)
        freq = win_count / max(self.window_days, 1)
        src_act = len([e for e in self.tm_graph._timeline
                       if e.effective_time and e.effective_time < before and e.source == source])
        tgt_act = len([e for e in self.tm_graph._timeline
                       if e.effective_time and e.effective_time < before and e.target == target])
        recency = 0.0
        past_edges = [e for e in self.tm_graph._timeline
                      if e.effective_time and e.effective_time < before
                      and {e.source, e.target} == {source, target}]
        if past_edges:
            last_ts = max(e.effective_time for e in past_edges)
            if last_ts:
                recency = max((before - last_ts).total_seconds() / 86400, 0.0)
        burstiness = 0.0
        node_feat = self.tm_graph.temporal_node_features(source)
        if node_feat.get("first_seen") and node_feat.get("first_seen") <= self.as_of:
            burstiness = node_feat.get("burstiness", 0.0)
        temporal_overlap = 0.0
        # fraction of the window where both nodes were active
        if before:
            ws = before - timedelta(days=self.window_days)
            src_dates = {e.effective_time.date() for e in self.tm_graph._timeline
                         if e.effective_time and ws <= e.effective_time < before
                         and e.source == source}
            tgt_dates = {e.effective_time.date() for e in self.tm_graph._timeline
                         if e.effective_time and ws <= e.effective_time < before
                         and e.target == target}
            if src_dates and tgt_dates:
                temporal_overlap = len(src_dates & tgt_dates) / max(len(src_dates | tgt_dates), 1)

        # --- evidence ---
        shared_evidence = 0.0
        src_ev = set(self.tm_graph.graph.nodes[source].get("attributes", {}).get("evidence_ids", [])) \
            if source in self.tm_graph.graph else set()
        tgt_ev = set(self.tm_graph.graph.nodes[target].get("attributes", {}).get("evidence_ids", [])) \
            if target in self.tm_graph.graph else set()
        shared_evidence = float(len(src_ev & tgt_ev))

        # --- entity resolution ---
        name_sim = 0.0
        if self.name_lookup:
            sn = self.tm_graph.graph.nodes[source].get("canonical_name", "") \
                if source in self.tm_graph.graph else ""
            tn = self.tm_graph.graph.nodes[target].get("canonical_name", "") \
                if target in self.tm_graph.graph else ""
            if sn and tn:
                from difflib import SequenceMatcher
                name_sim = SequenceMatcher(None, sn.lower(), tn.lower()).ratio()

        return {
            "common_neighbors": cn,
            "jaccard": round(jaccard, 4),
            "adamic_adar": round(adamic_adar, 4),
            "resource_allocation": round(ra, 4),
            "preferential_attachment": round(pa, 4),
            "shortest_path_length": spl,
            "source_degree": src_deg,
            "target_degree": tgt_deg,
            "source_betweenness": round(src_btw, 4),
            "target_betweenness": round(tgt_btw, 4),
            "source_pagerank": round(src_pr, 4),
            "target_pagerank": round(tgt_pr, 4),
            "source_community": float(src_comm),
            "target_community": float(tgt_comm),
            "same_community": same_comm,
            "interaction_frequency": round(freq, 4),
            "source_activity": float(src_act),
            "target_activity": float(tgt_act),
            "recency_days": round(recency, 2),
            "temporal_overlap": round(temporal_overlap, 4),
            "temporal_burstiness": round(burstiness, 4),
            "shared_evidence_count": shared_evidence,
            "name_similarity": round(name_sim, 4),
        }

    def feature_vector(self, source: str, target: str) -> List[float]:
        """Ordered feature vector matching :data:`FEATURE_NAMES`."""
        feats = self.features_for(source, target)
        return [float(feats[name]) for name in FEATURE_NAMES]

    # ------------------------------------------------------------------ #
    def build_candidates(self, top_n: int = 500,
                         exclude_observed: bool = True) -> List[Tuple[str, str]]:
        """Generate candidate (source, target) pairs from the snapshot.

        Candidates are non-observed node pairs, ranked by resource
        allocation + jaccard (classical heuristics) so we don't brute-force
        the full O(n^2) space.
        """
        snap = self.snapshot
        nodes = list(snap.nodes())
        observed = set()
        if exclude_observed:
            for u, v in snap.edges():
                observed.add(tuple(sorted((u, v))))

        scored: List[Tuple[float, str, str]] = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                u, v = nodes[i], nodes[j]
                if (u, v) in observed or (v, u) in observed:
                    continue
                common = set(snap.neighbors(u)) & set(snap.neighbors(v))
                if not common:
                    continue
                ra = sum(1.0 / max(snap.degree(n), 1e-9) for n in common)
                jac = len(common) / max(len(set(snap.neighbors(u)) | set(snap.neighbors(v))), 1)
                scored.append((ra + jac, u, v))
        scored.sort(reverse=True)
        return [(u, v) for _, u, v in scored[:top_n]]


def build_temporal_candidates(graph: nx.MultiDiGraph, as_of: str,
                              top_n: int = 500) -> List[Tuple[str, str]]:
    """Convenience: build a candidate list from a graph at a snapshot time."""
    engine = TemporalFeatureEngine.from_graph(graph, as_of)
    return engine.build_candidates(top_n=top_n)