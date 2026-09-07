"""
routers/data.py
------------------
Read-only endpoints over the generator/preprocessing outputs: persons,
gangs (derived), calls, transactions, meetings, cleaned records. All
support simple pagination via ?page=&page_size=.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from src.api import data_access, paths

router = APIRouter(prefix="/api/data", tags=["data"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


def _page_params(page: int, page_size: int) -> tuple[int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return page, page_size


@router.get("/summary")
def data_summary():
    """Quick counts of everything currently on disk, for a frontend dashboard."""

    def _count_csv(path):
        try:
            return len(data_access.get_persons_csv(path))
        except Exception:
            return 0

    def _count_json(path):
        try:
            return len(data_access.get_cleaned_records(path))
        except Exception:
            return 0

    return {
        "persons": _count_csv(paths.PERSONS_CSV),
        "calls": _count_csv(paths.CALLS_CSV),
        "transactions": _count_csv(paths.TRANSACTIONS_CSV),
        "meetings": _count_csv(paths.MEETINGS_CSV),
        "cleaned_records": _count_json(paths.CLEANED_RECORDS_PATH),
        "graph_triplets_exists": paths.GRAPH_TRIPLETS_PATH.exists(),
        "graph_built": paths.GRAPH_PKL_PATH.exists(),
        "ghost_predictions_exist": paths.GHOST_PREDICTIONS_PATH.exists(),
    }


@router.get("/persons")
def list_persons(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    gang_id: Optional[str] = None,
    role: Optional[str] = None,
):
    page, page_size = _page_params(page, page_size)
    rows = data_access.get_persons_csv(paths.PERSONS_CSV)
    if gang_id:
        rows = [r for r in rows if r.get("gang_id") == gang_id]
    if role:
        rows = [r for r in rows if r.get("role") == role]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/gangs")
def list_gangs():
    """Derived from persons.csv (there's no gangs.csv on disk)."""
    rows = data_access.get_persons_csv(paths.PERSONS_CSV)
    gangs: dict[str, dict] = {}
    for row in rows:
        gid = row.get("gang_id")
        if not gid:
            continue
        gang = gangs.setdefault(gid, {"gang_id": gid, "member_count": 0, "roles": {}})
        gang["member_count"] += 1
        role = row.get("role") or "unknown"
        gang["roles"][role] = gang["roles"].get(role, 0) + 1
    return {"items": list(gangs.values()), "total": len(gangs)}


@router.get("/calls")
def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    person_id: Optional[str] = None,
):
    page, page_size = _page_params(page, page_size)
    rows = data_access.get_calls_csv(paths.CALLS_CSV)
    if person_id:
        rows = [r for r in rows if person_id in (r.get("caller_id"), r.get("receiver_id"))]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/transactions")
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    person_id: Optional[str] = None,
):
    page, page_size = _page_params(page, page_size)
    rows = data_access.get_transactions_csv(paths.TRANSACTIONS_CSV)
    if person_id:
        rows = [r for r in rows if person_id in (r.get("sender_id"), r.get("receiver_id"))]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/meetings")
def list_meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    person_id: Optional[str] = None,
):
    page, page_size = _page_params(page, page_size)
    rows = data_access.get_meetings_csv(paths.MEETINGS_CSV)
    if person_id:
        rows = [r for r in rows if person_id in r.get("attendee_ids", [])]
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/records")
def list_cleaned_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    record_type: Optional[str] = Query(
        None, description="person | fir | intelligence_report"
    ),
):
    page, page_size = _page_params(page, page_size)
    rows = data_access.get_cleaned_records(paths.CLEANED_RECORDS_PATH, record_type=record_type)
    items, total = data_access.paginate(rows, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}
