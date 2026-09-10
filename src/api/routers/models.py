"""
routers/models.py
-----------------
Model registry API (route group: /api/models/*).

Exposes model cards, run records, the capability matrix, and a benchmark
view over measured model metrics (real values only: precision@10, recall@10,
PR-AUC, calibration...).  The registry is JSON-backed and only records
metrics that were actually computed — nothing is fabricated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services, services_intel

router = APIRouter(prefix="/api/models", tags=["models"])


def _registry():
    return services_intel.model_registry()


@router.get("")
@router.get("/")
def list_models():
    """All registered model cards (purpose, capabilities, version)."""
    return {"items": _registry().list_models(), "total": len(_registry().list_models())}


# NOTE: Specific routes (runs, capabilities, benchmark) MUST come before
# the catch-all /{model_name} route so FastAPI matches them first.


@router.get("/runs")
def list_runs(
    model: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """Recent model-run records (run_id, model, version, metrics, status)."""
    runs = _registry().list_runs()
    if model:
        runs = [r for r in runs if r.model == model]
    runs.sort(key=lambda r: r.started_at, reverse=True)
    return {"items": [r.model_dump(mode="json") for r in runs[:limit]],
            "total": len(runs)}


@router.get("/capabilities")
def capability_matrix():
    """Which models are registered for which analytical capability."""
    models = _registry().list_models()
    matrix = {}
    for m in models:
        for cap in m.get("capabilities", []):
            matrix.setdefault(cap, []).append(m["name"])
    return {"capabilities": matrix, "models": [m["name"] for m in models]}


@router.get("/benchmark/metrics")
def benchmark_metrics():
    """Measured model metrics from the last benchmark run (if any).

    Returns precision@10 / recall@10 / F1 / PR-AUC per model family.
    These are real measured values from ``run_benchmark.py`` — never
    interpolated or fabricated.
    """
    from src.api import paths

    metrics_path = paths.GRAPH_OUTPUT_DIR / "model_metrics.json"
    if not metrics_path.exists():
        return {
            "available": False,
            "note": "No benchmark metrics yet. Run the benchmark stage to populate model_metrics.json.",
            "items": [],
        }
    import json

    data = json.loads(metrics_path.read_text())
    items = data.get("task_metrics") or data.get("models") or data.get("metrics") or []
    return {"available": True, "items": items, "source": str(metrics_path)}


@router.post("/benchmark/run")
def run_benchmark():
    """Trigger a reproducible benchmark run (synchronous, bounded).

    Runs the evaluation suite's synthetic benchmark and records metrics in
    the model registry.  Returns a masked run summary — full output is
    written to data/exports/benchmark/.
    """
    try:
        from src.evaluation.run_benchmark import run_as_api

        summary = run_as_api()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {exc}")
    audit.record_action("models.benchmark_run")
    return summary


# ── Catch-all route AFTER all specific routes ──────────────────
@router.get("/{model_name}")
def model_detail(model_name: str):
    model = _registry().get_model(model_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
    runs = [r for r in _registry().list_runs() if r.model == model_name]
    return {"model": model, "runs": [r.model_dump(mode="json") for r in runs]}