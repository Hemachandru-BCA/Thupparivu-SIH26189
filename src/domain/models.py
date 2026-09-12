"""
domain/models.py
----------------
Strongly-typed domain models for Thupparivu / SentinelGraph AI.

These models form the unified vocabulary shared by every intelligence layer:

* ``Provenance`` – provenance chain for any extracted fact.
* ``ConfidenceScore`` / ``ConfidenceExplanation`` – the unified scoring
  abstraction (a prediction is decomposed into structural / temporal /
  semantic / behavioral / evidence / entity-resolution components, with a
  counter-evidence penalty).
* ``ModelRun`` / ``ModelRunRecord`` – model-run tracking for reproducibility.
* ``Entity``, ``EntityMention``, ``EntityAlias`` – typed entities.
* ``Relationship``, ``RelationshipEvidence`` – typed, temporal, evidenced
  relationships with OBSERVED / INFERRED distinction.
* ``Event``, ``Case``, ``EvidenceItem``, ``Observation``, ``Inference``,
  ``Hypothesis``, ``Prediction``, ``CounterEvidence``, ``GraphSnapshot``,
  ``Investigation``, ``Finding``.

Semantics contract (non-negotiable):

* OBSERVED  – grounded in at least one evidence item (never invented).
* INFERRED  – a model / rule conclusion; must retain provenance + confidence.
* UNKNOWN   – the system explicitly says "I don't know".
* CONTRADICTED – supporting and counter evidence both exist.

Nothing in this module imports FastAPI, NetworkX or any heavyweight
dependency.  Pydantic only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------- #
# Namespaces (deterministic uuid5 ids, matching the legacy convention)
# --------------------------------------------------------------------------- #

DOMAIN_NAMESPACE = uuid.UUID("4a7c3e12-8b5f-4d2a-9e71-6c4b0f3a9d21")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def domain_uuid5(kind: str, seed: str) -> str:
    """Deterministic, stable id generator (uuid5 in the domain namespace)."""
    return str(uuid.uuid5(DOMAIN_NAMESPACE, f"{kind}|{seed}"))


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #


class FactStatus(str, Enum):
    """Core truth-semantics used across every model output.

    Never upgrade INFERRED -> OBSERVED, POSSIBLE -> FACT, or UNKNOWN -> FALSE.
    NEGATED marks statements explicitly negated in the source ("did not call").
    POSSIBLE marks modal statements ("may have transferred") - these must stay
    weaker than OBSERVED and must never be elevated automatically.
    """

    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    POSSIBLE = "POSSIBLE"
    NEGATED = "NEGATED"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"
    HYPOTHETICAL = "HYPOTHETICAL"


class RelationshipStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    POSSIBLE = "POSSIBLE"
    NEGATED = "NEGATED"
    PREDICTED_FUTURE = "PREDICTED_FUTURE"
    HYPOTHETICAL = "HYPOTHETICAL"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class SourceRef(BaseModel):
    """Reference to a source artifact (document, record, CSV row, ...)."""

    source: str = "UNKNOWN"                      # e.g. "CALL", "FIR", "DOCUMENT"
    record_id: Optional[str] = None
    uri: Optional[str] = None
    page: Optional[str] = None
    section: Optional[str] = None
    paragraph: Optional[str] = None
    sentence: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    offset: Optional[int] = None
    raw: Any = None


class Provenance(BaseModel):
    """Unified provenance chain for any extracted fact.

    Every fact must be traceable to:
    * the source document / record,
    * the extraction model (+ version),
    * when it was extracted,
    * the confidence of the extraction step.
    """

    source: SourceRef = Field(default_factory=SourceRef)
    extraction_model: Optional[str] = None
    model_version: Optional[str] = None
    extracted_at: str = Field(default_factory=_utcnow)
    confidence: float = 0.0
    notes: List[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _conf_range(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class TemporalSpan(BaseModel):
    """Time interval for a relationship / event where known."""

    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    observed_at: Optional[str] = None
    #: True when the ordering is known but absolute timestamps are not.
    relative: bool = False

    def overlaps(self, other: "TemporalSpan") -> bool:
        """Interval overlap test; missing bounds are treated as unbounded."""
        self_start = self.valid_from or self.observed_at
        self_end = self.valid_to or self.observed_at
        other_start = other.valid_from or other.observed_at
        other_end = other.valid_to or other.observed_at
        if self_start and other_end and self_start > other_end:
            return False
        if other_start and self_end and other_start > self_end:
            return False
        return True


# --------------------------------------------------------------------------- #
# Unified scoring abstraction (Phase 1, requirement 5)
# --------------------------------------------------------------------------- #


class ConfidenceExplanation(BaseModel):
    """Human-readable decomposition of a confidence score."""

    component: str
    value: float
    weight: float = 1.0
    description: str = ""
    evidence_ids: List[str] = Field(default_factory=list)


class ConfidenceScore(BaseModel):
    """Decomposable confidence for a model prediction.

    A prediction is the blend of independent signal families; exposing the
    decomposition (not just the scalar) is what makes the system
    explainable.
    """

    structural_score: float = 0.0
    temporal_score: float = 0.0
    semantic_score: float = 0.0
    behavioral_score: float = 0.0
    evidence_score: float = 0.0
    entity_resolution_score: float = 0.0
    counter_evidence_penalty: float = 0.0

    explanations: List[ConfidenceExplanation] = Field(default_factory=list)

    #: optional learned/calibrated blend weights; default is an equal blend.
    weights: Dict[str, float] = Field(default_factory=dict)

    @field_validator(
        "structural_score",
        "temporal_score",
        "semantic_score",
        "behavioral_score",
        "evidence_score",
        "entity_resolution_score",
        "counter_evidence_penalty",
    )
    @classmethod
    def _clamp(cls, v: float) -> float:
        return round(max(0.0, min(1.0, float(v))), 4)

    def component(self, name: str) -> float:
        return float(getattr(self, f"{name}_score", 0.0) or 0.0)

    def blended(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Weighted blend of the positive components minus the penalty.

        Missing weights default to an equal split across the available
        positive components.
        """
        components = {
            "structural": self.structural_score,
            "temporal": self.temporal_score,
            "semantic": self.semantic_score,
            "behavioral": self.behavioral_score,
            "evidence": self.evidence_score,
            "entity_resolution": self.entity_resolution_score,
        }
        w = weights or self.weights
        if not w:
            w = {k: 1.0 / len(components) for k in components}
        total = 0.0
        wsum = 0.0
        for k, v in components.items():
            weight = float(w.get(k, 0.0))
            total += weight * v
            wsum += weight
        if wsum <= 0:
            return 0.0
        blended = max(0.0, min(1.0, total / wsum - self.counter_evidence_penalty))
        return round(blended, 4)

    @property
    def value(self) -> float:
        """The scalar confidence used by downstream consumers."""
        return self.blended()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "structural": self.structural_score,
            "temporal": self.temporal_score,
            "semantic": self.semantic_score,
            "behavioral": self.behavioral_score,
            "evidence": self.evidence_score,
            "entity_resolution": self.entity_resolution_score,
            "counter_evidence_penalty": self.counter_evidence_penalty,
            "blended": self.value,
            "explanations": [e.model_dump(mode="json") for e in self.explanations],
        }


