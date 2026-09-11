"""
nlp/negation_modality.py
------------------------
Negation and Modality / Epistemic Certainty Analyzer.

Distinguishes:
 - Factual vs Alleged vs Reported vs Denied vs Uncertain
 - Positively asserted vs Negated ("did not call", "no evidence of transfer")
"""

from __future__ import annotations
from typing import List
from src.nlp.document import NegationSpan, ModalityType, SourceSpan

def detect_negations(text: str, sentence_index: int) -> List[NegationSpan]:
    """Detect negation cues and estimate their scope."""
    # Placeholder: pattern matching on "not", "never", "denied", etc.
    return []

def detect_modality(text: str) -> ModalityType:
    """Classify the certainty/epistemic status of a statement."""
    # Placeholder: classify into FACTUAL, ALLEGED, REPORTED, etc.
    return ModalityType.FACTUAL
