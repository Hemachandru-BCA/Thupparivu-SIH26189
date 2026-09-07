"""SentinelGraph - Part B: Arrest Simulation.

Simulates "arresting" (removing) high-value nodes from the resolved graph and
measures how much each removal damages the network, producing a ranked list
of optimal interventions.

For every simulated arrest the engine recomputes:

- **network density**        (directed multigraph density)
- **fragmentation**          (1 - largest weakly-connected component / nodes)
- **shortest paths**         (mean path length inside the surviving giant
  component plus global efficiency, which stays well-defined for
  disconnected graphs)
- **community changes**      (Louvain community count, modularity and
  normalised mutual information against the baseline partition)

Baseline nodes are ranked by a composite of PageRank, betweenness and degree
centrality (reusing the ``metrics`` block already attached by the analytics
pipeline when present).  The default ``top_k`` is 100 and is automatically
capped to the graph size.  Each removal receives an impact score - a weighted
blend of fragmentation increase, relative efficiency loss, giant-component
loss, community disruption (1 - NMI), mean-path-length increase and
modularity drop - plus a disruption class (critical / high / medium / low).

Optionally (default on) a Node2Vec embedding of the *baseline* graph is used
to suggest "role inheritor" candidates: the structurally most similar
surviving nodes for every arrested node.

Output: ``simulation_results.json`` (schema documented in README.md).

Run as a script::

    python simulation.py --graph output/graph.pkl --out output/simulation_results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Hashable, List, Mapping, Optional, Sequence, Set, Tuple

import networkx as nx
import numpy as np

from src.graph.graph_embeddings import (
    EmbeddingConfig,
    cosine_similarity,
    node2vec_embeddings,
    undirected_weighted_projection,
)

logger = logging.getLogger(__name__)

__all__ = [
    "SimulationConfig",
    "snapshot_metrics",
    "simulate_node_removal",
    "run_arrest_simulation",
    "write_results",
    "load_simulation_results",
    "get_top_interventions",
    "get_node_simulation",
    "SIMULATION_RESULTS_NAME",
]

SIMULATION_RESULTS_NAME = "simulation_results.json"
_MODULE_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"


class SimulationError(RuntimeError):
    """Base class for arrest-simulation failures."""


class GraphArtifactError(SimulationError):
    """Raised when the input graph.pkl is missing or not a NetworkX graph."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SimulationConfig:
    """All knobs of the arrest simulation."""

    top_k: int = 100
    """Simulate the top-K baseline-ranked nodes (auto-capped to graph size)."""

    # baseline ranking composite
    rank_weight_pagerank: float = 0.40
    rank_weight_betweenness: float = 0.40
    rank_weight_degree: float = 0.20

    # impact composition
    impact_weight_fragmentation: float = 0.25
    impact_weight_efficiency: float = 0.25
    impact_weight_community: float = 0.20
    impact_weight_gcc: float = 0.15
    impact_weight_paths: float = 0.10
    impact_weight_modularity: float = 0.05

    # disruption classes (on the 0-1 impact scale)
    critical_threshold: float = 0.30
    high_threshold: float = 0.15
    medium_threshold: float = 0.07

    # computational guards
    efficiency_exact_limit: int = 1500
    """Exact all-pairs global efficiency up to this node count; sampled beyond."""
    efficiency_sample_size: int = 512
    louvain_seed: int = 42
    louvain_resolution: float = 1.0

    # role-inheritor analysis (Node2Vec on the baseline graph)
    use_embedding_successors: bool = True
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    successor_candidates: int = 3


# ---------------------------------------------------------------------------
# Helpers
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
        raise SimulationError(f"{p} contains an empty graph")
    return graph


def _round(value: Any, precision: int = 6) -> Any:
    if isinstance(value, (float, np.floating)):
        finite = float(value)
        return round(finite, precision) if np.isfinite(finite) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_json_safe(v) for v in obj.tolist()]
    if isinstance(obj, (np.floating, float)):
        finite = float(obj)
        return round(finite, 6) if np.isfinite(finite) else None
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def _display_name(graph: nx.Graph, node: Hashable) -> str:
    data = graph.nodes[node]
    return str(data.get("canonical_name") or data.get("label") or node)


