"""
routers/communities.py
----------------------
Community intelligence API (route group: /api/communities/*).

Provides structural community profiles (size, density, internal/external
edge weight, key entities, bridge entities), entity classification within
communities (CORE / PERIPHERAL / BRIDGE / BROKER...), and a before/after
comparison of two time windows.

Community labels are *analytical* — never legal conclusions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import networkx as nx
from fastapi import APIRouter, Body, HTTPException, Query

from src.api import audit, services

router = APIRouter(prefix="/api/communities", tags=["communities"])


def _community_assignments(graph: nx.MultiDiGraph) -> Dict[str, int]:
    """Louvain community assignment per node."""
    ug = graph.to_undirected()
    if ug.number_of_nodes() == 0:
        return {}
    try:
        from networkx.algorithms.community import louvain_communities

        comms = louvain_communities(ug, seed=42)
        out = {}
        for i, c in enumerate(comms):
            for n in c:
                out[n] = i
        return out
    except Exception:
        out = {}
        for i, c in enumerate(nx.connected_components(ug)):
            for n in c:
                out[n] = i
        return out


def _profile(graph: nx.MultiDiGraph, cid: int, members: set) -> Dict[str, Any]:
    ug = graph.to_undirected()
    internal = 0
    external = 0
    degrees = {}
    for u, v in ug.edges():
        u_in = u in members
        v_in = v in members
        if u_in and v_in:
            internal += 1
        elif u_in or v_in:
            external += 1
    for n in members:
        degrees[n] = ug.degree(n)
    m = len(members)
    max_possible = m * (m - 1) / 2
    density = (internal / max_possible) if max_possible else 0.0

    # bridge entities: members with >= 1 external edge
    bridges = [n for n in members if any(
        (u not in members) or (v not in members) for u, v in ug.edges(n) if u == n or v == n)]
    bridges = sorted(bridges, key=lambda n: -degrees.get(n, 0))[:12]

    key_entities = sorted(members, key=lambda n: -degrees.get(n, 0))[:12]
    return {
        "community_id": f"C{cid:02d}",
        "size": m,
        "density": round(density, 4),
        "internal_edges": internal,
        "external_edges": external,
        "key_entities": [_node_label(graph, n) for n in key_entities],
        "key_entity_ids": list(key_entities),
        "bridge_entities": [_node_label(graph, n) for n in bridges],
        "bridge_entity_ids": list(bridges),
        "total_degree_bridge": sum(degrees.get(n, 0) for n in bridges),
    }


def _node_label(graph: nx.MultiDiGraph, node) -> str:
    return (graph.nodes[node].get("canonical_name")
            or graph.nodes[node].get("label")
            or str(node))


@router.get("")
@router.get("/")
def list_communities(
    min_size: int = Query(2, ge=2, le=100000),
    limit: int = Query(60, ge=1, le=500),
):
    """Community profiles sorted by size (largest first)."""
    graph = services.load_graph()
    assignments = _community_assignments(graph)
    by_comm: Dict[int, set] = {}
    for n, c in assignments.items():
        by_comm.setdefault(c, set()).add(n)

    profiles = []
    for cid, members in by_comm.items():
        if len(members) < min_size:
            continue
        profiles.append(_profile(graph, cid, members))
    profiles.sort(key=lambda p: -p["size"])
    audit.record_action("communities.list")
    return {"items": profiles[:limit], "total": len(profiles)}


@router.get("/{community_id}")
def community_detail(community_id: str):
    """One community profile plus member list."""
    graph = services.load_graph()
    try:
        cid = int(community_id.lstrip("C"))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown community: {community_id}")
    assignments = _community_assignments(graph)
    members = {n for n, c in assignments.items() if c == cid}
    if not members:
        raise HTTPException(status_code=404, detail=f"Community not found: {community_id}")
    profile = _profile(graph, cid, members)
    profile["members"] = [
        {"id": n, "label": _node_label(graph, n),
         "type": graph.nodes[n].get("entity_type", "UNKNOWN"),
         "degree": graph.to_undirected().degree(n)}
        for n in sorted(members, key=lambda n: -graph.to_undirected().degree(n))[:200]
    ]
    return profile


@router.get("/{community_id}/roles")
def community_roles(community_id: str):
    """Classify community members into analytical roles."""
    graph = services.load_graph()
    try:
        cid = int(community_id.lstrip("C"))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown community: {community_id}")
    assignments = _community_assignments(graph)
    members = {n for n, c in assignments.items() if c == cid}
    if not members:
        raise HTTPException(status_code=404, detail=f"Community not found: {community_id}")

    ug = graph.to_undirected()
    roles: List[Dict[str, Any]] = []
    for n in members:
        degree = ug.degree(n)
        external = sum(1 for u, v in ug.edges(n) if (u == n or v == n)
                       and (assignments.get(u) != cid or assignments.get(v) != cid))
        m = graph.nodes[n].get("metrics") or {}
        betweenness = m.get("betweenness_centrality", 0.0) or 0.0
        if external >= 2 and betweenness > 0.05:
            role = "BROKER"
        elif external >= 1:
            role = "BRIDGE"
        elif degree >= 3:
            role = "CORE"
        elif degree >= 1:
            role = "PERIPHERAL"
        else:
            role = "ISOLATE"
        roles.append({
            "id": n, "label": _node_label(graph, n),
            "type": graph.nodes[n].get("entity_type", "UNKNOWN"),
            "role": role, "degree": degree,
            "external_edges": external, "betweenness": round(betweenness, 4),
        })
    roles.sort(key=lambda r: -r["degree"])
    return {"community_id": community_id, "roles": roles[:300]}


@router.post("/compare")
def compare_communities(body: Dict[str, Any] = Body(...)):
    """Before/after community comparison across two time windows.

    body: {"before": {"start": iso, "end": iso}, "after": {"start": iso, "end": iso}}
    """
    from src.api import services_intel

    before = body.get("before") or {}
    after = body.get("after") or {}
    tm = services_intel.temporal_graph()
    g1 = tm.graph_between(before.get("start", ""), before.get("end", ""))
    g2 = tm.graph_between(after.get("start", ""), after.get("end", ""))

    a1 = _community_assignments(g1)
    a2 = _community_assignments(g2)
    by1: Dict[int, set] = {}
    by2: Dict[int, set] = {}
    for n, c in a1.items():
        by1.setdefault(c, set()).add(n)
    for n, c in a2.items():
        by2.setdefault(c, set()).add(n)

    summary = {
        "communities_before": len(by1),
        "communities_after": len(by2),
        "largest_before": max((len(v) for v in by1.values()), default=0),
        "largest_after": max((len(v) for v in by2.values()), default=0),
        "growth": round((len(by2) - len(by1)) / max(len(by1), 1), 4),
    }
    audit.record_action("communities.compare", detail=summary)
    return {"before": {"communities": len(by1), "largest": summary["largest_before"]},
            "after": {"communities": len(by2), "largest": summary["largest_after"]},
            "summary": summary}