# --------------------------------------------------------------------------- #
# Model-run tracking (Phase 1, requirement 6)
# --------------------------------------------------------------------------- #


class ModelRun(BaseModel):
    """Metadata for a single ML/AI execution."""

    model_name: str
    model_version: str = "0.0.0"
    configuration: Dict[str, Any] = Field(default_factory=dict)
    input_dataset_version: Optional[str] = None
    timestamp: str = Field(default_factory=_utcnow)
    random_seed: Optional[int] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    output_ids: List[str] = Field(default_factory=list)
    status: str = "COMPLETED"       # COMPLETED | FAILED | PARTIAL
    notes: List[str] = Field(default_factory=list)

    @property
    def run_id(self) -> str:
        return domain_uuid5("model_run", f"{self.model_name}|{self.model_version}|{self.timestamp}")


class ModelRunRecord(BaseModel):
    """A persisted model-run record (registered in the ModelRegistry)."""

    run_id: str
    model: str
    version: str
    config: Dict[str, Any] = Field(default_factory=dict)
    dataset_version: Optional[str] = None
    started_at: str = Field(default_factory=_utcnow)
    finished_at: Optional[str] = None
    seed: Optional[int] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    outputs: List[str] = Field(default_factory=list)
    status: str = "COMPLETED"
    tags: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Entities
