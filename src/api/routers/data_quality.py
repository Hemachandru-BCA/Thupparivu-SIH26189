"""
routers/data_quality.py
-----------------------
Data Quality & Intelligence Reliability API (route group: /api/data-quality/*).

Answers: "How much should I trust the data behind this analysis?"
Outputs are *data quality indicators*, never "truth scores."
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query

from src.api import audit, services, services_intel

router = APIRouter(prefix="/api/data-quality", tags=["data-quality"])


def _get_assessor():
    from src.analysis.data_quality import DataQualityAssessor
    graph = services.load_graph()
    evidence = services.evidence_store()
    # Load findings
    findings = []
    try:
        import json
        from src.api.paths import FINDINGS_PATH
        if FINDINGS_PATH.exists():
            data = json.loads(FINDINGS_PATH.read_text())
            findings = data.get("findings", [])
    except Exception:
        pass
    return DataQualityAssessor(graph, evidence, findings)


@router.get("/")
def data_quality_report(
    entity_ids: Optional[str] = Query(None, description="Comma-separated entity IDs"),
):
    """Full data quality report."""
    assessor = _get_assessor()
    ids = [e.strip() for e in entity_ids.split(",")] if entity_ids else None
    report = assessor.assess(entity_ids=ids)
    audit.record_action("data-quality.report", detail={"entity_count": len(ids or [])})
    return report.model_dump()


@router.get("/entity/{entity_id}")
def entity_quality(entity_id: str):
    """Data quality for a specific entity."""
    assessor = _get_assessor()
    q = assessor.entity_quality(entity_id)
    if q is None:
        return {"error": "Entity not found", "entity_id": entity_id}
    audit.record_action("data-quality.entity", object_ids=[entity_id])
    return q.model_dump()