def _global_efficiency(graph: nx.Graph, config: SimulationConfig) -> Optional[float]:
    """Global efficiency on an undirected projection; sampled for big graphs."""
    n = graph.number_of_nodes()
    if n < 2:
        return None
    if n <= config.efficiency_exact_limit:
        return float(nx.global_efficiency(graph))
    # sampled approximation over random ordered pairs
    rng = np.random.default_rng(config.louvain_seed)
    nodes = list(graph.nodes())
    total, pairs = 0.0, 0
    for _ in range(config.efficiency_sample_size):
        u, v = rng.choice(nodes, size=2, replace=False)
        try:
            d = nx.shortest_path_length(graph, u, v)
        except nx.NetworkXNoPath:
            continue
        total += 1.0 / d
        pairs += 1
    return total / pairs if pairs else 0.0


def _sampled_apl(graph: nx.Graph, config: SimulationConfig) -> Optional[float]:
    """Sampled average shortest path length over random node pairs.

    Mirrors the sampled global-efficiency guard: exact computation over the
    giant component is O(n * (n + m)) and uninteractive above the exact
    limit, so large graphs use the same seeded pair sampling.
    """
    n = graph.number_of_nodes()
    if n < 2:
        return None
    rng = np.random.default_rng(config.louvain_seed)
    nodes = list(graph.nodes())
    total, pairs = 0.0, 0
    for _ in range(config.efficiency_sample_size):
        u, v = rng.choice(nodes, size=2, replace=False)
        try:
            d = nx.shortest_path_length(graph, u, v)
        except nx.NetworkXNoPath:
            continue
        total += d
        pairs += 1
    return total / pairs if pairs else None


def _louvain_partition(projection: nx.Graph, config: SimulationConfig) -> List[Set[Hashable]]:
    communities = nx.community.louvain_communities(
        projection, seed=config.louvain_seed, resolution=config.louvain_resolution,
        weight="weight",
    )
    return sorted((set(c) for c in communities),
                  key=lambda c: (-len(c), min(str(n) for n in c)))


def _partition_lookup(partition: Sequence[Set[Hashable]]) -> Dict[Hashable, int]:
    return {node: idx for idx, comm in enumerate(partition) for node in comm}


def _nmi(part_a: Sequence[Set[Hashable]], part_b: Sequence[Set[Hashable]]) -> float:
    """Normalised mutual information between two partitions over common nodes.

    Uses scikit-learn when available; otherwise a pure-python equivalent
    (arithmetic-mean normalisation, matching sklearn's default).
    """
    map_a, map_b = _partition_lookup(part_a), _partition_lookup(part_b)
    common = sorted((set(map_a) & set(map_b)), key=str)
    if not common:
        return 0.0
    labels_a = [map_a[n] for n in common]
    labels_b = [map_b[n] for n in common]
    try:
        from sklearn.metrics import normalized_mutual_info_score

        return float(normalized_mutual_info_score(labels_a, labels_b))
    except ImportError:
        pass
    n = len(common)
    import math
    from collections import Counter

    joint = Counter(zip(labels_a, labels_b))
    marg_a, marg_b = Counter(labels_a), Counter(labels_b)
    mi = sum(
        (c / n) * math.log((c / n) / ((marg_a[a] / n) * (marg_b[b] / n)))
        for (a, b), c in joint.items()
    )
    h_a = -sum((c / n) * math.log(c / n) for c in marg_a.values())
    h_b = -sum((c / n) * math.log(c / n) for c in marg_b.values())
    denom = math.sqrt(h_a * h_b) if h_a > 0 and h_b > 0 else 0.0
    if denom == 0.0:
        return 1.0 if set(labels_a) == set(labels_b) else 0.0
    return max(0.0, mi / denom)


# ---------------------------------------------------------------------------
# Metrics snapshot
# ---------------------------------------------------------------------------

def snapshot_metrics(
    graph: nx.MultiDiGraph,
    projection: nx.Graph,
    config: SimulationConfig,
) -> Dict[str, Any]:
    """Recompute the full metric battery for a (possibly damaged) graph."""
    n = graph.number_of_nodes()
    m = graph.number_of_edges()
    if n == 0:
        return {
            "nodes": 0, "edges": 0, "density": None, "fragmentation": 1.0,
            "weak_components": 0, "gcc_size": 0, "gcc_fraction": 0.0,
            "global_efficiency": None, "avg_shortest_path_gcc": None,
            "num_communities": 0, "modularity": None,
        }

    gcc = max(nx.connected_components(projection), key=len)
    gcc_size = len(gcc)
    gcc_sub = projection.subgraph(gcc)

    efficiency = _global_efficiency(projection, config)
    apl: Optional[float] = None
    if gcc_size >= 2:
        if gcc_size <= config.efficiency_exact_limit:
            apl = float(nx.average_shortest_path_length(gcc_sub))
        else:
            apl = _sampled_apl(gcc_sub, config)

    communities = _louvain_partition(projection, config)
    modularity = float(
        nx.community.modularity(projection, communities, weight="weight")
    ) if len(communities) > 0 else None

    return {
        "nodes": n,
        "edges": m,
        "density": _round(nx.density(graph)),
        "fragmentation": _round(1.0 - gcc_size / n),
        "weak_components": nx.number_weakly_connected_components(graph),
        "gcc_size": gcc_size,
        "gcc_fraction": _round(gcc_size / n),
        "global_efficiency": _round(efficiency),
        "avg_shortest_path_gcc": _round(apl),
        "num_communities": len(communities),
        "modularity": _round(modularity),
    }


