"""
graph/ml/feature_extraction.py
------------------------------
Per-node feature extraction for ghost-coordinator classification.

Turns a NetworkX ``MultiDiGraph`` into a flat, order-stable feature matrix
where each row is one node and columns are structural / temporal / bridging
signals the existing heuristic already computes.  The heuristic score itself
is included as one input feature (it encodes domain knowledge) — it is just
no longer the *only* signal (MASTER DIRECTIVE Task 1 §3).

Feature names are stable and exposed via ``FEATURE_COLUMNS`` so the trained
model artifact and caller stay in sync.
"""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Mapping, Optional, Sequence, Tuple

import networkx as nx
import numpy as np

# The features extracted in :mod:`src.graph.ghost_nodes` are reused here, but
# we import lazily to avoid pulling the whole ghost module at import time.
from src.graph.ghost_nodes import (
    GhostConfig,
    detect_communities,
    detect_structural_holes,
    _community_membership_map,
    _extract_anchor_evidence,
    _community_shared_surfaces,
    _taxonomy,
)
from src.graph.graph_embeddings import undirected_weighted_projection

FEATURE_COLUMNS: List[str] = [
    # degree / size
    "degree",
    "in_degree",
    "out_degree",
    "neighbor_count",
    # structural holes
    "structural_hole_score",
    "constraint",
    "effective_size",
    "betweenness",
    # community / bridging
    "is_broker_in_any_community",
    "num_communities_connected",
    "community_size_rank",
    "bridges_communities",
    # shared anchors
    "shared_anchor_count",
    "max_shared_anchor_overlap",
    "money_anchor_overlap",
    "location_anchor_overlap",
    "supplier_anchor_overlap",
    # temporal
    "temporal_fanout",
    "temporal_affinity",
    # heuristic (kept as input feature)
    "heuristic_score",
]

N_FEATURES = len(FEATURE_COLUMNS)


def _safe(fn, default: float = 0.0) -> float:
    try:
        val = fn()
        if val is None or (isinstance(val, float) and not np.isfinite(val)):
            return default
        return float(val)
    except Exception:
        return default