# --------------------------------------------------------------------------- #


class Entity(BaseModel):
    """A typed entity in the knowledge graph (person, phone, account, ...)."""

    id: str
    entity_type: str = "UNKNOWN"          # PERSON | ORGANIZATION | PHONE | ...
    canonical_name: str = ""
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    mention_count: int = 0
    confidence: Optional[float] = None
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: str = Field(default_factory=_utcnow)
    status: str = "ACTIVE"
    version: str = "1.0.0"
    source: str = "UNKNOWN"
    extra: Dict[str, Any] = Field(default_factory=dict)


class EntityMention(BaseModel):
    """An occurrence of an entity inside a source document."""

    id: str = Field(default_factory=lambda: domain_uuid5("mention", uuid.uuid4().hex))
    entity_id: Optional[str] = None
    text: str
    label: str = "UNKNOWN"
    start: Optional[int] = None
    end: Optional[int] = None
    sentence_index: Optional[int] = None
    document_id: Optional[str] = None
    confidence: float = 0.0
    provenance: Provenance = Field(default_factory=Provenance)


class EntityAlias(BaseModel):
    """An alias resolved to a canonical entity."""

    id: str
    entity_id: str
    alias: str
    alias_type: str = "NAME"       # NAME | TRANSLITERATION | INITIALS | PHONE | ...
    normalized: str = ""
    confidence: float = 0.0
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: str = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Relationships & evidence
# --------------------------------------------------------------------------- #


class RelationshipEvidence(BaseModel):
    """The evidence linking two entities (one edge justification)."""

    evidence_id: str
    source: str = "UNKNOWN"
    excerpt: str = ""
    confidence: float = 0.0
    timestamp: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    """A typed, temporal, evidenced relationship between two entities."""

    id: str
    source_entity: str
    target_entity: str
    relationship_type: str = "ASSOCIATED_WITH"
    status: RelationshipStatus = RelationshipStatus.OBSERVED
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    observed_at: Optional[str] = None
    source: str = "UNKNOWN"
    confidence: float = 0.0
    evidence_ids: List[str] = Field(default_factory=list)
    evidence: List[RelationshipEvidence] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: str = Field(default_factory=_utcnow)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"


class Event(BaseModel):
    """A reified event node (MEETING / CALL / TRANSACTION / ...)."""

    id: str
    event_type: str = "EVENT"
    participants: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    timestamp: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    evidence_id: Optional[str] = None
    source: str = "UNKNOWN"
    confidence: float = 0.0
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: str = Field(default_factory=_utcnow)


class Case(BaseModel):
    """An investigation case (workspace of entities/evidence/findings)."""

    id: str
    title: str = ""
    description: str = ""
    status: str = "OPEN"
    items: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    dossier_ids: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    source: str = "UNKNOWN"


# --------------------------------------------------------------------------- #
# Evidence & reasoning primitives
# --------------------------------------------------------------------------- #


class EvidenceItem(BaseModel):
    """Normalized evidence unit (one source record excerpt + hash + refs)."""

    id: str
    source_type: str = "DOCUMENT"
    source_record_id: Optional[str] = None
    uri: Optional[str] = None
    timestamp: Optional[str] = None
    excerpt: str = ""
    structured_fields: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    provenance: Provenance = Field(default_factory=Provenance)
    confidence: float = 0.0
    subject_ids: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utcnow)


