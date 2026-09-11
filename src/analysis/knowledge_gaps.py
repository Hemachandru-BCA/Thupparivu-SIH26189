"""
analysis/knowledge_gaps.py
--------------------------
Investigative Knowledge Gap Engine ("What Thupparivu Does Not Know").

Discovers:
  - Unverified phone/account ownerships
  - Single-source uncorroborated allegations
  - Missing temporal stamps or locations
  - Contradictory witness statements
  - Low-confidence entity linkages
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class KnowledgeGap:
    """An identified gap in investigative evidence."""
    gap_id: str
    gap_type: str        # UNVERIFIED_IDENTIFIER | UNCORROBORATED_CLAIM | MISSING_TIMESTAMP | CONFLICTING_ACCOUNTS
    subject_id: str
    description: str
    severity: str        # HIGH | MEDIUM | LOW
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "gap_type": self.gap_type,
            "subject_id": self.subject_id,
            "description": self.description,
            "severity": self.severity,
            "recommended_action": self.recommended_action,
        }
