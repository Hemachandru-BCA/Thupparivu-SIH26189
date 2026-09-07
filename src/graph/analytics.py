"""Graph analytics: centrality, PageRank, Louvain communities, graph stats.

Computes, per node:

- Degree centrality (plus in/out variants on directed graphs)
- Betweenness centrality
- PageRank
- Louvain community membership

and, at graph level:

- node / edge counts, density, connectivity, average degree
- number of communities (and their members)
- entity-resolution counts (original vs resolved entities)

Results are attached to each node's ``metrics`` attribute and written to
``graph_metrics.json`` in a fully JSON-serializable form.

Standalone use::

    python analytics.py --graph output/graph.pkl --output output

or programmatically::

    import networkx as nx, analytics
    graph = nx.read_gpickle(...)           # or pickle.load(...)
    doc = analytics.attach_metrics(graph)  # mutates node["metrics"]
    analytics.write_graph_metrics(doc, "output")
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import networkx as nx

logger = logging.getLogger(__name__)

__all__ = [
    "AnalyticsConfig",
    "compute_node_metrics",
    "detect_communities",
    "build_metrics_document",
    "attach_metrics",
    "write_graph_metrics",
    "get_graph_metrics",
    "get_node_metrics",
    "get_communities",
]

GRAPH_METRICS_NAME = "graph_metrics.json"

#: Environment variable that overrides the artifact search directory
#: (kept in sync with :mod:`graph_builder`).
ARTIFACT_DIR_ENV = "GRAPH_PIPELINE_DIR"

_MODULE_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"


@dataclass(frozen=True)
class AnalyticsConfig:
    """Tunables for the analytics pass.

    Attributes:
        louvain_resolution: Louvain resolution parameter (>1 -> more, <1 -> fewer
            communities).
        louvain_seed: Random seed for reproducible community detection.
        pagerank_alpha: PageRank damping factor.
        pagerank_max_iter: PageRank power-iteration cap.
        pagerank_tolerance: PageRank convergence tolerance.
        betweenness_normalized: Use normalized betweenness centrality.
        weight_attribute: Edge attribute used as weight (``None`` = unweighted).
        float_precision: Decimal places used when rounding JSON floats.
    """

    louvain_resolution: float = 1.0
    louvain_seed: int = 42
    pagerank_alpha: float = 0.85
    pagerank_max_iter: int = 100
    pagerank_tolerance: float = 1e-6
    betweenness_normalized: bool = True
    betweenness_k: Optional[int] = 256
    weight_attribute: Optional[str] = None
    float_precision: int = 6


def _round(value: float, precision: int) -> float:
    """Round to ``precision`` decimals, tolerating None/NaN safely."""
    if value is None:
        return 0.0
    try:
        rounded = round(float(value), precision)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if rounded != rounded else rounded  # NaN guard


# --------------------------------------------------------------------------
# Metric computations
# --------------------------------------------------------------------------

def compute_node_metrics(
    graph: nx.MultiDiGraph, config: Optional[AnalyticsConfig] = None
) -> Dict[str, Dict[str, Any]]:
    """Compute per-node metrics; returns ``{guid: metrics_dict}``.

    Nodes receive: ``degree_centrality``, ``in_degree_centrality``,
    ``out_degree_centrality``, ``betweenness_centrality``, ``pagerank``,
    ``community``, ``degree``, ``in_degree``, ``out_degree``.
    """
    cfg = config or AnalyticsConfig()
    if graph.number_of_nodes() == 0:
        return {}

    degree_centrality = nx.degree_centrality(graph)
    in_centrality = nx.in_degree_centrality(graph)
    out_centrality = nx.out_degree_centrality(graph)
    # Exact betweenness is O(V*E) and is not tractable for the project's 5k-person synthetic graph.
    # Use a deterministic node sample while preserving the metric name and normalization.
    if cfg.betweenness_k is None or cfg.betweenness_k >= graph.number_of_nodes():
        betweenness = nx.betweenness_centrality(graph, normalized=cfg.betweenness_normalized)
    else:
        nodes = sorted(graph.nodes(), key=str)
        sample = nodes[: max(1, int(cfg.betweenness_k))]
        betweenness = nx.betweenness_centrality(graph, k=len(sample), normalized=cfg.betweenness_normalized, seed=cfg.louvain_seed)

    try:
        pagerank = nx.pagerank(
            graph,
            alpha=cfg.pagerank_alpha,
            max_iter=cfg.pagerank_max_iter,
            tol=cfg.pagerank_tolerance,
            weight=cfg.weight_attribute,
        )
    except nx.NetworkXException as exc:  # pragma: no cover - defensive fallback
        logger.warning("PageRank failed on the multigraph (%s); retrying on a simple projection", exc)
        simple = nx.DiGraph()
        for source, target, attrs in graph.edges(data=True):
            weight = 1 if cfg.weight_attribute is None else attrs.get(cfg.weight_attribute, 1)
            if simple.has_edge(source, target):
                simple[source][target]["weight"] += weight
            else:
                simple.add_edge(source, target, weight=weight)
        pagerank = nx.pagerank(
            simple,
            alpha=cfg.pagerank_alpha,
            max_iter=cfg.pagerank_max_iter,
            tol=cfg.pagerank_tolerance,
            weight=cfg.weight_attribute,
        )

    community_map, _communities = detect_communities(graph, cfg)

    metrics: Dict[str, Dict[str, Any]] = {}
    for node in graph.nodes():
        metrics[node] = {
            "degree_centrality": _round(degree_centrality.get(node, 0.0), cfg.float_precision),
            "in_degree_centrality": _round(in_centrality.get(node, 0.0), cfg.float_precision),
            "out_degree_centrality": _round(out_centrality.get(node, 0.0), cfg.float_precision),
            "betweenness_centrality": _round(betweenness.get(node, 0.0), cfg.float_precision),
            "pagerank": _round(pagerank.get(node, 0.0), cfg.float_precision),
            "community": community_map.get(node, -1),
            "degree": int(graph.degree(node)),
            "in_degree": int(graph.in_degree(node)),
            "out_degree": int(graph.out_degree(node)),
        }
    return metrics


def _undirected_weighted_projection(
    graph: nx.MultiDiGraph, weight_attribute: Optional[str]
) -> nx.Graph:
    """Collapse a (multi)(di)graph into a simple undirected weighted graph.

    Parallel edges accumulate their weight (default 1 per edge), which gives
    Louvain a sensible relationship-strength signal. Self-loops are skipped.
    """
    projection = nx.Graph()
    projection.add_nodes_from(graph.nodes())
    for source, target, attrs in graph.edges(data=True):
        if source == target:
            continue
        weight = 1 if weight_attribute is None else attrs.get(weight_attribute, 1)
        if projection.has_edge(source, target):
            projection[source][target]["weight"] += weight
        else:
            projection.add_edge(source, target, weight=weight)
    return projection


def detect_communities(
    graph: nx.MultiDiGraph, config: Optional[AnalyticsConfig] = None
) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """Detect Louvain communities on the undirected projection.

    Returns:
        ``(community_map, communities)`` where ``community_map`` maps every
        node GUID to a community id (0..k-1, ordered by community size) and
        ``communities`` is a list of ``{"id", "size"}`` records.
    """
    cfg = config or AnalyticsConfig()
    if graph.number_of_nodes() == 0:
        return {}, []

    projection = _undirected_weighted_projection(graph, cfg.weight_attribute)
    try:
        partition = nx.algorithms.community.louvain_communities(
            projection,
            weight="weight",
            resolution=cfg.louvain_resolution,
            seed=cfg.louvain_seed,
        )
    except (AttributeError, nx.NetworkXException) as exc:  # pragma: no cover
        logger.warning("Louvain unavailable (%s); falling back to connected components", exc)
        partition = list(nx.algorithms.components.connected_components(projection))

    # Deterministic ids: largest community first, ties broken by member list.
    ordered = sorted(
        partition,
        key=lambda members: (-len(members), sorted(str(n) for n in members)),
    )
    community_map: Dict[str, int] = {}
    communities: List[Dict[str, Any]] = []
    for community_id, members in enumerate(ordered):
        for node in members:
            community_map[node] = community_id
        communities.append({"id": community_id, "size": len(members)})
    return community_map, communities


# --------------------------------------------------------------------------
# Document assembly
# --------------------------------------------------------------------------

def graph_metadata(
    graph: nx.MultiDiGraph,
    number_of_communities: int,
    er_summary: Optional[Mapping[str, Any]],
    config: Optional[AnalyticsConfig] = None,
) -> Dict[str, Any]:
    """Assemble the graph-level metadata block for ``graph_metrics.json``."""
    cfg = config or AnalyticsConfig()
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    if node_count > 1:
        density = nx.density(graph)
        try:
            component_count = nx.number_weakly_connected_components(graph)
        except nx.NetworkXNotImplemented:  # pragma: no cover - undirected pkl
            component_count = nx.number_connected_components(graph)
    else:
        density = 0.0
        component_count = node_count

    metadata: Dict[str, Any] = {
        "node_count": node_count,
        "edge_count": edge_count,
        "density": _round(density, cfg.float_precision),
        "is_directed": bool(graph.is_directed()),
        "is_multigraph": bool(graph.is_multigraph()),
        "weakly_connected_components": int(component_count),
        "number_of_communities": int(number_of_communities),
        "average_degree": _round(
            (sum(dict(graph.degree()).values()) / node_count) if node_count else 0.0,
            cfg.float_precision,
        ),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "louvain_resolution": cfg.louvain_resolution,
        "louvain_seed": cfg.louvain_seed,
        "betweenness_k": cfg.betweenness_k,
    }

    if er_summary:
        original_names = int(er_summary.get("original_unique_names", 0))
        resolved = int(er_summary.get("resolved_entity_count", 0))
        metadata.update(
            {
                "resolved_entity_count": resolved,
                "original_entity_count": original_names,
                "original_mention_count": int(er_summary.get("original_mention_count", 0)),
                "entity_reduction_ratio": _round(
                    (1.0 - resolved / original_names) if original_names else 0.0,
                    cfg.float_precision,
                ),
            }
        )
    return metadata


def build_metrics_document(
    graph: nx.MultiDiGraph,
    er_summary: Optional[Mapping[str, Any]] = None,
    config: Optional[AnalyticsConfig] = None,
) -> Dict[str, Any]:
    """Build the full ``graph_metrics.json`` document (without writing it)."""
    cfg = config or AnalyticsConfig()

    node_metrics = compute_node_metrics(graph, cfg)
    _community_map, communities = detect_communities(graph, cfg)

    # Reverse map: community id -> member nodes (for detail enrichment).
    members_by_community: Dict[int, List[str]] = {record["id"]: [] for record in communities}
    for node, metrics in node_metrics.items():
        members_by_community.setdefault(metrics["community"], []).append(node)

    # Enrich community records with member details (PageRank-ordered).
    communities_detailed: List[Dict[str, Any]] = []
    for record in communities:
        members = members_by_community.get(record["id"], [])
        members.sort(key=lambda n: (-node_metrics[n]["pagerank"], str(n)))
        communities_detailed.append(
            {
                "id": record["id"],
                "size": record["size"],
                "members": [
                    {
                        "guid": node,
                        "label": graph.nodes[node].get("canonical_name"),
                        "type": graph.nodes[node].get("entity_type"),
                    }
                    for node in members
                ],
            }
        )

    metadata = graph_metadata(graph, len(communities), er_summary, cfg)

    document: Dict[str, Any] = {
        "metadata": metadata,
        "node_metrics": node_metrics,
        "communities": communities_detailed,
        "entity_resolution": dict(er_summary) if er_summary else {},
    }
    return document


def attach_metrics(
    graph: nx.MultiDiGraph,
    er_summary: Optional[Mapping[str, Any]] = None,
    config: Optional[AnalyticsConfig] = None,
) -> Dict[str, Any]:
    """Compute all metrics, attach them to ``graph``'s nodes, return the document.

    Mutating convenience used by :func:`graph_builder.run_pipeline`: each node
    gets a ``metrics`` attribute; the graph gains an ``analytics`` metadata key.
    """
    cfg = config or AnalyticsConfig()
    document = build_metrics_document(graph, er_summary, cfg)

    for node, metrics in document.get("node_metrics", {}).items():
        if node in graph:
            graph.nodes[node]["metrics"] = metrics

    graph.graph["analytics"] = {
        "computed_at": document["metadata"].get("computed_at"),
        "number_of_communities": document["metadata"].get("number_of_communities"),
        "louvain_resolution": cfg.louvain_resolution,
        "louvain_seed": cfg.louvain_seed,
        "betweenness_k": cfg.betweenness_k,
    }
    return document


def write_graph_metrics(
    document: Mapping[str, Any], output_dir: str | os.PathLike[str]
) -> Path:
    """Write ``graph_metrics.json`` into ``output_dir`` and return its path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / GRAPH_METRICS_NAME
    with path.open("w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, ensure_ascii=False)
    logger.info("Saved %s", path)
    return path


# --------------------------------------------------------------------------
# Reusable loaders for FastAPI (artifact readers only)
# --------------------------------------------------------------------------

def _find_metrics_file(
    path: str | os.PathLike[str] | None = None,
) -> Path:
    """Locate ``graph_metrics.json`` (explicit path > env dir > defaults)."""
    if path is not None:
        candidate = Path(path)
        if candidate.is_dir():
            candidate = candidate / GRAPH_METRICS_NAME
        return candidate
    env_dir = os.environ.get(ARTIFACT_DIR_ENV)
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir) / GRAPH_METRICS_NAME)
    candidates.append(_MODULE_DIR / "output" / GRAPH_METRICS_NAME)
    candidates.append(_MODULE_DIR / GRAPH_METRICS_NAME)
    candidates.append(Path.cwd() / GRAPH_METRICS_NAME)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    from src.graph.graph_builder import ArtifactNotFoundError

    raise ArtifactNotFoundError(
        f"{GRAPH_METRICS_NAME} not found. Searched: "
        + ", ".join(str(c) for c in candidates)
        + f". Run the pipeline first or set ${ARTIFACT_DIR_ENV}."
    )


