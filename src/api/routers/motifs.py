"""
routers/motifs.py
-----------------
Network motif / structural pattern detection API (route group: /api/motifs/*).

Detects recurring structural patterns: hubs, brokers, chains, fan-in,
fan-out, rings, multi-community connectors.  Each motif carries confidence
and limitations — this is structural pattern detection, NOT criminal
classification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services

router = APIRouter(prefix="/api/motifs", tags=["motifs"])


def _get_detector():
    from src.analysis.motif_detector import MotifDetector
    graph = services.load_graph()
    return MotifDetector(graph)


@router.get("/")
def list_motifs(
    motif_type: Optional[str] = Query(None, description="Filter by motif type"),
    limit: int = Query(50, ge=1, le=200),
):
    """List all detected structural motifs."""
    detector = _get_detector()
    report = detector.detect_all(top_n=limit)
    motifs = report.motifs
    if motif_type:
        motifs = [m for m in motifs if m.motif_type == motif_type.upper()]
    audit.record_action("motifs.list", detail={"type": motif_type, "count": len(motifs)})
    return {
        "motifs": [m.model_dump() for m in motifs[:limit]],
        "summary": report.summary,
        "total": len(motifs),
        "limitations": report.limitations,
    }


@router.get("/types")
def motif_types():
    """List available motif types."""
    return {
        "types": [
            {"id": "HUB", "label": "Hub", "description": "Entity with unusually high connectivity"},
            {"id": "BROKER", "label": "Broker / Bridge", "description": "Entity connecting weakly-connected communities"},
            {"id": "CHAIN", "label": "Chain", "description": "Linear chain A → B → C → …"},
            {"id": "FAN_IN", "label": "Fan-In", "description": "Multiple sources → single target"},
            {"id": "FAN_OUT", "label": "Fan-Out", "description": "Single source → multiple targets"},
            {"id": "RING", "label": "Ring / Cycle", "description": "Closed loop A → B → C → A"},
            {"id": "MULTI_COMMUNITY_CONNECTOR", "label": "Multi-Community Connector", "description": "Entity connecting 3+ communities"},
        ],
    }


@router.get("/{motif_id}")
def get_motif(motif_id: str):
    """Get details for a specific motif."""
    detector = _get_detector()
    report = detector.detect_all(top_n=100)
    for m in report.motifs:
        if m.motif_id == motif_id:
            audit.record_action("motifs.detail", object_ids=[motif_id])
            return m.model_dump()
    raise HTTPException(status_code=404, detail=f"Motif not found: {motif_id}")
