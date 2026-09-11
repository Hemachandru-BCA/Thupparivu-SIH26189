"""
resolution/entity_context.py
----------------------------
Cross-Document Entity Context Aggregator.

Maintains a comprehensive context for every canonical entity:
 - all surface mentions & source documents
 - explicit aliases & variants
 - extracted claims & relationships
 - temporal presence across cases
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

@dataclass
class CrossDocumentEntityContext:
    """Consolidated profile spanning multiple cases and sources."""
    canonical_id: str
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    document_ids: List[str] = field(default_factory=list)
    cases: List[str] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    match_explanations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "phone_numbers": self.phone_numbers,
            "document_ids": self.document_ids,
            "cases": self.cases,
            "relationships_count": len(self.relationships),
            "events_count": len(self.events),
        }
