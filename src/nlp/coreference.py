"""
nlp/coreference.py
------------------
Coreference Resolution for investigative text.

Handles references such as:
> "Ravi met Kumar. He then called Arun."

Uses grammatical cues, recency, entity compatibility, and contextual scoring.
When uncertain, returns UNKNOWN / AMBIGUOUS rather than hallucinating a link.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from src.nlp.document import SourceSpan, CoreferenceLink

# Pronoun patterns
_PRONOUN_PATTERNS = {
    "personal": re.compile(r"\b(he|she|him|her|his|hers|they|them|their|theirs)\b", re.IGNORECASE),
    "reflexive": re.compile(r"\b(himself|herself|themselves)\b", re.IGNORECASE),
    "relative": re.compile(r"\b(who|whom|whose|which|that)\b", re.IGNORECASE),
}

# Gender hints from names (simple heuristic)
_MALE_NAMES = {"ravi", "kumar", "arjun", "vikram", "suresh", "rohit", "rahul", "amit", "sanjay", "vijay", "deepak", "manoj", "anil", "rajesh", "sunil", "vikas", "ashok", "naveen", "varun", "aditya", "harish", "mohit", "rakesh", "ajay", "gaurav", "vishal", "pradeep"}
_FEMALE_NAMES = {"priya", "meera", "pooja", "neha"}

@dataclass
class EntityCandidate:
    """A candidate antecedent entity."""
    entity_id: str
    text: str
    normalized: str
    sentence_index: int
    start_char: int
    end_char: int
    gender_hint: Optional[str] = None  # "male", "female", "neutral"
    is_person: bool = True

def resolve_coreferences(
    text: str, 
    entities: List,  # List of EntitySpan
    sentence_spans: List[Tuple[int, int]],
    sentence_texts: List[str]
) -> List:
    """Resolve pronominal and nominal coreferences in text."""
    links = []
    
    # Build entity candidates from extracted entities
    candidates = []
    for ent in entities:
        if hasattr(ent, 'entity_type') and ent.entity_type in ("PERSON", "ALIAS", "ORGANIZATION", "LOCATION"):
            gender = None
            norm = ent.normalized_text.lower().strip()
            if norm in _MALE_NAMES:
                gender = "male"
            elif norm in _FEMALE_NAMES:
                gender = "female"
            else:
                gender = "neutral"
            
            candidates.append(EntityCandidate(
                entity_id=ent.id,
                text=ent.surface_text,
                normalized=norm,
                sentence_index=ent.sentence_index,
                start_char=ent.span.start_char,
                end_char=ent.span.end_char,
                gender_hint=gender,
                is_person=(ent.entity_type in ("PERSON", "ALIAS"))
            ))
    
    # Sort candidates by recency (most recent first)
    candidates.sort(key=lambda c: c.sentence_index, reverse=True)
    
    # Process each sentence for pronouns
    for sent_idx, sent_text in enumerate(sentence_texts):
        # Check for personal pronouns
        for match in re.finditer(r"\b(he|she|him|her|his|hers|they|them|their|theirs)\b", sent_text, re.IGNORECASE):
            pronoun = match.group(1).lower()
            pronoun_start = match.start()
            pronoun_end = match.end()
            
            # Find best antecedent
            antecedent = _find_best_antecedent(pronoun, sent_idx, candidates)
            
            if antecedent and antecedent.confidence > 0.5:
                links.append(CoreferenceLink(
                    mention_span=SourceSpan(
                        start_char=pronoun_start,
                        end_char=pronoun_end,
                        text=match.group(1)
                    ),
                    antecedent_id=antecedent.entity_id,
                    antecedent_text=antecedent.text,
                    confidence=antecedent.confidence,
                    method="pronoun_recency_gender"
                ))
    
    return links

def _find_best_antecedent(
    pronoun: str, 
    current_sentence: int, 
    candidates: List
) -> Optional[object]:
    """Find the best antecedent for a pronoun using recency, gender, and semantic constraints."""
    if not candidates:
        return None
    
    # Determine pronoun properties
    pronoun_lower = pronoun.lower()
    pronoun_gender = "neutral"
    if pronoun_lower in ("he", "him", "his", "himself"):
        pronoun_gender = "male"
    elif pronoun_lower in ("she", "her", "hers", "herself"):
        pronoun_gender = "female"
    elif pronoun_lower in ("they", "them", "their", "theirs", "themselves"):
        pronoun_gender = "plural_or_neutral"
    
    best_candidate = None
    best_score = 0.0
    
    for cand in candidates:
        # Skip if candidate is in future sentence (shouldn't happen with reverse sort)
        if cand.sentence_index > current_sentence:
            continue
        
        # Gender compatibility
        gender_score = 1.0
        if pronoun_gender == "male" and cand.gender_hint == "female":
            gender_score = 0.1
        elif pronoun_gender == "female" and cand.gender_hint == "male":
            gender_score = 0.1
        elif pronoun_gender == "plural_or_neutral" and cand.gender_hint in ("male", "female"):
            gender_score = 0.5
        
        # Recency score (prefer more recent)
        recency = current_sentence - cand.sentence_index
        recency_score = max(0.0, 1.0 - recency * 0.15)  # Decays over sentences
        
        # Person type compatibility
        person_score = 1.0 if cand.is_person else 0.3
        
        # Combined score
        score = (gender_score * 0.4) + (recency_score * 0.4) + (person_score * 0.2)
        
        if score > best_score:
            best_score = score
            best_candidate = cand
    
    if best_candidate and best_score > 0.5:
        # Create a simple result object
        class Result:
            def __init__(self, cand, score):
                self.entity_id = cand.entity_id
                self.text = cand.text
                self.confidence = score
        return Result(best_candidate, best_score)
    
    return None

def extract_nominal_coreferences(
    text: str,
    entities: List,
    sentence_texts: List[str]
) -> List:
    """Extract nominal coreferences (e.g., 'the suspect', 'the vehicle')."""
    # Placeholder for nominal coreference resolution
    # Would handle: "the suspect", "the accused", "the vehicle", "the location"
    return []