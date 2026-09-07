"""
routers/audit.py
----------------
Read-only view over the audit log (Phase AC).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.api import audit

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
@router.get("/")
def recent(limit: int = Query(100, ge=1, le=1000)):
    """Most recent audit entries (action + timestamp + object ids only)."""
    return {"items": audit.recent_entries(limit), "total": len(audit.recent_entries(limit))}
