"""
postgres_repository.py
----------------------
SourceRepository interface + optional PostgreSQL adapter (Phase T).

Disabled by default; requires ``psycopg`` (v3) and connection settings via
environment variables.  The local demo reads CSV/JSON artifacts directly
and does not need this adapter.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


class AdapterNotConfigured(RuntimeError):
    """Raised when an optional adapter is used without configuration."""


class SourceRepository(Protocol):
    """Relational access to ingested source records."""

    def fetch_record(self, source: str, record_id: str) -> Optional[Dict[str, Any]]: ...

    def fetch_by_type(self, source: str, record_type: str,
                      *, limit: int = 100) -> List[Dict[str, Any]]: ...

    def upsert_record(self, source: str, record: Dict[str, Any]) -> None: ...


class PostgresSourceRepository:
    """PostgreSQL-backed SourceRepository (psycopg v3, lazy import).

    Configuration (env):
        SENTINELGRAPH_PG_DSN   e.g. postgresql://user:pass@host:5432/sentinelgraph
        SENTINELGRAPH_PG_TABLE records table (default: source_records)
    """

    def __init__(self, dsn: Optional[str] = None, table: Optional[str] = None) -> None:
        try:
            import psycopg  # noqa: F401
        except ImportError as exc:
            raise AdapterNotConfigured(
                "psycopg is not installed. Install with: pip install psycopg[binary]"
            ) from exc
        self.dsn = dsn or os.environ.get("SENTINELGRAPH_PG_DSN")
        if not self.dsn:
            raise AdapterNotConfigured("SENTINELGRAPH_PG_DSN is not set")
        self.table = table or os.environ.get("SENTINELGRAPH_PG_TABLE", "source_records")

    # ------------------------------------------------------------------ #
    def _conn(self):
        import psycopg

        return psycopg.connect(self.dsn)

    def ensure_schema(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    source        TEXT NOT NULL,
                    record_id     TEXT NOT NULL,
                    record_type   TEXT,
                    payload       JSONB NOT NULL,
                    updated_at    TIMESTAMPTZ DEFAULT now(),
                    PRIMARY KEY (source, record_id)
                )
                """
            )

    def fetch_record(self, source: str, record_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT payload FROM {self.table} WHERE source = %s AND record_id = %s",
                (source, record_id),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def fetch_by_type(self, source: str, record_type: str,
                      *, limit: int = 100) -> List[Dict[str, Any]]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT payload FROM {self.table} "
                f"WHERE source = %s AND record_type = %s LIMIT %s",
                (source, record_type, limit),
            )
            rows = cur.fetchall()
        return [r[0] for r in rows]

    def upsert_record(self, source: str, record: Dict[str, Any]) -> None:
        record_id = str(record.get("record_id", ""))
        if not record_id:
            raise ValueError("record requires record_id")
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.table} (source, record_id, record_type, payload)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source, record_id)
                DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                """,
                (source, record_id, str(record.get("record_type", "")),
                 json.dumps(record, default=str)),
            )