class Observation(BaseModel):
    """A fact grounded in evidence (never invented)."""

    id: str
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    timestamp: Optional[str] = None
    source: str = "UNKNOWN"
    confidence: float = 1.0
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: str = Field(default_factory=_utcnow)


class Inference(BaseModel):
    """A model conclusion; must retain provenance, confidence, and caveats."""

    id: str
    text: str
    model: str = "UNKNOWN"
    model_version: str = "0.0.0"
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    status: FactStatus = FactStatus.INFERRED
    created_at: str = Field(default_factory=_utcnow)
    source: str = "UNKNOWN"
    explanation: str = ""


class Hypothesis(BaseModel):
    """A structured investigative hypothesis (Phase 5)."""

    id: str
    hypothesis_type: str = "POTENTIAL_MISSING_LINK"
    subject: str = ""
    confidence: float = 0.0
    confidence_score: ConfidenceScore = Field(default_factory=ConfidenceScore)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    model_signals: Dict[str, Any] = Field(default_factory=dict)
    temporal_scope: Optional[str] = None
    graph_scope: Dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    status: str = "OPEN"       # OPEN | SUPPORTED | WEAKENED | CONTRADICTED | RESOLVED | REQUIRES_REVIEW
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    source: str = "UNKNOWN"
    provenance: Provenance = Field(default_factory=Provenance)


class Prediction(BaseModel):
    """A predicted (future / hidden) relationship."""

    id: str
    candidate_source: str = ""
    candidate_target: str = ""
    relationship_type: str = "ASSOCIATED_WITH"
    probability: float = 0.0
    model: str = "UNKNOWN"
    model_version: str = "0.0.0"
    status: RelationshipStatus = RelationshipStatus.PREDICTED_FUTURE
    features: Dict[str, Any] = Field(default_factory=dict)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    confidence_score: ConfidenceScore = Field(default_factory=ConfidenceScore)
    explanation: str = ""
    timestamp: str = Field(default_factory=_utcnow)
    model_run_id: Optional[str] = None


class CounterEvidence(BaseModel):
    """Evidence that weakens or contradicts a hypothesis."""

    id: str
    evidence_ids: List[str] = Field(default_factory=list)
    relationship: str = "CONTRADICTS"    # SUPPORTS | CONTRADICTS | UNKNOWN
    description: str = ""
    severity: float = 0.0                # 0..1 penalty weight
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: str = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Graph / investigation
# --------------------------------------------------------------------------- #


class GraphSnapshot(BaseModel):
    """A consistent snapshot of the knowledge graph at (or between) times.

    ``as_of`` is the snapshot timestamp; the snapshot must only contain
    facts whose ``observed_at`` <= ``as_of`` (no future leakage).
    """

    id: str
    as_of: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    nodes: List[Entity] = Field(default_factory=list)
    edges: List[Relationship] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utcnow)
    source: str = "TEMPORAL_GRAPH_SERVICE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Investigation(BaseModel):
    """A full investigation workspace."""

    id: str
    name: str = ""
    description: str = ""
    graph_id: Optional[str] = None
    hypothesis_ids: List[str] = Field(default_factory=list)
    finding_ids: List[str] = Field(default_factory=list)
    dossier_ids: List[str] = Field(default_factory=list)
    status: str = "OPEN"
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    source: str = "UNKNOWN"


class Finding(BaseModel):
    """A consolidated, explainable conclusion (Phase 5 / dossier input)."""

    id: str
    finding_type: str = "GENERAL"
    subject_id: str = ""
    subject_label: str = ""
    status: FactStatus = FactStatus.INFERRED
    observations: List[Observation] = Field(default_factory=list)
    inferences: List[Inference] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    confidence_score: ConfidenceScore = Field(default_factory=ConfidenceScore)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utcnow)
    source: str = "UNKNOWN"
    provenance: Provenance = Field(default_factory=Provenance)