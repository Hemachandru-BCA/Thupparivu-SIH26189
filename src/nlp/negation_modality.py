"""
nlp/negation_modality.py
------------------------
Negation and Modality / Epistemic Certainty Analyzer.

Distinguishes:
 - Factual vs Alleged vs Reported vs Denied vs Uncertain
 - Positively asserted vs Negated ("did not call", "no evidence of transfer")
"""

from __future__ import annotations
import re
from typing import List, Optional
from src.nlp.document import NegationSpan, ModalityType, SourceSpan

# Negation patterns
_NEGATION_CUES = [
    r"\b(not|never|no|none|nothing|nowhere|neither|nor)\b",
    r"\b(didn't|doesn't|don't|did not|does not|do not|was not|were not|is not|are not|wasn't|weren't|isn't|aren't)\b",
    r"\b(denied|denies|denial|refuted|refutes|refutation|contradicted|contradicts|contradiction)\b",
    r"\b(lacked|lacks|lack of|absence of|no evidence of|no indication of|no sign of)\b",
    r"\b(without|free from|clear of)\b",
]

# Modality/uncertainty patterns
_UNCERTAINTY_CUES = [
    r"\b(may|might|could|possibly|potentially|apparently|allegedly|reportedly|supposedly|purportedly)\b",
    r"\b(likely|unlikely|probable|improbable|plausible|implausible)\b",
    r"\b(suspected|suspicion|hypothesis|speculation|conjecture)\b",
    r"\b(uncertain|unclear|unknown|ambiguous|vague|inconclusive)\b",
    r"\b(believed|believed to be|thought to be|understood to be)\b",
]

# Attribution patterns
_ATTRIBUTION_CUES = [
    r"\b(according to|as per|based on|stated by|reported by|told by|said by)\b",
    r"\b(witness|source|informant|official|document|record)\s+(stated|said|reported|claimed|alleged)\b",
]

# Affirmation patterns
_AFFIRMATION_CUES = [
    r"\b(confirmed|confirms|confirmed that|verified|verifies|established|establishes)\b",
    r"\b(admitted|admits|acknowledged|acknowledges|accepted|accepts)\b",
    r"\b(observed|observed that|found that|discovered|discovered that)\b",
]

# Negation scope heuristics
_NEGATION_SCOPE_WINDOW = 15  # words

def detect_negations(text: str, sentence_index: int = 0) -> List[NegationSpan]:
    """Detect negation cues and estimate their scope."""
    negations = []
    
    # Compile combined pattern
    combined = "|".join(f"({cue})" for cue in _NEGATION_CUES)
    pattern = re.compile(combined, re.IGNORECASE)
    
    for match in pattern.finditer(text):
        cue_text = match.group(0)
        start, end = match.start(), match.end()
        
        # Estimate scope: find the next clause boundary or window
        scope_start = max(0, start - _NEGATION_SCOPE_WINDOW * 6)  # rough char estimate
        scope_end = min(len(text), end + _NEGATION_SCOPE_WINDOW * 6)
        
        # Find actual clause boundaries
        scope_text = text[scope_start:scope_end]
        # Look for clause separators
        clause_separators = [',', ';', '.', '!', '?', ' and ', ' but ', ' or ']
        actual_scope_start = scope_start
        actual_scope_end = scope_end
        
        # Simple heuristic: scope extends to next clause boundary after cue
        for sep in clause_separators:
            pos = scope_text.find(sep, end - scope_start)
            if pos != -1:
                actual_scope_end = scope_start + pos + len(sep)
                break
        
        negations.append(NegationSpan(
            cue_text=cue_text,
            cue_span=SourceSpan(start_char=start, end_char=end, text=cue_text),
            scope_span=SourceSpan(start_char=actual_scope_start, end_char=actual_scope_end, text=text[actual_scope_start:actual_scope_end]),
            sentence_index=sentence_index,
            negated_entities=[],  # Would be populated by entity resolver
            negated_relations=[],
        ))
    
    return negations

def detect_modality(text: str) -> ModalityType:
    """Classify the certainty/epistemic status of a statement."""
    text_lower = text.lower()
    
    # Check for explicit denial
    if re.search(r"\b(denied|denies|denial|refuted|refutes)\b", text_lower):
        return ModalityType.DENIED
    
    # Check for attribution/allegation (also bare "alleged X did Y")
    if re.search(r"\b(alleged|alleges|allegation)\b", text_lower):
        return ModalityType.ALLEGED
    for cue in _ATTRIBUTION_CUES:
        if re.search(cue, text_lower):
            return ModalityType.REPORTED
    
    # Check for suspicion/hypothesis
    if re.search(r"\b(suspected|suspicion|hypothesis|speculation)\b", text_lower):
        return ModalityType.SUSPECTED
    
    # Check for uncertainty
    for cue in _UNCERTAINTY_CUES:
        if re.search(cue, text_lower):
            return ModalityType.UNCERTAIN
    
    # Check for affirmation
    for cue in _AFFIRMATION_CUES:
        if re.search(cue, text_lower):
            return ModalityType.FACTUAL
    
    # Default to factual for direct statements
    return ModalityType.FACTUAL

def analyze_sentence_claims(text: str, sentence_index: int = 0) -> dict:
    """Analyze a sentence for negation, modality, and attribution."""
    negations = detect_negations(text, sentence_index)
    modality = detect_modality(text)
    
    # Determine polarity
    polarity = "NEGATED" if negations else "POSITIVE"
    
    # Check for attribution
    attributed = False
    for cue in _ATTRIBUTION_CUES:
        if re.search(cue, text, re.IGNORECASE):
            attributed = True
            break
    
    return {
        "text": text,
        "sentence_index": sentence_index,
        "negations": [n.to_dict() for n in negations],
        "modality": modality.value,
        "polarity": polarity,
        "attributed": attributed,
        "has_negation": len(negations) > 0,
    }