def extract_features(
    graph: nx.MultiDiGraph,
    node: Hashable,
    *,
    node_data: Optional[Mapping[str, Any]] = None,
    hole_scores: Optional[Mapping[Hashable, float]] = None,
    constraint: Optional[Mapping[Hashable, float]] = None,
    effective_size: Optional[Mapping[Hashable, float]] = None,
    betweenness: Optional[Mapping[Hashable, float]] = None,
    communities: Optional[Sequence[Set[Hashable]]] = None,
    community_of: Optional[Mapping[Hashable, int]] = None,
    anchors_by_cat: Optional[Mapping[str, Mapping[int, Set[Hashable]]]] = None,
    tokens_by_cat: Optional[Mapping[str, Mapping[int, Set[str]]]] = None,
    rarity: Optional[Mapping[str, Mapping[Hashable, float]]] = None,
    config: Optional[GhostConfig] = None,
) -> Dict[str, float]:
    """Extract a flat feature dict for a single node.

    Any computed metric that is unavailable just becomes 0.0 — the feature
    vector stays order-stable and shape-stable.
    """
    config = config or GhostConfig()
    data = dict(node_data) if node_data else dict(graph.nodes.get(node, {}))

    # ---- degree features ----------------------------------------------------
    in_deg = _safe(lambda: graph.in_degree(node))
    out_deg = _safe(lambda: graph.out_degree(node))
    deg = _safe(lambda: graph.degree(node))
    nbrs = _safe(lambda: len(set(graph.successors(node)) | set(graph.predecessors(node))))

    # ---- structural holes ----------------------------------------------------
    hole = hole_scores.get(node, 0.0) if hole_scores else 0.0
    cons = constraint.get(node, 0.0) if constraint else 0.0
    eff = effective_size.get(node, 0.0) if effective_size else 0.0
    bet = betweenness.get(node, 0.0) if betweenness else 0.0
    # Disconnected nodes yield NaN for constraint/effective-size; sanitize.
    if not np.isfinite(hole):
        hole = 0.0
    if not np.isfinite(cons):
        cons = 0.0
    if not np.isfinite(eff):
        eff = 0.0
    if not np.isfinite(bet):
        bet = 0.0

    # ---- community / bridging -------------------------------------------------
    is_broker = 0.0
    num_comms = 0.0
    comm_size_rank = 0.0
    bridges = 0.0
    if communities and community_of:
        my_comm = community_of.get(node)
        if my_comm is not None:
            comm_size = len(communities[my_comm])
            # node bridges if it has a neighbor in a different community
            neighbors = set(graph.successors(node)) | set(graph.predecessors(node))
            other_comms = {
                community_of.get(nbr) for nbr in neighbors
                if community_of.get(nbr) is not None and community_of.get(nbr) != my_comm
            }
            bridges = float(len(other_comms) > 0)
            num_comms = float(len(other_comms) + 1)
            # rank: 1.0 for the largest community, scaled by fraction
            comm_size_rank = comm_size / max(1, max(len(c) for c in communities))
        # approximate broker: node is in top-broker pool of any community
        for ci, comm in enumerate(communities):
            if node in comm:
                top = sorted(comm, key=lambda n: hole_scores.get(n, 0.0), reverse=True)[:5]
                if node in top:
                    is_broker = 1.0
                    break

    # ---- shared anchors ---------------------------------------------------------
    shared_anchor_count = 0.0
    max_overlap = 0.0
    money_overlap = 0.0
    loc_overlap = 0.0
    supp_overlap = 0.0
    if community_of and anchors_by_cat and communities:
        my_comm = community_of.get(node)
        if my_comm is not None:
            # anchors shared between my community and ANY other community
            for category, per_comm in anchors_by_cat.items():
                my_anchors = per_comm.get(my_comm, set())
                for ci, other_anchors in per_comm.items():
                    if ci == my_comm:
                        continue
                    shared = my_anchors & other_anchors
                    if shared:
                        shared_anchor_count += float(len(shared))
                        union = my_anchors | other_anchors
                        if union:
                            ov = len(shared) / len(union)
                            max_overlap = max(max_overlap, ov)
                            if category in config.category_weights:
                                if "money" in category.lower():
                                    money_overlap = max(money_overlap, ov)
                                elif "location" in category.lower():
                                    loc_overlap = max(loc_overlap, ov)
                                elif "supplier" in category.lower():
                                    supp_overlap = max(supp_overlap, ov)

    # ---- temporal ---------------------------------------------------------------
    temporal_fanout = 0.0
    ts_count = 0
    seen_ts: List[str] = []
    try:
        edge_iter = graph.edges(node, data=True)
    except Exception:
        edge_iter = []
    for _u, _v, attrs in edge_iter:
        ts = attrs.get("timestamp") or attrs.get("date")
        if ts:
            ts_count += 1
            seen_ts.append(str(ts)[:10])
    temporal_fanout = float(len(set(seen_ts))) / max(1, ts_count) if ts_count else 0.0
    temporal_affinity = min(1.0, ts_count / 20.0)  # normalized call/event volume signal

    # ---- heuristic (domain-knowledge prior) --------------------------------------
    heuristic_score = hole  # best single scalar we have without the full pair scan

    return {
        "degree": deg,
        "in_degree": in_deg,
        "out_degree": out_deg,
        "neighbor_count": nbrs,
        "structural_hole_score": hole,
        "constraint": cons,
        "effective_size": eff,
        "betweenness": bet,
        "is_broker_in_any_community": is_broker,
        "num_communities_connected": num_comms,
        "community_size_rank": comm_size_rank,
        "bridges_communities": bridges,
        "shared_anchor_count": shared_anchor_count,
        "max_shared_anchor_overlap": max_overlap,
        "money_anchor_overlap": money_overlap,
        "location_anchor_overlap": loc_overlap,
        "supplier_anchor_overlap": supp_overlap,
        "temporal_fanout": temporal_fanout,
        "temporal_affinity": temporal_affinity,
        "heuristic_score": heuristic_score,
    }


