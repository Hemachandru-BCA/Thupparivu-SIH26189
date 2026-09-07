"""SentinelGraph - Part A: Ghost Node Detection.

Detects *synthetic ghost nodes*: unobserved intermediary entities that are
implied by the structure of a resolved knowledge graph even though they never
appear in the source data.

Method (four stages):

1. **Structural hole analysis** - every node is scored with Burt's network
   constraint, effective size and betweenness centrality.  Low-constraint,
   high-betweenness nodes are "brokers" that span structural holes and are
   the most plausible contact points for a hidden intermediary.

2. **Community detection** - Louvain communities over the undirected weighted
   projection.  Communities whose members consist mostly of *shared anchor*
   nodes are classified as infrastructure rather than cells.

3. **Shared-surface discovery** - for every pair of *disconnected*
   communities (no direct edges between non-anchor members) the engine
   computes what they share through three evidence categories:

   - **locations**    (LIVES_IN / BASED_IN / TRANSITS_THROUGH / ...)
   - **money routes** (FUNDS / TRANSFERS_TO / ... plus edge attributes such
     as ``account_id`` / ``amount_usd`` / ``currency``)
   - **suppliers**    (SUPPLIES_TO / SHIPS_TO / ... - direction-aware: only
     the supplying side counts)

   Each category yields a rarity-weighted, union-normalised overlap score
   (IDF-style: an anchor shared by many communities is less diagnostic).

4. **Ghost synthesis** - for pairs whose combined evidence passes the
   configured thresholds a ghost node is synthesised: a deterministic GUID,
   a subtype reflecting the dominant evidence category, itemised evidence,
   predicted edges to the most plausible brokers on both sides, and a
   confidence score decomposed into

   ``attribute affinity + Node2Vec embedding affinity + structural-hole
   signal + optional GraphSAGE-style inductive affinity``.

Output: ``ghost_predictions.json`` (schema documented in README.md).
The module never mutates the input graph; use
:func:`augment_graph_with_ghosts` to obtain a graph copy containing the
synthetic nodes/edges.

Run as a script::

    python ghost_nodes.py --graph output/graph.pkl --out output/ghost_predictions.json
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import networkx as nx
import numpy as np

from src.graph.graph_embeddings import (
    EmbeddingConfig,
    cosine_similarity,
    embedding_centroid,
    embeddings_available,
    graphsage_embeddings,
    node2vec_embeddings,
    undirected_weighted_projection,
)

logger = logging.getLogger(__name__)

__all__ = [
    "GhostConfig",
    "detect_ghost_nodes",
    "augment_graph_with_ghosts",
    "write_predictions",
    "load_ghost_predictions",
    "get_ghost_nodes",
    "get_ghost",
    "get_structural_holes",
    "GHOST_PREDICTIONS_NAME",
]

GHOST_PREDICTIONS_NAME = "ghost_predictions.json"
_MODULE_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"
GHOST_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "sentinelgraph/ghost-node")


class GhostDetectionError(RuntimeError):
    """Base class for ghost-detection failures."""


class GraphArtifactError(GhostDetectionError):
    """Raised when the input graph.pkl is missing or not a NetworkX graph."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class GhostConfig:
    """Every knob of the ghost detector; all thresholds are configurable."""

    # relation taxonomies (matched upper-case against edge ``relation``)
    location_relations: Tuple[str, ...] = (
        "LIVES_IN", "BASED_IN", "HEADQUARTERED_IN", "LOCATED_IN", "OPERATES_IN",
        "SEEN_IN", "TRANSITS_THROUGH", "IS_IN_COUNTRY", "TRAVELS_TO", "STAYED_AT",
    )
    money_relations: Tuple[str, ...] = (
        "FUNDS", "FUNDED", "TRANSFERS_TO", "TRANSFERRED_TO", "USES_ACCOUNT", "PAYS", "PAYS_TO",
        "PAID_TO", "WIRES_TO", "WIRED_TO", "LAUNDERS_TO", "RECEIVES_FROM",
        "MOVES_FUNDS", "PAYMENT_TO", "TRANSACTION_TO",
    )
    supplier_relations: Tuple[str, ...] = (
        "SUPPLIES_TO", "SUPPLIER_OF", "SUPPLIES", "SHIPS_TO", "DELIVERS_TO",
        "PURCHASES_FROM", "VENDOR_OF", "PROVIDES", "SELLS_TO",
    )

    # edge/node attribute keys that also constitute shared evidence
    money_attribute_keys: Tuple[str, ...] = (
        "account_id", "account", "iban", "bank", "bank_account", "payment_ref",
    )
    supplier_attribute_keys: Tuple[str, ...] = ("supplier", "vendor", "contract_id", "goods")
    location_attribute_keys: Tuple[str, ...] = (
        "city", "country", "location", "region", "address", "base",
    )

    # category weighting for the aggregate attribute affinity (money evidence
    # is deliberately the strongest signal in intelligence analysis)
    category_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "locations": 0.25, "money_routes": 0.50, "suppliers": 0.25,
        }
    )

    # per-category dampening: score *= s / (s + 1), s = shared evidence count
    shared_dampening: bool = True
    breadth_boost: float = 0.12
    """Multiplier bonus per additional evidence category beyond the first:
    total *= 1 + breadth_boost * (active_categories - 1)."""

    # proposal gates
    attribute_affinity_threshold: float = 0.25
    confidence_threshold: float = 0.46

    # confidence composition (renormalised when GraphSAGE is disabled)
    weight_attribute: float = 0.50
    weight_embedding: float = 0.25
    weight_structural_hole: float = 0.15
    weight_graphsage: float = 0.10

    # community / pair handling
    infrastructure_anchor_fraction: float = 0.30
    """Communities whose members are this fraction of shared anchors are
    treated as shared infrastructure and excluded from pair evaluation."""
    allow_connected_pairs: bool = False
    max_direct_member_edges: int = 2
    max_direct_member_edge_density: float = 0.002
    direct_edge_penalty: float = 0.15
    temporal_window_days: int = 14
    """Propose ghosts even when a few direct member-member edges exist."""
    brokers_per_side: int = 2
    broker_pool: int = 5
    """How many top structural-hole brokers per community are considered."""

    # embeddings
    use_embeddings: bool = False
    use_graphsage: bool = False
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    # misc
    seed: int = 42
    member_name_cap: int = 100


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def load_graph(path: str | Path) -> nx.MultiDiGraph:
    """Load the serialized NetworkX graph produced by the pipeline."""
    p = Path(path)
    if not p.exists():
        raise GraphArtifactError(f"graph file not found: {p}")
    try:
        with p.open("rb") as fh:
            graph = pickle.load(fh)
    except Exception as exc:  # pragma: no cover - corrupt pickle
        raise GraphArtifactError(f"cannot unpickle {p}: {exc}") from exc
    if not isinstance(graph, nx.Graph):
        raise GraphArtifactError(f"{p} does not contain a NetworkX graph")
    if graph.number_of_nodes() == 0:
        raise GhostDetectionError(f"{p} contains an empty graph")
    return graph


