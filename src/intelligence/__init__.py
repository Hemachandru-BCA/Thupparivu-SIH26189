"""Evidence Conflict Detection Engine.

This module identifies contradictions and conflicts in evidence records,
helping investigators understand where evidence disagrees and why.

Conflict types detected:
- Temporal conflicts (incompatible timestamps)
- Location conflicts (entity can't be in two places at once)
- Identity conflicts (contradictory identity claims)
- Relationship conflicts (contradictory relationship assertions)
- Attribute conflicts (conflicting attributes for same entity)
"""

from src.intelligence.conflict import (
    ConflictDetector,
    ConflictType,
    EvidenceConflict,
    ConflictSeverity,
)

__all__ = [
    "ConflictDetector",
    "ConflictType",
    "EvidenceConflict",
    "ConflictSeverity",
]
