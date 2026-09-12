"""
analysis/modus_operandi.py
--------------------------
Modus Operandi (MO) Pattern Extraction and Clustering.

Discovers recurring sequences of events, communication patterns, and
movement structures across heterogeneous cases and intelligence reports.

Critical epistemic boundary (MASTER DIRECTIVE §21):

    "The same operational pattern appears across these cases."
      ≠
    "The same person committed all of them."

The engine reports pattern similarity only - it never attributes identity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Sequence

MO_NAMESPACE = uuid.UUID("3f2a8d57-9b27-4a3c-b1e4-2d0f6c8a5f31")

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
    supporting_evidence: List[str] = field(default_factory=list)
    similarity_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def disclaimer(self) -> str:
        """Operational pattern similarity is not identity attribution."""
        return "Operational pattern similarity is not identity attribution."

    @property
    def epistemic_status(self) -> str:
        return "INFERRED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "event_sequence": self.event_sequence,
            "frequency": self.frequency,
            "associated_cases": self.associated_cases,
            "confidence": round(self.confidence, 3),
            "description": self.description,
            "supporting_evidence": self.supporting_evidence,
            "similarity_scores": self.similarity_scores,
            "epistemic_status": "INFERRED",
            "disclaimer": "Operational pattern similarity is not identity attribution.",
        }


@dataclass
class CrossCaseLink:
    """A structured cross-case correlation result.

    Highlights shared structural features (entities, phones, accounts,
    locations, relationship shapes) between two apparently separate cases.
    """

    link_id: str
    case_a: str
    case_b: str
    shared_entities: List[str] = field(default_factory=list)
    shared_phones: List[str] = field(default_factory=list)
    shared_accounts: List[str] = field(default_factory=list)
    shared_locations: List[str] = field(default_factory=list)
    shared_mo_patterns: List[str] = field(default_factory=list)
    overlap_score: float = 0.0
    explanation: str = ""
    supporting_evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "link_id": self.link_id,
            "case_a": self.case_a,
            "case_b": self.case_b,
            "shared_entities": self.shared_entities,
            "shared_phones": self.shared_phones,
            "shared_accounts": self.shared_accounts,
            "shared_locations": self.shared_locations,
            "shared_mo_patterns": self.shared_mo_patterns,
            "overlap_score": round(self.overlap_score, 4),
            "explanation": self.explanation,
            "supporting_evidence": self.supporting_evidence,
            "disclaimer": "Shared features indicate correlation, not causation or identity.",
        }


def make_mo_id(sequence: Sequence[str]) -> str:
    """Deterministic MO pattern ID from the event sequence."""
    return "MO-" + str(uuid.uuid5(MO_NAMESPACE, "|".join(sequence)))


def sequence_similarity(seq_a: Sequence[str], seq_b: Sequence[str]) -> float:
    """Jaccard-style similarity between two event sequences."""
    if not seq_a or not seq_b:
        return 0.0
    a, b = set(seq_a), set(seq_b)
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class MOAnalyzer:
    """Extracts recurring MO patterns and cross-case links from case timelines."""

    def __init__(self, min_frequency: int = 2, min_similarity: float = 0.5) -> None:
        self.min_frequency = min_frequency
        self.min_similarity = min_similarity

    def extract_patterns(self, case_sequences: Dict[str, List[str]]) -> List[MOPattern]:
        """Group event sequences from multiple cases into recurring MO patterns.

        ``case_sequences`` maps case_id -> ordered event-type sequence.
        """
        from collections import Counter
        sequence_counter: Counter = Counter()
        case_map: Dict[tuple, List[str]] = {}

        for case_id, seq in case_sequences.items():
            key = tuple(seq)
            if not key:
                continue  # empty sequences are not operational patterns
            sequence_counter[key] += 1
            case_map.setdefault(key, []).append(case_id)

        patterns: List[MOPattern] = []
        for key, count in sequence_counter.items():
            if count < self.min_frequency:
                continue
            cases = case_map[key]
            pattern_id = make_mo_id(key)
            patterns.append(MOPattern(
                pattern_id=pattern_id,
                name=" > ".join(key[:4]) + (" ..." if len(key) > 4 else ""),
                event_sequence=list(key),
                frequency=count,
                associated_cases=cases,
                confidence=round(min(1.0, 0.4 + 0.15 * count), 3),
                supporting_evidence=[f"case:{c}" for c in cases],
                similarity_scores={c: 1.0 for c in cases},
            ))
        # Sort by frequency
        patterns.sort(key=lambda p: (-p.frequency, p.pattern_id))
        return patterns

    def cross_case_links(
        self,
        case_entities: Dict[str, List[str]],
        case_sequences: Dict[str, List[str]],
    ) -> List[CrossCaseLink]:
        """Find structural correlations between case pairs.

        A shared name alone is insufficient (MASTER DIRECTIVE §26); we
        require at least one shared non-entity identifier (phone/account) OR
        a recurring MO sequence before emitting a link.
        """
        links: List[CrossCaseLink] = []
        case_ids = list(case_entities.keys())
        mo_patterns = self.extract_patterns(case_sequences)
        mo_by_case: Dict[str, List[str]] = {c: [] for c in case_ids}
        for pat in mo_patterns:
            for c in pat.associated_cases:
                mo_by_case.setdefault(c, []).append(pat.pattern_id)

        for i in range(len(case_ids)):
            for j in range(i + 1, len(case_ids)):
                a, b = case_ids[i], case_ids[j]
                entities_a = set(case_entities.get(a, []))
                entities_b = set(case_entities.get(b, []))
                shared_entities = sorted(entities_a & entities_b)
                shared_mo = sorted(set(mo_by_case.get(a, [])) & set(mo_by_case.get(b, [])))

                # Decomposable overlap components (MASTER DIRECTIVE §27)
                entity_overlap = (len(shared_entities) / max(1, len(entities_a | entities_b))
                                  if shared_entities else 0.0)
                mo_overlap = (len(shared_mo) / max(1, len(set(mo_by_case.get(a, [])) | set(mo_by_case.get(b, []))))
                              if shared_mo else 0.0)

                has_strong_identifier = False
                # Require at least one shared non-entity identifier (phone/
                # account) OR a recurring MO sequence OR very high entity
                # overlap before emitting a link (MASTER DIRECTIVE §26).
                # A shared name alone is NOT sufficient.
                if mo_overlap >= 0.5 or entity_overlap >= 0.6:
                    has_strong_identifier = True

                if not has_strong_identifier:
                    continue

                link_id = "XL-" + str(uuid.uuid5(MO_NAMESPACE, f"{a}|{b}"))
                overlap_score = round(0.5 * entity_overlap + 0.5 * mo_overlap, 4)
                explanation_parts = []
                if shared_entities:
                    explanation_parts.append(f"shared entities: {', '.join(shared_entities[:5])}")
                if shared_mo:
                    explanation_parts.append(f"shared MO patterns: {', '.join(shared_mo[:3])}")
                links.append(CrossCaseLink(
                    link_id=link_id,
                    case_a=a,
                    case_b=b,
                    shared_entities=shared_entities,
                    shared_mo_patterns=shared_mo,
                    overlap_score=overlap_score,
                    explanation="; ".join(explanation_parts) or "structural overlap",
                    supporting_evidence=[f"case:{a}", f"case:{b}"],
                ))

        links.sort(key=lambda l: (-l.overlap_score, l.link_id))
        return links
