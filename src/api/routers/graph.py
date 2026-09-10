"""
routers/graph.py
------------------
Read-only endpoints over the knowledge graph and ghost-node predictions.

Sources (all from api.paths):
    - graph_triplets.json  -> { metadata, entities, triplets, events }
    - ghost_predictions.json
    - graph_data.json       (NetworkX node-link serialized, optional)
    - graph_metrics.json    (graph-level metrics, optional)

Conventions mirror routers/data.py and routers/pipeline.py:
    - router = APIRouter(prefix="/api/graph", tags=["graph"])
    - uses api.paths for file locations
    - uses api.data_access.paginate for consistent pagination
"""

from __future__ import annotations

import json
from typing import Any, Optional

import networkx as nx
from fastapi import APIRouter, HTTPException, Query

from src.api import audit, data_access, paths, services

router = APIRouter(prefix="/api/graph", tags=["graph"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


@router.get("/events")
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    entity_id: Optional[str] = Query(None, description="Only events involving this entity"),
):
    """Expose the events already stored in graph_triplets.json."""
    page, page_size = _page_params(page, page_size)
    rows = _load_triplets_file().get("events", [])
    if entity_id:
        # adjust the key once you inspect one event object's shape
        rows = [e for e in rows if entity_id in (e.get("entities") or e.get("participants") or [])]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _page_params(page: int, page_size: int) -> tuple[int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return page, page_size


def _load_json(path) -> Any:
    """Load a JSON file. Returns None if missing or unreadable so callers
    can decide whether to 404, return [], or return {}."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _load_triplets_file() -> dict:
    """Load graph_triplets.json. Always returns a dict (possibly empty) so
    endpoints never KeyError on a missing/corrupt file."""
    data = _load_json(paths.GRAPH_TRIPLETS_PATH)
    if not isinstance(data, dict):
        return {"metadata": {}, "entities": [], "triplets": [], "events": []}
    data.setdefault("metadata", {})
    data.setdefault("entities", [])
    data.setdefault("triplets", [])
    data.setdefault("events", [])
    return data


def _load_ghost_predictions() -> list[dict]:
    """Load ghost_predictions.json. Tolerates either a top-level list or a
    dict with a 'ghosts' / 'predictions' key. Always returns a list."""
    data = _load_json(paths.GHOST_PREDICTIONS_PATH)
    if data is None:
        return []
    if isinstance(data, list):
        return [g for g in data if isinstance(g, dict)]
    if isinstance(data, dict):
        for key in ("ghosts", "ghost_nodes", "predictions", "nodes", "items"):
            v = data.get(key)
            if isinstance(v, list):
                return [g for g in v if isinstance(g, dict)]
    return []


# --------------------------------------------------------------------------- #
# Metadata / info
# --------------------------------------------------------------------------- #
@router.get("/info")
def graph_info():
    """High-level metadata about the built graph: artifact existence flags,
    entity/triplet/ghost counts, and the raw metadata block from the
    extraction stage. Useful for frontend dashboard / polling."""
    triplets_file = _load_triplets_file()
    ghosts = _load_ghost_predictions()
    metadata = triplets_file.get("metadata", {}) or {}

    return {
        "graph_built": paths.GRAPH_PKL_PATH.exists(),
        "graph_data_exists": paths.GRAPH_DATA_PATH.exists(),
        "graph_metrics_exists": paths.GRAPH_METRICS_PATH.exists(),
        "graph_triplets_exists": paths.GRAPH_TRIPLETS_PATH.exists(),
        "ghost_predictions_exist": paths.GHOST_PREDICTIONS_PATH.exists(),
        "entities_count": len(triplets_file.get("entities", [])),
        "triplets_count": len(triplets_file.get("triplets", [])),
        "events_count": len(triplets_file.get("events", [])),
        "ghost_predictions_count": len(ghosts),
        "metadata": metadata,
    }


@router.get("/metadata")
def graph_metadata():
    """The raw metadata block from graph_triplets.json: generated_at,
    spacy_model, num_records, num_entities, num_triplets, entity_type_counts,
    relation_counts, event_type_counts, etc."""
    return _load_triplets_file().get("metadata", {})


# --------------------------------------------------------------------------- #
# Entities / nodes
# --------------------------------------------------------------------------- #
@router.get("/entities")
def list_entities(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    type: Optional[str] = Query(
        None, description="Filter by entity type, e.g. PERSON | LOCATION | ORGANIZATION"
    ),
    min_mentions: Optional[int] = Query(
        None, ge=0, description="Only entities with at least this many mentions"
    ),
):
    """Paginated list of extracted entities from graph_triplets.json."""
    page, page_size = _page_params(page, page_size)
    rows = _load_triplets_file().get("entities", [])
    if type:
        rows = [r for r in rows if r.get("type") == type]
    if min_mentions is not None:
        rows = [r for r in rows if (r.get("mentions") or 0) >= min_mentions]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/nodes")
def list_nodes(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
):
    """Same payload as /entities but under the 'nodes' name for graph
    rendering libraries that expect a nodes+edges vocabulary
    (react-force-graph, cytoscape, sigma.js)."""
    page, page_size = _page_params(page, page_size)
    rows = _load_triplets_file().get("entities", [])
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# --------------------------------------------------------------------------- #
# Triplets / edges
# --------------------------------------------------------------------------- #
@router.get("/triplets")
def list_triplets(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    relation: Optional[str] = Query(
        None, description="Filter by relation label, e.g. ASSOCIATED_WITH"
    ),
    source: Optional[str] = Query(None, description="Filter by exact source label"),
    target: Optional[str] = Query(None, description="Filter by exact target label"),
    min_confidence: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Only triplets with confidence >= this value"
    ),
):
    """Paginated list of (source, relation, target) triplets extracted from
    cleaned_records.json by the NLP extraction stage."""
    page, page_size = _page_params(page, page_size)
    rows = _load_triplets_file().get("triplets", [])
    if relation:
        rows = [r for r in rows if r.get("relation") == relation]
    if source:
        rows = [r for r in rows if r.get("source") == source]
    if target:
        rows = [r for r in rows if r.get("target") == target]
    if min_confidence is not None:
        rows = [r for r in rows if (r.get("confidence") or 0) >= min_confidence]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/edges")
def list_edges(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    relation: Optional[str] = Query(None, description="Filter by relation label"),
):
    """Alias of /triplets under the 'edges' name for graph-rendering
    libraries that expect a nodes+edges vocabulary."""
    page, page_size = _page_params(page, page_size)
    rows = _load_triplets_file().get("triplets", [])
    if relation:
        rows = [r for r in rows if r.get("relation") == relation]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# --------------------------------------------------------------------------- #
# Ghosts / metrics
# --------------------------------------------------------------------------- #
@router.get("/ghosts")
def list_ghosts(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
):
    """Paginated list of ghost-node predictions produced by the ghost
    detection stage of the pipeline."""
    page, page_size = _page_params(page, page_size)
    rows = _load_ghost_predictions()
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}




@router.get("/ghosts/{ghost_id}/evidence")
def ghost_evidence(ghost_id: str):
    """Return one ghost prediction with its full evidence payload."""
    for ghost in _load_ghost_predictions():
        if ghost.get("ghost_id") == ghost_id:
            return ghost
    raise HTTPException(status_code=404, detail=f"Ghost prediction not found: {ghost_id}")

@router.get("/metrics")
def graph_metrics():
    """Graph-level metrics produced by the graph-build stage
    (graph_metrics.json). 404 if not yet built."""
    data = _load_json(paths.GRAPH_METRICS_PATH)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Graph metrics not found at {paths.GRAPH_METRICS_PATH}",
        )
    return data


@router.get("/communities")
def list_communities():
    """Graph communities detected during graph analysis.
    Returns list of communities with id, size, and members."""
    data = _load_json(paths.GRAPH_METRICS_PATH)
    if data and "communities" in data:
        return data["communities"]
    return []


@router.get("/data")
def graph_data():
    """Full NetworkX-serialized graph (node-link format from graph_data.json).
    404 if not yet built. Not paginated -- the frontend typically fetches
    this once and renders it locally."""
    data = _load_json(paths.GRAPH_DATA_PATH)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Graph data not found at {paths.GRAPH_DATA_PATH}",
        )
    return data


# --------------------------------------------------------------------------- #
# Neighborhood
# --------------------------------------------------------------------------- #
@router.get("/neighbors/{node_label}")
def node_neighbors(node_label: str):
    """All in/out edges incident to a single node, matched by source or
    target label against the triplets file. 404 if the node label doesn't
    appear in any triplet."""
    triplets = _load_triplets_file().get("triplets", [])

    neighbors: list[dict] = []
    for t in triplets:
        src = t.get("source")
        tgt = t.get("target")
        if src == node_label:
            neighbors.append(
                {
                    "node": tgt,
                    "node_type": t.get("target_type"),
                    "relation": t.get("relation"),
                    "direction": "out",
                    "triplet": t,
                }
            )
        elif tgt == node_label:
            neighbors.append(
                {
                    "node": src,
                    "node_type": t.get("source_type"),
                    "relation": t.get("relation"),
                    "direction": "in",
                    "triplet": t,
                }
            )

    if not neighbors:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_label}' not found in any triplet",
        )

    return {"node": node_label, "neighbors": neighbors, "count": len(neighbors)}


# --------------------------------------------------------------------------- #
# Subgraph + paths (Phase H / S / P) - server-side selection for large graphs
# --------------------------------------------------------------------------- #

def _rank_nodes(candidates, graph, max_nodes):
    """Pick the highest-signal nodes first (PageRank when available)."""
    def score(n):
        metrics = graph.nodes[n].get("metrics") or {}
        return (float(metrics.get("pagerank") or 0.0), graph.degree(n))
    return sorted(candidates, key=score, reverse=True)[:max_nodes]


@router.get("/subgraph")
def get_subgraph(
    node_id: str = Query(..., description="Focus node guid"),
    depth: int = Query(2, ge=1, le=4, description="Neighborhood depth"),
    max_nodes: int = Query(500, ge=1, le=5000, description="Hard node cap"),
    entity_type: Optional[str] = Query(None, description="Filter: PERSON | LOCATION | ..."),
    include_ghosts: bool = Query(True, description="Include ghost candidates if linked"),
):
    """Server-side subgraph extraction with hard limits (large-graph mode).

    Selection strategy: BFS by depth from the focus node over the undirected
    projection, ranked by PageRank/degree when the limit is hit.
    """
    try:
        graph = services.load_graph()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if node_id not in graph:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

    projection = _projection_of(graph)
    visited = {node_id: 0}
    frontier = [node_id]
    for level in range(1, depth + 1):
        nxt = []
        for current in frontier:
            for nbr in projection.neighbors(current):
                if nbr not in visited:
                    visited[nbr] = level
                    nxt.append(nbr)
        frontier = nxt
        if len(visited) >= max_nodes * 2:
            break
    visited.pop(node_id, None)
    selected = [node_id] + _rank_nodes(visited, graph, max_nodes - 1)
    if entity_type:
        upper = entity_type.upper()
        selected = [n for n in selected
                    if n == node_id or str(graph.nodes[n].get("entity_type", "")).upper() == upper]
    sub = graph.subgraph([n for n in selected if n in graph])

    nodes, edges = _serialize_sub(sub, include_evidence=True)
    audit.record_action("graph.subgraph", object_ids=[node_id],
                        detail={"depth": depth, "max_nodes": max_nodes,
                                "returned_nodes": len(nodes)})
    return {
        "focus_node_id": node_id,
        "depth": depth,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "truncated": len(visited) + 1 > len(selected),
        "method": "SERVER_SIDE_SUBGRAPH",
    }


@router.get("/paths/{source}/{target}")
def get_paths(source: str, target: str, k: int = Query(3, ge=1, le=5)):
    """Path candidates between two nodes with edge types + evidence ids."""
    try:
        graph = services.load_graph()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if source not in graph:
        raise HTTPException(status_code=404, detail=f"Source node not found: {source}")
    if target not in graph:
        raise HTTPException(status_code=404, detail=f"Target node not found: {target}")

    projection = _projection_of(graph)
    store = None
    try:
        store = services.evidence_store()
    except Exception:  # noqa: BLE001 - evidence optional for paths
        store = None

    out = []
    try:
        from itertools import islice

        candidates = list(islice(nx.shortest_simple_paths(projection, source, target), k))
    except (nx.NetworkXNoPath, nx.NetworkXError):
        candidates = []
    for path in candidates:
        edge_entries = []
        for u, v in zip(path, path[1:]):
            data = graph.get_edge_data(u, v) or {}
            best = None
            for key, attrs in data.items():
                if best is None or float(attrs.get("weight") or 1) > float(
                        best.get("weight") or 1):
                    best = dict(attrs)
                    best["_key"] = key
            eid = (best or {}).get("id")
            ev_ids = []
            if store and eid:
                ev_ids = [r.evidence_id for r in store.get_evidence_for_edge(str(eid))]
            edge_entries.append({
                "edge_id": eid,
                "relation": (best or {}).get("relation"),
                "source": str(u),
                "target": str(v),
                "evidence_ids": ev_ids,
            })
        out.append({
            "path": [str(p) for p in path],
            "path_length": len(path) - 1,
            "edges": edge_entries,
            "bottleneck_nodes": _bottlenecks(projection, path),
        })
    audit.record_action("graph.paths", object_ids=[source, target],
                        detail={"k": k, "found": len(out)})
    return {"source": source, "target": target, "paths": out, "count": len(out)}


def _bottlenecks(projection, path):
    """Bottleneck nodes on the path: nodes that are articulation points of
    the projection (removal disconnects their component).  Computed once via
    O(n + m) articulation-point search instead of per-node graph copies."""
    try:
        art_points = nx.articulation_points(projection)
        art = set(art_points)
    except nx.NetworkXError:
        return []
    return [str(node) for node in path[1:-1] if node in art][:5]


# --------------------------------------------------------------------------- #
# Large-graph progressive endpoints (P0 network overhaul)
#
# These endpoints never serialize the whole graph. Each returns exactly the
# slice the investigator needs — aggregates, one community's members, or a
# relevance-ranked neighborhood — with hard caps so payloads stay small.
# --------------------------------------------------------------------------- #

@router.get("/summary")
def graph_summary():
    """Compact graph summary for progressive rendering: counts, top
    communities, top entities, and bridge candidates. Never includes the
    full node list."""
    metrics = _load_json(paths.GRAPH_METRICS_PATH) or {}

    # Prefer the in-memory NetworkX graph (has real UUIDs, labels, metrics).
    graph = None
    try:
        graph = services.load_graph()
    except Exception:  # noqa: BLE001 - fall back to triplets file below
        graph = None

    node_count = graph.number_of_nodes() if graph else 0
    edge_count = graph.number_of_edges() if graph else 0

    top_entities: list[dict] = []
    top_communities: list[dict] = []

    if graph is not None:
        def _score(n):
            metrics_map = graph.nodes[n].get("metrics") or {}
            return (
                float(metrics_map.get("pagerank") or 0.0),
                float(metrics_map.get("betweenness_centrality") or 0.0),
                int(graph.nodes[n].get("mention_count") or 0),
            )

        ranked = sorted(graph.nodes, key=_score, reverse=True)[:50]
        for n in ranked:
            attrs = graph.nodes[n]
            metrics_map = attrs.get("metrics") or {}
            top_entities.append({
                "id": str(n),
                "label": attrs.get("canonical_name") or attrs.get("label") or str(n),
                "type": attrs.get("entity_type") or attrs.get("type"),
                "degree": int(graph.degree(n)),
                "pagerank": metrics_map.get("pagerank"),
                "betweenness": metrics_map.get("betweenness_centrality"),
                "mention_count": attrs.get("mention_count", 0),
            })

# Communities from graph_metrics.json (has rich members with labels/types).
    communities = metrics.get("communities", []) if isinstance(metrics, dict) else []
    top_communities = sorted(
        (c for c in communities if isinstance(c, dict)),
        key=lambda c: int(c.get("size") or len(c.get("members") or []) or 0),
        reverse=True,
    )[:50]
    top_communities = [
        {
            "id": c.get("id") or c.get("community_id"),
            "size": int(c.get("size") or len(c.get("members") or []) or 0),
            "members": [
                {
                    "id": str(m.get("guid") or m.get("id") or m.get("label") or m),
                    "label": m.get("label") if isinstance(m, dict) else str(m),
                    "type": m.get("type") if isinstance(m, dict) else None,
                }
                for m in (c.get("members") or [])[:10]
            ],
            "modularity": c.get("modularity"),
        }
        for c in top_communities
    ]

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "community_count": len(top_communities),
        "top_entities": top_entities,
        "top_communities": top_communities,
        "has_full_graph": bool(graph),
        "truncated": True,
    }


@router.get("/community/{community_id}")
def get_community_members(
    community_id: str,
    max_nodes: int = Query(300, ge=1, le=2000, description="Hard member cap"),
):
    """Members (with their intra-community edges) of one community. Used by
    the Level-1 cluster expansion — the investigator never loads more than
    one community at a time."""
    metrics = _load_json(paths.GRAPH_METRICS_PATH)
    if not isinstance(metrics, dict) or "communities" not in metrics:
        raise HTTPException(status_code=404, detail="No communities computed yet")

    target = None
    for c in metrics["communities"]:
        cid = c.get("id") if c.get("id") is not None else c.get("community_id")
        if str(cid) == str(community_id):
            target = c
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"Community not found: {community_id}")

    # members may be plain IDs or rich dicts {guid, label, type}
    raw_members = list(target.get("members") or [])[:max_nodes]
    members = [str(m.get("guid") or m.get("id") or m.get("label") or m) if isinstance(m, dict) else str(m)
               for m in raw_members]
    member_set = {m for m in members}

    try:
        graph = services.load_graph()
    except FileNotFoundError:
        return {
            "community_id": community_id,
            "members": [
                {"id": str(m), "label": str(m), "type": None} for m in members
            ],
            "edges": [],
            "member_count": len(members),
            "truncated": len(target.get("members") or []) > len(members),
        }

    nodes, edges = [], []
    seen_edges = set()
    member_attr = {}
    for m in members:
        if m in graph:
            member_attr[m] = graph.nodes[m]

    for raw, key in zip(raw_members, members):
        attrs = member_attr.get(key) or {}
        metrics_map = attrs.get("metrics") or {}
        nodes.append({
            "id": key,
            "label": attrs.get("canonical_name") or (raw.get("label") if isinstance(raw, dict) else None) or key,
            "type": attrs.get("entity_type") or (raw.get("type") if isinstance(raw, dict) else None),
            "mention_count": attrs.get("mention_count", 0),
            "metrics": metrics_map,
        })

    for u, v, attrs in graph.edges(data=True):
        su, sv = str(u), str(v)
        if su in member_set and sv in member_set:
            ekey = (su, sv) if su <= sv else (sv, su)
            if ekey in seen_edges:
                continue
            seen_edges.add(ekey)
            edges.append({
                "id": attrs.get("id"),
                "source": su,
                "target": sv,
                "type": attrs.get("relation"),
                "attributes": attrs.get("attributes", {}),
            })

    return {
        "community_id": community_id,
        "members": nodes,
        "edges": edges,
        "member_count": len(nodes),
        "edge_count": len(edges),
        "truncated": len(target.get("members") or []) > len(members),
    }


@router.get("/node/{node_id}/neighborhood")
def get_node_neighborhood(
    node_id: str,
    depth: int = Query(1, ge=1, le=3, description="Neighborhood depth"),
    max_nodes: int = Query(200, ge=1, le=2000, description="Hard node cap"),
    relationship_type: Optional[str] = Query(None, description="e.g. FINANCIAL"),
):
    """Relevance-ranked neighborhood expansion (Level 2/3 progressive load).
    Returns only the highest-signal nodes around the focus entity as ranked
    by PageRank/degree, with hard caps."""
    try:
        graph = services.load_graph()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if node_id not in graph:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

    projection = _projection_of(graph)
    visited: dict = {node_id: 0}
    frontier = [node_id]
    for level in range(1, depth + 1):
        nxt = []
        for current in frontier:
            for nbr in projection.neighbors(current):
                if nbr not in visited:
                    visited[nbr] = level
                    nxt.append(nbr)
        frontier = nxt
        if len(visited) >= max_nodes * 4:
            break

    if relationship_type:
        upper = relationship_type.upper()

        def rel_ok(u, v):
            data = graph.get_edge_data(u, v) or {}
            for attrs in data.values():
                r = str(attrs.get("relation") or "").upper()
                if upper in r or r in upper:
                    return True
            return False

        visited = {n: d for n, d in visited.items()
                   if n == node_id or rel_ok(node_id, n) or any(
                       rel_ok(n, nb) for nb in projection.neighbors(n) if nb in visited)}

    selected = [node_id] + _rank_nodes([n for n in visited if n != node_id], graph, max_nodes - 1)
    selected = [n for n in selected if n in graph][:max_nodes]
    sub = graph.subgraph(selected)

    nodes, edges = _serialize_sub(sub, include_evidence=True)
    audit.record_action(
        "graph.neighborhood",
        object_ids=[node_id],
        detail={
            "depth": depth,
            "max_nodes": max_nodes,
            "relationship_type": relationship_type,
            "returned_nodes": len(nodes),
            "returned_edges": len(edges),
            "truncated": len(visited) > len(selected),
        },
    )
    return {
        "focus_node_id": node_id,
        "depth": depth,
        "max_nodes": max_nodes,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "truncated": len(visited) > len(selected),
        "method": "SERVER_SIDE_NEIGHBORHOOD",
    }


def _projection_of(graph):
    from src.graph.graph_embeddings import undirected_weighted_projection

    return undirected_weighted_projection(graph)


def _serialize_sub(sub, include_evidence: bool = False):
    store = None
    if include_evidence:
        try:
            store = services.evidence_store()
        except Exception:  # noqa: BLE001
            store = None
    nodes = []
    for n, attrs in sub.nodes(data=True):
        metrics = attrs.get("metrics") or {}
        nodes.append({
            "id": str(n),
            "guid": attrs.get("guid"),
            "label": attrs.get("canonical_name"),
            "type": attrs.get("entity_type"),
            "mention_count": attrs.get("mention_count", 0),
            "metrics": metrics,
            "attributes": attrs.get("attributes", {}),
        })
    edges = []
    for u, v, attrs in sub.edges(data=True):
        eid = attrs.get("id")
        ev_ids = []
        if store and eid:
            ev_ids = [r.evidence_id for r in store.get_evidence_for_edge(str(eid))]
        edges.append({
            "id": eid,
            "source": str(u),
            "target": str(v),
            "type": attrs.get("relation"),
            "attributes": attrs.get("attributes", {}),
            "evidence_ids": ev_ids,
        })
    return nodes, edges