def get_graph_metrics(path: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    """Load (and cache) the full ``graph_metrics.json`` document."""
    return _load_metrics_cached(str(_find_metrics_file(path).resolve()))


def get_node_metrics(
    guid: str, path: str | os.PathLike[str] | None = None
) -> Optional[Dict[str, Any]]:
    """Return the metrics dictionary for one node GUID (or ``None``)."""
    return get_graph_metrics(path).get("node_metrics", {}).get(guid)


def get_communities(path: str | os.PathLike[str] | None = None) -> List[Dict[str, Any]]:
    """Return the community records (id, size, members) from the metrics file."""
    return list(get_graph_metrics(path).get("communities", []))


try:
    from functools import lru_cache
except ImportError:  # pragma: no cover
    lru_cache = None

if lru_cache is not None:

    @lru_cache(maxsize=4)
    def _load_metrics_cached(resolved_path: str) -> Dict[str, Any]:
        with Path(resolved_path).open("r", encoding="utf-8") as fh:
            return json.load(fh)

else:  # pragma: no cover
    def _load_metrics_cached(resolved_path: str) -> Dict[str, Any]:
        with Path(resolved_path).open("r", encoding="utf-8") as fh:
            return json.load(fh)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _cli() -> int:  # pragma: no cover - manual invocation helper
    import argparse
    import pickle

    parser = argparse.ArgumentParser(description="Compute graph analytics artifacts")
    parser.add_argument("--graph", "-g", default=None, help="Path to graph.pkl")
    parser.add_argument("--output", "-o", default=None, help="Output directory for graph_metrics.json")
    parser.add_argument("--resolution", type=float, default=1.0, help="Louvain resolution")
    parser.add_argument("--seed", type=int, default=42, help="Louvain random seed")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    graph_path = args.graph or str(_MODULE_DIR / "output" / "graph.pkl")
    with open(graph_path, "rb") as fh:
        graph = pickle.load(fh)

    config = AnalyticsConfig(louvain_resolution=args.resolution, louvain_seed=args.seed)
    document = build_metrics_document(graph, er_summary=None, config=config)
    for node, metrics in document["node_metrics"].items():
        graph.nodes[node]["metrics"] = metrics
    with open(graph_path, "wb") as fh:  # keep pkl in sync
        pickle.dump(graph, fh, protocol=pickle.HIGHEST_PROTOCOL)

    out_dir = args.output or str(Path(graph_path).parent)
    written = write_graph_metrics(document, out_dir)
    print(f"graph_metrics.json written to {written}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
