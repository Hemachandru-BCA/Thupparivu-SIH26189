"""
routers/cases.py
----------------
Case workspace API (Phase Q route group: /api/cases/*).

A local, demo-safe workspace where an investigator collects entities,
paths, evidence, findings, simulations and notes.  Stored as JSON under
``data/cases/``.  A generated case file is a working artifact, NOT an
official legal record.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from src.api import audit, paths, schemas

router = APIRouter(prefix="/api/cases", tags=["cases"])
_lock = threading.Lock()


def _case_path(case_id: str) -> Path:
    safe = "".join(c for c in case_id if c.isalnum() or c in "-_")
    return paths.CASES_DIR / f"{safe}.json"


def _load_case(case_id: str) -> Dict:
    path = _case_path(case_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Corrupt case file: {case_id}")


def _save_case(case: Dict) -> None:
    path = _case_path(case["id"])
    path.write_text(json.dumps(case, indent=2, default=str))


@router.get("")
@router.get("/")
def list_cases():
    """All cases (summaries)."""
    items = []
    for p in sorted(paths.CASES_DIR.glob("CASE-*.json")):
        try:
            case = json.loads(p.read_text())
            items.append({
                "id": case.get("id"),
                "title": case.get("title"),
                "status": case.get("status"),
                "items_count": len(case.get("items", [])),
                "updated_at": case.get("updated_at"),
            })
        except json.JSONDecodeError:
            continue
    return {"items": items, "total": len(items)}


@router.post("", status_code=201)
@router.post("/", status_code=201)
def create_case(request: schemas.CaseCreateRequest):
    """Create a new case workspace."""
    now = datetime.now(timezone.utc).isoformat()
    case = {
        "id": f"CASE-{uuid.uuid4().hex[:8].upper()}",
        "title": request.title,
        "description": request.description,
        "investigator": request.investigator,
        "status": "OPEN",
        "items": [],
        "notes": [],
        "dossier_ids": [],
        "created_at": now,
        "updated_at": now,
        "disclaimer": "Working case file - not an official legal record.",
    }
    with _lock:
        _save_case(case)
    audit.record_action("cases.create", object_ids=[case["id"]])
    return case


@router.get("/{case_id}")
def get_case(case_id: str):
    case = _load_case(case_id)
    audit.record_action("cases.view", object_ids=[case_id])
    return case


@router.patch("/{case_id}")
def update_case(case_id: str, request: schemas.CaseUpdateRequest):
    """Update title/description, add or remove workspace items, add notes."""
    with _lock:
        case = _load_case(case_id)
        if request.title is not None:
            case["title"] = request.title
        if request.description is not None:
            case["description"] = request.description
        if request.add_item is not None:
            item = request.add_item.model_dump(mode="json")
            existing = {(i["kind"], i["ref_id"]) for i in case["items"]}
            if (item["kind"], item["ref_id"]) not in existing:
                case["items"].append(item)
        if request.remove_item is not None:
            ref = request.remove_item
            case["items"] = [
                i for i in case["items"]
                if not (i["kind"] == ref.kind and i["ref_id"] == ref.ref_id)
            ]
        if request.note:
            case["notes"].append({
                "text": request.note,
                "at": datetime.now(timezone.utc).isoformat(),
            })
        case["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_case(case)
    audit.record_action("cases.update", object_ids=[case_id])
    return case


@router.delete("/{case_id}")
def delete_case(case_id: str):
    with _lock:
        path = _case_path(case_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        path.unlink()
    audit.record_action("cases.delete", object_ids=[case_id])
    return {"deleted": case_id}
