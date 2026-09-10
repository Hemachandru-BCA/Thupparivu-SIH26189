"""
routers/hypotheses.py
---------------------
Hypothesis engine API (route group: /api/hypotheses/*).

Exposes the structured hypothesis engine, the evidence-contradiction
detector, and a human-in-the-loop disposition workflow:

* generate a full hypothesis set from graph + ghost + prediction signals
* list hypotheses (filter by type/status/confidence)
* get a single hypothesis + its evidence/contradiction breakdown
* record an analyst disposition (CONFIRM / REJECT / DEFER / REQUEST_EVIDENCE)

A hypothesis is an *analysis object* — never a legal conclusion.  Every
hypothesis carries supporting and counter evidence ids, model signals, and
explicit status.
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from src.api import audit, paths, services, services_intel

router = APIRouter(prefix="/api/hypotheses", tags=["hypotheses"])

_lock = threading.Lock()

HYPOTHESIS_ARTIFACT = paths.GRAPH_OUTPUT_DIR / "hypotheses.json"

VALID_STATUSES = {"OPEN", "UNDER_REVIEW", "SUPPORTED", "WEAKENED",
                  "CONTRADICTED", "RESOLVED", "REJECTED"}
VALID_DISPOSITIONS = {"CONFIRM", "REJECT", "DEFER", "REQUEST_EVIDENCE"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_hypotheses() -> List[Dict[str, Any]]:
    if not HYPOTHESIS_ARTIFACT.exists():
        return []
    try:
        doc = json.loads(HYPOTHESIS_ARTIFACT.read_text())
        return doc.get("hypotheses", []) if isinstance(doc, dict) else doc
    except (OSError, json.JSONDecodeError):
        return []


def _save_hypotheses(hypotheses: List[Dict[str, Any]]) -> None:
    HYPOTHESIS_ARTIFACT.write_text(
        json.dumps({"generated_at": _utcnow(), "hypotheses": hypotheses}, indent=2)
    )


def _hypothesis_to_dict(h) -> Dict[str, Any]:
    if hasattr(h, "model_dump"):
        return h.model_dump(mode="json")
    if hasattr(h, "dict"):
        return h.dict()
    return dict(h) if not isinstance(h, dict) else h


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #

def _generate_hypotheses() -> List[Dict[str, Any]]:
    """Run the HypothesisEngine against current artifacts."""
    from src.investigation.hypothesis_engine import Hypothesis

    engine = services_intel.hypothesis_engine()

    # ghost candidates from the ghost predictions artifact
    ghosts = []
    try:
        doc = services.ghost_document()
        ghosts = doc.get("ghost_nodes", []) if isinstance(doc, dict) else doc
    except FileNotFoundError:
        ghosts = []

    # predicted links from the link-prediction engine (bounded, top pool)
    predicted = []
    try:
        graph = services.load_graph()
        lp = services_intel.link_engine()
        lp.fit(graph, top_k=80, train_fraction=0.6)
        predicted = lp.predict_links(graph, top_k=40)
    except Exception:
        predicted = []

    try:
        hyps = engine.generate_all(ghost_candidates=ghosts, predicted_links=predicted)
    except Exception as exc:
        logger.warning("Full hypothesis generation failed (%s); falling back to ghosts-only", exc)
        try:
            hyps = engine.from_ghosts(ghosts)
        except Exception:
            hyps = []
    serialized = []
    for h in hyps:
        if isinstance(h, Hypothesis):
            serialized.append(h.model_dump(mode="json"))
        else:
            serialized.append(dict(h) if isinstance(h, dict) else {"id": str(h)})
    _save_hypotheses(serialized)
    return serialized


@router.post("/generate")
def generate_hypotheses():
    """(Re)generate the full hypothesis set from current graph signals."""
    with _lock:
        hyps = _generate_hypotheses()
    audit.record_action("hypotheses.generate", object_ids=[h.get("id") for h in hyps[:20]])
    return {"generated_at": _utcnow(), "count": len(hyps), "hypotheses": hyps}


# --------------------------------------------------------------------------- #
# Listing / detail
# --------------------------------------------------------------------------- #

@router.get("")
@router.get("/")
def list_hypotheses(
    hypothesis_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    limit: int = Query(200, ge=1, le=1000),
):
    """List hypotheses, optionally filtered by type / status / confidence."""
    hyps = _load_hypotheses()
    if hypothesis_type:
        hyps = [h for h in hyps if h.get("hypothesis_type") == hypothesis_type]
    if status:
        hyps = [h for h in hyps if h.get("status") == status]
    if min_confidence is not None:
        hyps = [h for h in hyps if (h.get("confidence") or 0) >= min_confidence]
    hyps.sort(key=lambda h: -(h.get("confidence") or 0))
    hyps = [_with_polarity(h) for h in hyps[:limit]]
    return {"items": hyps, "total": len(hyps)}


@router.get("/{hypothesis_id}")
def hypothesis_detail(hypothesis_id: str):
    """One hypothesis with evidence + contradiction breakdown."""
    for h in _load_hypotheses():
        if h.get("id") == hypothesis_id:
            return _with_polarity(h)
    raise HTTPException(status_code=404, detail=f"Hypothesis not found: {hypothesis_id}")


def _with_polarity(h: Dict[str, Any]) -> Dict[str, Any]:
    """Attach a contradiction report to a hypothesis using real evidence."""
    try:
        from src.investigation.contradiction import EvidenceContradictionDetector

        store = services.evidence_store()
        detector = EvidenceContradictionDetector(store)
        claim = h.get("explanation") or h.get("subject") or ""
        all_ids = list(h.get("supporting_evidence_ids") or []) + list(
            h.get("counter_evidence_ids") or [])
        report = detector.analyse(h.get("id", ""), claim, all_ids[:40])
        h = dict(h)
        h["contradiction"] = report.to_dict()
    except Exception:
        h = dict(h)
        h["contradiction"] = None
    return h


# --------------------------------------------------------------------------- #
# Analyst disposition
# --------------------------------------------------------------------------- #

@router.post("/{hypothesis_id}/disposition")
def disposition(
    hypothesis_id: str,
    body: Dict[str, Any] = Body(...),
):
    """Record an analyst disposition (CONFIRM / REJECT / DEFER / REQUEST_EVIDENCE)."""
    verdict = str(body.get("disposition", "")).upper()
    if verdict not in VALID_DISPOSITIONS:
        raise HTTPException(status_code=422, detail=f"disposition must be one of {sorted(VALID_DISPOSITIONS)}")
    reason = str(body.get("reason", "") or "")[:1000]
    analyst = str(body.get("analyst", "anonymous"))[:80]

    hyps = _load_hypotheses()
    target = next((h for h in hyps if h.get("id") == hypothesis_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Hypothesis not found: {hypothesis_id}")

    status_map = {
        "CONFIRM": "SUPPORTED",
        "REJECT": "REJECTED",
        "DEFER": "UNDER_REVIEW",
        "REQUEST_EVIDENCE": "UNDER_REVIEW",
    }
    with _lock:
        fresh = _load_hypotheses()
        t2 = next((h for h in fresh if h.get("id") == hypothesis_id), None)
        if t2 is None:
            raise HTTPException(status_code=404, detail=f"Hypothesis not found: {hypothesis_id}")
        t2["status"] = status_map[verdict]
        t2["updated_at"] = _utcnow()
        t2.setdefault("dispositions", []).append({
            "disposition": verdict,
            "reason": reason,
            "analyst": analyst,
            "timestamp": _utcnow(),
        })
        _save_hypotheses(fresh)

    audit.record_action(
        "hypotheses.disposition",
        object_ids=[hypothesis_id],
        detail={"disposition": verdict},
    )
    return {"id": hypothesis_id, "status": status_map[verdict],
            "disposition": verdict, "recorded_at": _utcnow()}