"""
analysis/modus_operandi.py
--------------------------
Modus Operandi (MO) Pattern Extraction and Clustering.

Discovers recurring sequences of events, communication patterns, and
movement structures across heterogeneous cases and intelligence reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class MOPattern:
    """A recurring sequence of actions/events forming an operational signature."""
    pattern_id: str
    name: str
    event_sequence: List[str]
    frequency: int = 1
    associated_cases: List[str] = field(default_factory=list)
    confidence: float = 0.8
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "event_sequence": self.event_sequence,
            "frequency": self.frequency,
            "associated_cases": self.associated_cases,
            "confidence": round(self.confidence, 3),
            "description": self.description,
        }
