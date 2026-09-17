"""
routers/ghost_ranker.py
------------------------
Status endpoint for the trained supervised ghost ranker.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.ml.ghost_ranker import DEFAULT_RANKER_PATH, load_ranker_if_available, ranker_exists

router = APIRouter(prefix="/api/ghost", tags=["ghost"])


@router.get("/ranker/status")
def ranker_status():
    """Return whether a trained ranker exists, its training date,
    cross-val metrics, and Brier score."""
    if not ranker_exists(DEFAULT_RANKER_PATH):
        return {
            "exists": False,
            "trained_at": None,
            "kind": None,
            "cv_metrics": None,
            "brier_score": None,
            "ece": None,
            "n_samples": 0,
        }
    ranker = load_ranker_if_available(DEFAULT_RANKER_PATH)
    if ranker is None:
        return {"exists": False, "trained_at": None, "kind": None,
                "cv_metrics": None, "brier_score": None, "ece": None}
    return ranker.status()