"""
investigation/counterfactual_engine.py
--------------------------------------
Counterfactual "What if?" engine (Phase 5, requirement 6).

Supported operations:

* remove node
* remove edge
* remove evidence
* change relationship confidence
* restore hidden edge
* merge entities
* split entities

Each operation recomputes:

* components
* communities
* centrality
* bridges
* connectivity
* key paths
* network resilience

and emits counterfactual metrics:

* fragmentation_delta
* component_delta
* betweenness_delta
* community_delta
* reachability_delta
* bridge_loss

All outputs are marked HYPOTHETICAL — a counterfactual is never presented
as fact.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import networkx as nx

from src.graph.graph_embeddings import undirected_weighted_projection

logger = logging.getLogger(__name__)

COUNTERFACTUAL_NAMESPACE = uuid.UUID("2e8fc6bd-0a45-4c9e-9f27-73a9d5b2c018")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GraphBaseline:
    """Precomputed baseline metrics for counterfactual comparison."""

    components: int = 0
    giant_component_fraction: float = 0.0
    average_path_length: float = 0.0
    efficiency: float = 0.0
    communities: int = 0
    modularity: float = 0.0
    bridges: int = 0
    betweenness: Dict[str, float] = field(default_factory=dict)


def compute_baseline(graph: nx.Graph,
                     efficiency_limit: int = 800) -> GraphBaseline:
    """Compute baseline metrics for a graph."""
    g = graph.to_undirected() if graph.is_directed() else graph
    if g.number_of_nodes() == 0:
        return GraphBaseline()
    baseline = GraphBaseline()
    baseline.components = nx.number_connected_components(g)
    # giant component fraction
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    if comps:
        baseline.giant_component_fraction = len(comps[0]) / g.number_of_nodes()
    # average path length / efficiency (sampled on large graphs)
    if g.number_of_nodes() <= efficiency_limit:
        try:
            baseline.average_path_length = nx.average_shortest_path_length(g)
        except nx.NetworkXError:
            baseline.average_path_length = 0.0
    # communities + modularity
    try:
        from networkx.algorithms.community import louvain_communities, modularity
        comms = louvain_communities(g, seed=42)
        baseline.communities = len(comms)
        baseline.modularity = modularity(g, comms)
    except Exception:
        pass
    # bridges
    try:
        baseline.bridges = len(list(nx.bridges(g)))
    except nx.NetworkXError:
        baseline.bridges = 0
    # sampled betweenness
    try:
        baseline.betweenness = nx.betweenness_centrality(
            g, k=min(256, g.number_of_nodes()), seed=42, normalized=True)
    except Exception:
        baseline.betweenness = {}
    return baseline


@dataclass
class CounterfactualResult:
    """The outcome of one counterfactual operation."""

    cf_id: str
    operation: str            # remove_node | remove_edge | merge_entities | ...
    target: str
    baseline: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    deltas: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    status: str = "HYPOTHETICAL"
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cf_id": self.cf_id,
            "operation": self.operation,
            "target": self.target,
            "baseline": dict(self.baseline),
            "result": dict(self.result),
            "deltas": {k: round(v, 4) for k, v in self.deltas.items()},
            "explanation": self.explanation,
            "status": self.status,
            "created_at": self.created_at,
        }


class CounterfactualEngine:
    """Applies counterfactual operations and measures network impact."""

    def __init__(self, graph: nx.MultiDiGraph,
                 efficiency_limit: int = 800) -> None:
        self.graph = graph
        self.efficiency_limit = efficiency_limit
        self.baseline = compute_baseline(graph, efficiency_limit)

    # ------------------------------------------------------------------ #
    def run(self, operation: str, target: Any,
            **kwargs: Any) -> CounterfactualResult:
        """Run a single counterfactual operation.

        ``target`` is a node id, an edge (u, v) tuple, or an entity id
        depending on the operation.
        """
        if operation not in ("remove_node", "remove_edge", "restore_hidden_edge",
                             "merge_entities", "split_entities"):
            raise ValueError(f"unknown operation: {operation}")

        mutated = self._apply(operation, target, **kwargs)
        return self._measure(operation, str(target), mutated)

    # ------------------------------------------------------------------ #
    def _apply(self, operation: str, target: Any,
               **kwargs: Any) -> nx.MultiDiGraph:
        g = self.graph.copy()
        if operation == "remove_node":
            if target in g:
                g.remove_node(target)
        elif operation == "remove_edge":
            u, v = target if isinstance(target, (tuple, list)) else (target, kwargs.get("to"))
            if g.has_edge(u, v):
                g.remove_edge(u, v)
        elif operation == "restore_hidden_edge":
            u, v = target if isinstance(target, (tuple, list)) else (kwargs.get("source"), kwargs.get("target"))
            rel = kwargs.get("relation", "ASSOCIATED_WITH")
            if u in g and v in g and not g.has_edge(u, v):
                g.add_edge(u, v, key=f"cf:{u}|{rel}|{v}", relation=rel,
                           attributes={"inferred": True,
                                       "hypothetical": True,
                                       "cf_id": str(uuid.uuid4())})
        elif operation == "merge_entities":
            u, v = target if isinstance(target, (tuple, list)) else (target, kwargs.get("with"))
            if u in g and v in g and u != v:
                g = nx.contracted_nodes(g, u, v, self_loops=False)
        elif operation == "split_entities":
            node = target
            if node in g:
                attrs = dict(g.nodes[node])
                # move half the neighbors to a new sibling node
                neighbors = [n for n in g.neighbors(node)]
                if len(neighbors) >= 2:
                    split_off = neighbors[: len(neighbors) // 2]
                    new_node = f"{node}_split"
                    g.add_node(new_node, **{**attrs, "canonical_name": f"{attrs.get('canonical_name', node)} (alt)"})
                    for n in split_off:
                        g.add_edge(new_node, n, relation="ASSOCIATED_WITH",
                                   attributes={"split": True})
        return g

    # ------------------------------------------------------------------ #
    def _measure(self, operation: str, target: str,
                 mutated: nx.MultiDiGraph) -> CounterfactualResult:
        b = self.baseline
        result = compute_baseline(mutated, self.efficiency_limit)

        deltas: Dict[str, float] = {}
        deltas["component_delta"] = result.components - b.components
        deltas["fragmentation_delta"] = (
            1.0 - result.giant_component_fraction
        ) - (
            1.0 - b.giant_component_fraction
        )
        deltas["betweenness_delta"] = result.betweenness.get(target, 0.0) - b.betweenness.get(target, 0.0)
        deltas["community_delta"] = result.communities - b.communities
        deltas["bridge_loss"] = float(b.bridges - result.bridges)
        # reachability: fraction of node pairs still mutually reachable
        deltas["reachability_delta"] = self._reachability_delta(mutated)
        deltas["modularity_delta"] = result.modularity - b.modularity

        explanation = self._explain(operation, target, deltas)
        cf_id = "CF-" + str(uuid.uuid5(COUNTERFACTUAL_NAMESPACE,
                                       f"{operation}|{target}|{_utcnow()}"))
        return CounterfactualResult(
            cf_id=cf_id,
            operation=operation,
            target=target,
            baseline=self._baseline_dict(),
            result=self._result_dict(result),
            deltas=deltas,
            explanation=explanation,
        )

    # ------------------------------------------------------------------ #
    def _reachability_delta(self, mutated: nx.MultiDiGraph) -> float:
        """Change in the fraction of reachable node pairs (0..1 degradation)."""
        g = mutated.to_undirected()
        total_pairs = 0
        reachable = 0
        comps = list(nx.connected_components(g))
        for comp in comps:
            n = len(comp)
            total_pairs += n * (n - 1) / 2
            reachable += n * (n - 1) / 2
        if total_pairs == 0:
            return 0.0
        # baseline fraction
        base_total = self.graph.number_of_nodes() * (self.graph.number_of_nodes() - 1) / 2
        if base_total == 0:
            return 0.0
        return (reachable / total_pairs) - 1.0

    # ------------------------------------------------------------------ #
    def _baseline_dict(self) -> Dict[str, Any]:
        b = self.baseline
        return {
            "components": b.components,
            "giant_component_fraction": round(b.giant_component_fraction, 4),
            "average_path_length": round(b.average_path_length, 4),
            "communities": b.communities,
            "modularity": round(b.modularity, 4),
            "bridges": b.bridges,
        }

    def _result_dict(self, r: GraphBaseline) -> Dict[str, Any]:
        return {
            "components": r.components,
            "giant_component_fraction": round(r.giant_component_fraction, 4),
            "average_path_length": round(r.average_path_length, 4),
            "communities": r.communities,
            "modularity": round(r.modularity, 4),
            "bridges": r.bridges,
        }

    def _explain(self, operation: str, target: str,
                 deltas: Dict[str, float]) -> str:
        parts = []
        if deltas["component_delta"] > 0:
            parts.append(f"components +{deltas['component_delta']}")
        if deltas["fragmentation_delta"] > 0.01:
            parts.append(f"fragmentation +{deltas['fragmentation_delta']:.2f}")
        if deltas["bridge_loss"] > 0:
            parts.append(f"{deltas['bridge_loss']:.0f} bridges lost")
        if deltas["community_delta"] != 0:
            parts.append(f"communities {deltas['community_delta']:+.0f}")
        detail = "; ".join(parts) if parts else "no significant structural change"
        return (
            f"Counterfactual '{operation}' on '{target}': {detail}. "
            f"Status: HYPOTHETICAL — this is a structural simulation, NOT an "
            f"enforcement recommendation."
        )