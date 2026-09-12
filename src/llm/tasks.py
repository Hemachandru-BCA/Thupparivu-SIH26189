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
from src.llm.guardrails import LLMGuardrails, safe_fallback_brief

class ConstrainedSummarizer:
    """Generates strictly evidence-grounded briefs and explanations."""

    @staticmethod
    def generate_entity_brief(
        context: Dict[str, Any],
        valid_evidence_ids: Optional[set] = None,
        run_guardrails: bool = True,
    ) -> Dict[str, Any]:
        """Produce an evidence-grounded summary of an entity.

        The deterministic path says ONLY what the structured data supports
        (MASTER DIRECTIVE §35) - never invented structural claims.
        """
        name = context.get("canonical_name") or context.get("entity_id") or "Unknown"
        rel_count = len(context.get("relationships", []))
        ev_count = len(context.get("evidence_ids", []))
        observed_facts = context.get("observed_facts", []) or []
        unknowns = context.get("unknowns", []) or []
        evidence_ids = context.get("evidence_ids", []) or []
        counter_ids = context.get("counter_evidence_ids", []) or []

        summary_parts = [
            f"{name} is linked to {rel_count} observed relationships across "
            f"{ev_count} verifiable evidence records."
        ]
        if observed_facts:
            summary_parts.append("Observed facts: " + "; ".join(observed_facts[:5]))
        if unknowns:
            summary_parts.append("Remaining unknowns: " + "; ".join(unknowns[:3]))

        output = {
            "title": f"Entity Intelligence Brief: {name}",
            "summary": " ".join(summary_parts),
            "status": "OBSERVED",
            "observed_facts": observed_facts,
            "inferred_findings": context.get("inferred_findings", []),
            "unknowns": unknowns,
            "evidence_ids": evidence_ids[:20],
            "counter_evidence_ids": counter_ids[:10],
            "method": "deterministic_constrained_v2",
            "disclaimer": "Analytical priority indicator, not an accusation of guilt.",
            "dossier_status": "DRAFT_FOR_HUMAN_REVIEW",
        }

        if run_guardrails and valid_evidence_ids is not None:
            output = LLMGuardrails.validate_grounding(
                output, valid_evidence_ids, set(), None
            )
        return output

    @staticmethod
    def generate_why_flagged(context: Dict[str, Any]) -> Dict[str, Any]:
        """Produce a transparent 'Why Flagged?' analytical explanation.

        Always includes supporting evidence, counter-evidence, unknowns, and
        the analytical-priority disclaimer (MASTER DIRECTIVE §36).
        """
        entity_id = context.get("entity_id", "")
        reasons = context.get("reasons", [])
        supporting = context.get("supporting_evidence_ids", []) or []
        counter = context.get("counter_evidence_ids", []) or []
        unknowns = context.get("unknowns", []) or []

        return {
            "entity_id": entity_id,
            "reasons": reasons,
            "supporting_evidence_ids": supporting[:20],
            "counter_evidence_ids": counter[:10],
            "unknowns": unknowns,
            "disclaimer": (
                "Analytical priority indicator, not an accusation of guilt. "
                "This explains why the entity receives analytical attention; "
                "it is not a legal conclusion."
            ),
        }

    @staticmethod
    def generate_behavior_summary(change_report: Dict[str, Any]) -> Dict[str, Any]:
        """Narrate the structured 'WHAT CHANGED?' findings.

        The LLM may rephrase the structured findings but must not invent new
        ones; the deterministic narrative lists exactly the signals detected.
        """
        entity_id = change_report.get("entity_id", "")
        findings = change_report.get("findings", []) or []
        change_score = change_report.get("change_score", 0.0)

        narrative_parts = [f"Behavioral comparison for {entity_id}."]
        if findings:
            for f in findings[:8]:
                narrative_parts.append(
                    f"{f['signal']}: {f['change']} (before={f['before']}, after={f['after']})"
                )
        else:
            narrative_parts.append("No significant change detected across profiled signals.")

        return {
            "entity_id": entity_id,
            "summary": " ".join(narrative_parts),
            "findings": findings,
            "change_score": round(change_score, 4),
            "evidence_ids": change_report.get("evidence_ids", [])[:20],
            "method": "behavioral_baseline_comparison",
            "status": "INFERRED",
            "disclaimer": "Change score is analytical relevance, not a guilt assessment.",
        }
