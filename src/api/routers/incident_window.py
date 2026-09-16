"""
routers/incident_window.py
--------------------------
Pre-incident window analysis API (route group: /api/temporal/incident-window).

* GET /api/temporal/incidents                       - list FIR incidents
* GET /api/temporal/incident-window/{incident_id}   - pre-incident analysis
  with configurable window (15m, 30m, 1h, 3h, 6h, 24h)

Output is a set of analytical leads (calls, transfers, new contacts,
cross-community activity) - never proof of causation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/temporal", tags=["temporal", "incident-window"])

#: Supported pre-incident windows (hours).
SUPPORTED_WINDOWS = (0.25, 0.5, 1, 3, 6, 24)
DEFAULT_WINDOW = 1.0


def _get_analyzer():
    from src.analysis.incident_window import IncidentWindowAnalyzer

    return IncidentWindowAnalyzer(
        evidence_store=services.evidence_store(),
        graph=services.load_graph(),
    )


@router.get("/incidents")
def list_incidents(limit: int = Query(100, ge=1, le=500)):
    """List FIR incidents (newest first) for the timeline view."""
    analyzer = _get_analyzer()
    incidents = analyzer.list_incidents(limit=limit)
    audit.record_action("incident-window.list", detail={"count": len(incidents)})
    return {"items": incidents, "total": len(incidents)}


@router.get("/incident-window/{incident_id}")
def incident_window(
    incident_id: str,
    window_hours: float = Query(
        DEFAULT_WINDOW,
        ge=0.25,
        le=168,
        description="Pre-incident window in hours (15m=0.25 ... 24h=24, 7d=168)",
    ),
    max_activities: int = Query(500, ge=1, le=2000),
):
    """Pre-incident window analysis for one FIR incident.

    Returns activities within the configured window *before* the incident,
    plus analytical signals (calls, transfers, meetings, involved entities).
    """
    analyzer = _get_analyzer()
    result = analyzer.analyze_incident(
        incident_id, window_hours=window_hours, max_activities=max_activities
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident not found or not an FIR: {incident_id}",
        )
    audit.record_action(
        "incident-window.analyze",
        object_ids=[incident_id],
        detail={
            "window_hours": window_hours,
            "activities": len(result.activities),
            "calls": result.call_count,
            "transfers": result.transfer_count,
        },
    )
    return result.model_dump()