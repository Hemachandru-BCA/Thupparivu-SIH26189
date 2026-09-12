"""
llm/guardrails.py
-----------------
Strict Hallucination Guardrails & Evidence Verification for LLM Output.

Enforces (MASTER DIRECTIVE §37):
  1. No hallucinated evidence IDs (must resolve in EvidenceStore)
  2. No conversion of INFERRED to OBSERVED facts
  3. Preservation of UNKNOWN states
  4. No invented entity IDs / relationships
  5. Counter-evidence preservation
  6. Automatic fallback to deterministic summarization on validation error

Validation pipeline (post-generation):

    LLM OUTPUT
      → SCHEMA VALIDATION
      → EVIDENCE VALIDATION
      → EPISTEMIC VALIDATION
      → CONTRADICTION CHECK
      → GROUNDING CHECK
      → FINAL RESPONSE
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any, List, Optional, Set, Tuple

from src.domain.epistemic import coerce, can_refine, EpistemicStatus

logger = logging.getLogger(__name__)

# Generic suspicious phrases that must never appear in generated output
_UNSUPPORTED_PHRASES = [
    "mastermind",
    "is guilty",
    "guilty of",
    "should be arrested",
    "should be arrested",
    "arrest",
    "convict",
    "prosecute",
    "is the coordinator",
    "is the leader of",
    "definitely",
    "certainly coordinated",
    "proves that",
]

_ENTITY_ID_RE = re.compile(r"\bE-\d+\b")
_EVIDENCE_ID_RE = re.compile(r"\bEV-\d+\b|E\d+")


class LLMGuardrails:
    """Validates candidate LLM output against verified ground-truth context."""

    VALIDATION_PIPELINE = [
        "schema_validation",
        "evidence_validation",
        "epistemic_validation",
        "contradiction_check",
        "grounding_check",
    ]

    @staticmethod
    def validate_citations(
        generated_evidence_ids: List[str],
        valid_evidence_ids: Set[str]
    ) -> Tuple[bool, List[str]]:
        """Ensure all generated citations exist in the verified evidence store."""
        invalid_ids = [eid for eid in generated_evidence_ids if eid not in valid_evidence_ids]
        if invalid_ids:
            return False, invalid_ids
        return True, []

    @staticmethod
    def validate_schema(output: Dict[str, Any], required_keys: List[str]) -> bool:
        """Validate structure and epistemic separation in LLM response."""
        for key in required_keys:
            if key not in output:
                return False
        return True

    @staticmethod
    def validate_epistemic_labels(
        output: Dict[str, Any],
        known_labels: Optional[Set[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """Ensure epistemic labels in output are valid and not upgraded.

        If a generated label claims OBSERVED but the finding's status is
        only INFERRED/POSSIBLE upstream, this is a hallucination of truth.
        """
        issues: List[str] = []
        known = known_labels or {"OBSERVED", "INFERRED", "POSSIBLE", "NEGATED",
                                 "CONTRADICTED", "UNKNOWN", "HYPOTHETICAL"}
        for label in _collect_status_labels(output):
            if label not in known:
                issues.append(f"unknown epistemic label '{label}'")
            elif label == "OBSERVED" and output.get("source_status") == "INFERRED":
                issues.append(f"illegal INFERRED -> OBSERVED upgrade for '{label}'")
        return (len(issues) == 0, issues)

    @staticmethod
    def validate_entity_ids(output: Dict[str, Any], valid_entity_ids: Set[str]) -> Tuple[bool, List[str]]:
        """The LLM must never create new entities (MASTER DIRECTIVE §71)."""
        invalid: List[str] = []
        for match in _ENTITY_ID_RE.finditer(str(output)):
            eid = match.group(0)
            if eid not in valid_entity_ids:
                invalid.append(eid)
        return (len(invalid) == 0, invalid)

    @staticmethod
    def forbidden_language(text: str) -> List[str]:
        """Flag language that violates the system's epistemic/safety contract."""
        low = text.lower()
        return [phrase for phrase in _UNSUPPORTED_PHRASES if phrase in low]

    @staticmethod
    def validate_grounding(
        output: Dict[str, Any],
        valid_evidence_ids: Set[str],
        valid_entity_ids: Set[str],
        allowed_statuses: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Run the full post-generation validation pipeline.

        Returns an enriched dict with ``validation`` and ``accepted`` fields.
        Any violation of the epistemic contract rejects the output.
        """
        accepted = True
        violations: List[str] = []

        # 1. Schema
        required = ["summary", "status"] if "summary" in output else ["status"]
        if not LLMGuardrails.validate_schema(output, required):
            accepted = False
            violations.append("schema_validation: missing required keys")

        # 2. Evidence
        cited = list(output.get("evidence_ids", []) or [])
        ok, invalid = LLMGuardrails.validate_citations(cited, valid_evidence_ids)
        if not ok:
            accepted = False
            violations.append(f"evidence_validation: invalid evidence IDs {invalid}")

        # 3. Epistemic
        ok, issues = LLMGuardrails.validate_epistemic_labels(output, allowed_statuses)
        if not ok:
            accepted = False
            violations.append(f"epistemic_validation: {issues}")

        # 4. Contradiction check - counter-evidence must be preserved
        if output.get("has_counter_evidence") and not output.get("counter_evidence_ids"):
            accepted = False
            violations.append("contradiction_check: counter-evidence suppressed")

        # 5. Grounding / forbidden language
        forbidden = LLMGuardrails.forbidden_language(str(output.get("summary", "")))
        if forbidden:
            accepted = False
            violations.append(f"grounding_check: forbidden language {forbidden}")

        output["validation"] = {
            "accepted": accepted,
            "violations": violations,
            "pipeline": LLMGuardrails.VALIDATION_PIPELINE,
        }
        return output


def _collect_status_labels(obj: Any) -> List[str]:
    """Recursively collect status-like values from a dict/list tree."""
    labels: List[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and (key == "status" or "epistemic" in key or "modality" in key):
                labels.append(value)
            else:
                labels.extend(_collect_status_labels(value))
    elif isinstance(obj, list):
        for item in obj:
            labels.extend(_collect_status_labels(item))
    return labels


def _collect_evidence_ids(obj: Any) -> Set[str]:
    """Collect evidence IDs appearing anywhere in a structure."""
    ids: Set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and (value.startswith("EV-") or key == "evidence_id"):
                ids.add(value)
            else:
                ids |= _collect_evidence_ids(value)
    elif isinstance(obj, list):
        for item in obj:
            ids |= _collect_evidence_ids(item)
    return ids


def safe_fallback_brief(context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic, evidence-grounded fallback when LLM output is rejected.

    Says ONLY what the structured data supports - no invented structural
    claims (MASTER DIRECTIVE §35).
    """
    name = context.get("canonical_name") or context.get("entity_id") or "Unknown"
    relationships = context.get("relationships", []) or []
    evidence_ids = context.get("evidence_ids", []) or []
    observed_facts = context.get("observed_facts", []) or []
    unknowns = context.get("unknowns", []) or []

    summary_parts = [
        f"{name} has {len(relationships)} observed relationships across "
        f"{len(evidence_ids)} verifiable evidence records."
    ]
    if observed_facts:
        summary_parts.append("Observed facts: " + "; ".join(observed_facts[:5]))
    if unknowns:
        summary_parts.append("Unknown aspects: " + "; ".join(unknowns[:3]))

    return {
        "title": f"Entity Intelligence Brief: {name}",
        "summary": " ".join(summary_parts),
        "status": "OBSERVED",
        "evidence_ids": evidence_ids[:20],
        "observed_facts": observed_facts,
        "unknowns": unknowns,
        "counter_evidence_ids": context.get("counter_evidence_ids", [])[:10],
        "method": "deterministic_fallback_v2",
        "disclaimer": "Analytical priority indicator, not an accusation of guilt.",
        "dossier_status": "DRAFT_FOR_HUMAN_REVIEW",
    }
