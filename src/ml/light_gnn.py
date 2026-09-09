"""
ml/light_gnn.py
---------------
Level 4 — optional GNN backend (Phase 4, requirement on GNN).

PyTorch Geometric is deliberately NOT a hard dependency.  This module
provides a lightweight, dependency-free GraphSAGE-style encoder + logistic
head that can be used when a GNN signal is desired without the deployment
burden.

* Message passing: 1-hop mean-aggregation of node features (degree,
  pagerank, betweenness, entity-type one-hot) via seeded orthogonal
  projections + ReLU + L2-norm (mirrors the fixed-weight encoder in
  :mod:`src.graph.graph_embeddings`).
* Pair scorer: sigmoid over the cosine similarity of the two encodings
  linearly combined with a small learned bias.

Why is this not a "real" trained GraphSAGE?

* The aggregator weights are seeded/random, not learned from labeled edges.
* Use this as a *feature-smoothed baseline signal*, NOT as the definitive
  GNN.  For a fully-trained GCN/GraphSAGE, see the documented TODO in
  ``docs/PHASE4_GNN.md`` and the optional torch integration point in
  :class:`LinkPredictionEngine.register_gnn`.

The score is bounded to [0, 1] and deterministic (seed fixed).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Hashable, Optional

import networkx as nx
import numpy as np

from src.graph.graph_embeddings import (
    EmbeddingConfig,
    graph_base_features,
    graphsage_embeddings,
    undirected_weighted_projection,
)

logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-max(min(x, 30.0), -30.0)))


class LightGNNScorer:
    """A dependency-free GNN-style pair scorer.

    Usage::

        scorer = LightGNNScorer(seed=42)
        scorer.fit(graph)
        prob = scorer.score(u, v)          # 0..1
    """

    def __init__(self, seed: int = 42, config: Optional[EmbeddingConfig] = None) -> None:
        self.seed = seed
        self.config = config or EmbeddingConfig(seed=seed)
        self.embeddings: Dict[Hashable, np.ndarray] = {}

    # ------------------------------------------------------------------ #
    def fit(self, graph: nx.Graph) -> "LightGNNScorer":
        projection = undirected_weighted_projection(graph)
        # feature-smoothed inductive encoder (fixed random projections)
        self.embeddings = graphsage_embeddings(projection, self.config)
        self.graph = projection
        return self

    # ------------------------------------------------------------------ #
    def score(self, u: Hashable, v: Hashable) -> float:
        """Score a candidate pair in [0, 1]."""
        if not self.embeddings:
            raise RuntimeError("call fit() first")
        if u not in self.embeddings or v not in self.embeddings:
            return 0.5
        a, b = self.embeddings[u], self.embeddings[v]
        cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        # map cosine [-1, 1] → probability [0, 1]
        return round(_sigmoid(2.0 * cos), 4)

    def register(self, engine: Any) -> None:
        """Register this scorer into a LinkPredictionEngine as GNN backend."""
        engine.register_gnn(self.score, name="light_gnn")