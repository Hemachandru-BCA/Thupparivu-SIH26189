"""Graph embedding utilities for the SentinelGraph engine.

Provides two complementary embedding views over a NetworkX graph:

1. **Node2Vec** - biased second-order random walks (Grover & Leskovec, 2016)
   fed into a skip-gram Word2Vec model (via ``gensim``).  Used to measure
   how structurally "close" two otherwise disconnected communities are and
   to pick the best attachment points for synthetic ghost nodes.

2. **GraphSAGE-style inductive encoder** *(optional)* - a dependency-free
   numpy implementation of mean-neighbourhood aggregation with fixed
   (untrained, seeded orthogonal) projection weights.  It is NOT a trained
   GraphSAGE network; it is an inductive feature smoother used as a weak
   auxiliary similarity signal when torch-scale training is unnecessary or
   unavailable.

All functions are deterministic: node order is sorted and every stochastic
step is seeded.  If ``gensim`` is missing the module falls back to a spectral
embedding (SVD of the weighted adjacency), so the engine degrades gracefully.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Dict, Hashable, Iterable, List, Mapping, Optional, Tuple

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when gensim is present
    from gensim.models import Word2Vec

    _HAS_GENSIM = True
except ImportError:  # pragma: no cover
    Word2Vec = None  # type: ignore[assignment]
    _HAS_GENSIM = False

__all__ = [
    "EmbeddingConfig",
    "undirected_weighted_projection",
    "node2vec_embeddings",
    "spectral_embeddings",
    "graph_base_features",
    "graphsage_embeddings",
    "cosine_similarity",
    "embedding_centroid",
    "embeddings_available",
]

_ENTITY_TYPES = ("person", "organization", "location", "event", "document", "project")


@dataclass
class EmbeddingConfig:
    """Configuration for both embedding views. All defaults are deterministic."""

    dimensions: int = 64
    walk_length: int = 12
    num_walks: int = 10
    """Random walks started per node."""
    p: float = 1.0
    """Return parameter (probability of immediately revisiting a node)."""
    q: float = 0.5
    """In-out parameter; ``q < 1`` biases towards BFS, emphasising structural
    equivalence - the right regime for cross-community ghost detection."""
    window: int = 5
    epochs: int = 8
    seed: int = 42
    sage_layers: int = 2
    sage_dimensions: int = 32


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------

def undirected_weighted_projection(graph: nx.Graph) -> nx.Graph:
    """Collapse any NetworkX graph (directed/multi) into a weighted undirected
    simple graph. Edge weight = number of underlying edge records."""
    projection = nx.Graph()
    for node, data in graph.nodes(data=True):
        projection.add_node(node, **data)
    if graph.is_multigraph():
        for u, v, _key in graph.edges(keys=True):
            if projection.has_edge(u, v):
                projection[u][v]["weight"] += 1
            else:
                projection.add_edge(u, v, weight=1)
    else:
        for u, v, data in graph.edges(data=True):
            weight = data.get("weight", 1)
            if projection.has_edge(u, v):
                projection[u][v]["weight"] += weight
            else:
                projection.add_edge(u, v, weight=weight)
    return projection


# ---------------------------------------------------------------------------
# Node2Vec
# ---------------------------------------------------------------------------

def _precompute_transition_tables(
    graph: nx.Graph,
) -> Tuple[Dict[Hashable, List[Hashable]], Dict[Hashable, Dict[Hashable, float]], Dict[Tuple[Hashable, Hashable], set]]:
    """Neighbour lists, edge weights and neighbour sets for fast biased walks."""
    nodes = sorted(graph.nodes(), key=str)
    neighbours: Dict[Hashable, List[Hashable]] = {}
    weights: Dict[Hashable, Dict[Hashable, float]] = {}
    neigh_sets: Dict[Hashable, set] = {}
    for node in nodes:
        nbrs = list(graph.neighbors(node))
        neighbours[node] = nbrs
        neigh_sets[node] = set(nbrs)
        weights[node] = {nbr: float(graph[node][nbr].get("weight", 1.0)) for nbr in nbrs}
    return neighbours, weights, neigh_sets


def _biased_walks(
    graph: nx.Graph,
    config: EmbeddingConfig,
) -> List[List[Hashable]]:
    """Generate ``num_walks`` biased random walks per node (node2vec style)."""
    neighbours, weights, neigh_sets = _precompute_transition_tables(graph)
    rng = random.Random(config.seed)
    walks: List[List[Hashable]] = []

    for start in sorted(graph.nodes(), key=str):
        for _ in range(config.num_walks):
            walk = [start]
            while len(walk) < config.walk_length:
                current = walk[-1]
                candidates = neighbours[current]
                if not candidates:
                    break
                if len(walk) == 1:
                    nxt = rng.choices(
                        candidates, weights=[weights[current][c] for c in candidates]
                    )[0]
                else:
                    prev = walk[-2]
                    adjusted: List[float] = []
                    for cand in candidates:
                        if cand == prev:
                            weight = 1.0 / max(config.p, 1e-9)
                        elif cand in neigh_sets[prev]:
                            weight = 1.0
                        else:
                            weight = 1.0 / max(config.q, 1e-9)
                        adjusted.append(weight * weights[current][cand])
                    nxt = rng.choices(candidates, weights=adjusted)[0]
                walk.append(nxt)
            walks.append(walk)
    return walks


def node2vec_embeddings(
    graph: nx.Graph,
    config: Optional[EmbeddingConfig] = None,
) -> Dict[Hashable, np.ndarray]:
    """Compute Node2Vec embeddings for every node of ``graph``.

    Falls back to :func:`spectral_embeddings` when gensim is unavailable.
    The input may be directed/multi; it is projected internally.
    """
    config = config or EmbeddingConfig()
    projection = graph if (not graph.is_directed() and not graph.is_multigraph()) else undirected_weighted_projection(graph)
    if projection.number_of_nodes() == 0:
        return {}

    if not _HAS_GENSIM:
        logger.info("gensim not installed - falling back to spectral embeddings")
        return spectral_embeddings(projection, dimensions=config.dimensions)

    walks = _biased_walks(projection, config)
    corpus = [[str(n) for n in walk] for walk in walks]
    logging.getLogger("gensim").setLevel(logging.WARNING)
    model = Word2Vec(
        sentences=corpus,
        vector_size=config.dimensions,
        window=config.window,
        min_count=0,
        sg=1,  # skip-gram
        workers=1,  # deterministic
        seed=config.seed,
        epochs=config.epochs,
    )
    str_index = {str(node): node for node in projection.nodes()}
    embeddings: Dict[Hashable, np.ndarray] = {}
    for key in model.wv.index_to_key:
        node = str_index.get(key)
        if node is not None:
            embeddings[node] = np.asarray(model.wv[key], dtype=float)
    for node in projection.nodes():
        embeddings.setdefault(node, np.zeros(config.dimensions, dtype=float))
    return embeddings


def spectral_embeddings(graph: nx.Graph, dimensions: int = 64) -> Dict[Hashable, np.ndarray]:
    """Deterministic SVD-of-adjacency embedding fallback (no gensim needed)."""
    nodes = sorted(graph.nodes(), key=str)
    index = {node: i for i, node in enumerate(nodes)}
    n = len(nodes)
    if n == 0:
        return {}
    matrix = np.zeros((n, n), dtype=float)
    for u, v, data in graph.edges(data=True):
        matrix[index[u], index[v]] = float(data.get("weight", 1.0))
        matrix[index[v], index[u]] = float(data.get("weight", 1.0))
    dims = min(dimensions, n - 1) if n > 1 else 1
    try:
        u_matrix, s_vals, _ = np.linalg.svd(matrix, full_matrices=False)
        vecs = u_matrix[:, :dims] * s_vals[:dims]
    except np.linalg.LinAlgError:  # pragma: no cover - extremely unlikely
        rng = np.random.default_rng(0)
        vecs = rng.standard_normal((n, dims))
    return {node: vecs[index[node]] for node in nodes}


# ---------------------------------------------------------------------------
# GraphSAGE-style inductive encoder (optional, dependency-free)
# ---------------------------------------------------------------------------

def graph_base_features(graph: nx.Graph) -> Dict[Hashable, np.ndarray]:
    """Build the raw per-node feature vectors consumed by the SAGE encoder."""
    features: Dict[Hashable, np.ndarray] = {}
    metrics_by_node: Dict[Hashable, Mapping] = {}
    for node, data in graph.nodes(data=True):
        metrics_by_node[node] = data.get("metrics", {}) or {}

    max_degree = max((graph.degree(n) for n in graph.nodes()), default=1) or 1
    for node, data in graph.nodes(data=True):
        metrics = metrics_by_node[node]
        entity_type = str(data.get("entity_type", "other")).lower()
        type_onehot = [1.0 if entity_type == t else 0.0 for t in _ENTITY_TYPES]
        vector = np.array(
            [
                math.log1p(graph.degree(node)) / math.log1p(max_degree),
                float(metrics.get("degree_centrality", 0.0)),
                float(metrics.get("pagerank", 0.0)),
                float(metrics.get("betweenness_centrality", 0.0)),
                *type_onehot,
            ],
            dtype=float,
        )
        features[node] = vector
    return features


def _orthogonal_matrix(rows: int, cols: int, rng: np.random.Generator) -> np.ndarray:
    """Deterministic semi-orthogonal projection matrix via QR decomposition."""
    rows, cols = max(rows, 1), max(cols, 1)
    a_matrix = rng.standard_normal((max(rows, cols), max(rows, cols)))
    q_matrix, _ = np.linalg.qr(a_matrix)
    return q_matrix[:rows, :cols]


def graphsage_embeddings(
    graph: nx.Graph,
    config: Optional[EmbeddingConfig] = None,
    base_features: Optional[Dict[Hashable, np.ndarray]] = None,
) -> Dict[Hashable, np.ndarray]:
    """Fixed-weight GraphSAGE-style mean aggregation (optional view).

    Two layers of neighbourhood mean-aggregation passed through seeded
    orthogonal projections and ReLU, then L2-normalised.  Deterministic and
    dependency-free; intended as a weak auxiliary similarity signal.
    """
    config = config or EmbeddingConfig()
    projection = graph if (not graph.is_directed() and not graph.is_multigraph()) else undirected_weighted_projection(graph)
    nodes = sorted(projection.nodes(), key=str)
    if not nodes:
        return {}
    if base_features is None:
        base_features = graph_base_features(projection)

    feat_dim = len(next(iter(base_features.values())))
    rng = np.random.default_rng(config.seed)
    current: Dict[Hashable, np.ndarray] = {
        node: np.asarray(base_features.get(node, np.zeros(feat_dim)), dtype=float)
        for node in nodes
    }

    dims_in = feat_dim
    for _ in range(max(config.sage_layers, 1)):
        weight = _orthogonal_matrix(config.sage_dimensions, dims_in, rng)
        aggregated: Dict[Hashable, np.ndarray] = {}
        for node in nodes:
            neighbours = [n for n in projection.neighbors(node) if n in current]
            if neighbours:
                neigh_mean = np.mean([current[n] for n in neighbours], axis=0)
            else:
                neigh_mean = np.zeros_like(current[node])
            mixed = 0.5 * current[node] + 0.5 * neigh_mean
            aggregated[node] = np.maximum(weight @ mixed, 0.0)  # ReLU
        current = aggregated
        dims_in = config.sage_dimensions

    out: Dict[Hashable, np.ndarray] = {}
    for node, vector in current.items():
        norm = np.linalg.norm(vector)
        out[node] = vector / norm if norm > 1e-12 else vector
    return out


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------

def cosine_similarity(a_vec: np.ndarray, b_vec: np.ndarray) -> float:
    """Cosine similarity with zero-norm safety."""
    norm_a, norm_b = float(np.linalg.norm(a_vec)), float(np.linalg.norm(b_vec))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return float(np.dot(a_vec, b_vec) / (norm_a * norm_b))


def embedding_centroid(vectors: Iterable[np.ndarray]) -> np.ndarray:
    """L2-normalised mean of a collection of embedding vectors."""
    stacked = [np.asarray(v, dtype=float) for v in vectors]
    if not stacked:
        return np.zeros(1)
    centroid = np.mean(stacked, axis=0)
    norm = np.linalg.norm(centroid)
    return centroid / norm if norm > 1e-12 else centroid


def embeddings_available() -> bool:
    """True when the full Node2Vec path (gensim) is installed."""
    return _HAS_GENSIM
