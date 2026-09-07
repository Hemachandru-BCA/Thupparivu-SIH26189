"""
routers/findings.py
-------------------
XAI findings API (route group: /api/findings/*).
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, paths, services
from src.api.data_access import paginate

router = APIRouter(prefix="/api/findings", tags=["findings"])


def _load_findings() -> list:
    if not paths.FINDINGS_PATH.exists():
        return []
    try:
        payload = json.loads(paths.FINDINGS_PATH.read_text())
        return payload.get("findings", [])
    except (OSError, json.JSONDecodeError):
        return []


@router.get("")
@router.get("/")
def list_findings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
):
    """All generated XAI findings (deterministic order: confidence desc)."""
    findings = _load_findings()
    if status:
        findings = [f for f in findings if f.get("status") == status]
    if min_confidence is not None:
        findings = [f for f in findings if f.get("confidence", 0) >= min_confidence]
    findings.sort(key=lambda f: (-f.get("confidence", 0.0), f.get("id", "")))
    items, total = paginate(findings, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{finding_id}")
def get_finding(finding_id: str):
    """One finding with full XAI structure."""
    for finding in _load_findings():
        if finding.get("id") == finding_id:
            audit.record_action("findings.view", object_ids=[finding_id])
            return finding
    raise HTTPException(status_code=404, detail=f"Finding not found: {finding_id}")


@router.post("/generate")
def generate_findings(min_confidence: float = Query(0.0, ge=0.0, le=1.0)):
    """(Re)build findings from the current ghost predictions + evidence index."""
    try:
        store = services.evidence_store()
        ghost_doc = services.ghost_document()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ghosts: list = []
    if isinstance(ghost_doc, dict):
        for key in ("ghost_nodes", "ghosts", "predictions"):
            val = ghost_doc.get(key)
            if isinstance(val, list):
                ghosts = [g for g in val if isinstance(g, dict)]
                break
    elif isinstance(ghost_doc, list):
        ghosts = [g for g in ghost_doc if isinstance(g, dict)]

    from src.xai.findings import FindingBuilder, save_findings, validate_finding

    builder = FindingBuilder(store)
    findings = builder.build_all(ghosts, min_confidence=min_confidence)
    reports = [validate_finding(f, store) for f in findings]
    builder.link_store(findings)
    out = save_findings(findings, paths.FINDINGS_PATH)
    audit.record_action("findings.generate",
                        object_ids=[f.id for f in findings],
                        detail={"count": len(findings)})
    return {
        "generated": len(findings),
        "output_path": str(out),
        "validation": {
            "valid": sum(1 for r in reports if r.valid),
            "invalid": sum(1 for r in reports if not r.valid),
            "reports": [r.model_dump(mode="json") for r in reports if not r.valid][:20],
        },
    }
