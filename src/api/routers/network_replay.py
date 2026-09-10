"""
routers/network_replay.py
-------------------------
Network Replay / Temporal Evolution API (route group: /api/replay/*).

Provides timeline replay with delta updates, important event markers,
and three timeline modes (snapshot, cumulative, sliding-window).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.api import audit, services

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/replay", tags=["network-replay"])


def _get_engine():
    from src.analysis.network_replay import NetworkReplayEngine
    graph = services.load_graph()
    return NetworkReplayEngine(graph)


@router.get("/buckets")
def replay_buckets(n_buckets: int = Query(12, ge=4, le=60)):
    """Timeline bucket timestamps for replay animation."""
    engine = _get_engine()
    timestamps = engine.get_bucket_timestamps(n_buckets)
    audit.record_action("replay.buckets", detail={"n_buckets": n_buckets})
    return {"timestamps": timestamps, "count": len(timestamps)}


@router.get("/snapshot")
def replay_snapshot(
    timestamp: str = Query(..., description="ISO timestamp"),
    mode: str = Query("cumulative", description="cumulative | snapshot | sliding_window"),
    max_edges: int = Query(5000, ge=100, le=30000),
):
    """Graph state at a specific timestamp."""
    engine = _get_engine()
    snap = engine.snapshot_at(timestamp, mode=mode)
    result = snap.model_dump()
    if snap.truncated:
        result["nodes"] = result["nodes"][:max_edges * 2]
        result["edges"] = result["edges"][:max_edges]
    audit.record_action("replay.snapshot", detail={"timestamp": timestamp, "mode": mode})
    return result


@router.get("/diff")
def replay_diff(
    from_ts: str = Query(..., alias="from", description="Start timestamp"),
    to_ts: str = Query(..., alias="to", description="End timestamp"),
):
    """Structural diff between two timestamps."""
    engine = _get_engine()
    delta = engine.compute_delta(from_ts, to_ts)
    audit.record_action("replay.diff", detail={"from": from_ts, "to": to_ts})
    return delta.model_dump()


@router.get("/events")
def replay_events():
    """Important temporal events identified in the network."""
    engine = _get_engine()
    events = engine.identify_events()
    audit.record_action("replay.events", detail={"count": len(events)})
    return {
        "events": [e.model_dump() for e in events],
        "total": len(events),
    }
