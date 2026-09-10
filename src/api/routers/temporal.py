"""
routers/temporal.py
-------------------
Temporal intelligence API (route group: /api/temporal/*).

Exposes the TemporalMultilayerGraph engine to the UI:

* snapshot at a timestamp (no future leakage)        -> GET /snapshot
* edges/window between two timestamps                -> GET /between
* edge timeline buckets for replay animation         -> GET /timeline
* graph diff between two timestamps                  -> GET /diff
* community evolution across buckets                 -> GET /communities/evolution
* multilayer views (COMMUNICATION/FINANCIAL/...)     -> GET /layers
* node temporal features                             -> GET /nodes/{node_id}/features

Every payload is a *temporal snapshot*; relationships are labeled with
their observation status, never presented as legal conclusions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import networkx as nx
from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services, services_intel
from src.graph.temporal_graph import RelationshipLayer

router = APIRouter(prefix="/api/temporal", tags=["temporal"])

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _edge_to_dict(g: nx.MultiDiGraph, src, tgt, key) -> Dict[str, Any]:
    data = g.edges[src, tgt, key]
    a = data.get("attributes") or {}
    nested = a.get("attributes") or {}
    return {
        "id": data.get("id") or str(key),
        "source": src,
        "target": tgt,
        "relation": data.get("relation", "ASSOCIATED_WITH"),
        "source_name": data.get("source_name", ""),
        "target_name": data.get("target_name", ""),
        "confidence": float(a.get("confidence", 1.0)),
        "timestamp": nested.get("timestamp") or a.get("timestamp") or a.get("observed_at"),
        "evidence": a.get("evidence", ""),
        "record_id": a.get("record_id", ""),
    }


def _node_to_dict(g: nx.MultiDiGraph, node) -> Dict[str, Any]:
    data = dict(g.nodes[node])
    return {
        "id": node,
        "label": data.get("canonical_name") or data.get("label") or str(node),
        "type": data.get("entity_type") or data.get("type") or "UNKNOWN",
        "aliases": data.get("aliases") or [],
        "mention_count": int(data.get("mention_count") or 0),
        "metrics": data.get("metrics") or {},
    }


def _subgraph_doc(g: nx.MultiDiGraph) -> Dict[str, Any]:
    """Serialize a NetworkX subgraph for the UI (bounded node set)."""
    nodes = [_node_to_dict(g, n) for n in g.nodes()]
    edges = []
    for src, tgt, key, data in g.edges(keys=True, data=True):
        edges.append(_edge_to_dict(g, src, tgt, key))
    return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}


def _snapshot_nodes(g: nx.MultiDiGraph, limit: int = 0) -> List[Dict[str, Any]]:
    """Names for the node set of a snapshot (used by diff/evolution)."""
    out = []
    for n in g.nodes():
        d = dict(g.nodes[n])
        out.append({
            "id": n,
            "label": d.get("canonical_name") or d.get("label") or str(n),
            "type": d.get("entity_type") or "UNKNOWN",
        })
        if limit and len(out) >= limit:
            break
    return out


def _diff_edges(g: nx.MultiDiGraph) -> set:
    return {frozenset((src, tgt)) for src, tgt in g.edges()}


# --------------------------------------------------------------------------- #
# Ring buffer of N snapshots over the graph's full temporal range
# --------------------------------------------------------------------------- #

def _temporal_buckets(n_buckets: int = 8) -> List[str]:
    """Equally spaced timestamps covering the graph's observed edge range."""
    tm = services_intel.temporal_graph()
    times = [e.effective_time for e in tm._edges if e.effective_time]
    if not times:
        now = _iso_now()
        return [now] * n_buckets
    lo = min(times)
    hi = max(times)
    span = (hi - lo).total_seconds()
    if span <= 0:
        return [hi.isoformat()] * n_buckets
    step = span / n_buckets
    return [(lo + timedelta(seconds=step * i)).isoformat() for i in range(n_buckets + 1)]


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get("/info")
def temporal_info():
    """Temporal range, edge/timestamp coverage, and available layers."""
    tm = services_intel.temporal_graph()
    times = [e.effective_time for e in tm._edges if e.effective_time]
    layers = {}
    for e in tm._edges:
        layers[e.layer.value] = layers.get(e.layer.value, 0) + 1
    return {
        "edge_count": len(tm._edges),
        "timestamped_edge_count": len(times),
        "timestamp_coverage": round(len(times) / max(len(tm._edges), 1), 4),
        "earliest": min(times).isoformat() if times else None,
        "latest": max(times).isoformat() if times else None,
        "layers": layers,
        "layer_names": [l.value for l in RelationshipLayer],
        "bucket_timestamps": _temporal_buckets(8),
    }


@router.get("/snapshot")
def snapshot(
    as_of: str = Query(..., description="ISO-8601 timestamp"),
    max_edges: int = Query(5000, ge=100, le=30000),
):
    """The known graph as of a timestamp (strictly no future leakage)."""
    tm = services_intel.temporal_graph()
    g = tm.graph_as_of(as_of)
    doc = _subgraph_doc(g)
    doc["as_of"] = as_of
    if doc["edge_count"] > max_edges:
        # progressive delivery: cap edges, keep all node names
        doc["nodes"] = doc["nodes"][: max_edges * 3]
        doc["edges"] = doc["edges"][:max_edges]
        doc["truncated"] = True
    audit.record_action("temporal.snapshot", detail={"as_of": as_of})
    return doc


@router.get("/between")
def between(
    start: str = Query(...),
    end: str = Query(...),
    max_edges: int = Query(5000, ge=100, le=30000),
):
    """Edges observed strictly inside the window [start, end]."""
    tm = services_intel.temporal_graph()
    g = tm.graph_between(start, end)
    doc = _subgraph_doc(g)
    doc["start"] = start
    doc["end"] = end
    if doc["edge_count"] > max_edges:
        doc["nodes"] = doc["nodes"][: max_edges * 3]
        doc["edges"] = doc["edges"][:max_edges]
        doc["truncated"] = True
    return doc