def feature_vector(features: Mapping[str, float]) -> np.ndarray:
    """Convert a feature dict into an order-stable numpy vector."""
    return np.array([float(features.get(col, 0.0)) for col in FEATURE_COLUMNS], dtype=np.float64)


def _fast_structural_holes(
    graph: nx.MultiDiGraph,
    projection: nx.Graph,
) -> Tuple[List[Dict[str, Any]], Dict[Hashable, float], Dict[Hashable, float], Dict[Hashable, float]]:
    """Fast vectorized Burt-constraint approximation for training only.

    Computes constraint, effective size, and betweenness over the projection
    using ego-graph neighborhood weights instead of the O(n^2) exact networkx
    algorithms.  Output shape matches ``detect_structural_holes`` so the
    feature extractor stays drop-in compatible.
    """
    nodes = list(projection.nodes())
    index = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    adj = {node: set(projection.neighbors(node)) for node in nodes}
    constraint: Dict[Hashable, float] = {}
    effective: Dict[Hashable, float] = {}

    for u in nodes:
        nbrs = adj[u]
        if not nbrs:
            constraint[u] = 0.0
            effective[u] = 0.0
            continue
        deg_u = max(len(nbrs), 1)
        p_ij = 1.0 / deg_u
        c = 0.0
        eff = float(len(nbrs))
        for j in nbrs:
            nbrs_j = adj[j]
            overlap = len(nbrs & nbrs_j)
            p_ijj = (1.0 / max(len(nbrs_j), 1)) if nbrs_j else 0.0
            local = p_ij + p_ijj * overlap
            c += local * local
            # effective size: 1 - overlap/deg_j summed over j
            eff -= overlap / max(len(nbrs_j), 1) if nbrs_j else 0.0
        constraint[u] = c
        effective[u] = eff

    # fast betweenness approximation via node-neighbor pairs (Brandes-lite)
    betweenness: Dict[Hashable, float] = {}
    for u in nodes:
        betweenness[u] = 0.0
    for u in nodes:
        # BFS from u, count shortest-path dependencies cheaply
        dist: Dict[Hashable, int] = {}
        sigma: Dict[Hashable, float] = {}
        stack: List[Hashable] = []
        dist[u] = 0
        sigma[u] = 1.0
        queue = [u]
        while queue:
            v = queue.pop(0)
            stack.append(v)
            for w in adj[v]:
                if w not in dist:
                    dist[w] = dist[v] + 1
                    sigma[w] = 0.0
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
        delta: Dict[Hashable, float] = {v: 0.0 for v in dist}
        while stack:
            w = stack.pop()
            for v in adj[w]:
                if dist.get(v) == dist.get(w, -1) - 1:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != u:
                betweenness[w] += delta[w]
    if n > 1:
        scale = (n - 1) * (n - 2)
        betweenness = {u: (betweenness[u] / scale) if scale > 0 else 0.0 for u in nodes}

    inv_constraint = _normalise_01_fast(constraint)
    eff_norm = _normalise_01_fast(effective)
    bet_norm = _normalise_01_fast(betweenness)

    results: List[Dict[str, Any]] = []
    for node in nodes:
        score = (
            0.50 * inv_constraint[node]
            + 0.30 * eff_norm.get(node, 0.0)
            + 0.20 * bet_norm.get(node, 0.0)
        )
        results.append({
            "guid": node,
            "name": str(node),
            "entity_type": graph.nodes[node].get("entity_type", "unknown"),
            "constraint": float(constraint.get(node, 0.0)),
            "effective_size": float(effective.get(node, 0.0)),
            "betweenness_centrality": float(bet_norm.get(node, 0.0)),
            "structural_hole_score": round(float(score), 6),
        })
    return results, constraint, effective, betweenness


