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
