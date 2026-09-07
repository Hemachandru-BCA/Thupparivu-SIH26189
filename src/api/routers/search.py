"""
routers/search.py
-----------------
Global search (Phase X): person / organization / phone / account / vehicle /
location / document id / evidence id / ghost id - one endpoint.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query

from src.api import audit, services

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
@router.get("/")
def global_search(q: str = Query(..., min_length=2, max_length=200),
                  limit: int = Query(20, ge=1, le=100)):
    """Search graph nodes, ghosts and evidence in one call.

    Results carry entity type, id, display name, confidence/status and a
    quick-action hint for the UI.
    """
    q_lower = q.strip().lower()
    results: List[dict] = []

    # ---- graph nodes ----
    try:
        doc = services.graph_document()
        for node in doc.get("nodes", []):
            hay = " ".join(
                [str(node.get("label") or ""), str(node.get("id") or "")]
                + [str(a) for a in (node.get("aliases") or [])]
            ).lower()
            if q_lower in hay:
                attrs = node.get("attributes") or {}
                results.append({
                    "result_type": "node",
                    "id": node.get("id"),
                    "entity_type": node.get("type"),
                    "display_name": node.get("label"),
                    "mention_count": node.get("mention_count", 0),
                    "pagerank": (node.get("metrics") or {}).get("pagerank"),
                    "quick_action": "inspect",
                })
            if len(results) >= limit:
                break
    except FileNotFoundError:
        pass

    # ---- ghosts ----
    try:
        ghost_doc = services.ghost_document()
        ghosts: list = []
        if isinstance(ghost_doc, dict):
            for key in ("ghost_nodes", "ghosts", "predictions"):
                val = ghost_doc.get(key)
                if isinstance(val, list):
                    ghosts = [g for g in val if isinstance(g, dict)]
                    break
        elif isinstance(ghost_doc, list):
            ghosts = [g for g in ghost_doc if isinstance(g, dict)]
        for g in ghosts:
            hay = f"{g.get('ghost_id', '')} {g.get('label', '')} {g.get('subtype', '')}".lower()
            if q_lower in hay or "ghost" in q_lower:
                results.append({
                    "result_type": "ghost",
                    "id": g.get("ghost_id"),
                    "entity_type": "GHOST",
                    "display_name": g.get("label"),
                    "confidence": g.get("confidence"),
                    "status": "HYPOTHESIS",
                    "quick_action": "open_ghost",
                })
    except FileNotFoundError:
        pass

    # ---- evidence ----
    store = services.evidence_store()
    for rec in store.search_evidence(q, limit=max(0, limit - len(results))):
        results.append({
            "result_type": "evidence",
            "id": rec.evidence_id,
            "entity_type": rec.source_type,
            "display_name": rec.source_record_id,
            "excerpt": rec.text_excerpt[:160],
            "quick_action": "open_evidence",
        })
        if len(results) >= limit:
            break

    audit.record_action("search", object_ids=[], detail={"q": q[:120], "results": len(results)})
    return {"query": q, "items": results[:limit], "total": len(results[:limit])}
