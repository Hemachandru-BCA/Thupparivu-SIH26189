"""Pydantic schemas for LLM-assisted extraction.

These schemas enforce strict validation on LLM output, ensuring:
1. All claims are grounded in evidence IDs
2. Extraction methods are tracked
3. Observation status is explicit (OBSERVED/INFERRED/UNKNOWN)
4. Confidence scores are decomposed and transparent

Safety rules:
- LLM output without valid evidence IDs is rejected
- Malformed extractions fail validation
- Every extraction preserves source spans when available
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExtractionMethod(str, Enum):
    """Method used for extraction."""
    RULE_BASED = "RULE_BASED"
    STATISTICAL_NLP = "STATISTICAL_NLP"
    SPACY_NER = "SPACY_NER"
    LLM_ASSISTED = "LLM_ASSISTED"
    LLM_SEMANTIC = "LLM_SEMANTIC"
    HYBRID = "HYBRID"
    MANUAL = "MANUAL"


class ObservationStatus(str, Enum):
    """Observation status of an extraction.
    
    CRITICAL: This is the core epistemic distinction.
    - OBSERVED: Directly present in evidence (e.g., "Ravi met Kumar")
    - INFERRED: Derived from patterns/analysis (e.g., "Ravi likely knows Kumar")
    - UNKNOWN: Cannot determine from available evidence
    - CONTRADICTED: Evidence exists that contradicts this claim
    
    These statuses are NEVER collapsed - the distinction is preserved
    throughout the pipeline.
    """
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"


class EntityType(str, Enum):
    """Entity types recognized by the extraction system."""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    VEHICLE = "VEHICLE"
    ACCOUNT = "ACCOUNT"
    DEVICE = "DEVICE"
    DOCUMENT = "DOCUMENT"
    CASE = "CASE"
    EVENT = "EVENT"
    FINANCIAL_INSTRUMENT = "FINANCIAL_INSTRUMENT"
    COMMUNICATION_ENDPOINT = "COMMUNICATION_ENDPOINT"
    SOCIAL_IDENTIFIER = "SOCIAL_IDENTIFIER"
    UNKNOWN = "UNKNOWN"


class RelationshipType(str, Enum):
    """Relationship types between entities."""
    KNOWS = "KNOWS"
    CALLS = "CALLS"
    MESSAGES = "MESSAGES"
    MEETS = "MEETS"
    OWNS = "OWNS"
    USES = "USES"
    VISITS = "VISITS"
    LOCATED_AT = "LOCATED_AT"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    MENTIONED_IN = "MENTIONED_IN"
    PARTICIPATED_IN = "PARTICIPATED_IN"
    WORKS_FOR = "WORKS_FOR"
    CONNECTED_TO = "CONNECTED_TO"
    RELATED_TO = "RELATED_TO"
    UNKNOWN = "UNKNOWN"


class EventType(str, Enum):
    """Event types extracted from evidence."""
    MEETING = "MEETING"
    COMMUNICATION = "COMMUNICATION"
    TRANSACTION = "TRANSACTION"
    INCIDENT = "INCIDENT"
    MOVEMENT = "MOVEMENT"
    ARREST = "ARREST"
    INVESTIGATION = "INVESTIGATION"
    COURT_PROCEEDING = "COURT_PROCEEDING"
    UNKNOWN = "UNKNOWN"


class SourceSpan(BaseModel):
    """Source location in original document."""
    model_config = ConfigDict(extra="forbid")
    
    start_offset: int = Field(..., ge=0, description="Character start offset in source")
    end_offset: int = Field(..., ge=0, description="Character end offset in source")
    text: str = Field(..., min_length=1, description="Extracted text snippet")
    
    @field_validator("end_offset")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        if "start_offset" in info.data and v < info.data["start_offset"]:
            raise ValueError("end_offset must be >= start_offset")
        return v


class ConfidenceComponents(BaseModel):
    """Decomposed confidence score.
    
    Instead of a single mysterious number, we break down confidence
    into transparent components that can be inspected and challenged.
    """
    model_config = ConfigDict(extra="forbid")
    
    evidence_quality: float = Field(0.5, ge=0.0, le=1.0, 
                                     description="Quality of supporting evidence")
    extraction_confidence: float = Field(0.5, ge=0.0, le=1.0,
                                          description="Confidence in extraction method")
    entity_resolution: float = Field(0.5, ge=0.0, le=1.0,
                                      description="Entity resolution confidence")
    temporal_consistency: float = Field(0.5, ge=0.0, le=1.0,
                                         description="Temporal consistency score")
    graph_support: float = Field(0.5, ge=0.0, le=1.0,
                                  description="Support from graph structure")
    counter_evidence_penalty: float = Field(0.0, ge=0.0, le=1.0,
                                             description="Penalty from counter-evidence")
    
    def overall(self) -> float:
        """Calculate weighted overall confidence.
        
        Formula: weighted average with counter-evidence penalty.
        Weights are transparent and auditable.
        """
        weights = {
            "evidence_quality": 0.25,
            "extraction_confidence": 0.20,
            "entity_resolution": 0.20,
            "temporal_consistency": 0.15,
            "graph_support": 0.20,
        }
        weighted_sum = sum(
            getattr(self, k) * w for k, w in weights.items()
        )
        # Apply counter-evidence penalty
        return max(0.0, weighted_sum * (1.0 - self.counter_evidence_penalty))


class EntityMention(BaseModel):
    """A mention of an entity in evidence.
    
    Represents a single instance of an entity being mentioned,
    with full provenance tracking.
    """
    model_config = ConfigDict(extra="forbid")
    
    mention_id: str = Field(..., description="Unique ID for this mention (EV-XXX)")
    entity_text: str = Field(..., min_length=1, description="Text as it appears in source")
    entity_type: EntityType = Field(..., description="Type of entity")
    normalized_form: Optional[str] = Field(None, description="Normalized/canonical form")
    
    # Provenance
    source_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence IDs this mention appears in (REQUIRED for OBSERVED)"
    )
    source_spans: List[SourceSpan] = Field(
        default_factory=list,
        description="Source locations in original documents"
    )
    
    # Extraction metadata
    extraction_method: ExtractionMethod = Field(..., description="How this was extracted")
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When this extraction was made"
    )
    
    # Status
    status: ObservationStatus = Field(..., description="Observation status")
    confidence: ConfidenceComponents = Field(
        default_factory=ConfidenceComponents,
        description="Decomposed confidence score"
    )
    
    # Additional attributes
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional entity attributes"
    )
    
    @model_validator(mode="after")
    def observed_requires_evidence(self) -> "EntityMention":
        """OBSERVED entities must have evidence IDs."""
        if self.status == ObservationStatus.OBSERVED and not self.source_evidence_ids:
            raise ValueError(
                "OBSERVED entities must have at least one source_evidence_id"
            )
        return self
    
    def resolved_entity_id(self) -> Optional[str]:
        """Get resolved entity ID if available."""
        return self.attributes.get("resolved_entity_id")


class RelationshipCandidate(BaseModel):
    """A candidate relationship between entities.
    
    Represents a potential relationship extracted from evidence,
    with full provenance and confidence decomposition.
    """
    model_config = ConfigDict(extra="forbid")
    
    candidate_id: str = Field(..., description="Unique ID for this candidate")
    subject: str = Field(..., description="Subject entity mention ID or resolved ID")
    subject_text: str = Field(..., description="Subject entity text")
    predicate: RelationshipType = Field(..., description="Relationship type")
    object: str = Field(..., description="Object entity mention ID or resolved ID")
    object_text: str = Field(..., description="Object entity text")
    
    # Temporal context
    valid_from: Optional[datetime] = Field(None, description="Relationship start time")
    valid_to: Optional[datetime] = Field(None, description="Relationship end time")
    observed_at: Optional[datetime] = Field(None, description="When this was observed")
    
    # Provenance
    source_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting this relationship"
    )
    source_spans: List[SourceSpan] = Field(
        default_factory=list,
        description="Source locations in original documents"
    )
    
    # Extraction metadata
    extraction_method: ExtractionMethod = Field(..., description="How this was extracted")
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When this extraction was made"
    )
    
    # Status
    status: ObservationStatus = Field(..., description="Observation status")
    confidence: ConfidenceComponents = Field(
        default_factory=ConfidenceComponents,
        description="Decomposed confidence score"
    )
    
    # Context
    context: Optional[str] = Field(None, description="Surrounding context")
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    @model_validator(mode="after")
    def observed_requires_evidence(self) -> "RelationshipCandidate":
        """OBSERVED relationships must have evidence IDs."""
        if self.status == ObservationStatus.OBSERVED and not self.source_evidence_ids:
            raise ValueError(
                "OBSERVED relationships must have at least one source_evidence_id"
            )
        return self


class EventCandidate(BaseModel):
    """A candidate event extracted from evidence.
    
    Events are occurrences in time that may involve multiple entities
    and have temporal/spatial context.
    """
    model_config = ConfigDict(extra="forbid")
    
    event_id: str = Field(..., description="Unique ID for this event")
    event_type: EventType = Field(..., description="Type of event")
    description: str = Field(..., min_length=1, description="Event description")
    
    # Participants
    participants: List[str] = Field(
        default_factory=list,
        description="Entity mention IDs or resolved IDs of participants"
    )
    participant_texts: List[str] = Field(
        default_factory=list,
        description="Text forms of participants"
    )
    
    # Temporal context
    event_time: Optional[datetime] = Field(None, description="When event occurred")
    event_time_relative: Optional[str] = Field(
        None,
        description="Relative time expression (e.g., 'two days before')"
    )
    duration: Optional[str] = Field(None, description="Event duration")
    
    # Spatial context
    location: Optional[str] = Field(None, description="Location text")
    location_entity_id: Optional[str] = Field(None, description="Resolved location ID")
    
    # Provenance
    source_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence IDs mentioning this event"
    )
    source_spans: List[SourceSpan] = Field(
        default_factory=list,
        description="Source locations in original documents"
    )
    
    # Extraction metadata
    extraction_method: ExtractionMethod = Field(..., description="How this was extracted")
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When this extraction was made"
    )
    
    # Status
    status: ObservationStatus = Field(..., description="Observation status")
    confidence: ConfidenceComponents = Field(
        default_factory=ConfidenceComponents,
        description="Decomposed confidence score"
    )
    
    # Additional context
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    @model_validator(mode="after")
    def observed_requires_evidence(self) -> "EventCandidate":
        """OBSERVED events must have evidence IDs."""
        if self.status == ObservationStatus.OBSERVED and not self.source_evidence_ids:
            raise ValueError(
                "OBSERVED events must have at least one source_evidence_id"
            )
        return self


class EvidenceClaim(BaseModel):
    """A structured claim extracted from evidence.
    
    Represents a subject-predicate-object claim with full provenance
    and confidence decomposition. This is the core unit of knowledge
    extraction.
    """
    model_config = ConfigDict(extra="forbid")
    
    claim_id: str = Field(..., description="Unique claim ID (CL-XXX)")
    subject: str = Field(..., description="Subject entity")
    predicate: str = Field(..., description="Claim predicate/relationship")
    object: Optional[str] = Field(None, description="Object entity or value")
    value: Optional[str] = Field(None, description="Value for attribute claims")
    
    # Provenance
    source_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting this claim (REQUIRED)"
    )
    source_spans: List[SourceSpan] = Field(
        default_factory=list,
        description="Source locations in original documents"
    )
    
    # Extraction metadata
    extraction_method: ExtractionMethod = Field(..., description="How this was extracted")
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When this extraction was made"
    )
    
    # Status
    status: ObservationStatus = Field(..., description="Observation status")
    confidence: ConfidenceComponents = Field(
        default_factory=ConfidenceComponents,
        description="Decomposed confidence score"
    )
    
    # Context
    context: Optional[str] = Field(None, description="Surrounding context")
    notes: Optional[str] = Field(None, description="Analyst notes")
    
    @model_validator(mode="after")
    def claim_requires_evidence(self) -> "EvidenceClaim":
        """All claims must have evidence IDs."""
        if not self.source_evidence_ids:
            raise ValueError(
                "Claims must have at least one source_evidence_id. "
                "Claims without evidence are not allowed."
            )
        return self
    
    def to_graph_tuple(self) -> tuple:
        """Convert to (subject, predicate, object) tuple for graph insertion."""
        return (self.subject, self.predicate, self.object or self.value)


class ExtractionResult(BaseModel):
    """Complete extraction result from a document or evidence batch.
    
    Contains all entities, relationships, events, and claims extracted
    from a source, with full provenance chain.
    """
    model_config = ConfigDict(extra="forbid")
    
    extraction_id: str = Field(..., description="Unique extraction batch ID")
    source_document_id: str = Field(..., description="Source document/evidence ID")
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When extraction was performed"
    )
    
    # Extracted items
    entities: List[EntityMention] = Field(default_factory=list)
    relationships: List[RelationshipCandidate] = Field(default_factory=list)
    events: List[EventCandidate] = Field(default_factory=list)
    claims: List[EvidenceClaim] = Field(default_factory=list)
    
    # Metadata
    extraction_method: ExtractionMethod = Field(..., description="Primary method used")
    llm_provider: Optional[str] = Field(None, description="LLM provider if used")
    processing_time_ms: Optional[float] = Field(None, description="Processing time")
    
    # Validation status
    validated: bool = Field(False, description="Whether result passed validation")
    validation_errors: List[str] = Field(default_factory=list)
    
    def entity_count(self) -> int:
        return len(self.entities)
    
    def relationship_count(self) -> int:
        return len(self.relationships)
    
    def event_count(self) -> int:
        return len(self.events)
    
    def claim_count(self) -> int:
        return len(self.claims)
    
    def all_evidence_ids(self) -> set[str]:
        """Collect all evidence IDs referenced in this extraction."""
        ids = set()
        for e in self.entities:
            ids.update(e.source_evidence_ids)
        for r in self.relationships:
            ids.update(r.source_evidence_ids)
        for ev in self.events:
            ids.update(ev.source_evidence_ids)
        for c in self.claims:
            ids.update(c.source_evidence_ids)
        return ids