def _normalise_01_fast(values: Mapping[Hashable, float]) -> Dict[Hashable, float]:
    vals = [float(v) for v in values.values() if np.isfinite(v)]
    if not vals:
        return {k: 0.0 for k in values}
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    out: Dict[Hashable, float] = {}
    for k, v in values.items():
        v = float(v) if np.isfinite(v) else lo
        out[k] = (v - lo) / span
    return out


def extract_features_for_graph(
    graph: nx.MultiDiGraph,
    config: Optional[GhostConfig] = None,
    *,
    with_communities: bool = True,
    fast: bool = False,
) -> Tuple[List[Hashable], np.ndarray, Dict[str, Any]]:
    """Extract a dense feature matrix for all person nodes in a graph.

    Returns ``(nodes, X, context)`` where ``context`` carries the precomputed
    structural maps so a caller can reuse them (avoids recomputing Louvain /
    structural holes multiple times).

    With ``fast=True`` the structural-hole features use a lightweight
    vectorized Burt-constraint approximation — suitable for the training
    bundle where we iterate over many graphs.  Production inference keeps
    the authoritative ``detect_structural_holes`` path (``fast=False``).
    """
    config = config or GhostConfig()
    full_projection = undirected_weighted_projection(graph)
    projection = full_projection.subgraph([
        n for n, data in graph.nodes(data=True)
        if str(data.get("entity_type", "")).upper() not in {"LOCATION", "ACCOUNT"}
    ]).copy()

    taxonomy = _taxonomy(config)
    if fast:
        holes, constraint, effective, betweenness = _fast_structural_holes(graph, projection)
    else:
        holes = detect_structural_holes(graph, projection)
        constraint = {n: d.get("constraint", 0.0) for n, d in graph.nodes(data=True)}
        effective = {n: d.get("effective_size", 0.0) for n, d in graph.nodes(data=True)}
        betweenness = {n: d.get("betweenness_centrality", 0.0) for n, d in graph.nodes(data=True)}
        for hole in holes:
            constraint[hole["guid"]] = hole["constraint"]
            effective[hole["guid"]] = hole["effective_size"]
            betweenness[hole["guid"]] = hole["betweenness_centrality"]
    hole_scores = {entry["guid"]: entry["structural_hole_score"] for entry in holes}

    communities = None
    community_of = None
    anchors_by_cat = None
    tokens_by_cat = None
    rarity = None
    if with_communities:
        communities = detect_communities(projection, seed=config.seed)
        community_of = _community_membership_map(graph, communities)
        evidence = _extract_anchor_evidence(graph, communities, community_of, taxonomy, config)
        anchors_by_cat, tokens_by_cat, rarity = _community_shared_surfaces(
            evidence, communities, config
        )

    nodes: List[Hashable] = []
    rows: List[float] = []
    for node, data in graph.nodes(data=True):
        if str(data.get("entity_type", "")).upper() in {"LOCATION", "ACCOUNT"}:
            continue
        feats = extract_features(
            graph, node, node_data=data, hole_scores=hole_scores,
            constraint=constraint, effective_size=effective, betweenness=betweenness,
            communities=communities, community_of=community_of,
            anchors_by_cat=anchors_by_cat, tokens_by_cat=tokens_by_cat, rarity=rarity,
            config=config,
        )
        nodes.append(node)
        rows.append(list(feature_vector(feats)))

    return nodes, np.array(rows, dtype=np.float64), {
        "hole_scores": hole_scores,
        "constraint": constraint,
        "effective_size": effective,
        "betweenness": betweenness,
        "communities": communities,
        "community_of": community_of,
        "anchors_by_cat": anchors_by_cat,
        "tokens_by_cat": tokens_by_cat,
        "rarity": rarity,
    }