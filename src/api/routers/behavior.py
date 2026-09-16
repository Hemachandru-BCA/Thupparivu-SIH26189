"""
routers/behavior.py
-------------------
Behavioral profile + behavior change API (route group: /api/behavior/*).

* GET /api/behavior/{entity_id}/profile   - deterministic behavior profile
* GET /api/behavior/{entity_id}/change    - period-over-period change detection
* GET /api/behavior/ranked                - entities ranked by activity volume

The profile is *derived deterministically* from the graph - the LLM never
computes these numbers.  Behavior change severity is an analytical
indicator, never a guilt statement.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/behavior", tags=["behavior"])


def _get_builder():
    from src.analysis.behavior_profile import BehaviorProfileBuilder

    return BehaviorProfileBuilder(graph=services.load_graph())


def _get_change_detector():
    from src.analysis.behavior_profile import BehaviorChangeDetector

    return BehaviorChangeDetector(graph=services.load_graph())


@router.get("/{entity_id}/profile")
def entity_profile(entity_id: str):
    """Deterministic behavior profile for one entity (communications,
    financial, network, temporal, locations)."""
    builder = _get_builder()
    profile = builder.build(entity_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    audit.record_action("behavior.profile", object_ids=[entity_id])
    return profile.model_dump()


@router.get("/{entity_id}/change")
def entity_change(
    entity_id: str,
    window_days: int = Query(30, ge=7, le=180),
):
    """Period-over-period behavior change summary for one entity."""
    detector = _get_change_detector()
    change = detector.detect_change(entity_id, window_days=window_days)
    if change is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    audit.record_action(
        "behavior.change",
        object_ids=[entity_id],
        detail={"window_days": window_days, "severity": change.severity},
    )
    return change.model_dump()


@router.get("/ranked")
def ranked_by_activity(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Entities ranked by communication+financial activity volume."""
    graph = services.load_graph()
    rows = []
    for n, d in graph.nodes(data=True):
        et = str(d.get("entity_type") or "").upper()
        if entity_type and et != entity_type.upper():
            continue
        m = d.get("metrics") or {}
        degree = int(m.get("degree") or 0)
        if degree <= 0:
            continue
        rows.append({
            "entity_id": n,
            "entity_type": et,
            "entity_name": d.get("canonical_name") or d.get("label") or n,
            "degree": degree,
            "pagerank": float(m.get("pagerank") or 0.0),
        })
    rows.sort(key=lambda r: (-r["degree"], -r["pagerank"]))
    audit.record_action("behavior.ranked", detail={"limit": limit, "count": len(rows)})
    return {"items": rows[:limit], "total": len(rows)}