"""
ml/link_baselines.py
--------------------
Level 1 — classical link-prediction baselines (Phase 4).

Implements the standard heuristic scores over an undirected projection:

* Common Neighbors
* Jaccard
* Adamic-Adar
* Resource Allocation
* Preferential Attachment
* Katz
* Personalized PageRank

All functions are deterministic and dependency-light (networkx + numpy).
They operate on the *observed* graph only — callers must handle temporal
snapshots if leakage must be prevented.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Hashable, Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx

from src.graph.graph_embeddings import undirected_weighted_projection

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Low-level scores (pure functions over a networkx.Graph)
# --------------------------------------------------------------------------- #

def common_neighbors(graph: nx.Graph, u: Hashable, v: Hashable) -> float:
    if u not in graph or v not in graph:
        return 0.0
    return float(len(set(graph.neighbors(u)) & set(graph.neighbors(v))))


def jaccard(graph: nx.Graph, u: Hashable, v: Hashable) -> float:
    if u not in graph or v not in graph:
        return 0.0
    nu, nv = set(graph.neighbors(u)), set(graph.neighbors(v))
    union = nu | nv
    return len(nu & nv) / len(union) if union else 0.0


def adamic_adar(graph: nx.Graph, u: Hashable, v: Hashable) -> float:
    if u not in graph or v not in graph:
        return 0.0
    common = set(graph.neighbors(u)) & set(graph.neighbors(v))
    return sum(1.0 / math.log(graph.degree(n)) for n in common if graph.degree(n) > 1)


def resource_allocation(graph: nx.Graph, u: Hashable, v: Hashable) -> float:
    if u not in graph or v not in graph:
        return 0.0
    common = set(graph.neighbors(u)) & set(graph.neighbors(v))
    return sum(1.0 / max(graph.degree(n), 1e-9) for n in common)


def preferential_attachment(graph: nx.Graph, u: Hashable, v: Hashable) -> float:
    if u not in graph or v not in graph:
        return 0.0
    return float(graph.degree(u) * graph.degree(v))


def katz(graph: nx.Graph, u: Hashable, v: Hashable,
         beta: float = 0.005, max_iter: int = 20) -> float:
    """Katz score via the truncated Neumann-series approximation."""
    if u not in graph or v not in graph:
        return 0.0
    # beta^1 * A + beta^2 * A^2 + ...
    import numpy as np
    nodes = list(graph.nodes())
    n = len(nodes)
    if n == 0:
        return 0.0
    idx = {node: i for i, node in enumerate(nodes)}
    A = nx.to_numpy_array(graph, nodelist=nodes, weight="weight")
    score = 0.0
    power = A.copy()
    for k in range(1, max_iter + 1):
        score += beta ** k * power[idx[u], idx[v]]
        power = power @ A
    return float(score)


def personalized_pagerank(graph: nx.Graph, u: Hashable, v: Hashable,
                          alpha: float = 0.85) -> float:
    """Personalized PageRank: random walk restarting at *u*, score of *v*."""
    if u not in graph or v not in graph:
        return 0.0
    try:
        ppr = nx.pagerank(graph, alpha=alpha, personalization={u: 1.0},
                          max_iter=200, tol=1e-5)
        return float(ppr.get(v, 0.0))
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# Public scorable interface
# --------------------------------------------------------------------------- #

BASELINE_NAMES = [
    "common_neighbors",
    "jaccard",
    "adamic_adar",
    "resource_allocation",
    "preferential_attachment",
    "katz",
    "personalized_pagerank",
]

_BASELINE_FUNCS = {
    "common_neighbors": common_neighbors,
    "jaccard": jaccard,
    "adamic_adar": adamic_adar,
    "resource_allocation": resource_allocation,
    "preferential_attachment": preferential_attachment,
    "katz": katz,
    "personalized_pagerank": personalized_pagerank,
}


def baseline_scores(graph: nx.Graph, u: Hashable, v: Hashable) -> Dict[str, float]:
    """All baseline scores for a (u, v) pair on an undirected graph."""
    return {name: round(_BASELINE_FUNCS[name](graph, u, v), 6) for name in BASELINE_NAMES}


def rank_candidates(
    graph: nx.Graph,
    candidates: Sequence[Tuple[Hashable, Hashable]],
    metric: str = "adamic_adar",
) -> List[Tuple[Hashable, Hashable, float]]:
    """Rank candidate pairs by a given metric (descending)."""
    if metric not in _BASELINE_FUNCS:
        raise ValueError(f"Unknown metric: {metric}; choose from {BASELINE_NAMES}")
    scored = [
        (u, v, _BASELINE_FUNCS[metric](graph, u, v)) for u, v in candidates
    ]
    return sorted(scored, key=lambda x: -x[2])


def normalize_scores(scores: List[float]) -> List[float]:
    """Min-max normalize a list of scores into [0, 1]."""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi <= lo:
        return [0.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


class BaselineLinkPredictor:
    """Classical link-prediction model over an undirected projection.

    Supports a single metric or a small ensemble with equal weights.
    """

    def __init__(self, metric: str = "adamic_adar",
                 ensemble: Optional[Sequence[str]] = None) -> None:
        self.metric = metric
        self.ensemble = list(ensemble) if ensemble else ([metric] if metric else [])

    def fit(self, graph: nx.Graph) -> "BaselineLinkPredictor":
        self.graph = undirected_weighted_projection(graph)
        return self

    def predict(self, u: Hashable, v: Hashable) -> Dict[str, float]:
        """Return per-metric + ensemble probability (min-max calibrated to 0..1)."""
        if not hasattr(self, "graph"):
            raise RuntimeError("call fit() first")
        raw = baseline_scores(self.graph, u, v)
        probs: Dict[str, float] = {}
        for name in self.ensemble:
            # multiplicative scaling is meaningless across metrics; use
            # a bounded sigmoid to map raw scores into [0,1]
            score = raw.get(name, 0.0)
            probs[name] = 1.0 / (1.0 + math.exp(-min(score, 20.0)))
        probs["ensemble"] = sum(probs.values()) / len(probs) if probs else 0.0
        probs["raw"] = raw
        return probs