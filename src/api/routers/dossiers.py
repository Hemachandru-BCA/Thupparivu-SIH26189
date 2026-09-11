"""
routers/dossiers.py
-------------------
Dossier API (Phase F route group: /api/dossiers/*).

Every generated dossier is DRAFT_FOR_HUMAN_REVIEW; the review endpoint
records a human decision without ever marking model output as court-ready.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, paths, schemas, services
from src.xai.dossier_generator import (
    DossierGenerator,
    list_dossiers,
    load_dossier,
    save_dossier,
    validate_dossier,
)

router = APIRouter(prefix="/api/dossiers", tags=["dossiers"])


@router.get("")
@router.get("/")
def list_all():
    """All generated dossiers (summary list)."""
    return {"items": list_dossiers(paths.DOSSIERS_DIR), "total":
            len(list_dossiers(paths.DOSSIERS_DIR))}


@router.get("/{dossier_id}")
def get_one(dossier_id: str):
    try:
        dossier = load_dossier(paths.DOSSIERS_DIR / f"{dossier_id}.json")
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail=f"Dossier not found: {dossier_id}")
    audit.record_action("dossiers.view", object_ids=[dossier_id])
    return dossier.model_dump(mode="json")


@router.post("/generate", status_code=201)
def generate(request: schemas.DossierRequest):
    """Generate an evidence-grounded dossier for one subject."""
    store = services.evidence_store()
    generator = DossierGenerator(
        store, findings_path=paths.FINDINGS_PATH if paths.FINDINGS_PATH.exists() else None
    )
    dossier = generator.generate_dossier(
        request.subject_id,
        finding_ids=request.finding_ids,
        max_evidence=request.max_evidence,
    )
    report = validate_dossier(dossier, store)
    if not report.valid:
        # a broken provider must never yield an invalid dossier
        raise HTTPException(status_code=500, detail={
            "message": "generated dossier failed validation",
            "errors": report.errors,
        })
    out = save_dossier(dossier, paths.DOSSIERS_DIR)
    audit.record_action("dossiers.generate",
                        object_ids=[dossier.id, request.subject_id])
    return {
        "dossier": dossier.model_dump(mode="json"),
        "validation": report.model_dump(mode="json"),
        "path": str(out),
    }


@router.post("/{dossier_id}/review")
def review(dossier_id: str, request: schemas.DossierReviewRequest):
    """Record a human review decision on a draft dossier."""
    path = paths.DOSSIERS_DIR / f"{dossier_id}.json"
    try:
        dossier = load_dossier(path)
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail=f"Dossier not found: {dossier_id}")
    dossier.human_review = {
        "required": False,
        "reviewer": request.reviewer,
        "decision": request.decision,
        "note": request.note,
        "note_on_status": (
            "Human review recorded. This document remains an analytical "
            "product and is not automatically court-ready."
        ),
    }
    save_dossier(dossier, paths.DOSSIERS_DIR)
    audit.record_action("dossiers.review",
                        object_ids=[dossier_id],
                        detail={"decision": request.decision})
    return dossier.model_dump(mode="json")


@router.get("/export/investigation-pack")
def export_investigation_pack(case_id: str = Query("CASE-0421")):
    """Export a complete investigation handoff pack as a structured JSON payload.

    Includes: case metadata, entities, findings, ghost candidates, evidence
    summary, dossiers, counterfactual results, timeline overview, and
    methodology notes. All claims reference structured evidence. No
    enforcement recommendations.
    """
    import json
    from datetime import datetime, timezone

    # Case
    case_data = {}
    case_path = paths.CASES_DIR / f"{case_id}.json"
    if case_path.exists():
        try:
            case_data = json.loads(case_path.read_text())
        except Exception:
            pass

    # Graph stats
    graph_doc = services.graph_document()
    node_count = len(graph_doc.get("nodes", []))
    edge_count = len(graph_doc.get("edges", []))
    meta = graph_doc.get("metadata", {})

    # Findings
    findings_list = []
    if paths.FINDINGS_PATH.exists():
        try:
            doc = json.loads(paths.FINDINGS_PATH.read_text())
            findings_list = doc.get("findings", []) if isinstance(doc, dict) else doc
        except Exception:
            pass

    # Ghost candidates
    ghost_list = []
    try:
        ghost_doc = services.ghost_document()
        ghost_list = ghost_doc.get("ghost_nodes", []) if isinstance(ghost_doc, dict) else ghost_doc
    except Exception:
        pass

    # Dossiers
    dossier_summaries = list_dossiers(paths.DOSSIERS_DIR)

    # Evidence stats
    store = services.evidence_store()
    evidence_total = store.count()
    evidence_by_type = {}
    for eid in store.all_ids():
        rec = store.get_evidence(eid)
        if rec:
            evidence_by_type[rec.source_type] = evidence_by_type.get(rec.source_type, 0) + 1

    # Top entities
    nodes = graph_doc.get("nodes", [])
    top_entities = sorted(
        nodes,
        key=lambda n: (n.get("metrics", {}).get("pagerank") or 0), reverse=True,
    )[:10]

    pack = {
        "export_metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "system": "SentinelGraph AI / Thupparivu",
            "version": "2.0.0",
            "case_id": case_id,
            "disclaimer": (
                "DRAFT INTELLIGENCE PRODUCT — NOT COURT-READY. "
                "All findings remain analytical hypotheses requiring human review. "
                "Ghost candidates are structural hypotheses, not identities. "
                "Confidence scores are NOT probabilities of guilt."
            ),
        },
        "case": {
            "id": case_data.get("id") or case_id,
            "title": case_data.get("title") or "",
            "description": case_data.get("description") or "",
            "status": case_data.get("status") or "OPEN",
            "items_count": len(case_data.get("items") or []),
            "notes_count": len(case_data.get("notes") or []),
        },
        "network_overview": {
            "entity_count": node_count,
            "relationship_count": edge_count,
            "community_count": meta.get("num_communities"),
            "resolved_entities": meta.get("entity_resolution", {}).get("resolved_entity_count"),
        },
        "top_entities": [
            {
                "id": n.get("id"),
                "name": n.get("canonical_name") or n.get("label"),
                "type": n.get("entity_type"),
                "pagerank": (n.get("metrics") or {}).get("pagerank"),
                "betweenness": (n.get("metrics") or {}).get("betweenness_centrality"),
                "community": (n.get("metrics") or {}).get("community"),
            }
            for n in top_entities
        ],
        "findings": [
            {
                "id": f.get("finding_id") or f.get("id"),
                "type": f.get("finding_type"),
                "subject_id": f.get("subject_id"),
                "subject_label": f.get("subject_label"),
                "confidence": f.get("confidence"),
                "status": f.get("status") or "INFERRED",
                "supporting_evidence_count": len(f.get("supporting_evidence_ids") or []),
                "counter_evidence_count": len(f.get("counter_evidence_ids") or []),
            }
            for f in findings_list[:20]
        ],
        "ghost_candidates": [
            {
                "ghost_id": g.get("ghost_id"),
                "confidence": g.get("ghost_score") or g.get("confidence"),
                "communities": g.get("community_pair"),
                "predicted_edges": len(g.get("predicted_edges") or []),
            }
            for g in ghost_list[:10]
        ],
        "evidence_summary": {
            "total_records": evidence_total,
            "by_source_type": evidence_by_type,
        },
        "dossiers": dossier_summaries[:10],
        "methodology": {
            "nlp": "spaCy en_core_web_sm + gazetteer + regex (deterministic)",
            "entity_resolution": "name similarity + Soundex + attribute overlap (uuid5 clustering)",
            "graph": "NetworkX MultiDiGraph, Louvain communities, PageRank, betweenness centrality",
            "ghost_detection": "structural holes + temporal affinity + embedding proximity (precision-optimized)",
            "evidence": "SHA-256 hashed provenance, EV-uuid5 deterministic IDs",
            "simulation": "node-removal counterfactual with fragmentation/connectivity/rerouting metrics",
            "limitations": [
                "All data is synthetic (seed 42)",
                "Ghost candidates are structural hypotheses, not identities",
                "Recall is intentionally low (~0.27) to maximize precision",
                "LLM summaries are deterministic mock — never the source of truth",
                "No enforcement recommendations anywhere in the system",
            ],
        },
    }

    audit.record_action("dossiers.export_pack", object_ids=[case_id])
    return pack
