"""
routers/evidence.py
-------------------
Evidence provenance API (Phase C/D route group: /api/evidence/*).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services
from src.api.data_access import paginate

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/for-node/{node_id}")
def evidence_for_node(node_id: str, page: int = Query(1, ge=1),
                      page_size: int = Query(20, ge=1, le=200)):
    """Evidence linked to a graph node (guid, ghost id or known name)."""
    store = services.evidence_store()
    records = store.get_evidence_for_node(node_id, limit=2000)
    items, total = paginate([r.model_dump(mode="json") for r in records], page, page_size)
    audit.record_action("evidence.view_for_node", object_ids=[node_id])
    return {"node_id": node_id, "items": items, "total": total,
            "page": page, "page_size": page_size}


@router.get("/for-edge/{edge_id}")
def evidence_for_edge(edge_id: str):
    """Evidence supporting one graph edge."""
    store = services.evidence_store()
    records = store.get_evidence_for_edge(edge_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"No evidence for edge: {edge_id}")
    audit.record_action("evidence.view_for_edge", object_ids=[edge_id])
    return {"edge_id": edge_id,
            "items": [r.model_dump(mode="json") for r in records],
            "total": len(records)}


@router.get("/for-finding/{finding_id}")
def evidence_for_finding(finding_id: str):
    """Evidence bound to a finding."""
    store = services.evidence_store()
    records = store.get_evidence_for_finding(finding_id)
    audit.record_action("evidence.view_for_finding", object_ids=[finding_id])
    return {"finding_id": finding_id,
            "items": [r.model_dump(mode="json") for r in records],
            "total": len(records)}


@router.get("/search")
def search_evidence(q: str = Query(..., min_length=2),
                    source_type: Optional[str] = Query(None),
                    limit: int = Query(25, ge=1, le=100)):
    """Keyword search over evidence excerpts and record ids."""
    store = services.evidence_store()
    records = store.search_evidence(q, limit=limit, source_type=source_type)
    audit.record_action("evidence.search", object_ids=[],
                        detail={"q": q[:120], "results": len(records)})
    return {"query": q, "items": [r.model_dump(mode="json") for r in records],
            "total": len(records)}


@router.get("/timeline/{subject_id}")
def evidence_timeline(subject_id: str, limit: int = Query(100, ge=1, le=500)):
    """Chronological evidence for one subject."""
    store = services.evidence_store()
    timeline = store.get_timeline(subject_id, limit=limit)
    audit.record_action("evidence.timeline", object_ids=[subject_id])
    return {"subject_id": subject_id, "items": timeline, "total": len(timeline)}


@router.get("/stats/summary")
def evidence_stats():
    """Index summary (counts by source type)."""
    store = services.evidence_store()
    counts: dict = {}
    for eid in store.all_ids():
        rec = store.get_evidence(eid)
        if rec:
            counts[rec.source_type] = counts.get(rec.source_type, 0) + 1
    return {"total": store.count(), "by_source_type": counts}


# NOTE: the dynamic id route must be declared AFTER all static routes so
# FastAPI does not shadow /search, /stats, /for-node, ... under it.
@router.get("/{evidence_id}")
def get_evidence(evidence_id: str):
    """One evidence record by id (with integrity fields)."""
    store = services.evidence_store()
    rec = store.get_evidence(evidence_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {evidence_id}")
    audit.record_action("evidence.view", object_ids=[evidence_id])
    return rec.model_dump(mode="json")
