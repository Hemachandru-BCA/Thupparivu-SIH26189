"""Evidence Conflict API routes.

Endpoints for querying and analyzing evidence conflicts.

Routes:
- GET /api/evidence/conflicts - Get all conflicts
- GET /api/evidence/conflicts/entity/{entity_id} - Conflicts for entity
- GET /api/evidence/conflicts/evidence/{evidence_id} - Conflicts for evidence
- GET /api/evidence/conflicts/summary - Conflict summary statistics
- GET /api/evidence/conflicts/by-severity - Filter by severity
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, services
from src.intelligence.conflict import ConflictDetector, ConflictSeverity

router = APIRouter(prefix="/api/evidence/conflicts", tags=["evidence-conflicts"])
logger = logging.getLogger(__name__)


def _get_conflict_detector():
    """Get or create conflict detector."""
    graph = services.load_graph()
    evidence_store = services.evidence_store()
    return ConflictDetector(graph=graph, evidence_store=evidence_store)


@router.get("")
def get_all_conflicts() -> Dict[str, Any]:
    """Get all detected evidence conflicts.
    
    Returns all conflicts detected in the system with full details
    including conflict type, severity, and evidence references.
    """
    detector = _get_conflict_detector()
    conflicts = detector.detect_all_conflicts()
    
    audit.record_action("evidence.conflicts.get_all", detail={
        "total_conflicts": len(conflicts),
    })
    
    return {
        "conflicts": [c.model_dump() for c in conflicts],
        "count": len(conflicts),
    }


@router.get("/entity/{entity_id}")
def get_conflicts_for_entity(entity_id: str) -> Dict[str, Any]:
    """Get conflicts involving a specific entity.
    
    Args:
        entity_id: The entity to get conflicts for
        
    Returns:
        Conflicts where the entity is involved
    """
    detector = _get_conflict_detector()
    conflicts = detector.get_conflicts_for_entity(entity_id)
    
    audit.record_action("evidence.conflicts.get_entity", detail={
        "entity_id": entity_id,
        "conflict_count": len(conflicts),
    })
    
    return {
        "entity_id": entity_id,
        "conflicts": [c.model_dump() for c in conflicts],
        "count": len(conflicts),
    }


@router.get("/evidence/{evidence_id}")
def get_conflicts_for_evidence(evidence_id: str) -> Dict[str, Any]:
    """Get conflicts involving specific evidence.
    
    Args:
        evidence_id: The evidence record to get conflicts for
        
    Returns:
        Conflicts where the evidence is referenced
    """
    detector = _get_conflict_detector()
    conflicts = detector.get_conflicts_for_evidence(evidence_id)
    
    audit.record_action("evidence.conflicts.get_evidence", detail={
        "evidence_id": evidence_id,
        "conflict_count": len(conflicts),
    })
    
    return {
        "evidence_id": evidence_id,
        "conflicts": [c.model_dump() for c in conflicts],
        "count": len(conflicts),
    }


@router.get("/summary")
def get_conflict_summary() -> Dict[str, Any]:
    """Get summary statistics of all conflicts.
    
    Returns aggregate statistics including counts by type and severity.
    """
    detector = _get_conflict_detector()
    summary = detector.summarize_conflicts()
    
    audit.record_action("evidence.conflicts.summary")
    
    return summary


@router.get("/by-severity")
def get_conflicts_by_severity(
    min_severity: str = Query("LOW", description="Minimum severity threshold"),
) -> Dict[str, Any]:
    """Get conflicts filtered by minimum severity.
    
    Args:
        min_severity: Minimum severity (LOW, MEDIUM, HIGH, CRITICAL)
        
    Returns:
        Conflicts at or above the specified severity
    """
    try:
        severity = ConflictSeverity(min_severity.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity: {min_severity}. Must be LOW, MEDIUM, HIGH, or CRITICAL",
        )
    
    detector = _get_conflict_detector()
    conflicts = detector.get_conflicts_by_severity(severity)
    
    audit.record_action("evidence.conflicts.by_severity", detail={
        "min_severity": min_severity,
        "conflict_count": len(conflicts),
    })
    
    return {
        "min_severity": min_severity,
        "conflicts": [c.model_dump() for c in conflicts],
        "count": len(conflicts),
    }


@router.get("/types")
def get_conflict_types() -> Dict[str, Any]:
    """Get available conflict types.
    
    Returns the list of conflict types the system can detect.
    """
    from src.intelligence.conflict import ConflictType
    
    return {
        "types": [ct.value for ct in ConflictType],
        "count": len(ConflictType),
    }
