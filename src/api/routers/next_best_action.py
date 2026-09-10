"""
routers/next_best_action.py
---------------------------
Next-Best Analytical Action API (route group: /api/recommendations/*).

Recommends the most useful next analytical step based on investigation context.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from src.api import audit, services, services_intel

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

# In-memory feedback store (resets on restart)
_feedback: Dict[str, str] = {}


def _load_findings():
    try:
        from src.api.paths import FINDINGS_PATH
        if FINDINGS_PATH.exists():
            data = json.loads(FINDINGS_PATH.read_text())
            return data.get("findings", [])
    except Exception:
        pass
    return []


def _load_ghosts():
    try:
        from src.api.paths import GHOST_PREDICTIONS_PATH
        if GHOST_PREDICTIONS_PATH.exists():
            data = json.loads(GHOST_PREDICTIONS_PATH.read_text())
            return data.get("ghost_nodes", [])
    except Exception:
        pass
    return []


def _load_cross_case():
    try:
        from src.api.paths import CASES_DIR
        if CASES_DIR.exists():
            entities = []
            for p in CASES_DIR.glob("*.json"):
                data = json.loads(p.read_text())
                for e in data.get("entities", []):
                    entities.append({
                        "entity_id": e.get("id", ""),
                        "label": e.get("label", ""),
                        "case_id": data.get("case_id", p.stem),
                        "case_count": 2,
                    })
            return {"shared_entities": entities[:20]}
    except Exception:
        pass
    return {}


@router.get("/")
def get_recommendations(
    entity_id: Optional[str] = Query(None),
    limit: int = Query(12, ge=1, le=30),
):
    """Get next-best analytical recommendations."""
    from src.analysis.next_best_action import NextBestActionEngine
    graph = services.load_graph()
    findings = _load_findings()
    ghosts = _load_ghosts()
    cross_case = _load_cross_case()

    engine = NextBestActionEngine(
        graph=graph,
        findings=findings,
        ghost_predictions=ghosts,
        cross_case_data=cross_case,
    )
    report = engine.generate_recommendations()
    recs = report.recommendations[:limit]

    # Mark feedback status
    for r in recs:
        if r.recommendation_id in _feedback:
            r.status = _feedback[r.recommendation_id]

    audit.record_action("recommendations.get", detail={"count": len(recs)})
    return {"recommendations": [r.model_dump() for r in recs], "total": len(recs), "limitations": report.limitations}


@router.post("/feedback")
def submit_feedback(body: Dict[str, Any] = Body(...)):
    """Record investigator feedback on a recommendation."""
    rec_id = body.get("recommendation_id", "")
    action = body.get("action", "")
    if rec_id and action in ("DISMISS", "DEFER", "COMPLETE", "NOT_USEFUL"):
        _feedback[rec_id] = action
        audit.record_action("recommendations.feedback", object_ids=[rec_id], detail={"action": action})
        return {"status": "recorded", "recommendation_id": rec_id, "action": action}
    return {"error": "Invalid feedback"}
