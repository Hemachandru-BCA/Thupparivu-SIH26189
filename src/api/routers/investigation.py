"""
routers/investigation.py
------------------------
Deep-investigation API (route group: /api/investigation/*).

Exposes the CounterfactualEngine (remove node/edge, merge/split, restore
hidden edge...), relationship-gap detection (strong common-neighbor overlap
without an observed edge), and network-resilience analysis (remove top
bridges and measure fragmentation).

Every result is labelled HYPOTHETICAL — counterfactual network changes are
never presented as confirmed facts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import networkx as nx
from fastapi import APIRouter, Body, HTTPException, Query

from src.api import audit, services, services_intel

router = APIRouter(prefix="/api/investigation", tags=["investigation"])

logger = logging.getLogger(__name__)


@router.post("/counterfactual")
def counterfactual(body: Dict[str, Any] = Body(...)):
    """Run one counterfactual operation and return baseline + delta metrics."""
    graph = services.load_graph()
    operation = str(body.get("operation", ""))
    target = body.get("target")

    from src.investigation.counterfactual_engine import CounterfactualEngine

    engine = CounterfactualEngine(graph)
    try:
        result = engine.run(
            operation=operation,
            target=target,
            **body.get("params") or {},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Counterfactual failed: {exc}")

    audit.record_action(
        "investigation.counterfactual",
        object_ids=[str(target)] if target else [],
        detail={"operation": operation},
    )
    return {
        "operation": operation,
        "target": target,
        "hypothetical": True,
        "result": result,
    }


@router.get("/counterfactual/operations")
def list_operations():
    """Supported counterfactual operations for the UI."""
    return {
        "operations": [
            {"id": "remove_node", "label": "Remove entity"},
            {"id": "remove_edge", "label": "Remove relationship"},
            {"id": "restore_hidden_edge", "label": "Restore hidden relationship"},
            {"id": "merge_entities", "label": "Merge entities"},
            {"id": "split_entity", "label": "Split entity"},
            {"id": "change_confidence", "label": "Change relationship confidence"},
            {"id": "remove_evidence", "label": "Remove evidence"},
        ]
    }


# --------------------------------------------------------------------------- #
# Relationship gaps
# --------------------------------------------------------------------------- #

def _undirected(g: nx.MultiDiGraph) -> nx.Graph:
    return nx.to_undirected(g)


@router.get("/relationship-gaps")
def relationship_gaps(
    top_n: int = Query(20, ge=1, le=200),
    min_shared_neighbors: int = Query(3, ge=2, le=50),
):
    """Pairs with unusually strong common-neighbor overlap but no observed edge.

    A relationship gap is a hypothesis: strong structural overlap *suggests*
    a possible missing relationship.  The output explicitly says
    POTENTIAL MISSING RELATIONSHIP — not "hidden relationship confirmed".
    """
    graph = services.load_graph()
    ug = _undirected(graph)
    if ug.number_of_nodes() == 0:
        return {"items": [], "total": 0}

    gaps: List[Dict[str, Any]] = []
    nodes = list(ug.nodes)
    # Sample cheaply: only consider node pairs that share >= 1 neighbor via a
    # two-hop scan on high-degree nodes, bounded for performance.
    sampled = nodes[:4000] if len(nodes) > 4000 else nodes
    for i, a in enumerate(sampled):
        na = set(ug.neighbors(a))
        for b in sampled[i + 1:]:
            if a == b or ug.has_edge(a, b):
                continue
            nb = set(ug.neighbors(b))
            common = na & nb
            if len(common) >= min_shared_neighbors:
                gaps.append({
                    "entity_a": a,
                    "entity_b": b,
                    "name_a": _node_label(graph, a),
                    "name_b": _node_label(graph, b),
                    "common_neighbors": len(common),
                    "common_neighbor_ids": sorted(common)[:12],
                    "jaccard": round(len(common) / max(len(na | nb), 1), 4),
                    "adamic_adar": round(
                        sum(1.0 / max(len(list(ug.neighbors(c))) - 1, 1)
                            for c in common), 4) if common else 0.0,
                })
                if len(gaps) >= top_n * 5:
                    break
        if len(gaps) >= top_n * 5:
            break

    gaps.sort(key=lambda g: -g["adamic_adar"])
    audit.record_action("investigation.relationship_gaps")
    return {"items": gaps[:top_n], "total": len(gaps),
            "note": "POTENTIAL MISSING RELATIONSHIP — requires human review"}


def _node_label(graph: nx.MultiDiGraph, node) -> str:
    return (graph.nodes[node].get("canonical_name")
            or graph.nodes[node].get("label")
            or str(node))


# --------------------------------------------------------------------------- #
# Network resilience
# --------------------------------------------------------------------------- #

@router.post("/resilience")
def network_resilience(body: Dict[str, Any] = Body(...)):
    """Remove the top-N nodes by centrality and measure fragmentation impact."""
    graph = services.load_graph()
    n = int(body.get("top_n", 5))
    metric = str(body.get("metric", "pagerank"))

    if n < 1 or n > 50:
        raise HTTPException(status_code=422, detail="top_n must be 1..50")
    ug = graph.to_undirected()
    if ug.number_of_nodes() == 0:
        return {"items": [], "baseline": {}, "note": "EMPTY_GRAPH"}

    def fragmentation(g: nx.Graph) -> float:
        if g.number_of_nodes() == 0:
            return 1.0
        comps = list(nx.connected_components(g))
        return 1.0 - (len(max(comps, key=len)) / g.number_of_nodes())

    baseline_frag = fragmentation(ug)
    baseline_components = nx.number_connected_components(ug)

    scored = []
    for nid in ug.nodes():
        m = graph.nodes[nid].get("metrics") or {}
        if metric == "betweenness":
            score = m.get("betweenness_centrality", 0.0) or 0.0
        elif metric == "degree":
            score = m.get("degree", 0) or 0
        else:
            score = m.get("pagerank", 0.0) or 0.0
        scored.append((nid, score))
    scored.sort(key=lambda x: -x[1])
    top = [nid for nid, _ in scored[:n]]

    steps = []
    for i, nid in enumerate(top):
        g2 = ug.copy()
        g2.remove_node(nid)
        frag = fragmentation(g2)
        comps = nx.number_connected_components(g2)
        steps.append({
            "rank": i + 1,
            "node_id": nid,
            "label": _node_label(graph, nid),
            "score": round(float(dict(scored)[nid]), 6) if nid in dict(scored) else None,
            "fragmentation": round(frag, 4),
            "components": comps,
            "fragmentation_delta": round(frag - baseline_frag, 4),
            "components_delta": comps - baseline_components,
        })

    audit.record_action("investigation.resilience", object_ids=top,
                        detail={"metric": metric, "top_n": n})
    return {
        "metric": metric,
        "baseline": {
            "fragmentation": round(baseline_frag, 4),
            "components": baseline_components,
            "nodes": ug.number_of_nodes(),
            "edges": ug.number_of_edges(),
        },
        "steps": steps,
        "note": "NETWORK RESILIENCE ANALYSIS — structural fragility measure, not attribution",
    }