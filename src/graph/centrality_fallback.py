"""
graph/centrality_fallback.py
----------------------------
Graceful fallbacks for centrality measures when optional scientific
dependencies (scipy) are missing.

``networkx.pagerank`` and ``networkx.betweenness_centrality`` import scipy
under some numpy versions.  This module provides a power-method PageRank
that works with numpy only, so the CORE mode never hard-fails.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Hashable, Optional

import networkx as nx

logger = logging.getLogger(__name__)


def safe_pagerank(graph: nx.Graph, alpha: float = 0.85,
                  max_iter: int = 200, tol: float = 1e-6,
                  personalization: Optional[Dict[Hashable, float]] = None) -> Dict[Hashable, float]:
    """PageRank with a numpy-power-method fallback when scipy is missing."""
    try:
        return nx.pagerank(graph, alpha=alpha, max_iter=max_iter, tol=tol,
                           personalization=personalization)
    except ModuleNotFoundError:
        return _power_pagerank(graph, alpha=alpha, max_iter=max_iter,
                               tol=tol, personalization=personalization)


def _power_pagerank(graph: nx.Graph, alpha: float, max_iter: int, tol: float,
                    personalization: Optional[Dict[Hashable, float]]) -> Dict[Hashable, float]:
    """Simple power-method PageRank on numpy arrays (no scipy)."""
    import numpy as np
    g = graph.to_undirected() if graph.is_directed() else graph
    nodes = list(g.nodes())
    n = len(nodes)
    if n == 0:
        return {}
    idx = {node: i for i, node in enumerate(nodes)}

    # column-stochastic adjacency
    A = np.zeros((n, n))
    for u, v in g.edges():
        A[idx[u], idx[v]] += 1.0
        A[idx[v], idx[u]] += 1.0
    out_deg = A.sum(axis=1, keepdims=True)
    out_deg[out_deg == 0] = 1.0
    A = A / out_deg

    if personalization:
        p = np.zeros(n)
        total = sum(personalization.values()) or 1.0
        for node, val in personalization.items():
            if node in idx:
                p[idx[node]] = val / total
        if p.sum() > 0:
            p = p / p.sum()
    else:
        p = np.ones(n) / n

    r = p.copy()
    for _ in range(max_iter):
        new_r = (1 - alpha) * p + alpha * A.T @ r
        if np.linalg.norm(new_r - r, 1) < tol:
            r = new_r
            break
        r = new_r

    # dangling nodes redistribute
    r = r / r.sum() if r.sum() > 0 else r
    return {node: float(r[idx[node]]) for node in nodes}


def safe_betweenness(graph: nx.Graph, k: Optional[int] = None,
                     seed: int = 42, normalized: bool = True) -> Dict[Hashable, float]:
    """Betweenness centrality with a numpy-only fallback."""
    try:
        return nx.betweenness_centrality(graph, k=k, seed=seed, normalized=normalized)
    except ModuleNotFoundError:
        nodes = list(graph.nodes())
        n = len(nodes)
        if n == 0:
            return {}
        if k and k < n:
            import random
            rng = random.Random(seed)
            nodes = sorted(rng.sample(nodes, k))
        return _betweenness_fallback(graph, nodes, normalized)


def _betweenness_fallback(graph: nx.Graph, sample: list, normalized: bool) -> Dict[Hashable, float]:
    """Brandes' algorithm (numpy-free) over a node sample."""
    g = graph.to_undirected() if graph.is_directed() else graph
    result = {node: 0.0 for node in g.nodes()}
    n = g.number_of_nodes()
    for s in sample:
        if s not in g:
            continue
        # BFS from s
        stack = []
        pred = {s: []}
        sigma = {s: 1.0}
        dist = {s: 0}
        for w in g.neighbors(s):
            if w not in dist:
                dist[w] = 1
                pred[w] = [s]
                sigma[w] = 1.0
            elif dist[w] == 1:
                pred[w].append(s)
                sigma[w] += 1.0
        # simple BFS queue
        from collections import deque
        queue = deque([s, *(n for n in g.neighbors(s) if n in dist and dist[n] == 1)])
        seen = {s}
        while queue:
            v = queue.popleft()
            if v in seen:
                continue
            seen.add(v)
            stack.append(v)
            for w in g.neighbors(v):
                if w not in dist:
                    dist[w] = dist[v] + 1
                    sigma[w] = sigma[v]
                    pred[w] = [v]
                    queue.append(w)
                elif dist[w] == dist[v] + 1:
                    pred[w].append(v)
                    sigma[w] += sigma[v]
        delta = {v: 0.0 for v in g.nodes()}
        while stack:
            w = stack.pop()
            for v in pred.get(w, []):
                delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                result[w] += delta[w]
    if normalized and n > 2:
        scale = 2.0 / ((n - 1) * (n - 2))
        for node in result:
            result[node] *= scale
    return result