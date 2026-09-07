"""
data_access.py
----------------
Read helpers for the raw/generated artifacts (persons.csv, calls.csv,
transactions.csv, meetings.csv, cleaned_records.json). Kept deliberately
simple (csv.DictReader, no pandas) since the API only needs to page/filter
rows for the React frontend, not transform them.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{path.name} not found. Run POST /api/pipeline/generate first.",
        )
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def paginate(
    rows: List[Dict[str, Any]], page: int, page_size: int
) -> Tuple[List[Dict[str, Any]], int]:
    total = len(rows)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return rows[start:end], total


def get_persons_csv(path: Path) -> List[Dict[str, Any]]:
    return _read_csv(path)


def get_calls_csv(path: Path) -> List[Dict[str, Any]]:
    return _read_csv(path)


def get_transactions_csv(path: Path) -> List[Dict[str, Any]]:
    return _read_csv(path)


def get_meetings_csv(path: Path) -> List[Dict[str, Any]]:
    rows = _read_csv(path)
    for row in rows:
        raw = row.get("attendee_ids") or ""
        row["attendee_ids"] = [a for a in raw.split("|") if a]
    return rows


def get_cleaned_records(
    path: Path, record_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{path.name} not found. Run POST /api/pipeline/preprocess first.",
        )
    with path.open("r", encoding="utf-8") as f:
        records: List[Dict[str, Any]] = json.load(f)
    if record_type:
        records = [r for r in records if r.get("record_type") == record_type]
    return records
