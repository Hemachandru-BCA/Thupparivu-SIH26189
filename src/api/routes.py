"""
routes.py
---------
Single import point aggregating every API route group (Phase R organisation):

    /api/pipeline/*       - pipeline trigger + job status        (routers/pipeline)
    /api/data/*           - raw artifact browsing                (routers/data)
    /api/graph/*          - graph, subgraph, paths, ghosts       (routers/graph)
    /api/evidence/*       - evidence provenance + search         (routers/evidence)
    /api/findings/*       - XAI findings                         (routers/findings)
    /api/simulation/*     - counterfactual simulations           (routers/simulation)
    /api/dossiers/*       - dossier generation + review          (routers/dossiers)
    /api/cases/*          - case workspace                       (routers/cases)
    /api/search           - global search                        (routers/search)
    /api/audit            - audit log view                       (routers/audit)

Intelligence route groups (deeper analytical engines):

    /api/temporal/*       - temporal snapshots, replay, diff     (routers/temporal)
    /api/hypotheses/*     - hypothesis engine + disposition      (routers/hypotheses)
    /api/investigation/*  - counterfactual, gaps, resilience     (routers/investigation)
    /api/models/*         - model registry + benchmark           (routers/models)
    /api/communities/*    - community profiles + roles           (routers/communities)
    /api/financial/*      - fund-flow tracing                    (routers/financial)
    /api/intel/*          - case brief, gaps, cross-case         (routers/intel)
"""

from src.api.routers import (  # noqa: F401
    audit as audit_router,
    cases as cases_router,
    communities as communities_router,
    data as data_router,
    dossiers as dossiers_router,
    evidence as evidence_router,
    financial as financial_router,
    findings as findings_router,
    graph as graph_router,
    hypotheses as hypotheses_router,
    intel as intel_router,
    investigation as investigation_router,
    models as models_router,
    pipeline as pipeline_router,
    search as search_router,
    simulation as simulation_router,
    temporal as temporal_router,
)

ALL_ROUTERS = [
    pipeline_router.router,
    data_router.router,
    graph_router.router,
    evidence_router.router,
    findings_router.router,
    simulation_router.router,
    dossiers_router.router,
    cases_router.router,
    search_router.router,
    audit_router.router,
    # ── intelligence route groups ──────────────────────────────
    temporal_router.router,
    hypotheses_router.router,
    investigation_router.router,
    models_router.router,
    communities_router.router,
    financial_router.router,
    intel_router.router,
]
