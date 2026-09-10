"""
routers/method_agreement.py
---------------------------
Multi-method analytical agreement API (route group: /api/method-agreement/*).

Shows investigators whether analytical signals are robust across methods
or depend on a single approach.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query

from src.api import audit, services

router = APIRouter(prefix="/api/method-agreement", tags=["method-agreement"])


def _get_analyzer():
    from src.analysis.method_agreement import MethodAgreementAnalyzer
    graph = services.load_graph()
    # Load ghost predictions if available
    ghosts = []
    try:
        import json
        from src.api.paths import GHOST_PREDICTIONS_PATH
        if GHOST_PREDICTIONS_PATH.exists():
            data = json.loads(GHOST_PREDICTIONS_PATH.read_text())
            ghosts = data.get("ghost_nodes", [])
    except Exception:
        pass
    return MethodAgreementAnalyzer(graph, ghosts)


@router.get("/")
def method_agreement_report(
    entity_ids: Optional[str] = Query(None, description="Comma-separated entity IDs"),
    limit: int = Query(20, ge=1, le=50),
):
    """Full method agreement report."""
    analyzer = _get_analyzer()
    ids = [e.strip() for e in entity_ids.split(",")] if entity_ids else None
    report = analyzer.analyze(entity_ids=ids, top_n=limit)
    audit.record_action("method-agreement.report", detail={"entity_count": len(ids or [])})
    return report.model_dump()


@router.get("/entity/{entity_id}")
def entity_agreement(entity_id: str):
    """Method agreement for a specific entity."""
    analyzer = _get_analyzer()
    result = analyzer.analyze_entity(entity_id)
    if result is None:
        return {"error": "Entity not found or insufficient data", "entity_id": entity_id}
    audit.record_action("method-agreement.entity", object_ids=[entity_id])
    return result.model_dump()


@router.get("/disagreements")
def disagreements(
    limit: int = Query(20, ge=1, le=50),
):
    """Find entities with the largest method disagreements."""
    analyzer = _get_analyzer()
    result = analyzer.find_disagreements(top_n=limit)
    audit.record_action("method-agreement.disagreements", detail={"count": len(result)})
    return {"disagreements": [d.model_dump() for d in result], "total": len(result)}
