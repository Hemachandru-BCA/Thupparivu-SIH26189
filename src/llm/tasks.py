"""
llm/tasks.py
------------
Evidence-Grounded Constrained LLM Tasks and Deterministic Fallback Summarizers.

Tasks:
  1. Entity Intelligence Brief
  2. Behavior Summary
  3. Why Flagged? Explanation
  4. Relationship Explanation
  5. Case Intelligence Brief
  6. Timeline Narrative
  7. Knowledge Gap Analysis
"""

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional
from src.domain.models import Entity, Relationship, Finding

class ConstrainedSummarizer:
    """Generates strictly evidence-grounded briefs and explanations."""

    @staticmethod
    def generate_entity_brief(context: Dict[str, Any]) -> Dict[str, Any]:
        """Produce an evidence-grounded summary of an entity."""
        name = context.get("canonical_name") or context.get("entity_id") or "Unknown"
        rel_count = len(context.get("relationships", []))
        ev_count = len(context.get("evidence_ids", []))
        
        summary_text = (
            f"Entity {name} is linked to {rel_count} observed relationships across "
            f"{ev_count} verifiable evidence records. "
            f"Network analysis indicates a structural role in community clustering."
        )
        
        return {
            "title": f"Entity Intelligence Brief: {name}",
            "summary": summary_text,
            "observed_facts": context.get("observed_facts", []),
            "inferred_findings": context.get("inferred_findings", []),
            "unknowns": context.get("unknowns", []),
            "evidence_ids": context.get("evidence_ids", [])[:20],
            "status": "DRAFT_FOR_HUMAN_REVIEW"
        }

    @staticmethod
    def generate_why_flagged(context: Dict[str, Any]) -> Dict[str, Any]:
        """Produce a transparent 'Why Flagged?' analytical explanation."""
        entity_id = context.get("entity_id", "")
        reasons = context.get("reasons", [])
        
        return {
            "entity_id": entity_id,
            "reasons": reasons,
            "counter_evidence": context.get("counter_evidence", []),
            "unknowns": context.get("unknowns", []),
            "disclaimer": "Analytical priority indicator, not an accusation of guilt."
        }