# ---------------------------------------------------------------------------
# Baseline ranking
# ---------------------------------------------------------------------------

def baseline_ranking(graph: nx.MultiDiGraph, config: SimulationConfig) -> List[Dict[str, Any]]:
    """Rank nodes by a composite of PageRank, betweenness and degree centrality.

    Prefers the precomputed ``metrics`` block attached by the analytics
    pipeline and falls back to computing missing metrics on the fly.
    """
    projection = undirected_weighted_projection(graph)
    need_betweenness = any(
        "betweenness_centrality" not in (data.get("metrics") or {})
        for _, data in graph.nodes(data=True)
    )
    computed_betweenness = (
        nx.betweenness_centrality(projection, weight="weight") if need_betweenness else {}
    )

    entries: List[Dict[str, Any]] = []
    for node, data in graph.nodes(data=True):
        metrics = data.get("metrics") or {}
        pagerank = float(metrics.get("pagerank") or 0.0)
        betweenness = float(metrics.get("betweenness_centrality")
                            or computed_betweenness.get(node, 0.0))
        degree = float(metrics.get("degree_centrality")
                       or graph.degree(node) / max(1, graph.number_of_nodes() - 1))
        entries.append(
            {
                "guid": node,
                "name": _display_name(graph, node),
                "entity_type": data.get("entity_type", "unknown"),
                "pagerank": pagerank,
                "betweenness_centrality": betweenness,
                "degree_centrality": degree,
            }
        )

    for key in ("pagerank", "betweenness_centrality", "degree_centrality"):
        values = [e[key] for e in entries]
        lo, hi = (min(values), max(values)) if values else (0.0, 1.0)
        span = (hi - lo) or 1.0
        for e in entries:
            e[f"_{key}_norm"] = (e[key] - lo) / span
    for e in entries:
        e["composite_score"] = _round(
            config.rank_weight_pagerank * e["_pagerank_norm"]
            + config.rank_weight_betweenness * e["_betweenness_centrality_norm"]
            + config.rank_weight_degree * e["_degree_centrality_norm"]
        )
        for key in ("_pagerank_norm", "_betweenness_centrality_norm", "_degree_centrality_norm"):
            del e[key]

    entries.sort(key=lambda e: (-e["composite_score"], e["name"]))
    for rank, entry in enumerate(entries, start=1):
        entry["baseline_rank"] = rank
    return entries


# ---------------------------------------------------------------------------
# Single-node removal simulation
# ---------------------------------------------------------------------------

