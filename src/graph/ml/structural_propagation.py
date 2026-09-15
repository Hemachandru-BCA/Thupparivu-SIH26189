"""
graph/ml/structural_propagation.py
-----------------------------------
Graph-structure-aware second signal for the ghost ensemble (Task 1.3b).

This module is the *GNN-equivalent* for environments where PyTorch Geometric
is not available.  Instead of learning message-passing weights, it computes
topological propagation features that encode how information (or a hidden
coordinator) would flow through the graph:

1. **Random-walk restart centrality** — for each node, run a short random
   walk (restart probability 0.15, 10 steps) and measure the node's
   propensity to land on high-degree "hub" neighbours.  Ghost coordinators
   tend to have abnormally high hub-contact rates relative to their own
   degree.

2. **Community-blend score** — for each node, measure the fraction of
   distinct communities touched by a 2-hop neighbourhood walk.  Ghost
   coordinators bridge many communities despite having few edges.

3. **Degree-residual score** — compare each node's actual degree to the
   expected degree of nodes in its local neighbourhood, capturing
   degree-deficit patterns typical of hidden coordinators.

All three scores are combined into a single "structural propagation" vector
(3 floats per node) that feeds into the ensemble stacker as a second
independent signal alongside the GBM score.

Design constraints:  zero new dependencies, CPU-only, deterministic.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None  # type: ignore[assignment]


__all__ = [
    "structural_propagation_features",
    "StructuralPropagationModel",
]


# ── per-node feature extraction (training / inference) ────────────────


def structural_propagation_features(
    G: "nx.DiGraph",
    restart_prob: float = 0.15,
    n_steps: int = 10,
) -> Dict[str, np.ndarray]:
    """Compute structural-propagation features for every node in *G*.

    Returns a dict mapping node id → ``float64[3]`` array:
        [0] hub_contact_rate  – fraction of walk steps landing on top-20%
                               degree nodes
        [1] community_blend   – fraction of communities in 2-hop radius
        [2] degree_residual   – (node_degree − mean_neighbour_degree) /
                               max(1, mean_neighbour_degree)

    For a directed graph, edges are followed in the outgoing direction.
    Self-loops are ignored.
    """
    if nx is None:
        raise ImportError("networkx is required for structural_propagation")

    n = G.number_of_nodes()
    if n == 0:
        return {}

    nodes = list(G.nodes())

    # ── hub set (top 20 % by degree) ──────────────────────────────────
    degrees = {v: G.out_degree(v) + G.in_degree(v) for v in nodes}
    sorted_by_deg = sorted(degrees, key=degrees.get, reverse=True)  # type: ignore[arg-type]
    hub_cutoff = max(1, n // 5)
    hub_set = set(sorted_by_deg[:hub_cutoff])

    # ── community labels (weakly connected components as proxy) ───────
    undirected = G.to_undirected() if G.is_directed() else G
    try:
        communities: List[set] = [set(c) for c in nx.connected_components(undirected)]
    except Exception:
        communities = [set(nodes)]

    node_to_comm: Dict[str, int] = {}
    for i, members in enumerate(communities):
        for v in members:
            node_to_comm[v] = i

    # ── local structure for residual ──────────────────────────────────
    mean_neighbour_deg: Dict[str, float] = {}
    for v in nodes:
        neighbours = set(G.predecessors(v)) | set(G.successors(v))
        if neighbours:
            mean_neighbour_deg[v] = sum(degrees.get(nb, 0) for nb in neighbours) / len(neighbours)
        else:
            mean_neighbour_deg[v] = 0.0

    # ── random walk restart simulation (uniform transition) ──────────
    # Build adjacency lists for fast sampling
    out_adj: Dict[str, List[str]] = {}
    for v in nodes:
        succs = list(G.successors(v))
        if not succs:
            succs = [v]  # teleport to self if sink (avoids dead-end)
        out_adj[v] = succs

    rng = _Rng(42)
    result: Dict[str, np.ndarray] = {}

    for start in nodes:
        hub_hits = 0
        comms_hit: set = set()
        current = start

        for step in range(n_steps):
            if rng.random() < restart_prob:
                current = start
            else:
                succs = out_adj.get(current, [current])
                current = succs[rng.randint(0, len(succs) - 1)]

            if current in hub_set:
                hub_hits += 1
            comms_hit.add(node_to_comm.get(current, 0))

        hub_rate = hub_hits / n_steps
        comm_blend = len(comms_hit) / max(1, len(communities))
        deg = degrees.get(start, 0)
        mnd = mean_neighbour_deg.get(start, 0.0)
        deg_residual = (deg - mnd) / max(1.0, mnd)

        result[start] = np.array([hub_rate, comm_blend, deg_residual], dtype=np.float64)

    return result


# ── lightweight stateless RNG (deterministic) ─────────────────────────


class _Rng:
    """Minimal xorshift64 RNG — enough for reproducible random walks."""

    def __init__(self, seed: int) -> None:
        self._s = max(1, seed) & 0xFFFFFFFFFFFFFFFF

    def random(self) -> float:
        self._s ^= self._s << 13
        self._s ^= self._s >> 7
        self._s ^= self._s << 17
        return (self._s & 0xFFFFFFFFFFFFF) / 0x10000000000000

    def randint(self, lo: int, hi: int) -> int:
        return lo + int(self.random() * (hi - lo + 1)) % (hi - lo + 1)


# ── model wrapper ─────────────────────────────────────────────────────


class StructuralPropagationModel:
    """Trains a small linear classifier on top of structural-propagation
    features to produce a ghost-coordinator probability.

    This serves as the *second independent signal* in the ghost ensemble
    (the first being the GBM on hand-engineered features).  It learns
    directly from graph topology via the propagation features rather than
    from a fixed formula.

    API: ``fit(G, labels)`` / ``predict(G)`` / ``score(G, labels)``.
    """

    def __init__(self, n_features: int = 3, lr: float = 0.1, steps: int = 200) -> None:
        self.n_features = n_features
        self.lr = lr
        self.steps = steps
        self._weights: Optional[np.ndarray] = None
        self._bias: float = 0.0

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        ex = math.exp(x)
        return ex / (1.0 + ex)

    def fit(self, G: "nx.DiGraph", labels: Dict[str, int]) -> None:
        """Train the linear model on structural-propagation features.

        ``labels`` maps node id → 0/1.
        """
        feats = structural_propagation_features(G)
        nodes = [n for n in G.nodes() if n in labels and n in feats]
        X = np.array([feats[n] for n in nodes], dtype=np.float64)
        y = np.array([labels[n] for n in nodes], dtype=np.float64)

        n = len(nodes)
        if n == 0:
            self._weights = np.zeros(self.n_features)
            self._bias = 0.0
            return

        # standardise features
        mu = X.mean(axis=0)
        sigma = X.std(axis=0) + 1e-9
        X = (X - mu) / sigma
        self._mu = mu
        self._sigma = sigma

        # logistic regression via SGD
        rng = _Rng(42)
        w = np.zeros(self.n_features, dtype=np.float64)
        b = 0.0

        for _ in range(self.steps):
            for i in range(n):
                z = float(np.dot(w, X[i]) + b)
                p = self._sigmoid(z)
                err = p - y[i]
                w -= self.lr * err * X[i]
                b -= self.lr * err

        self._weights = w
        self._bias = b

    def predict(self, G: "nx.DiGraph") -> Dict[str, float]:
        """Return per-node probability in [0, 1]."""
        if self._weights is None:
            # untrained: return uniform 0.5
            return {n: 0.5 for n in G.nodes()}

        feats = structural_propagation_features(G)
        result: Dict[str, float] = {}
        for n in G.nodes():
            if n in feats:
                f = (feats[n] - self._mu) / self._sigma
                z = float(np.dot(self._weights, f) + self._bias)
                result[n] = self._sigmoid(z)
            else:
                result[n] = 0.5
        return result

    def score(self, G: "nx.DiGraph", labels: Dict[str, int]) -> Dict[str, float]:
        """Return precision/recall/F1 at threshold 0.5."""
        proba = self.predict(G)
        tp = fp = fn = tn = 0
        for n, truth in labels.items():
            pred = 1 if proba.get(n, 0.5) >= 0.5 else 0
            if pred == 1 and truth == 1:
                tp += 1
            elif pred == 1 and truth == 0:
                fp += 1
            elif pred == 0 and truth == 1:
                fn += 1
            else:
                tn += 1
        prec = tp / max(1, tp + fp)
        rec = tp / max(1, tp + fn)
        f1 = 2 * prec * rec / max(1e-9, prec + rec)
        return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}