@router.get("/timeline")
def edge_timeline(n_buckets: int = Query(12, ge=4, le=60)):
    """Edge counts + entity names per time bucket for replay animation."""
    tm = services_intel.temporal_graph()
    buckets = _temporal_buckets(n_buckets)
    out = []
    for i in range(len(buckets) - 1):
        g = tm.graph_between(buckets[i], buckets[i + 1])
        out.append({
            "bucket": i,
            "start": buckets[i],
            "end": buckets[i + 1],
            "edge_count": g.number_of_edges(),
            "node_count": g.number_of_nodes(),
            "node_types": _type_distribution(g),
        })
    return {
        "buckets": out,
        "timestamps": buckets,
        "total_edges": tm.graph.number_of_edges(),
    }


def _type_distribution(g: nx.MultiDiGraph) -> Dict[str, int]:
    counts = {}
    for n in g.nodes():
        t = (g.nodes[n].get("entity_type") or "UNKNOWN")
        counts[t] = counts.get(t, 0) + 1
    return counts


@router.get("/diff")
def graph_diff(
    start: str = Query(...),
    end: str = Query(...),
):
    """Structural difference between the graph at two timestamps."""
    tm = services_intel.temporal_graph()
    g1 = tm.graph_as_of(start)
    g2 = tm.graph_as_of(end)

    nodes1 = set(g1.nodes)
    nodes2 = set(g2.nodes)
    added_nodes = nodes2 - nodes1
    removed_nodes = nodes1 - nodes2

    edges1 = _diff_edges(g1)
    edges2 = _diff_edges(g2)
    added_edges = edges2 - edges1
    removed_edges = edges1 - edges2

    communities1 = _community_count(g1)
    communities2 = _community_count(g2)

    return {
        "start": start,
        "end": end,
        "delta": {
            "nodes_added": len(added_nodes),
            "nodes_removed": len(removed_nodes),
            "edges_added": len(added_edges),
            "edges_removed": len(removed_edges),
            "community_count_before": communities1,
            "community_count_after": communities2,
            "community_delta": communities2 - communities1,
        },
        "added_nodes": _snapshot_nodes(g2, 60),
        "removed_nodes": _snapshot_nodes(g1, 60),
        "added_edges": [list(e) for e in list(added_edges)[:100]],
        "removed_edges": [list(e) for e in list(removed_edges)[:100]],
        "statistics": {
            "nodes_before": g1.number_of_nodes(),
            "nodes_after": g2.number_of_nodes(),
            "edges_before": g1.number_of_edges(),
            "edges_after": g2.number_of_edges(),
        },
    }


def _community_count(g: nx.MultiDiGraph) -> int:
    if g.number_of_nodes() == 0:
        return 0
    try:
        from networkx.algorithms.community import louvain_communities

        return len(louvain_communities(g.to_undirected(), seed=42))
    except Exception:
        return len(list(nx.connected_components(g.to_undirected())))


@router.get("/communities/evolution")
def community_evolution(n_buckets: int = Query(8, ge=2, le=30)):
    """Community count, sizes and growth across time buckets."""
    tm = services_intel.temporal_graph()
    buckets = _temporal_buckets(n_buckets)
    out = []
    for i in range(len(buckets) - 1):
        g = tm.graph_between(buckets[i], buckets[i + 1])
        if g.number_of_nodes() == 0:
            out.append({"bucket": i, "start": buckets[i], "end": buckets[i + 1],
                        "community_count": 0, "sizes": [], "largest": 0})
            continue
        try:
            from networkx.algorithms.community import louvain_communities

            comms = louvain_communities(g.to_undirected(), seed=42)
            sizes = sorted((len(c) for c in comms), reverse=True)
        except Exception:
            sizes = sorted((len(c) for c in nx.connected_components(g.to_undirected())), reverse=True)
        out.append({
            "bucket": i,
            "start": buckets[i],
            "end": buckets[i + 1],
            "community_count": len(sizes),
            "sizes": sizes[:10],
            "largest": sizes[0] if sizes else 0,
            "node_count": g.number_of_nodes(),
        })
    return {"buckets": out, "timestamps": buckets}


@router.get("/layers")
def layer_views():
    """Per-layer graph sizes so the UI can show a layer selector."""
    tm = services_intel.temporal_graph()
    views = {}
    for layer in RelationshipLayer:
        g = tm.layer_view(layer)
        views[layer.value] = {
            "edge_count": g.number_of_edges(),
            "node_count": g.number_of_nodes(),
        }
    return {"layers": views}


@router.get("/layer/{layer_name}")
def layer_view(layer_name: str, max_edges: int = Query(5000, ge=100, le=30000)):
    """Full edge list for one relationship layer."""
    try:
        layer = RelationshipLayer(layer_name.upper())
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown layer: {layer_name}")
    tm = services_intel.temporal_graph()
    g = tm.layer_view(layer)
    doc = _subgraph_doc(g)
    doc["layer"] = layer.value
    if doc["edge_count"] > max_edges:
        doc["nodes"] = doc["nodes"][: max_edges * 3]
        doc["edges"] = doc["edges"][:max_edges]
        doc["truncated"] = True
    return doc


@router.get("/nodes/{node_id}/features")
def node_temporal_features(node_id: str):
    """Temporal features for one node (burstiness, persistence, recency...)."""
    tm = services_intel.temporal_graph()
    try:
        feats = tm.temporal_node_features(node_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return {"node_id": node_id, "features": feats}