def simulate_node_removal(
    graph: nx.MultiDiGraph,
    node: Hashable,
    baseline: Mapping[str, Any],
    baseline_partition: Sequence[Set[Hashable]],
    config: SimulationConfig,
    embeddings: Optional[Mapping[Hashable, np.ndarray]] = None,
) -> Dict[str, Any]:
    """Arrest one node and recompute density / fragmentation / paths / communities."""
    if node not in graph:
        raise SimulationError(f"node {node!r} not present in graph")
    damaged = graph.copy()
    damaged.remove_node(node)
    damaged_projection = undirected_weighted_projection(damaged)
    after = snapshot_metrics(damaged, damaged_projection, config)

    after_partition = _louvain_partition(damaged_projection, config)
    nmi = _nmi(baseline_partition, after_partition)

    baseline_eff = baseline.get("global_efficiency") or 0.0
    after_eff = after.get("global_efficiency") or 0.0
    eff_loss = (baseline_eff - after_eff) / baseline_eff if baseline_eff > 1e-12 else 0.0

    baseline_apl = baseline.get("avg_shortest_path_gcc")
    after_apl = after.get("avg_shortest_path_gcc")
    path_increase: Optional[float] = None
    if baseline_apl and after_apl and baseline_apl > 1e-12:
        path_increase = max(0.0, (after_apl - baseline_apl) / baseline_apl)

    frag_delta = after["fragmentation"] - baseline["fragmentation"]
    gcc_loss = (baseline["gcc_size"] - after["gcc_size"]) / max(1, baseline["nodes"])
    mod_drop = max(0.0, (baseline.get("modularity") or 0.0) - (after.get("modularity") or 0.0)) \
        / max(abs(baseline.get("modularity") or 0.0), 1e-9)

    # how many baseline communities got split across several after-communities
    after_lookup = _partition_lookup(after_partition)
    baseline_map = _partition_lookup(baseline_partition)
    split_count = 0
    for comm in baseline_partition:
        survivors = [after_lookup[n] for n in comm if n in after_lookup]
        if len(survivors) >= 2 and len(set(survivors)) > 1:
            split_count += 1

    breakdown = {
        "fragmentation_increase": _round(max(0.0, frag_delta)),
        "efficiency_loss": _round(max(0.0, eff_loss)),
        "community_disruption": _round(max(0.0, 1.0 - nmi)),
        "gcc_loss": _round(max(0.0, gcc_loss)),
        "path_length_increase": _round(max(0.0, path_increase or 0.0)),
        "modularity_drop": _round(min(1.0, mod_drop)),
    }
    weights = {
        "fragmentation_increase": config.impact_weight_fragmentation,
        "efficiency_loss": config.impact_weight_efficiency,
        "community_disruption": config.impact_weight_community,
        "gcc_loss": config.impact_weight_gcc,
        "path_length_increase": config.impact_weight_paths,
        "modularity_drop": config.impact_weight_modularity,
    }
    impact = sum(weights[k] * breakdown[k] for k in weights)

    successors: List[Dict[str, Any]] = []
    if embeddings is not None and node in embeddings:
        sims = [
            (cosine_similarity(embeddings[node], embeddings[other]), other)
            for other in damaged.nodes() if other in embeddings
        ]
        sims.sort(key=lambda sv: (-sv[0], str(sv[1])))
        for sim, other in sims[: config.successor_candidates]:
            successors.append(
                {
                    "guid": other,
                    "name": _display_name(graph, other),
                    "cosine_similarity": _round(sim),
                }
            )

    return {
        "removed": node,
        "after": after,
        "delta": {
            "density_delta": _round((after["density"] or 0.0) - (baseline["density"] or 0.0)),
            "fragmentation_delta": _round(frag_delta),
            "global_efficiency_loss_rel": _round(eff_loss),
            "avg_path_increase_rel": _round(path_increase) if path_increase is not None else None,
            "gcc_size_loss": int(baseline["gcc_size"] - after["gcc_size"]),
            "modularity_delta": _round((after.get("modularity") or 0.0) - (baseline.get("modularity") or 0.0)),
        },
        "community_changes": {
            "num_communities_before": baseline["num_communities"],
            "num_communities_after": after["num_communities"],
            "nmi_vs_baseline": _round(nmi),
            "split_baseline_communities": split_count,
        },
        "impact_breakdown": breakdown,
        "impact_score": _round(impact),
        "role_inheritor_candidates": successors,
    }


def _disruption_class(impact: float, config: SimulationConfig) -> str:
    if impact >= config.critical_threshold:
        return "critical"
    if impact >= config.high_threshold:
        return "high"
    if impact >= config.medium_threshold:
        return "medium"
    return "low"


def _rationale(result: Mapping[str, Any], breakdown: Mapping[str, float]) -> str:
    labels = {
        "fragmentation_increase": "network fragmentation",
        "efficiency_loss": "information-flow efficiency",
        "community_disruption": "community structure",
        "gcc_loss": "giant-component shrinkage",
        "path_length_increase": "mean path lengths",
        "modularity_drop": "modularity",
    }
    top = sorted(breakdown.items(), key=lambda kv: -kv[1])[:2]
    parts = [f"{labels[key]} (+{value:.3f})" for key, value in top if value > 1e-9]
    if not parts:
        return "Removal has negligible structural impact."
    return "Removal primarily damages " + " and ".join(parts) + "."


# ---------------------------------------------------------------------------
# Public pipeline
# ---------------------------------------------------------------------------

