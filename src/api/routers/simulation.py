"""
routers/simulation.py
---------------------
Counterfactual simulation API (Phase J/K route group: /api/simulation/*).

SAFETY: all endpoints here return *counterfactual network simulations*.
They are explicitly labelled as such in every payload and are never
enforcement recommendations.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api import audit, paths, schemas, services
from src.graph.simulation import (
    SimulationError,
    compare_interventions,
    counterfactual_node_removal,
)

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.post("/node-removal")
def simulate_node_removal(request: schemas.SimulationRequest):
    """Counterfactual node-removal simulation.

    Returns baseline + counterfactual metrics, deltas, community changes,
    new brokers, alternate paths, affected nodes/edges and warnings.
    Response is labelled: NETWORK EFFECT SCORE - NOT AN ENFORCEMENT
    RECOMMENDATION.
    """
    try:
        graph = services.load_graph()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    from src.graph.simulation import SimulationConfig

    config = SimulationConfig(efficiency_sample_size=256)
    try:
        result = counterfactual_node_removal(
            graph,
            request.node_id,
            depth=request.depth,
            include_reranking=request.include_reranking,
            config=config,
            new_broker_sample=150,
            precomputed=services.simulation_context(),
        )
    except SimulationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit.record_action(
        "simulation.node_removal",
        object_ids=[request.node_id],
        detail={"depth": request.depth, "include_reranking": request.include_reranking},
    )
    return result


@router.post("/compare")
def compare_scenarios(request: schemas.ComparisonRequest):
    """Intervention comparison sandbox (Phase M).

    Side-by-side counterfactuals ranked by network effect.  Explicitly
    labelled NOT AN ENFORCEMENT RECOMMENDATION.
    """
    try:
        graph = services.load_graph()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = compare_interventions(graph, request.node_ids)
    audit.record_action(
        "simulation.compare", object_ids=list(request.node_ids)
    )
    return result


@router.get("/results")
def stored_results(k: int = 10):
    """The batch arrest-simulation results document (if previously run)."""
    from src.graph.simulation import load_simulation_results

    try:
        doc = load_simulation_results(str(paths.GRAPH_OUTPUT_DIR / "simulation_results.json"))
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="No stored simulation results. Run POST /api/pipeline/simulation "
                   "or GET /api/simulation/node-removal for on-demand counterfactuals.",
        )
    return {
        "baseline": doc.get("baseline"),
        "top_interventions": doc.get("optimal_interventions", [])[:k],
        "summary": doc.get("summary"),
    }
