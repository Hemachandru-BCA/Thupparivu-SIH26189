"""
routers/geospatial.py
---------------------
Geospatial Intelligence API (route group: /api/geo/*).

Location extraction, clustering, proximity analysis, and map integration.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query

from src.api import audit, services

router = APIRouter(prefix="/api/geo", tags=["geospatial"])


def _get_engine():
    from src.analysis.geospatial import GeospatialEngine
    graph = services.load_graph()
    return GeospatialEngine(graph)


@router.get("/observations")
def observations(
    entity_ids: Optional[str] = Query(None, description="Comma-separated entity IDs"),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    """Geospatial observations from the graph."""
    engine = _get_engine()
    ids = [e.strip() for e in entity_ids.split(",")] if entity_ids else None
    report = engine.analyze(entity_ids=ids, entity_type=entity_type)
    audit.record_action("geo.observations", detail={"entity_type": entity_type, "count": len(report.observations)})
    return {"observations": [o.model_dump() for o in report.observations[:limit]], "total": len(report.observations)}


@router.get("/clusters")
def clusters(grid_size_km: float = Query(5.0, ge=1.0, le=50.0)):
    """Server-side location clusters."""
    engine = _get_engine()
    cluster_list = engine.cluster_observations(grid_size_km=grid_size_km)
    audit.record_action("geo.clusters", detail={"grid_km": grid_size_km, "count": len(cluster_list)})
    return {"clusters": [c.model_dump() for c in cluster_list], "total": len(cluster_list)}


@router.get("/proximity")
def proximity(max_distance_km: float = Query(5.0, ge=0.1, le=100.0)):
    """Spatial proximity analysis between entities."""
    engine = _get_engine()
    relations = engine.spatial_proximity(max_distance_km=max_distance_km)
    audit.record_action("geo.proximity", detail={"max_km": max_distance_km, "count": len(relations)})
    return {"relations": [r.model_dump() for r in relations], "total": len(relations)}


@router.get("/report")
def report(
    entity_ids: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
):
    """Full geospatial report."""
    engine = _get_engine()
    ids = [e.strip() for e in entity_ids.split(",")] if entity_ids else None
    result = engine.analyze(entity_ids=ids, entity_type=entity_type)
    audit.record_action("geo.report", detail={"entity_count": len(ids or [])})
    return result.model_dump()