def run_arrest_simulation(
    graph: nx.MultiDiGraph,
    config: Optional[SimulationConfig] = None,
) -> Dict[str, Any]:
    """Run the full Part B pipeline and return the simulation_results document."""
    config = config or SimulationConfig()
    projection = undirected_weighted_projection(graph)
    baseline = snapshot_metrics(graph, projection, config)
    baseline_partition = _louvain_partition(projection, config)

    ranking = baseline_ranking(graph, config)
    top_k = min(config.top_k, len(ranking))
    targets = ranking[:top_k]
    logger.info("baseline: %d nodes / %d edges; simulating top %d of %d",
                graph.number_of_nodes(), graph.number_of_edges(), top_k, len(ranking))

    embeddings: Optional[Dict[Hashable, np.ndarray]] = None
    if config.use_embedding_successors:
        logger.info("computing baseline Node2Vec embeddings for role-inheritor analysis")
        embeddings = node2vec_embeddings(graph, config.embedding)

    simulations: List[Dict[str, Any]] = []
    for progress, entry in enumerate(targets, start=1):
        result = simulate_node_removal(
            graph, entry["guid"], baseline, baseline_partition, config, embeddings
        )
        simulations.append(
            {
                "guid": entry["guid"],
                "name": entry["name"],
                "entity_type": entry["entity_type"],
                "baseline_rank": entry["baseline_rank"],
                "baseline_composite_score": entry["composite_score"],
                **result,
            }
        )
        if progress % 10 == 0 or progress == top_k:
            logger.info("simulated %d/%d removals", progress, top_k)

    simulations.sort(key=lambda s: (-s["impact_score"], s["name"]))
    for rank, sim in enumerate(simulations, start=1):
        sim["rank"] = rank
        sim["disruption_class"] = _disruption_class(sim["impact_score"], config)

    interventions = [
        {
            "rank": sim["rank"],
            "guid": sim["guid"],
            "name": sim["name"],
            "entity_type": sim["entity_type"],
            "impact_score": sim["impact_score"],
            "disruption_class": sim["disruption_class"],
            "key_effects": [
                {"effect": key, "magnitude": value}
                for key, value in sorted(
                    sim["impact_breakdown"].items(), key=lambda kv: -kv[1]
                )[:3]
            ],
            "rationale": _rationale(sim, sim["impact_breakdown"]),
        }
        for sim in simulations
    ]

    impacts = [s["impact_score"] for s in simulations] or [0.0]
    document = {
        "meta": {
            "engine": "SentinelGraph Arrest Simulation",
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_graph": {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
            },
            "config": {
                "top_k": config.top_k,
                "simulated": top_k,
                "ranking_weights": {
                    "pagerank": config.rank_weight_pagerank,
                    "betweenness": config.rank_weight_betweenness,
                    "degree": config.rank_weight_degree,
                },
                "impact_weights": {
                    "fragmentation": config.impact_weight_fragmentation,
                    "efficiency": config.impact_weight_efficiency,
                    "community_nmi": config.impact_weight_community,
                    "gcc": config.impact_weight_gcc,
                    "paths": config.impact_weight_paths,
                    "modularity": config.impact_weight_modularity,
                },
                "disruption_thresholds": {
                    "critical": config.critical_threshold,
                    "high": config.high_threshold,
                    "medium": config.medium_threshold,
                },
                "role_inheritor_analysis": config.use_embedding_successors,
            },
        },
        "baseline": baseline,
        "ranking_basis": ranking,
        "simulations": simulations,
        "optimal_interventions": interventions,
        "summary": {
            "requested_top_k": config.top_k,
            "simulated": top_k,
            "mean_impact": _round(float(np.mean(impacts))),
            "max_impact": _round(float(np.max(impacts))),
            "most_disruptive": interventions[0]["name"] if interventions else None,
            "least_disruptive": interventions[-1]["name"] if interventions else None,
            "class_distribution": {
                klass: sum(1 for s in simulations if s["disruption_class"] == klass)
                for klass in ("critical", "high", "medium", "low")
            },
        },
    }
    return _json_safe(document)


