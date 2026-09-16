"""
routers/priority.py
-------------------
Investigation Priority API (route group: /api/priority/*).

Surfaces the Investigation Priority Score engine (spec sections 32-33):

* GET /api/priority/             - ranked priority entities (dashboard list)
* GET /api/priority/entity/{id}  - one entity's priority + component breakdown
* GET /api/priority/config       - active component weights (transparency)

The score is an *investigative lead score*.  It is never a probability of
guilt and never a recommendation to take enforcement action.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services, services_intel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/priority", tags=["priority"])

#: Entity types that can be prioritised as investigative leads.  Infrastructure
#: nodes (accounts/locations/phones) are structural glue, not subjects.
DEFAULT_LEAD_TYPES = ["PERSON", "ORGANIZATION"]


def _get_engine():
    """Cached priority engine (rebuilt when graph.pkl changes)."""
    from src.analysis.investigation_priority import InvestigationPriorityEngine

    return services_intel.priority_engine(
        builder=lambda: InvestigationPriorityEngine(
            graph=services.load_graph(),
            evidence_store=services.evidence_store(),
        )
    )


@router.get("/")
def ranked_priority(
    entity_type: Optional[str] = Query(
        None,
        description="Restrict to a single entity type (e.g. PERSON). "
                    "Defaults to lead-bearing types (PERSON, ORGANIZATION).",
    ),
    include_all_types: bool = Query(
        False,
        description="Include infrastructure nodes (ACCOUNT, LOCATION, ...) too.",
    ),
    limit: int = Query(50, ge=1, le=500),
):
    """Ranked list of entities by investigation priority."""
    engine = _get_engine()

    include_types = None
    if not include_all_types:
        include_types = [entity_type.upper()] if entity_type else DEFAULT_LEAD_TYPES

    results = engine.ranked_entities(
        entity_type=entity_type,
        limit=limit,
        include_types=include_types,
    )
    audit.record_action(
        "priority.ranked",
        detail={"entity_type": entity_type, "count": len(results)},
    )
    return {
        "items": [r.model_dump() for r in results],
        "total": len(results),
        "weights": engine.weights,
        "disclaimer": (
            "Priority is a structural investigative lead score - not a "
            "probability of guilt."
        ),
    }


@router.get("/config")
def priority_config():
    """The active component weights (never silently changed)."""
    engine = _get_engine()
    from src.analysis.investigation_priority import DEFAULT_WEIGHTS

    return {
        "active_weights": engine.weights,
        "default_weights": DEFAULT_WEIGHTS,
        "components": [
            {"name": "network_influence", "label": "Network influence"},
            {"name": "bridge_potential", "label": "Bridge potential"},
            {"name": "communication_anomaly", "label": "Communication anomaly"},
            {"name": "financial_anomaly", "label": "Financial anomaly"},
            {"name": "temporal_correlation", "label": "Temporal correlation"},
            {"name": "cross_case_linkage", "label": "Cross-case linkage"},
            {"name": "evidence_strength", "label": "Evidence strength"},
        ],
    }


@router.get("/entity/{entity_id}")
def entity_priority(entity_id: str):
    """Priority score + full component breakdown for one entity."""
    engine = _get_engine()
    try:
        result = engine.score_entity(entity_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    audit.record_action("priority.entity", object_ids=[entity_id])
    return result.model_dump()