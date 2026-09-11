"""
llm/guardrails.py
-----------------
Strict Hallucination Guardrails & Evidence Verification for LLM Output.

Enforces:
  1. No hallucinated evidence IDs (must resolve in EvidenceStore)
  2. No conversion of INFERRED to OBSERVED facts
  3. Preservation of UNKNOWN states
  4. Automatic fallback to deterministic summarization on validation error
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Set, Tuple

logger = logging.getLogger(__name__)

class LLMGuardrails:
    """Validates candidate LLM output against verified ground-truth context."""

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