def write_results(document: Mapping[str, Any], out_path: str | Path) -> Path:
    """Serialise the simulation_results document (pretty, UTF-8, JSON-safe)."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(document), indent=2, ensure_ascii=False))
    return path


# ---------------------------------------------------------------------------
# FastAPI-friendly cached loaders
# ---------------------------------------------------------------------------

def load_simulation_results(path: str | Path | None = None) -> Dict[str, Any]:
    """Load ``simulation_results.json`` (cached, no recomputation)."""
    p = Path(path) if path else _MODULE_DIR / "output" / SIMULATION_RESULTS_NAME
    if not p.exists():
        raise FileNotFoundError(f"simulation results not found at {p}")
    return json.loads(p.read_text())


def get_top_interventions(k: int = 10, path: str | Path | None = None) -> List[Dict[str, Any]]:
    """The top-K ranked optimal interventions."""
    return load_simulation_results(path).get("optimal_interventions", [])[:k]


def get_node_simulation(guid: str, path: str | Path | None = None) -> Optional[Dict[str, Any]]:
    """Simulation record for one node (or None)."""
    for sim in load_simulation_results(path).get("simulations", []):
        if sim["guid"] == guid:
            return sim
    return None


# ---------------------------------------------------------------------------
# Counterfactual simulation API (Phase J / Phase K)
# ---------------------------------------------------------------------------
#
# IMPORTANT SAFETY / PRODUCT CONSTRAINT
#
# Everything in this section is a *counterfactual network simulation*: it
# recomputes graph statistics under a hypothetical removal.  It is NOT an
# arrest recommendation, NOT an enforcement suggestion, and NOT a prediction
# of real-world behaviour.  Callers must present results as analytical
# what-ifs for human review only.


def build_simulation_context(
    graph: nx.MultiDiGraph,
    *,
    config: Optional[SimulationConfig] = None,
    new_broker_sample: int = 300,
) -> Dict[str, Any]:
    """Precompute the expensive graph-wide context once (baseline metrics,
    baseline partition, sampled betweenness) so repeated counterfactual
    requests against the same artifact are fast.  Cache this per artifact
    file (keyed by path + mtime) in the API layer."""
    config = config or SimulationConfig()
    projection = undirected_weighted_projection(graph)
    return {
        "baseline": snapshot_metrics(graph, projection, config),
        "baseline_partition": _louvain_partition(projection, config),
        "baseline_betweenness": _approx_betweenness(
            projection, new_broker_sample, config.louvain_seed
        ),
    }


def counterfactual_node_removal(
    graph: nx.MultiDiGraph,
    node: Hashable,
    *,
    depth: int = 2,
    include_reranking: bool = True,
    config: Optional[SimulationConfig] = None,
    new_broker_sample: int = 300,
    reroute_pairs: int = 25,
    precomputed: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Simulate the removal of one node and return the full counterfactual
    payload for the API/UI:

    baseline metrics, counterfactual metrics, metric deltas, fragmentation
    and connectivity scores, community changes, newly-central nodes
    ("new brokers"), alternate paths (network adaptation), affected
    nodes/edges, warnings, and an explicit simulation method label.
    """
    config = config or SimulationConfig()
    if node not in graph:
        raise SimulationError(f"node {node!r} not present in graph")
    depth = max(1, min(int(depth), 4))

    warnings: List[str] = [
        "Counterfactual simulation only: no real-world action is implied or "
        "recommended.",
        "Community detection is stochastic (seeded); exact boundaries may vary "
        "between runs.",
    ]
    if graph.number_of_nodes() > config.efficiency_exact_limit:
        warnings.append(
            "Global efficiency is sampled for graphs above "
            f"{config.efficiency_exact_limit} nodes; values are approximate."
        )

    # ------------------------------------------------------------- baseline
    precomputed = precomputed or {}
    projection = undirected_weighted_projection(graph)
    baseline = precomputed.get("baseline") or snapshot_metrics(graph, projection, config)
    baseline_partition = precomputed.get("baseline_partition") or _louvain_partition(
        projection, config
    )
    baseline_betweenness = precomputed.get("baseline_betweenness") or _approx_betweenness(
        projection, new_broker_sample, config.louvain_seed
    )

    # --------------------------------------------------------- ego context
    try:
        ego = nx.ego_graph(projection, node, radius=depth)
    except nx.NetworkXError:
        ego = projection.subgraph([node])
    affected_nodes = sorted((str(n) for n in ego.nodes() if n != node), key=str)
    affected_edges = []
    for _, v, attrs in graph.out_edges(node, data=True):
        affected_edges.append({"source": str(node), "target": str(v),
                               "relation": attrs.get("relation", "RELATED_TO"),
                               "id": attrs.get("id")})
    for u, _, attrs in graph.in_edges(node, data=True):
        affected_edges.append({"source": str(u), "target": str(node),
                               "relation": attrs.get("relation", "RELATED_TO"),
                               "id": attrs.get("id")})

    # ------------------------------------------------------------ removal
    damaged = graph.copy()
    damaged.remove_node(node)
    damaged_projection = undirected_weighted_projection(damaged)
    after = snapshot_metrics(damaged, damaged_projection, config)
    after_partition = _louvain_partition(damaged_projection, config)
    after_betweenness = _approx_betweenness(
        damaged_projection, new_broker_sample, config.louvain_seed
    )

    # ------------------------------------------------------- metric deltas
    baseline_eff = baseline.get("global_efficiency") or 0.0
    after_eff = after.get("global_efficiency") or 0.0
    connectivity_change = (
        (baseline_eff - after_eff) / baseline_eff if baseline_eff > 1e-12 else 0.0
    )
    fragmentation_score = after.get("fragmentation")
    fragmentation_delta = after["fragmentation"] - baseline["fragmentation"]

    nmi = _nmi(baseline_partition, after_partition)
    after_lookup = _partition_lookup(after_partition)
    baseline_map = _partition_lookup(baseline_partition)
    split_communities = []
    for idx, comm in enumerate(baseline_partition):
        survivors = {after_lookup[n] for n in comm if n in after_lookup}
        if len(survivors) > 1:
            split_communities.append(idx)
    merged_count = _count_merges(baseline_map, after_partition)

    community_changes = {
        "num_communities_before": baseline["num_communities"],
        "num_communities_after": after["num_communities"],
        "nmi_vs_baseline": _round(nmi),
        "split_baseline_communities": split_communities,
        "merged_communities": merged_count,
    }

    # -------------------------------------------------------- new brokers
    new_brokers: List[Dict[str, Any]] = []
    for n in damaged_projection.nodes():
        before = float(baseline_betweenness.get(n, 0.0))
        gain = float(after_betweenness.get(n, 0.0)) - before
        if gain > 1e-9:
            new_brokers.append({
                "guid": str(n),
                "name": _display_name(graph, n),
                "betweenness_gain": _round(gain),
                "betweenness_after": _round(float(after_betweenness.get(n, 0.0))),
            })
    new_brokers.sort(key=lambda item: (-item["betweenness_gain"], item["name"]))
    new_brokers = new_brokers[:10]

    # ---------------------------------------------------- rerouting paths
    alternate_paths: List[Dict[str, Any]] = []
    rerouting_score: Optional[float] = None
    if include_reranking:
        alternate_paths, rerouting_score = _rerouting_analysis(
            graph, damaged_projection, node, reroute_pairs
        )

    # -------------------------------------------------------- composition
    delta = {
        "density_delta": _round((after["density"] or 0.0) - (baseline["density"] or 0.0)),
        "fragmentation_delta": _round(fragmentation_delta),
        "global_efficiency_loss_rel": _round(connectivity_change),
        "gcc_size_loss": int(baseline["gcc_size"] - after["gcc_size"]),
        "modularity_delta": _round(
            (after.get("modularity") or 0.0) - (baseline.get("modularity") or 0.0)
        ),
    }

    return _json_safe({
        "simulation_id": f"SIM-{uuid.uuid4().hex[:12].upper()}",
        "target_node_id": str(node),
        "target_name": _display_name(graph, node),
        "depth": depth,
        "baseline": baseline,
        "counterfactual": after,
        "delta": delta,
        "fragmentation_score": fragmentation_score,
        "connectivity_change": _round(connectivity_change),
        "community_changes": community_changes,
        "new_brokers": new_brokers,
        "alternate_paths": alternate_paths,
        "rerouting_score": _round(rerouting_score) if rerouting_score is not None else None,
        "affected_nodes": affected_nodes,
        "affected_node_count": len(affected_nodes),
        "affected_edges": affected_edges,
        "warnings": warnings,
        "method": "NODE_REMOVAL_COUNTERFACTUAL",
        "disclaimer": (
            "NETWORK EFFECT SCORE - analytical counterfactual, NOT an "
            "enforcement recommendation."
        ),
    })


