"""
clustering.py
-------------
Clustering utilities for entity resolution (Phase: resolution).

The entity matcher produces pairwise similarity scores; this module turns
those into *clusters* of mentions that refer to the same real-world entity.

Two complementary strategies are provided:

* :func:`cluster_by_similarity`  - connected components over a thresholded
  pairwise-similarity graph (transitive closure; high recall, can over-merge).
* :func:`cluster_by_canonical`   - greedy single-pass assignment to an
  existing canonical entity above a keep-out threshold (high precision,
  deterministic, O(n) after indexing).

Both operate on plain ``(mention_id, name, extra)`` tuples so they can be
used independently of the graph pipeline (e.g. in notebooks).

All thresholds and weights come from :class:`ClusterConfig`; results are
deterministic for a given input order and seed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Hashable, Iterable, List, Optional, Sequence, Set, Tuple

from src.resolution.entity_matcher import compare_names, normalize_name

__all__ = [
    "ClusterConfig",
    "ClusterResult",
    "cluster_by_similarity",
    "cluster_by_canonical",
]


@dataclass
class ClusterConfig:
    """Knobs for the clustering strategies."""

    sim_threshold: float = 0.86
    """Pairwise fuzzy similarity above which two mentions are linked."""

    canonical_keep_threshold: float = 0.90
    """Similarity above which a mention joins an existing canonical entity."""

    canonical_review_band: Tuple[float, float] = (0.75, 0.90)
    """Similarity band that flags a mention as 'needs review' instead of
    silently merging or splitting."""

    min_token_overlap: int = 1
    """Minimum shared normalized tokens before fuzzy comparison (fast path)."""

    seed: int = 42


@dataclass
class ClusterResult:
    """Outcome of a clustering run."""

    mention_to_cluster: Dict[Hashable, int]
    cluster_to_mentions: Dict[int, List[Hashable]]
    cluster_names: Dict[int, str]
    review_pairs: List[Tuple[Hashable, Hashable, float]] = field(default_factory=list)

    def summary(self) -> Dict[str, object]:
        sizes = sorted((len(v) for v in self.cluster_to_mentions.values()), reverse=True)
        return {
            "num_mentions": len(self.mention_to_cluster),
            "num_clusters": len(self.cluster_to_mentions),
            "largest_cluster": sizes[0] if sizes else 0,
            "singletons": sum(1 for s in sizes if s == 1),
            "review_pairs": len(self.review_pairs),
        }


# --------------------------------------------------------------------------- #
# Strategy 1: similarity-graph connected components
# --------------------------------------------------------------------------- #

def cluster_by_similarity(
    mentions: Sequence[Tuple[Hashable, str]],
    config: Optional[ClusterConfig] = None,
    similarity: Optional[Callable[[str, str], float]] = None,
) -> ClusterResult:
    """Union mentions whose pairwise fuzzy similarity exceeds the threshold.

    ``mentions`` is a sequence of ``(mention_id, name)``.  Complexity is
    O(n^2) in the worst case, but a token-overlap fast path skips most
    pairs; suitable for the 10-50k mention scale of this project.
    """
    config = config or ClusterConfig()
    similarity = similarity or (lambda a, b: compare_names(a, b).score)

    parent: Dict[Hashable, Hashable] = {}

    def find(x: Hashable) -> Hashable:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: Hashable, b: Hashable) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for mid, _name in mentions:
        parent[mid] = mid

    # token index fast path
    token_index: Dict[str, List[Hashable]] = {}
    names: Dict[Hashable, str] = {}
    for mid, name in mentions:
        names[mid] = name
        for tok in set(normalize_name(name).split()):
            token_index.setdefault(tok, []).append(mid)

    review_pairs: List[Tuple[Hashable, Hashable, float]] = []
    checked: Set[Tuple[Hashable, Hashable]] = set()
    ids = [mid for mid, _ in mentions]
    for mid in ids:
        candidates: Set[Hashable] = set()
        for tok in set(normalize_name(names[mid]).split()):
            candidates.update(token_index.get(tok, []))
        for other in candidates:
            if other == mid:
                continue
            key = (mid, other) if str(mid) <= str(other) else (other, mid)
            if key in checked:
                continue
            checked.add(key)
            sim = similarity(names[mid], names[other])
            if sim >= config.sim_threshold:
                union(mid, other)
            elif sim >= config.canonical_review_band[0]:
                review_pairs.append((mid, other, round(sim, 4)))

    cluster_of: Dict[Hashable, int] = {}
    clusters: Dict[int, List[Hashable]] = {}
    names_by_cluster: Dict[int, str] = {}
    for mid in ids:
        root = find(mid)
        idx = cluster_of.setdefault(root, len(cluster_of))
        cluster_of[mid] = idx
        clusters.setdefault(idx, []).append(mid)
    for idx, members in clusters.items():
        names_by_cluster[idx] = names[members[0]]

    return ClusterResult(
        mention_to_cluster=cluster_of,
        cluster_to_mentions=clusters,
        cluster_names=names_by_cluster,
        review_pairs=sorted(review_pairs, key=lambda p: -p[2])[:200],
    )


# --------------------------------------------------------------------------- #
# Strategy 2: greedy canonical assignment
# --------------------------------------------------------------------------- #

def cluster_by_canonical(
    mentions: Sequence[Tuple[Hashable, str]],
    config: Optional[ClusterConfig] = None,
    similarity: Optional[Callable[[str, str], float]] = None,
) -> ClusterResult:
    """Assign each mention to the first canonical entity it matches well
    enough, otherwise create a new canonical entity.

    Deterministic for a given input order; O(n * c) where c is the number of
    canonical entities (c << n for closed-world datasets).
    """
    config = config or ClusterConfig()
    similarity = similarity or (lambda a, b: compare_names(a, b).score)

    canon_names: List[str] = []
    canon_ids: List[Hashable] = []
    cluster_of: Dict[Hashable, int] = {}
    clusters: Dict[int, List[Hashable]] = {}
    review_pairs: List[Tuple[Hashable, Hashable, float]] = []
    low, high = config.canonical_review_band

    for mid, name in mentions:
        best_idx, best_sim = -1, 0.0
        for idx, cname in enumerate(canon_names):
            sim = similarity(name, cname)
            if sim > best_sim:
                best_idx, best_sim = idx, sim
            if sim >= config.canonical_keep_threshold:
                break
        if best_sim >= config.canonical_keep_threshold:
            cluster_of[mid] = best_idx
            clusters[best_idx].append(mid)
        else:
            if best_sim >= low:
                review_pairs.append((mid, canon_ids[best_idx], round(best_sim, 4)))
            idx = len(canon_names)
            canon_names.append(name)
            canon_ids.append(mid)
            cluster_of[mid] = idx
            clusters[idx] = [mid]

    names_by_cluster = {idx: canon_names[idx] for idx in range(len(canon_names))}
    return ClusterResult(
        mention_to_cluster=cluster_of,
        cluster_to_mentions=clusters,
        cluster_names=names_by_cluster,
        review_pairs=sorted(review_pairs, key=lambda p: -p[2])[:200],
    )
