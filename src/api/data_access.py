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
import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

logger = logging.getLogger(__name__)


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


# --------------------------------------------------------------------------- #
# StorageBackend abstraction (Task 10: S3 persistence for cases + audit log)
# --------------------------------------------------------------------------- #

class StorageBackend(ABC):
    """Interface for keyed blob storage (local files or S3)."""

    @abstractmethod
    def read(self, key: str) -> Optional[bytes]:
        """Return bytes for key, or None if missing."""

    @abstractmethod
    def write(self, key: str, data: bytes) -> None:
        """Write bytes to key (overwrites existing)."""

    @abstractmethod
    def list(self, prefix: str) -> List[str]:
        """List all keys under the given prefix."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete key if present; no-op if missing."""


class LocalStorageBackend(StorageBackend):
    """Current behavior: read/write local files under data/."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or Path("data")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Prevent path traversal
        safe = Path(key).name if "/" not in key else key
        return self.root / safe

    def read(self, key: str) -> Optional[bytes]:
        path = self._resolve(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def write(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def list(self, prefix: str) -> List[str]:
        prefix_path = self.root / prefix
        if not prefix_path.exists():
            return []
        return [str(p.relative_to(self.root)) for p in prefix_path.rglob("*") if p.is_file()]

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()


class AdapterNotConfigured(Exception):
    """Raised when an optional adapter (boto3) is not installed/configured."""


class S3StorageBackend(StorageBackend):
    """S3-backed storage. Requires SENTINELGRAPH_S3_BUCKET + boto3."""

    def __init__(
        self,
        bucket: Optional[str] = None,
        prefix: str = "",
        region: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        self.bucket = bucket or os.environ.get("SENTINELGRAPH_S3_BUCKET")
        if not self.bucket:
            raise AdapterNotConfigured("SENTINELGRAPH_S3_BUCKET not set")
        self.prefix = prefix.rstrip("/")
        self.region = region or os.environ.get("AWS_DEFAULT_REGION", "ap-south-1")
        try:
            import boto3  # lazy import - only required for S3
        except ImportError as exc:
            raise AdapterNotConfigured("boto3 not installed") from exc
        if access_key and secret_key:
            self.s3 = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            self.s3 = boto3.client("s3", region_name=self.region)

    def _full_key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def read(self, key: str) -> Optional[bytes]:
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=self._full_key(key))
            return resp["Body"].read()
        except Exception:
            return None

    def write(self, key: str, data: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=self._full_key(key), Body=data)

    def list(self, prefix: str) -> List[str]:
        full = self._full_key(prefix)
        keys = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def delete(self, key: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=self._full_key(key))
        except Exception:
            pass


def get_storage_backend() -> StorageBackend:
    """
    Factory: returns S3StorageBackend if SENTINELGRAPH_S3_BUCKET is set,
    else LocalStorageBackend.
    """
    if os.environ.get("SENTINELGRAPH_S3_BUCKET"):
        try:
            return S3StorageBackend()
        except AdapterNotConfigured as exc:
            logger.warning("S3 configured but unavailable: %s - falling back to local", exc)
    return LocalStorageBackend()


# --------------------------------------------------------------------------- #
# Audit log buffering for S3 (append semantics over PUT)
# --------------------------------------------------------------------------- #

class AuditLogWriter:
    """Buffered audit-log writer.

    Local backend: appends each line directly (existing behavior).
    S3 backend: buffers lines in memory for up to 50 entries OR 30 seconds,
    then flushes as a single PUT to "audit/audit_log_{ts}.jsonl".
    """

    FLUSH_ENTRY_COUNT = 50
    FLUSH_INTERVAL_SECONDS = 30

    def __init__(self, backend: Optional[StorageBackend] = None):
        self.backend = backend or get_storage_backend()
        self._buffer: List[str] = []
        self._last_flush = time.time()
        self._is_s3 = isinstance(self.backend, S3StorageBackend)
        self._lock = __import__("threading").Lock()

    def append(self, line: Dict[str, Any]) -> None:
        text = json.dumps(line, default=str)
        if not self._is_s3:
            # Local: direct append (atomic-ish)
            key = "exports/audit_log.jsonl"
            existing = self.backend.read(key) or b""
            self.backend.write(key, existing + text.encode("utf-8") + b"\n")
            return
        # S3: buffer
        with self._lock:
            self._buffer.append(text)
            if len(self._buffer) >= self.FLUSH_ENTRY_COUNT or \
               (time.time() - self._last_flush) >= self.FLUSH_INTERVAL_SECONDS:
                self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        with self._lock:
            lines = self._buffer
            self._buffer = []
            self._last_flush = time.time()
        if lines:
            ts = int(time.time())
            key = f"exports/audit_log_{ts}.jsonl"
            payload = "\n".join(lines).encode("utf-8") + b"\n"
            self.backend.write(key, payload)