def _round(value: Any, precision: int = 6) -> Any:
    if isinstance(value, (float, np.floating)):
        return round(float(value), precision)
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return int(value)
    return value


def _json_safe(obj: Any) -> Any:
    """Recursively convert numpy scalars/arrays into JSON-serialisable types."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return round(value, 6) if np.isfinite(value) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return [_json_safe(v) for v in obj.tolist()]
    return obj


def _display_name(graph: nx.Graph, node: Hashable) -> str:
    data = graph.nodes[node]
    return str(data.get("canonical_name") or data.get("label") or node)


def _percentile_scores(values: Mapping[Hashable, float]) -> Dict[Hashable, float]:
    """Rank-based normalisation of a score map into [0, 1] (robust to outliers)."""
    if not values:
        return {}
    items = sorted(values.items(), key=lambda kv: (kv[1], str(kv[0])))
    n = len(items)
    return {node: (rank / (n - 1)) if n > 1 else 0.5
            for rank, (node, _val) in enumerate(items)}


def _edge_records(graph: nx.Graph) -> Iterable[Tuple[Hashable, Hashable, str, Mapping]]:
    """Yield (u, v, relation, attrs) for every underlying edge record."""
    if graph.is_multigraph():
        iterator = ((u, v, str(data.get("relation", key)), data) for u, v, key, data in graph.edges(keys=True, data=True))
    else:
        iterator = ((u, v, str(data.get("relation", "")), data) for u, v, data in graph.edges(data=True))
    for u, v, relation, data in iterator:
        merged = dict(data)
        nested = data.get("attributes")
        if isinstance(nested, Mapping):
            merged.update(nested)
        yield u, v, relation, merged


# ---------------------------------------------------------------------------
# Stage 1 - structural holes
# ---------------------------------------------------------------------------

def detect_structural_holes(
    graph: nx.MultiDiGraph,
    projection: nx.Graph,
) -> List[Dict[str, Any]]:
    """Score every node as a structural-hole spanner.

    Combines Burt's ``constraint`` (inverted), ``effective_size`` and
    betweenness centrality into ``structural_hole_score`` in [0, 1].
    """
    constraint = nx.constraint(projection)
    effective = nx.effective_size(projection)
    betweenness: Mapping[Hashable, float] = {}
    for node, data in graph.nodes(data=True):
        metrics = data.get("metrics") or {}
        if "betweenness_centrality" in metrics:
            betweenness[node] = float(metrics["betweenness_centrality"])
    if len(betweenness) != graph.number_of_nodes():
        if projection.number_of_nodes() > 2000:
            sample = sorted(projection.nodes(), key=str)[:256]
            betweenness = nx.betweenness_centrality(projection, k=len(sample), normalized=True, weight="weight", seed=42)
        else:
            betweenness = nx.betweenness_centrality(projection, weight="weight")

    # (hi - v) / span  ->  high score for LOW constraint (structural-hole spanner)
    inv_constraint = _normalise_01(constraint, inverse=True)
    eff_norm = _normalise_01(effective)
    bet_norm = _percentile_scores(betweenness)

    results: List[Dict[str, Any]] = []
    for node in projection.nodes():
        data = graph.nodes[node]
        score = (
            0.50 * inv_constraint[node]
            + 0.30 * eff_norm.get(node, 0.0)
            + 0.20 * bet_norm.get(node, 0.0)
        )
        results.append(
            {
                "guid": node,
                "name": _display_name(graph, node),
                "entity_type": data.get("entity_type", "unknown"),
                "constraint": _round(constraint.get(node, 0.0), 4),
                "effective_size": _round(effective.get(node, 0.0), 4),
                "betweenness_centrality": _round(bet_norm.get(node, 0.0), 6),
                "structural_hole_score": _round(score, 6),
            }
        )
    results.sort(key=lambda item: (-item["structural_hole_score"], item["name"]))
    return results


def _normalise_01(values: Mapping[Hashable, float], inverse: bool = False) -> Mapping[Hashable, float]:
    """Min-max normalise finite values, mapping disconnected-metric NaNs to 0."""
    finite = [float(v) for v in values.values() if np.isfinite(v)]
    if not finite:
        return {k: 0.0 for k in values}
    lo, hi = min(finite), max(finite)
    span = (hi - lo) or 1.0
    out: Dict[Hashable, float] = {}
    for k, v in values.items():
        value = float(v) if np.isfinite(v) else lo
        out[k] = (hi - value) / span if inverse else (value - lo) / span
    return out


# ---------------------------------------------------------------------------
# Stage 2 - communities
# ---------------------------------------------------------------------------

def detect_communities(
    projection: nx.Graph, seed: int = 42, *, exclude_entity_types: Sequence[str] = ("LOCATION", "ACCOUNT")
) -> List[Set[Hashable]]:
    """Detect person-centric communities without letting infrastructure hubs
    (locations/accounts) merge otherwise separate cells.

    Infrastructure nodes remain in the original graph and are still used as
    shared evidence; they are intentionally excluded only from the Louvain
    topology used to define the communities.
    """
    blocked = {str(t).upper() for t in exclude_entity_types}
    nodes = sorted(
        (n for n, data in projection.nodes(data=True)
         if str(data.get("entity_type", "")).upper() not in blocked),
        key=str,
    )
    # Rebuild with a stable insertion order; Louvain's seeded RNG does not by
    # itself remove dependence on graph iteration order when there are ties.
    person_projection = nx.Graph()
    person_projection.add_nodes_from((n, projection.nodes[n]) for n in nodes)
    for u, v, data in sorted(projection.subgraph(nodes).edges(data=True), key=lambda e: (str(e[0]), str(e[1]))):
        person_projection.add_edge(u, v, **dict(data))
    communities = nx.community.louvain_communities(person_projection, seed=seed, weight="weight")
    return sorted((set(c) for c in communities),
                  key=lambda c: (-len(c), min(str(n) for n in c)))


# ---------------------------------------------------------------------------
# Stage 3 - shared-surface (anchor) discovery
# ---------------------------------------------------------------------------

_TAXONOMY_FIELD = {"locations": "location_relations", "money_routes": "money_relations",
                   "suppliers": "supplier_relations"}


def _taxonomy(config: GhostConfig) -> Dict[str, Set[str]]:
    return {
        category: {rel.upper() for rel in getattr(config, field_name)}
        for category, field_name in _TAXONOMY_FIELD.items()
    }


def _relation_category(relation: str, taxonomy: Mapping[str, Set[str]]) -> Optional[str]:
    rel = relation.upper()
    for category, rels in taxonomy.items():
        if rel in rels:
            return category
    return None


def _category_allows_source_anchor(category: str) -> bool:
    """Supplier evidence is direction-aware: only the supplying side of a
    SUPPLIES_TO-style edge can be a shared supplier anchor."""
    return category in ("money_routes", "suppliers")


def _attribute_tokens(
    category: str,
    attrs: Mapping[str, Any],
    config: GhostConfig,
) -> List[str]:
    keys = {
        "locations": config.location_attribute_keys,
        "money_routes": config.money_attribute_keys,
        "suppliers": config.supplier_attribute_keys,
    }[category]
    tokens = []
    for key in keys:
        if key in attrs and attrs[key] not in (None, ""):
            tokens.append(f"{key}={attrs[key]}")
    return tokens


def _extract_anchor_evidence(
    graph: nx.MultiDiGraph,
    communities: List[Set[Hashable]],
    community_of: Mapping[Hashable, int],
    taxonomy: Mapping[str, Set[str]],
    config: GhostConfig,
) -> Dict[str, Any]:
    """Shared-anchor and attribute-token extraction (direction-aware).

    A node becomes a *shared anchor* for a category when it is adjacent (via
    that category's relations) to members of >= 2 distinct communities.
    Directionality matters:

    - **supplier relations**: only the **supplying** side gains adjacency
      (a receiver of supplies is not itself a shared supplier);
    - **money relations**: only the **receiving** side (the money sink)
      gains adjacency - a shell account collecting transfers from several
      communities is the classic shared money route, while the individual
      senders merely re-state that same fact (``RECEIVES_FROM`` inverts the
      flow, so its *head* is the sink);
    - **location relations**: both directions count (a city used by two
      communities is shared surface regardless of edge direction).
    """
    # category incidence: node -> category -> {community: [contact nodes]}
    incidence: Dict[Hashable, Dict[str, Dict[int, List[Hashable]]]] = {}

    def add_contact(src: Hashable, category: str, dst: Hashable) -> None:
        comm = community_of.get(dst, -1)
        if comm < 0:
            return
        incidence.setdefault(src, {}).setdefault(category, {}).setdefault(
            comm, []
        ).append(dst)

    for u, v, relation, attrs in _edge_records(graph):
        category = _relation_category(relation, taxonomy)
        if category is None:
            continue
        if category == "suppliers":
            add_contact(u, category, v)          # supplying side only
        elif category == "money_routes":
            # Account nodes are the strongest latent financial surfaces in this
            # dataset. Do not turn a random cross-community person-to-person
            # transfer into a shared anchor. A receiving PERSON may still be
            # useful evidence through directed relation logic, but the shared
            # anchor set is deliberately restricted to non-PERSON sinks.
            sink, source = (u, v) if relation.upper() == "RECEIVES_FROM" else (v, u)
            sink_type = str(graph.nodes[sink].get("entity_type", "")).lower()
            # A generated one-off transaction account links exactly two people
            # and is not useful as a hidden shared surface. Reused accounts
            # (degree >= 3) survive this filter and are substantially more
            # diagnostic of an intermediary/coordinator pattern.
            if sink_type == "account" and graph.degree(sink) >= 3:
                add_contact(sink, category, source)
            elif sink_type not in {"person", "account"}:
                add_contact(sink, category, source)
        else:  # locations - both directions, but only geographic nodes are anchors
            if str(graph.nodes[u].get("entity_type", "")).lower() == "location":
                add_contact(u, category, v)
            if str(graph.nodes[v].get("entity_type", "")).lower() == "location":
                add_contact(v, category, u)

    anchors: Set[Hashable] = {
        node
        for node, per_cat in incidence.items()
        if any(len(comms) >= 2 for comms in per_cat.values())
    }

    anchor_adjacency: Dict[str, Dict[Hashable, Set[int]]] = {}
    for node in sorted(anchors, key=str):
        for category, per_comm in incidence[node].items():
            if len(per_comm) >= 2:
                anchor_adjacency.setdefault(category, {})[node] = set(per_comm)

    # per-community attribute tokens from category edges (both endpoints)
    tokens: Dict[str, List[Dict[str, Any]]] = {c: [] for c in taxonomy}
    for u, v, relation, attrs in _edge_records(graph):
        category = _relation_category(relation, taxonomy)
        if category is None:
            continue
        comms = {c for c in (community_of.get(u, -1), community_of.get(v, -1)) if c >= 0}
        for token in _attribute_tokens(category, attrs, config):
            tokens[category].append({"token": token, "communities": comms})

    return {
        "anchors": anchors,
        "anchor_adjacency": anchor_adjacency,
        "tokens": tokens,
    }


def _community_shared_surfaces(
    evidence: Mapping[str, Any],
    communities: List[Set[Hashable]],
    config: GhostConfig,
) -> Tuple[Dict[str, Dict[int, Set[Hashable]]], Dict[str, Dict[int, Set[str]]], Dict[str, Dict[Hashable, float]]]:
    """Per category: {category -> {community -> set of anchors / tokens}} plus
    per-anchor rarity weights (shared by more communities => less diagnostic)."""
    anchors_by_cat: Dict[str, Dict[int, Set[Hashable]]] = {}
    for category, per_anchor in evidence["anchor_adjacency"].items():
        for anchor, comms in per_anchor.items():
            for comm in comms:
                anchors_by_cat.setdefault(category, {}).setdefault(comm, set()).add(anchor)

    tokens_by_cat: Dict[str, Dict[int, Set[str]]] = {}
    token_freq: Dict[str, Dict[str, int]] = {}
    for category, entries in evidence["tokens"].items():
        for entry in entries:
            for comm in entry["communities"]:
                tokens_by_cat.setdefault(category, {}).setdefault(comm, set()).add(entry["token"])
            token_freq.setdefault(category, {})
            token_freq[category][entry["token"]] = token_freq[category].get(entry["token"], 0) + 1

    rarity: Dict[str, Dict[Hashable, float]] = {}
    for category, per_anchor in evidence["anchor_adjacency"].items():
        rarity[category] = {
            anchor: 1.0 / max(1, len(comms) - 1)
            for anchor, comms in per_anchor.items()
        }
    return anchors_by_cat, tokens_by_cat, rarity


# ---------------------------------------------------------------------------
# Stage 4 - pair evaluation and ghost synthesis
# ---------------------------------------------------------------------------

def _category_overlap(
    set_i: Set[Any],
    set_j: Set[Any],
    weight_of: Mapping[Any, float],
) -> Tuple[float, int, List[Any]]:
    """Rarity-weighted, union-normalised overlap of two evidence sets."""
    shared = set_i & set_j
    union = set_i | set_j
    if not union or not weight_of:
        return 0.0, len(shared), sorted(map(str, shared))
    weight_of_eff = {k: weight_of.get(k, 1.0) for k in union}
    denom = sum(weight_of_eff.values()) or 1.0
    overlap_score = sum(weight_of_eff[k] for k in shared) / denom
    # Preserve the original union-normalised score, but add a peak-rarity term:
    # one highly diagnostic shared anchor should not be diluted by dozens of
    # unrelated anchors unique to each community. This is especially important
    # for shared account IDs in the synthetic coordinator scenario.
    peak_rarity = max((weight_of_eff[k] for k in shared), default=0.0)
    score = 0.50 * overlap_score + 0.50 * min(1.0, peak_rarity)
    return score, len(shared), sorted(map(str, shared))


def _pair_attribute_affinity(
    community_i: int,
    community_j: int,
    anchors_by_cat: Mapping[str, Mapping[int, Set[Hashable]]],
    tokens_by_cat: Mapping[str, Mapping[int, Set[str]]],
    rarity: Mapping[str, Mapping[Hashable, float]],
    token_freq: Mapping[str, Mapping[str, int]],
    config: GhostConfig,
) -> Tuple[float, Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """Aggregate attribute affinity across the three evidence categories."""
    per_category: Dict[str, Any] = {}
    contributions: Dict[str, float] = {}
    evidence_by_cat: Dict[str, List[Dict[str, Any]]] = {}

    for category, cat_weight in config.category_weights.items():
        anchor_sets = anchors_by_cat.get(category, {})
        token_sets = tokens_by_cat.get(category, {})
        w_anchor = rarity.get(category, {})
        set_i = anchor_sets.get(community_i, set()) | {f"tok:{t}" for t in token_sets.get(community_i, set())}
        set_j = anchor_sets.get(community_j, set()) | {f"tok:{t}" for t in token_sets.get(community_j, set())}
        weights = dict(w_anchor)
        for tok in set_i | set_j:
            if isinstance(tok, str) and tok.startswith("tok:"):
                freq = token_freq.get(category, {}).get(tok[4:], 1)
                weights[tok] = 1.0 / max(1, freq - 1)

        score, n_shared, shared_names = _category_overlap(set_i, set_j, weights)
        damp = (n_shared / (n_shared + 1)) if config.shared_dampening else 1.0
        weighted = cat_weight * score * damp
        contributions[category] = weighted
        per_category[category] = {
            "score": _round(score),
            "shared_count": n_shared,
            "peak_rarity": _round(max((weights.get(k, 0.0) for k in set_i & set_j), default=0.0)),
            "shared": shared_names,
            "dampening": _round(damp),
            "weighted_contribution": _round(weighted),
        }
        if shared_names:
            evidence_by_cat[category] = [{"anchor": s} for s in shared_names]

    total = sum(contributions.values())
    active = sum(1 for v in contributions.values() if v > 1e-9)
    multiplier = 1.0 + config.breadth_boost * max(0, active - 1)
    total *= multiplier
    per_category["_breadth"] = {
        "active_categories": active,
        "multiplier": _round(multiplier),
    }
    return total, per_category, evidence_by_cat


def _broker_scores(
    graph: nx.MultiDiGraph,
    community: Set[Hashable],
    hole_scores: Mapping[Hashable, float],
    shared_anchors: Set[Hashable],
    taxonomy: Mapping[str, Set[str]],
    exclude_nodes: Optional[Set[Hashable]] = None,
) -> List[Tuple[Hashable, float]]:
    """Rank a community's members as ghost attachment candidates.

    Shared anchors and location nodes are excluded (a ghost intermediary
    attaches to people/organisations, not to the hubs it was inferred from).
    score = 0.5 * structural_hole_score + 0.3 * direct adjacency to the
    pair's shared anchors + 0.2 * normalised degree.
    """
    max_degree = max((graph.degree(n) for n in graph.nodes()), default=1) or 1
    excluded = (exclude_nodes or set()) | {
        n for n in community
        if str(graph.nodes[n].get("entity_type", "")).lower() == "location"
    }
    scored: List[Tuple[Hashable, float]] = []
    for node in community:
        if node in excluded:
            continue
        adjacent_shared = set()
        for _, nbr, attrs in graph.out_edges(node, data=True):
            relation = attrs.get("relation", "")
            if nbr in shared_anchors and _relation_category(str(relation), taxonomy) is not None:
                adjacent_shared.add(nbr)
        for nbr, _, attrs in graph.in_edges(node, data=True):
            relation = attrs.get("relation", "")
            if nbr in shared_anchors and _relation_category(str(relation), taxonomy) is not None:
                adjacent_shared.add(nbr)
        proximity = len(adjacent_shared) / len(shared_anchors) if shared_anchors else 0.0
        score = (
            0.5 * hole_scores.get(node, 0.0)
            + 0.3 * proximity
            + 0.2 * (graph.degree(node) / max_degree)
        )
        scored.append((node, score))
    scored.sort(key=lambda kv: (-kv[1], str(kv[0])))
    return scored


def _synthesise_ghost(
    community_i: int,
    community_j: int,
    graph: nx.MultiDiGraph,
    communities: List[Set[Hashable]],
    attribute_affinity: float,
    per_category: Mapping[str, Any],
    embedding_affinity: float,
    sage_affinity: float,
    hole_scores: Mapping[Hashable, float],
    shared_anchor_nodes: Set[Hashable],
    taxonomy: Mapping[str, Set[str]],
    config: GhostConfig,
    use_graphsage: bool,
    use_embedding: bool = False,
    all_anchors: Optional[Set[Hashable]] = None,
) -> Dict[str, Any]:
    """Build one ghost node record with evidence, predicted edges, confidence."""
    low, high = min(community_i, community_j), max(community_i, community_j)
    weights = {
        "attribute_affinity": config.weight_attribute,
        "embedding_affinity": config.weight_embedding if use_embedding else 0.0,
        "structural_hole_signal": config.weight_structural_hole,
        "graphsage_affinity": config.weight_graphsage if use_graphsage else 0.0,
    }
    norm = sum(weights.values()) or 1.0
    hole_signal = float(np.mean([
        np.mean(sorted((hole_scores.get(n, 0.0) for n in communities[low]), reverse=True)[:config.broker_pool]),
        np.mean(sorted((hole_scores.get(n, 0.0) for n in communities[high]), reverse=True)[:config.broker_pool]),
    ]))
    components = {
        "attribute_affinity": attribute_affinity,
        "embedding_affinity": embedding_affinity,
        "structural_hole_signal": hole_signal,
        "graphsage_affinity": sage_affinity,
    }
    confidence = sum(weights[k] * components[k] for k in weights) / norm

    scored_categories = {
        c: v for c, v in per_category.items() if not c.startswith("_")
    }
    dominant = max(scored_categories, key=lambda c: scored_categories[c]["weighted_contribution"]) if scored_categories else "money_routes"
    subtype_by_cat = {
        "money_routes": "money_intermediary",
        "suppliers": "supply_intermediary",
        "locations": "location_intermediary",
    }
    subtype = subtype_by_cat.get(dominant, "intermediary")
    ghost_id = str(uuid.uuid5(GHOST_NAMESPACE, f"{low}|{high}|{','.join(sorted(map(str, shared_anchor_nodes)))}"))
    label = f"Ghost {dominant.replace('_', ' ').rstrip('s').title()} Intermediary"

    predicted_edges: List[Dict[str, Any]] = []
    for comm, side in ((low, "cell_a"), (high, "cell_b")):
        ranked = _broker_scores(graph, communities[comm], hole_scores, shared_anchor_nodes, taxonomy,
                                exclude_nodes=all_anchors)
        for node, attach_score in ranked[: config.brokers_per_side]:
            probability = float(np.clip(0.35 + 0.45 * confidence + 0.20 * attach_score, 0.0, 0.99))
            predicted_edges.append(
                {
                    "source": ghost_id,
                    "target": node,
                    "target_name": _display_name(graph, node),
                    "side": side,
                    "direction": "bidirectional_inferred",
                    "probability": _round(probability),
                    "rationale": (
                        f"Top structural-hole broker of community {comm} "
                        f"(attach score {_round(attach_score)}); plausible contact "
                        f"point for the hidden {subtype.replace('_', ' ')}."
                    ),
                }
            )

    evidence: List[Dict[str, Any]] = []
    for anchor in sorted(shared_anchor_nodes, key=str):
        data = graph.nodes[anchor]
        rels = set()
        sides: Dict[int, List[str]] = {low: [], high: []}
        # Inspect only edges incident to the shared anchor instead of scanning
        # the entire graph for every anchor.
        incident = []
        incident.extend((anchor, v, attrs) for _, v, attrs in graph.out_edges(anchor, data=True))
        incident.extend((u, anchor, attrs) for u, _, attrs in graph.in_edges(anchor, data=True))
        for u, v, attrs in incident:
            relation = str(attrs.get("relation", ""))
            other = None
            if u == anchor and v in communities[low]:
                other = (low, _display_name(graph, v))
            elif v == anchor and u in communities[low]:
                other = (low, _display_name(graph, u))
            elif u == anchor and v in communities[high]:
                other = (high, _display_name(graph, v))
            elif v == anchor and u in communities[high]:
                other = (high, _display_name(graph, u))
            if other and _relation_category(relation, taxonomy):
                rels.add(relation)
                sides[other[0]].append(other[1])
        evidence.append(
            {
                "anchor_guid": anchor,
                "anchor_name": _display_name(graph, anchor),
                "anchor_type": data.get("entity_type", "unknown"),
                "relations": sorted(rels),
                f"community_{low}_nodes": sorted(set(sides[low]))[:config.member_name_cap],
                f"community_{high}_nodes": sorted(set(sides[high]))[:config.member_name_cap],
                "detail": (
                    f"'{_display_name(graph, anchor)}' is shared by communities {low} "
                    f"and {high} via {sorted(rels) or ['attribute tokens']} without any "
                    f"direct member-to-member edge between them."
                ),
            }
        )

    return {
        "ghost_id": ghost_id,
        "label": label,
        "type": "ghost",
        "entity_type": "ghost",
        "subtype": subtype,
        "between_communities": [low, high],
        "confidence": _round(confidence),
        "confidence_breakdown": {
            "attribute_affinity": _round(components["attribute_affinity"]),
            "temporal_affinity": _round(per_category.get("_temporal_affinity", 0.0)),
            "embedding_affinity": _round(components["embedding_affinity"]),
            "structural_hole_signal": _round(components["structural_hole_signal"]),
            "graphsage_affinity": _round(components["graphsage_affinity"]),
            "weights": {k: _round(v / norm) for k, v in weights.items()},
        },
        "dominant_evidence_category": dominant,
        "predicted_edges": predicted_edges,
        "evidence": evidence,
        "per_category": per_category,
        "synthetic": True,
    }


def _community_membership_map(
    graph: nx.MultiDiGraph,
    communities: List[Set[Hashable]],
) -> Mapping[Hashable, int]:
    return {node: idx for idx, comm in enumerate(communities) for node in comm}


def _direct_edge_count(
    graph: nx.MultiDiGraph,
    set_a: Set[Hashable],
    set_b: Set[Hashable],
) -> int:
    count = 0
    for u, v, _rel, _attrs in _edge_records(graph):
        if (u in set_a and v in set_b) or (u in set_b and v in set_a):
            count += 1
    return count


def _direct_edge_counts_by_community(
    graph: nx.MultiDiGraph,
    community_of: Mapping[Hashable, int],
    anchors: Set[Hashable],
) -> Dict[Tuple[int, int], int]:
    """Count non-anchor member-to-member edges once for all community pairs."""
    counts: Dict[Tuple[int, int], int] = {}
    for u, v, _relation, _attrs in _edge_records(graph):
        if u in anchors or v in anchors:
            continue
        ci, cj = community_of.get(u), community_of.get(v)
        if ci is None or cj is None or ci == cj:
            continue
        key = (ci, cj) if ci < cj else (cj, ci)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _build_temporal_index(
    graph: nx.MultiDiGraph,
    community_of: Mapping[Hashable, int],
    config: GhostConfig,
) -> Dict[Hashable, Dict[int, List[datetime]]]:
    """Index timestamped anchor observations once for all community pairs."""
    taxonomy = _taxonomy(config)
    by_anchor: Dict[Hashable, Dict[int, List[datetime]]] = {}
    for u, v, relation, attrs in _edge_records(graph):
        if _relation_category(relation, taxonomy) is None:
            continue
        raw = attrs.get("timestamp") or attrs.get("date")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        for anchor, other in ((u, v), (v, u)):
            if str(graph.nodes[anchor].get("entity_type", "")).upper() not in {"ACCOUNT", "LOCATION"}:
                continue
            comm = community_of.get(other)
            if comm is None:
                continue
            by_anchor.setdefault(anchor, {}).setdefault(comm, []).append(dt)
    return by_anchor


def _temporal_pair_affinity(
    graph: nx.MultiDiGraph,
    community_i: int,
    community_j: int,
    communities: List[Set[Hashable]],
    shared_nodes: Set[Hashable],
    community_of: Mapping[Hashable, int],
    config: GhostConfig,
    temporal_index: Optional[Mapping[Hashable, Mapping[int, List[datetime]]]] = None,
) -> float:
    """Score whether shared-anchor evidence occurs close in time on both sides."""
    if not shared_nodes:
        return 0.0
    by_anchor = temporal_index or _build_temporal_index(graph, community_of, config)
    matched = 0
    considered = 0
    from datetime import timedelta
    window = timedelta(days=max(1, config.temporal_window_days))
    for sides in by_anchor.values():
        left, right = sides.get(community_i, []), sides.get(community_j, [])
        if not left or not right:
            continue
        considered += 1
        if any(abs(a - b) <= window for a in left for b in right):
            matched += 1
    return matched / considered if considered else 0.0


def _mask_nodes(graph: nx.MultiDiGraph, hidden_names: Set[str]) -> nx.MultiDiGraph:
    """Create the observed graph for a ghost run by hiding known synthetic coordinators."""
    hidden_norm = {str(n).strip().casefold() for n in hidden_names}
    masked = graph.copy()
    remove = [n for n in masked.nodes if _display_name(masked, n).strip().casefold() in hidden_norm]
    masked.remove_nodes_from(remove)
    masked.graph["ghost_masked_nodes"] = len(remove)
    return masked


# ---------------------------------------------------------------------------
# Public pipeline
# ---------------------------------------------------------------------------

def detect_ghost_nodes(
    graph: nx.MultiDiGraph,
    config: Optional[GhostConfig] = None,
) -> Dict[str, Any]:
    """Run the full Part A pipeline and return the ghost_predictions document."""
    config = config or GhostConfig()
    full_projection = undirected_weighted_projection(graph)
    # Structural holes and communities are person-centric. Infrastructure
    # nodes such as accounts/locations remain in the original graph as
    # evidence, but excluding them here prevents hubs and thousands of leaf
    # infrastructure nodes from dominating expensive network metrics.
    projection = full_projection.subgraph([
        n for n, data in graph.nodes(data=True)
        if str(data.get("entity_type", "")).upper() not in {"LOCATION", "ACCOUNT"}
    ]).copy()
    taxonomy = _taxonomy(config)

    logger.info("stage 1/4: structural hole analysis over %d nodes", graph.number_of_nodes())
    holes = detect_structural_holes(graph, projection)
    hole_scores = {entry["guid"]: entry["structural_hole_score"] for entry in holes}

    logger.info("stage 2/4: Louvain community detection (seed=%d)", config.seed)
    communities = detect_communities(projection, seed=config.seed)
    community_of = _community_membership_map(graph, communities)

    logger.info("stage 3/4: shared-surface (anchor) discovery")
    evidence = _extract_anchor_evidence(graph, communities, community_of, taxonomy, config)
    anchors_by_cat, tokens_by_cat, rarity = _community_shared_surfaces(
        evidence, communities, config
    )
    token_freq: Dict[str, Dict[str, int]] = {}
    for category, entries in evidence["tokens"].items():
        for entry in entries:
            freq = token_freq.setdefault(category, {})
            freq[entry["token"]] = freq.get(entry["token"], 0) + 1

    anchors = evidence["anchors"]
    # Only evaluate community pairs that share at least one diagnostic anchor.
    # This turns the former O(C²) pair scan into a sparse evidence-driven scan.
    candidate_pairs_set: Set[Tuple[int, int]] = set()
    for per_cat in anchors_by_cat.values():
        anchor_lists = list(per_cat.items())
        for idx, (ci, ci_anchors) in enumerate(anchor_lists):
            for cj, cj_anchors in anchor_lists[idx + 1:]:
                if ci != cj and ci_anchors & cj_anchors:
                    candidate_pairs_set.add((min(ci, cj), max(ci, cj)))
    direct_counts = _direct_edge_counts_by_community(graph, community_of, anchors)
    infrastructure_ids: Set[int] = set()
    community_profiles: List[Dict[str, Any]] = []
    for idx, comm in enumerate(communities):
        frac = len([n for n in comm if n in anchors]) / len(comm) if comm else 0.0
        if frac >= config.infrastructure_anchor_fraction:
            infrastructure_ids.add(idx)
        community_profiles.append(
            {
                "community_id": idx,
                "size": len(comm),
                "is_infrastructure": idx in infrastructure_ids,
                "anchor_fraction": _round(frac),
                "top_brokers": [
                    {"guid": n, "name": _display_name(graph, n),
                     "structural_hole_score": _round(hole_scores.get(n, 0.0))}
                    for n, _s in _broker_scores(graph, comm, hole_scores, set(), taxonomy,
                                                exclude_nodes=anchors)[: config.broker_pool]
                ],
                "members": [
                    {"guid": n, "name": _display_name(graph, n)}
                    for n in sorted(comm, key=str)[: config.member_name_cap]
                ],
            }
        )

    embeddings: Dict[Hashable, np.ndarray] = {}
    sage: Dict[Hashable, np.ndarray] = {}
    if config.use_embeddings:
        logger.info("computing Node2Vec embeddings (gensim=%s)", embeddings_available())
        embeddings = node2vec_embeddings(graph, config.embedding)
    if config.use_graphsage:
        sage = graphsage_embeddings(graph, config.embedding)

    temporal_index = _build_temporal_index(graph, community_of, config)
    logger.info("stage 4/4: evaluating community pairs")
    ghosts: List[Dict[str, Any]] = []
    evaluated: List[Dict[str, Any]] = []
    for ci, cj in sorted(candidate_pairs_set):
        if ci in infrastructure_ids or cj in infrastructure_ids:
            continue
        shared_nodes: Set[Hashable] = set()
        for category in config.category_weights:
            a_cat = anchors_by_cat.get(category, {})
            shared_nodes |= {
                a for a in (a_cat.get(ci, set()) & a_cat.get(cj, set()))
                if a in anchors
            }
        attr_affinity, per_category, _ev = _pair_attribute_affinity(
            ci, cj, anchors_by_cat, tokens_by_cat, rarity, token_freq, config
        )
        direct = direct_counts.get((ci, cj), 0)
        pair_area = max(1, len(communities[ci] - anchors) * len(communities[cj] - anchors))
        direct_density = direct / pair_area

        embed_affinity = 0.0
        if embeddings and shared_nodes is not None:
            brokers_i = [n for n, _ in _broker_scores(graph, communities[ci], hole_scores, shared_nodes, taxonomy, exclude_nodes=anchors)[: config.broker_pool]]
            brokers_j = [n for n, _ in _broker_scores(graph, communities[cj], hole_scores, shared_nodes, taxonomy, exclude_nodes=anchors)[: config.broker_pool]]
            sims = [cosine_similarity(embeddings[a], embeddings[b]) for a in brokers_i for b in brokers_j]
            embed_affinity = (float(np.mean(sims)) + 1.0) / 2.0 if sims else 0.0
        sage_affinity = 0.0
        if sage:
            brokers_i = [n for n, _ in _broker_scores(graph, communities[ci], hole_scores, shared_nodes, taxonomy, exclude_nodes=anchors)[: config.broker_pool]]
            brokers_j = [n for n, _ in _broker_scores(graph, communities[cj], hole_scores, shared_nodes, taxonomy, exclude_nodes=anchors)[: config.broker_pool]]
            sims = [cosine_similarity(sage[a], sage[b]) for a in brokers_i for b in brokers_j]
            sage_affinity = (float(np.mean(sims)) + 1.0) / 2.0 if sims else 0.0

        temporal_affinity = _temporal_pair_affinity(
            graph, ci, cj, communities, shared_nodes, community_of, config, temporal_index=temporal_index
        )
        if temporal_affinity > 0:
            attr_affinity = min(1.0, attr_affinity * (0.85 + 0.15 * temporal_affinity))
        negative_penalty = min(0.30, config.direct_edge_penalty * (direct_density / max(config.max_direct_member_edge_density, 1e-9)))
        confidence, _bd = _confidence_from_components(
            max(0.0, attr_affinity - negative_penalty), embed_affinity, hole_scores, communities, ci, cj, sage_affinity, config,
            use_graphsage=bool(sage), embedding_available=bool(embeddings)
        )

        connected = (
            not config.allow_connected_pairs
            and direct > config.max_direct_member_edges
            and direct_density > config.max_direct_member_edge_density
        )
        proposed = (
            not connected
            and bool(shared_nodes)
            and attr_affinity >= config.attribute_affinity_threshold
            and confidence >= config.confidence_threshold
        )
        record = {
            "community_pair": [ci, cj],
            "direct_member_edges": direct,
            "direct_member_edge_density": _round(direct_density),
            "connected": bool(connected),
            "shared_anchor_count": len(shared_nodes),
            "attribute_affinity": _round(attr_affinity),
            "temporal_affinity": _round(temporal_affinity),
            "negative_evidence_penalty": _round(negative_penalty),
            "embedding_affinity": _round(embed_affinity),
            "confidence": _round(confidence),
            "ghost_proposed": bool(proposed),
            "per_category": per_category,
        }
        if not proposed:
            record["not_proposed_reason"] = (
                "direct member edges exist" if connected
                else "no shared anchor" if not shared_nodes
                else f"attribute affinity {_round(attr_affinity)} < "
                     f"{config.attribute_affinity_threshold} or confidence "
                     f"{_round(confidence)} < {config.confidence_threshold}"
            )
        per_category["_temporal_affinity"] = _round(temporal_affinity)
        evaluated.append(record)

        if proposed:
            ghosts.append(
                _synthesise_ghost(
                    ci, cj, graph, communities, attr_affinity, per_category,
                    embed_affinity, sage_affinity, hole_scores, shared_nodes,
                    taxonomy, config, use_graphsage=bool(sage), use_embedding=bool(embeddings), all_anchors=anchors,
                )
            )

    ghosts.sort(key=lambda g: (-g["confidence"], g["ghost_id"]))
    for rank, ghost in enumerate(ghosts, start=1):
        ghost["rank"] = rank

    document = {
        "meta": {
            "engine": "SentinelGraph Ghost Node Detection",
            "version": "1.2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_graph": {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
            },
            "config": {
                "attribute_affinity_threshold": config.attribute_affinity_threshold,
                "max_direct_member_edge_density": config.max_direct_member_edge_density,
                "confidence_threshold": config.confidence_threshold,
                "category_weights": dict(config.category_weights),
                "confidence_weights": {
                    "attribute": config.weight_attribute,
                    "embedding": config.weight_embedding,
                    "structural_hole": config.weight_structural_hole,
                    "graphsage": config.weight_graphsage if config.use_graphsage else 0.0,
                },
                "embedding": {"requested": bool(config.use_embeddings),
                              "source": "node2vec" if embeddings_available() and config.use_embeddings else ("spectral_fallback" if config.use_embeddings else "disabled"),
                              "dimensions": config.embedding.dimensions,
                              "gensim_available": embeddings_available()},
                "graphsage": {"enabled": bool(sage), "is_learned_model": False},
            },
            "method": {
                "structural_holes": "Burt constraint (inverted, 50%) + effective size (30%) + betweenness (20%)",
                "communities": "Louvain on person-centric undirected weighted projection; infrastructure nodes are excluded from community topology but retained as shared evidence",
                "affinity": "rarity-weighted union-normalised overlap of shared anchors/tokens with common-infrastructure down-weighting",
                "confidence": "weighted blend of rarity-weighted shared-surface affinity, embedding similarity, structural-hole signal; shared evidence is temporally adjusted and direct-cross-community links receive a negative-evidence penalty",
            },
        },
        "summary": {
            "num_communities": len(communities),
            "infrastructure_communities": sorted(infrastructure_ids),
            "pairs_evaluated": len(evaluated),
            "disconnected_pairs": sum(1 for r in evaluated if not r["connected"]),
            "ghosts_proposed": len(ghosts),
            "mean_confidence": _round(float(np.mean([g["confidence"] for g in ghosts]))) if ghosts else 0.0,
        },
        "communities": community_profiles,
        "structural_holes": holes,
        "ghost_nodes": ghosts,
        "evaluated_pairs": sorted(evaluated, key=lambda r: (-r["confidence"], r["community_pair"])),
    }
    return _json_safe(document)


def _confidence_from_components(
    attribute_affinity: float,
    embedding_affinity: float,
    hole_scores: Mapping[Hashable, float],
    communities: List[Set[Hashable]],
    ci: int,
    cj: int,
    sage_affinity: float,
    config: GhostConfig,
    use_graphsage: bool,
    embedding_available: bool = True,
) -> Tuple[float, Dict[str, float]]:
    hole_signal = float(np.mean([
        np.mean(sorted((hole_scores.get(n, 0.0) for n in communities[ci]), reverse=True)[: config.broker_pool]),
        np.mean(sorted((hole_scores.get(n, 0.0) for n in communities[cj]), reverse=True)[: config.broker_pool]),
    ]))
    weights = {
        "attribute": config.weight_attribute,
        "embedding": config.weight_embedding if embedding_available else 0.0,
        "hole": config.weight_structural_hole,
        "sage": config.weight_graphsage if use_graphsage else 0.0,
    }
    norm = sum(weights.values()) or 1.0
    confidence = (
        weights["attribute"] * attribute_affinity
        + weights["embedding"] * embedding_affinity
        + weights["hole"] * hole_signal
        + weights["sage"] * sage_affinity
    ) / norm
    return confidence, {"hole_signal": hole_signal}


# ---------------------------------------------------------------------------
# Graph augmentation + persistence + loaders
# ---------------------------------------------------------------------------

def augment_graph_with_ghosts(
    graph: nx.MultiDiGraph,
    predictions: Mapping[str, Any],
) -> nx.MultiDiGraph:
    """Return a copy of ``graph`` with synthetic ghost nodes/edges inserted.

    Ghost edges carry ``inferred=True`` plus the ghost's confidence so a
    React/FastAPI layer can render them differently (dashed, translucent...).
    """
    augmented = graph.copy()
    for ghost in predictions.get("ghost_nodes", []):
        ghost_id = ghost["ghost_id"]
        augmented.add_node(
            ghost_id,
            guid=ghost_id,
            canonical_name=ghost["label"],
            aliases=[],
            entity_type="ghost",
            subtype=ghost.get("subtype"),
            attributes={"synthetic": True, "dominant_evidence_category": ghost.get("dominant_evidence_category")},
            mention_count=0,
            metrics={},
            confidence=ghost.get("confidence", 0.0),
        )
        for edge in ghost.get("predicted_edges", []):
            augmented.add_edge(
                ghost_id,
                edge["target"],
                id=str(uuid.uuid5(GHOST_NAMESPACE, f"{ghost_id}->{edge['target']}")),
                relation="GHOST_LINK",
                inferred=True,
                confidence=edge.get("probability", ghost.get("confidence", 0.0)),
                attributes={"method": "sentinelgraph-ghost-detection"},
            )
    return augmented


def write_predictions(document: Mapping[str, Any], out_path: str | Path) -> Path:
    """Serialise the ghost_predictions document (pretty, UTF-8, JSON-safe)."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(document), indent=2, ensure_ascii=False))
    return path


def load_ghost_predictions(path: str | Path | None = None) -> Dict[str, Any]:
    """Load ``ghost_predictions.json`` (FastAPI-friendly cached loader)."""
    p = Path(path) if path else _MODULE_DIR / "output" / GHOST_PREDICTIONS_NAME
    if not p.exists():
        # fall back to the sibling output/ directory of the caller's project
        alt = _MODULE_DIR.parent / "graph_pipeline" / "output" / GHOST_PREDICTIONS_NAME
        if not alt.exists():
            raise FileNotFoundError(f"ghost predictions not found at {p}")
        p = alt
    return json.loads(p.read_text())


def get_ghost_nodes(path: str | Path | None = None) -> List[Dict[str, Any]]:
    """All proposed ghost nodes, ranked by confidence."""
    return load_ghost_predictions(path).get("ghost_nodes", [])


def get_ghost(ghost_id: str, path: str | Path | None = None) -> Optional[Dict[str, Any]]:
    """One ghost node by its id (or None)."""
    for ghost in get_ghost_nodes(path):
        if ghost["ghost_id"] == ghost_id:
            return ghost
    return None


def get_structural_holes(path: str | Path | None = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Top structural-hole spanners."""
    return load_ghost_predictions(path).get("structural_holes", [])[:limit]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:  # pragma: no cover - manual invocation helper
    parser = argparse.ArgumentParser(description="SentinelGraph Part A: ghost node detection")
    parser.add_argument("--graph", "-g", default=str(_MODULE_DIR / "output" / "graph.pkl"))
    parser.add_argument("--out", "-o", default=str(_MODULE_DIR / "output" / GHOST_PREDICTIONS_NAME))
    parser.add_argument("--confidence-threshold", type=float, default=None)
    parser.add_argument("--attribute-threshold", type=float, default=None)
    parser.add_argument("--brokers-per-side", type=int, default=None)
    parser.add_argument("--no-embeddings", action="store_true", help="disable Node2Vec")
    parser.add_argument("--no-graphsage", action="store_true", help="disable GraphSAGE-style encoder")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    config = GhostConfig(seed=args.seed)
    # The standalone CLI mirrors the API pipeline: when the synthetic
    # persons.csv is available, hide generator-marked coordinators before
    # inference so the CLI cannot accidentally score the known hidden nodes
    # as if they were observed evidence.
    hidden_file = Path(graph_path).resolve().parents[2] / "data" / "synthetic" / "persons.csv"
    if hidden_file.exists():
        import csv
        hidden_names = set()
        with hidden_file.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if str(row.get("is_hidden_coordinator", "")).strip().lower() == "true" and row.get("full_name"):
                    hidden_names.add(row["full_name"])
    else:
        hidden_names = set()
    if args.confidence_threshold is not None:
        config.confidence_threshold = args.confidence_threshold
    if args.attribute_threshold is not None:
        config.attribute_affinity_threshold = args.attribute_threshold
    if args.brokers_per_side is not None:
        config.brokers_per_side = args.brokers_per_side
    if args.no_embeddings:
        config.use_embeddings = False
    if args.no_graphsage:
        config.use_graphsage = False

    graph = load_graph(args.graph)
    observed_graph = _mask_nodes(graph, hidden_names) if hidden_names else graph
    document = detect_ghost_nodes(observed_graph, config)
    document.setdefault("meta", {})["synthetic_hidden_nodes_masked"] = len(hidden_names)
    out = write_predictions(document, args.out)

    summary = document["summary"]
    print("Ghost detection finished.")
    print(f"  communities           : {summary['num_communities']}")
    print(f"  infrastructure comms  : {summary['infrastructure_communities']}")
    print(f"  pairs evaluated       : {summary['pairs_evaluated']}")
    print(f"  ghosts proposed       : {summary['ghosts_proposed']}")
    print(f"  mean confidence       : {summary['mean_confidence']}")
    print(f"  written               : {out}")
    for ghost in document["ghost_nodes"]:
        print(f"    - {ghost['ghost_id']}  conf={ghost['confidence']:.3f}  "
              f"{ghost['subtype']}  between {ghost['between_communities']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