def _approx_betweenness(projection: nx.Graph, k: int, seed: int) -> Dict[Hashable, float]:
    """Sampled betweenness centrality (exact for small graphs)."""
    n = projection.number_of_nodes()
    if n == 0:
        return {}
    if n <= 1200:
        return nx.betweenness_centrality(projection, weight="weight")
    k = min(k, n)
    return nx.betweenness_centrality(projection, k=k, weight="weight", seed=seed)


def _count_merges(baseline_map: Mapping[Hashable, int],
                  after_partition: Sequence[Set[Hashable]]) -> int:
    """How many after-communities span multiple baseline communities."""
    mapping: Dict[int, Set[int]] = {}
    for after_idx, comm in enumerate(after_partition):
        for n in comm:
            before = baseline_map.get(n)
            if before is not None:
                mapping.setdefault(after_idx, set()).add(before)
    return sum(1 for spans in mapping.values() if len(spans) > 1)


def _rerouting_analysis(
    graph: nx.MultiDiGraph,
    damaged_projection: nx.Graph,
    node: Hashable,
    pair_budget: int,
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    """Transparent rerouting simulation (Phase K).

    For sampled former neighbour pairs that were connected *through* the
    removed node, check whether an alternate path still exists and record
    it.  ``rerouting_score`` = fraction of broken pairs that reconnected.
    All outcomes are simulated alternatives, not predictions.
    """
    former_neighbors = set(graph.neighbors(node)) if node in graph else set()
    if len(former_neighbors) < 2:
        return [], None
    nodes_list = sorted(former_neighbors, key=str)
    pairs: List[Tuple[Hashable, Hashable]] = []
    rng = random.Random(42)
    for _ in range(pair_budget):
        u, v = rng.sample(nodes_list, 2)
        if u != v:
            pairs.append((u, v))

    alternate_paths: List[Dict[str, Any]] = []
    found, attempted = 0, 0
    for u, v in pairs:
        attempted += 1
        try:
            path = nx.shortest_path(damaged_projection, u, v, weight=None)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        found += 1
        if len(alternate_paths) < 10:
            alternate_paths.append({
                "source": str(u),
                "target": str(v),
                "length": len(path) - 1,
                "path": [str(p) for p in path[:12]],
                "note": "alternate path after simulated removal",
            })
    score = (found / attempted) if attempted else None
    return alternate_paths, score


def compare_interventions(
    graph: nx.MultiDiGraph,
    node_ids: Sequence[Hashable],
    *,
    config: Optional[SimulationConfig] = None,
) -> Dict[str, Any]:
    """Intervention comparison sandbox (Phase M).

    Runs the counterfactual removal for each requested node and returns a
    side-by-side comparison ranked by network effect.  The ranking is a
    NETWORK EFFECT SCORE, explicitly NOT an enforcement recommendation.
    """
    config = config or SimulationConfig()
    scenarios: List[Dict[str, Any]] = []
    for raw_id in node_ids:
        node = raw_id
        try:
            result = counterfactual_node_removal(
                graph, node, depth=1, include_reranking=False, config=config,
            )
        except SimulationError as exc:
            scenarios.append({"node_id": str(node), "error": str(exc)})
            continue
        scenarios.append({
            "node_id": str(node),
            "name": result["target_name"],
            "fragmentation_score": result["fragmentation_score"],
            "connectivity_change": result["connectivity_change"],
            "gcc_size_loss": result["delta"]["gcc_size_loss"],
            "communities_after": result["community_changes"]["num_communities_after"],
            "affected_node_count": result["affected_node_count"],
            "warnings": result["warnings"],
        })

    ranked = [s for s in scenarios if "error" not in s]
    ranked.sort(key=lambda s: (
        -(s["fragmentation_score"] or 0.0),
        -(s["connectivity_change"] or 0.0),
    ))
    for rank, scenario in enumerate(ranked, start=1):
        scenario["network_effect_rank"] = rank

    return {
        "scenarios": scenarios,
        "ranking_note": "NETWORK EFFECT SCORE - NOT AN ENFORCEMENT RECOMMENDATION",
        "method": "INTERVENTION_COMPARISON_SANDBOX",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:  # pragma: no cover - manual invocation helper
    parser = argparse.ArgumentParser(description="SentinelGraph Part B: arrest simulation")
    parser.add_argument("--graph", "-g", default=str(_MODULE_DIR / "output" / "graph.pkl"))
    parser.add_argument("--out", "-o", default=str(_MODULE_DIR / "output" / SIMULATION_RESULTS_NAME))
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--no-embeddings", action="store_true",
                        help="skip Node2Vec role-inheritor analysis")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    config = SimulationConfig(top_k=args.top_k, louvain_seed=args.seed)
    if args.no_embeddings:
        config.use_embedding_successors = False

    graph = load_graph(args.graph)
    document = run_arrest_simulation(graph, config)
    out = write_results(document, args.out)

    summary = document["summary"]
    print("Arrest simulation finished.")
    print(f"  baseline              : {document['baseline']['nodes']} nodes / "
          f"{document['baseline']['edges']} edges / density "
          f"{document['baseline']['density']} / fragmentation "
          f"{document['baseline']['fragmentation']}")
    print(f"  simulated removals    : {summary['simulated']} (top_k={summary['requested_top_k']})")
    print(f"  mean / max impact     : {summary['mean_impact']} / {summary['max_impact']}")
    print(f"  class distribution    : {summary['class_distribution']}")
    print(f"  written               : {out}")
    print("  top interventions:")
    for item in document["optimal_interventions"][:5]:
        print(f"    #{item['rank']} {item['name']:<28} impact={item['impact_score']:.3f} "
              f"[{item['disruption_class']}]")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
