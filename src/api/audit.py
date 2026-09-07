"""
audit.py
--------
Append-only audit log (Phase AC).

Records investigator actions (searches, graph expansions, evidence views,
simulations, dossier generation) with action, timestamp and object ids -
never raw personal payloads.  Written as JSON Lines under
``data/exports/audit_log.jsonl``; failures never break the API response.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.api import paths

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def record_action(action: str, *, actor: str = "anonymous",
                  object_ids: Optional[Iterable[str]] = None,
                  detail: Optional[Dict[str, Any]] = None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "object_ids": [str(o) for o in (object_ids or [])][:50],
        "detail": detail or {},
    }
    try:
        path = Path(paths.AUDIT_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
    except OSError:  # pragma: no cover - audit must never break requests
        logger.exception("failed to append audit entry")


def recent_entries(limit: int = 100) -> list:
    try:
        path = Path(paths.AUDIT_LOG_PATH)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
        return [json.loads(line) for line in lines[-limit:] if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []
