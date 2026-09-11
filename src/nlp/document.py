"""
nlp/document.py
---------------
Universal Document Understanding Abstraction for Thupparivu.

Every unstructured or semi-structured source (FIR, complaint, CDR, transaction,
witness report, intelligence note, CCTV report) is structured into a rich,
traceable Document model preserving exact character spans, provenance hashes,
modality, polarity, and multi-stage extraction artifacts.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ModalityType(str, Enum):
    """Epistemic modality / certainty level of statements."""
    FACTUAL = "FACTUAL"          # Directly observed / recorded record
    ALLEGED = "ALLEGED"          # Explicitly stated as allegation in complaint/FIR
    REPORTED = "REPORTED"        # Reported by third party / witness statement
    SUSPECTED = "SUSPECTED"      # Investigative suspicion / hypothesis
    DENIED = "DENIED"            # Explicitly denied by subject
    UNCONFIRMED = "UNCONFIRMED"  # Awaiting independent corroboration
    SPECULATIVE = "SPECULATIVE"  # Unsubstantiated inference
    INFERRED = "INFERRED"        # Model / graph derivation


class PolarityType(str, Enum):
    """Claim polarity."""
    POSITIVE = "POSITIVE"        # Asserted occurrence
    NEGATED = "NEGATED"          # Asserted non-occurrence (e.g. "did not call")
    UNCERTAIN = "UNCERTAIN"      # Ambiguous / unverifiable


class TemporalRelationType(str, Enum):
    """Temporal ordering between events / incidents."""
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    DURING = "DURING"
    OVERLAPS = "OVERLAPS"
    SAME_TIME = "SAME_TIME"
    APPROXIMATE = "APPROXIMATE"
    UNKNOWN = "UNKNOWN"


@dataclass
class SourceSpan:
    """Character-level slice into raw source text."""
    start_char: int
    end_char: int
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_char": self.start_char,
            "end_char": self.end_char,
            "text": self.text,
        }


@dataclass
class TokenUnit:
    """A token with character offsets and morph/pos attributes."""
    index: int
    text: str
    normalized: str
    start_char: int
    end_char: int
    pos: str = ""
    is_punct: bool = False
    is_stop: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "normalized": self.normalized,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "pos": self.pos,
        }


@dataclass
class SentenceUnit:
    """A sentence segment with span offsets and contained tokens."""
    index: int
    text: str
    start_char: int
    end_char: int
    tokens: List[TokenUnit] = field(default_factory=list)
    has_negation: bool = False
    modality: ModalityType = ModalityType.FACTUAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "token_count": len(self.tokens),
            "has_negation": self.has_negation,
            "modality": self.modality.value,
        }


@dataclass
class EntitySpan:
    """An extracted entity mention with exact source provenance."""
    id: str
    entity_type: str
    surface_text: str
    normalized_text: str
    span: SourceSpan
    sentence_index: int = 0
    confidence: float = 1.0
    extractor: str = "rule_ner"
    attributes: Dict[str, Any] = field(default_factory=dict)
    resolved_entity_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "surface_text": self.surface_text,
            "normalized_text": self.normalized_text,
            "span": self.span.to_dict(),
            "sentence_index": self.sentence_index,
            "confidence": round(self.confidence, 4),
            "extractor": self.extractor,
            "attributes": self.attributes,
            "resolved_entity_id": self.resolved_entity_id,
        }


@dataclass
class TemporalSpan:
    """An extracted temporal expression (relative or absolute)."""
    id: str
    surface_text: str
    span: SourceSpan
    sentence_index: int
    normalized_iso: Optional[str] = None
    is_relative: bool = False
    temporal_relation: TemporalRelationType = TemporalRelationType.UNKNOWN
    reference_anchor: Optional[str] = None
    delta_minutes: Optional[float] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "surface_text": self.surface_text,
            "span": self.span.to_dict(),
            "sentence_index": self.sentence_index,
            "normalized_iso": self.normalized_iso,
            "is_relative": self.is_relative,
            "temporal_relation": self.temporal_relation.value,
            "reference_anchor": self.reference_anchor,
            "delta_minutes": self.delta_minutes,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class NegationSpan:
    """A detected negation cue and its grammatical scope."""
    cue_text: str
    cue_span: SourceSpan
    scope_span: SourceSpan
    sentence_index: int
    negated_entities: List[str] = field(default_factory=list)
    negated_relations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cue_text": self.cue_text,
            "cue_span": self.cue_span.to_dict(),
            "scope_span": self.scope_span.to_dict(),
            "sentence_index": self.sentence_index,
            "negated_entities": self.negated_entities,
            "negated_relations": self.negated_relations,
        }


@dataclass
class CoreferenceLink:
    """Pronominal or nominal coreference resolving mention to antecedent."""
    mention_span: SourceSpan
    antecedent_id: str
    antecedent_text: str
    confidence: float
    method: str = "distance_heuristic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mention_span": self.mention_span.to_dict(),
            "antecedent_id": self.antecedent_id,
            "antecedent_text": self.antecedent_text,
            "confidence": round(self.confidence, 4),
            "method": self.method,
        }


@dataclass
class ClaimUnit:
    """An atomic extracted investigative claim."""
    claim_id: str
    subject: str
    predicate: str
    object: str
    polarity: PolarityType = PolarityType.POSITIVE
    modality: ModalityType = ModalityType.FACTUAL
    confidence: float = 1.0
    source_span: Optional[SourceSpan] = None
    evidence_id: str = ""
    timestamp: Optional[str] = None
    location: Optional[str] = None
    sentence_index: int = 0
    is_negated: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "polarity": self.polarity.value,
            "modality": self.modality.value,
            "confidence": round(self.confidence, 4),
            "source_span": self.source_span.to_dict() if self.source_span else None,
            "evidence_id": self.evidence_id,
            "timestamp": self.timestamp,
            "location": self.location,
            "sentence_index": self.sentence_index,
            "is_negated": self.is_negated,
            "attributes": self.attributes,
        }


@dataclass
class EventUnit:
    """An extracted event with multi-entity participants, location & time."""
    event_id: str
    event_type: str
    participants: List[Dict[str, str]] = field(default_factory=list) # [{"id": "...", "role": "..."}]
    location: Optional[str] = None
    timestamp: Optional[str] = None
    source_span: Optional[SourceSpan] = None
    evidence_id: str = ""
    sentence_index: int = 0
    modality: ModalityType = ModalityType.FACTUAL
    polarity: PolarityType = PolarityType.POSITIVE
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "participants": self.participants,
            "location": self.location,
            "timestamp": self.timestamp,
            "source_span": self.source_span.to_dict() if self.source_span else None,
            "evidence_id": self.evidence_id,
            "sentence_index": self.sentence_index,
            "modality": self.modality.value,
            "polarity": self.polarity.value,
            "attributes": self.attributes,
        }


@dataclass
class Document:
    """The canonical Document representation across the NLP pipeline."""
    document_id: str
    source_id: str
    case_id: Optional[str] = None
    source_type: str = "REPORT"  # FIR | CDR | TRANSACTION | REPORT | WITNESS_STATEMENT | CCTV
    language: str = "en"
    language_confidence: float = 1.0
    raw_text: str = ""
    normalized_text: str = ""
    content_hash: str = ""
    created_at: str = field(default_factory=_utcnow)
    
    # Structural breakdown
    sentences: List[SentenceUnit] = field(default_factory=list)
    entities: List[EntitySpan] = field(default_factory=list)
    temporal_spans: List[TemporalSpan] = field(default_factory=list)
    negations: List[NegationSpan] = field(default_factory=list)
    coreferences: List[CoreferenceLink] = field(default_factory=list)
    claims: List[ClaimUnit] = field(default_factory=list)
    events: List[EventUnit] = field(default_factory=list)
    
    # Document-level intelligence metrics (Section 48)
    ocr_quality: float = 1.0
    extraction_confidence: float = 1.0
    contradiction_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content_hash and self.raw_text:
            self.content_hash = _sha256(self.raw_text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "case_id": self.case_id,
            "source_type": self.source_type,
            "language": self.language,
            "language_confidence": round(self.language_confidence, 3),
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "metrics": {
                "sentence_count": len(self.sentences),
                "entity_count": len(self.entities),
                "temporal_count": len(self.temporal_spans),
                "negation_count": len(self.negations),
                "coreference_count": len(self.coreferences),
                "claim_count": len(self.claims),
                "event_count": len(self.events),
                "ocr_quality": round(self.ocr_quality, 2),
                "extraction_confidence": round(self.extraction_confidence, 4),
            },
            "sentences": [s.to_dict() for s in self.sentences],
            "entities": [e.to_dict() for e in self.entities],
            "temporal_spans": [t.to_dict() for t in self.temporal_spans],
            "negations": [n.to_dict() for n in self.negations],
            "coreferences": [c.to_dict() for c in self.coreferences],
            "claims": [cl.to_dict() for cl in self.claims],
            "events": [ev.to_dict() for ev in self.events],
            "metadata": self.metadata,
        }
