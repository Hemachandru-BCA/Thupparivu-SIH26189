"""
ml/embedding_predictor.py
-------------------------
Level 2 — graph-embedding link predictor (Phase 4).

Uses the existing Node2Vec / GraphSAGE / spectral embeddings from
:mod:`src.graph.graph_embeddings` to score candidate edges by cosine
similarity of node embeddings.

* Node2Vec (gensim optional; falls back to spectral) — structural proximity.
* GraphSAGE-style fixed-weight inductive encoder — neighborhood smoothing.

The predictor never conflates OBSERVED and INFERRED links: it only scores
candidate pairs, and the caller labels the output.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Hashable, List, Optional, Sequence, Tuple

import networkx as nx

from src.graph.graph_embeddings import (
    EmbeddingConfig,
    cosine_similarity,
    graph_base_features,
    graphsage_embeddings,
    node2vec_embeddings,
    spectral_embeddings,
    undirected_weighted_projection,
)

logger = logging.getLogger(__name__)


class EmbeddingLinkPredictor:
    """Cosine-similarity link scorer over graph embeddings."""

    def __init__(self, config: Optional[EmbeddingConfig] = None,
                 method: str = "node2vec",
                 use_sage: bool = True,
                 seed: int = 42) -> None:
        self.config = config or EmbeddingConfig(seed=seed)
        self.method = method
        self.use_sage = use_sage
        self.embeddings: Dict[Hashable, Any] = {}
        self.sage: Dict[Hashable, Any] = {}

    # ------------------------------------------------------------------ #
    def fit(self, graph: nx.Graph) -> "EmbeddingLinkPredictor":
        projection = undirected_weighted_projection(graph)
        if self.method == "node2vec":
            try:
                self.embeddings = node2vec_embeddings(projection, self.config)
            except Exception as exc:  # pragma: no cover
                logger.warning("node2vec failed (%s); falling back to spectral", exc)
                self.embeddings = spectral_embeddings(projection, self.config.dimensions)
        else:
            self.embeddings = spectral_embeddings(projection, self.config.dimensions)
        if self.use_sage:
            try:
                self.sage = graphsage_embeddings(projection, self.config)
            except Exception:  # pragma: no cover
                self.sage = {}
        return self

    # ------------------------------------------------------------------ #
    def predict(self, u: Hashable, v: Hashable) -> Dict[str, float]:
        """Scores in [0,1]: cosine similarity of embeddings, plus optional
        GraphSAGE blended score."""
        if not self.embeddings:
            raise RuntimeError("call fit() first")
        emb_u = self.embeddings.get(u)
        emb_v = self.embeddings.get(v)
        sim = 0.0
        if emb_u is not None and emb_v is not None:
            sim = cosine_similarity(emb_u, emb_v)
        sage_sim = 0.0
        if self.use_sage and u in self.sage and v in self.sage:
            sage_sim = cosine_similarity(self.sage[u], self.sage[v])
        blend = 0.5 * sim + 0.5 * sage_sim if self.use_sage and sage_sim else sim
        return {
            "embedding_similarity": round(max(0.0, min(1.0, sim)), 4),
            "graphsage_similarity": round(max(0.0, min(1.0, sage_sim)), 4),
            "probability": round(max(0.0, min(1.0, blend)), 4),
        }

    def embedding_distance(self, u: Hashable, v: Hashable) -> Optional[float]:
        if u not in self.embeddings or v not in self.embeddings:
            return None
        return 1.0 - cosine_similarity(self.embeddings[u], self.embeddings[v])