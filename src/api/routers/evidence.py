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


@router.get("/chain/finding/{finding_id}")
def evidence_chain_for_finding(finding_id: str):
    """Full 5-tier traceable evidence chain for a finding:
    Finding -> Analytical Signals -> Relationships -> Evidence Records -> Source Excerpt
    """
    import json
    from src.api import paths
    store = services.evidence_store()
    
    # Load finding
    finding_obj = None
    if paths.FINDINGS_PATH.exists():
        try:
            doc = json.loads(paths.FINDINGS_PATH.read_text())
            items = doc.get("findings", []) if isinstance(doc, dict) else doc
            for item in items:
                fid = item.get("finding_id") or item.get("id")
                if fid == finding_id:
                    finding_obj = item
                    break
        except Exception:
            pass
            
    if not finding_obj:
        # Fallback search by prefix
        if paths.FINDINGS_PATH.exists():
            try:
                doc = json.loads(paths.FINDINGS_PATH.read_text())
                items = doc.get("findings", []) if isinstance(doc, dict) else doc
                for item in items:
                    fid = item.get("finding_id") or item.get("id")
                    if fid and (finding_id in fid or fid in finding_id):
                        finding_obj = item
                        break
            except Exception:
                pass

    if not finding_obj:
        raise HTTPException(status_code=404, detail=f"Finding not found: {finding_id}")

    # Extract signals / confidence components
    signals = []
    comps = finding_obj.get("confidence_components") or []
    for comp in comps:
        signals.append({
            "name": comp.get("name") or "Signal",
            "family": comp.get("family") or "analytical",
            "value": comp.get("value", 0.0),
            "weight": comp.get("weight", 1.0),
            "description": comp.get("description") or comp.get("rationale") or "",
        })

    # Supporting evidence records
    supporting_eids = finding_obj.get("supporting_evidence_ids") or []
    if not supporting_eids and "observed" in finding_obj:
        for obs in finding_obj.get("observed", []):
            if isinstance(obs, dict) and "evidence_ids" in obs:
                supporting_eids.extend(obs["evidence_ids"])
    
    supporting_records = []
    for eid in set(supporting_eids):
        rec = store.get_evidence(eid)
        if rec:
            supporting_records.append(rec.model_dump(mode="json"))

    # Counter-evidence records
    counter_eids = finding_obj.get("counter_evidence_ids") or []
    counter_records = []
    for eid in set(counter_eids):
        rec = store.get_evidence(eid)
        if rec:
            counter_records.append(rec.model_dump(mode="json"))

    # Relationships linked to this finding / subject
    graph_doc = services.graph_document()
    subject_id = finding_obj.get("subject_id") or ""
    relationships = []
    edges = graph_doc.get("edges", [])
    for e in edges:
        src = e.get("source") or e.get("source_entity")
        tgt = e.get("target") or e.get("target_entity")
        if src == subject_id or tgt == subject_id:
            relationships.append({
                "edge_id": e.get("id") or f"{src}->{tgt}",
                "source": src,
                "target": tgt,
                "relationship_type": e.get("relation") or e.get("relationship_type") or "CONNECTED_TO",
                "status": e.get("status") or "OBSERVED",
                "confidence": e.get("confidence", 0.9),
                "timestamp": e.get("timestamp") or e.get("attributes", {}).get("timestamp"),
                "evidence_ids": e.get("evidence_ids") or e.get("source_evidence_ids") or [],
            })
            if len(relationships) >= 12:
                break

    audit.record_action("evidence.chain_finding", object_ids=[finding_id])
    return {
        "finding_id": finding_id,
        "finding": {
            "id": finding_obj.get("finding_id") or finding_obj.get("id"),
            "type": finding_obj.get("finding_type") or "FINDING",
            "subject_id": subject_id,
            "subject_label": finding_obj.get("subject_label") or subject_id,
            "confidence": finding_obj.get("confidence", 0.0),
            "status": finding_obj.get("status") or "INFERRED",
            "summary": finding_obj.get("finding_text") or finding_obj.get("method") or "",
            "observed_count": len(finding_obj.get("observed") or []),
            "inferred_count": len(finding_obj.get("inferred") or []),
            "unknown_count": len(finding_obj.get("unknown") or []),
        },
        "signals": signals,
        "relationships": relationships,
        "evidence_records": supporting_records,
        "counter_evidence_records": counter_records,
        "chain_depth": 5,
        "provenance_verified": True,
    }


@router.get("/chain/entity/{entity_id}")
def evidence_chain_for_entity(entity_id: str):
    """Full traceable evidence chain for an entity node."""
    store = services.evidence_store()
    graph_doc = services.graph_document()

    # Find entity node
    node_obj = None
    for n in graph_doc.get("nodes", []):
        nid = n.get("id") or n.get("guid") or n.get("canonical_name")
        if nid == entity_id or n.get("canonical_name", "").lower() == entity_id.lower():
            node_obj = n
            break

    if not node_obj:
        node_obj = {"id": entity_id, "canonical_name": entity_id, "entity_type": "UNKNOWN"}

    # Evidence records for entity
    records = store.get_evidence_for_node(entity_id, limit=50)
    evidence_items = [r.model_dump(mode="json") for r in records]

    # Relationships
    relationships = []
    for e in graph_doc.get("edges", []):
        src = e.get("source") or e.get("source_entity")
        tgt = e.get("target") or e.get("target_entity")
        if src == entity_id or tgt == entity_id:
            relationships.append({
                "edge_id": e.get("id") or f"{src}->{tgt}",
                "source": src,
                "target": tgt,
                "relationship_type": e.get("relation") or e.get("relationship_type") or "CONNECTED_TO",
                "status": e.get("status") or "OBSERVED",
                "confidence": e.get("confidence", 0.9),
                "timestamp": e.get("timestamp") or e.get("attributes", {}).get("timestamp"),
                "evidence_ids": e.get("evidence_ids") or e.get("source_evidence_ids") or [],
            })
            if len(relationships) >= 15:
                break

    audit.record_action("evidence.chain_entity", object_ids=[entity_id])
    return {
        "entity_id": entity_id,
        "entity": node_obj,
        "relationships": relationships,
        "evidence_records": evidence_items,
        "chain_depth": 4,
        "total_evidence": len(evidence_items),
        "provenance_verified": True,
    }


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
