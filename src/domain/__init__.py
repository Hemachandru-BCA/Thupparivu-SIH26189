"""
domain/__init__.py
------------------
Thupparivu / SentinelGraph AI unified domain layer (Phase 1 of the
intelligence overhaul).

The existing backend scattered entity/graph/evidence shapes across
``src/resolution``, ``src/xai``, ``src/graph`` and ``src/api``.  This package
introduces a single strongly-typed domain vocabulary that every new
intelligence layer (temporal graph, ML, hypotheses, counterfactuals) builds
on — WITHOUT breaking the legacy modules, which keep their own dataclasses.

Design rules:

* Every domain object carries a stable id, ``created_at``, ``source``,
  ``provenance``, a status and (where meaningful) ``confidence``.
* OBSERVED / INFERRED / UNKNOWN / CONTRADICTED semantics are enforced at
  the type level through ``FactStatus`` and the ``Observation`` /
  ``Inference`` models.
* Nothing here imports FastAPI, NetworkX or any heavy dependency — the
  domain layer is pure Pydantic + stdlib, so it can be reused by
  notebooks, CLIs and adapters alike.

Status: PHASE 1 (foundation).  Subsequent phases import from this package.
"""

from src.domain.models import (
    # --- primitives ---
    FactStatus,
    RelationshipStatus,
    Provenance,
    ConfidenceScore,
    ConfidenceExplanation,
    ModelRun,
    SourceRef,
    # --- entities & mentions ---
    Entity,
    EntityMention,
    EntityAlias,
    # --- relationships & events ---
    Relationship,
    RelationshipEvidence,
    TemporalSpan,
    Event,
    Case,
    # --- evidence & reasoning ---
    EvidenceItem,
    Observation,
    Inference,
    Hypothesis,
    Prediction,
    CounterEvidence,
    # --- graph / investigation ---
    GraphSnapshot,
    Investigation,
    Finding,
    ModelRunRecord,
)

__all__ = [
    # primitives
    "FactStatus",
    "RelationshipStatus",
    "Provenance",
    "ConfidenceScore",
    "ConfidenceExplanation",
    "ModelRun",
    "SourceRef",
    # entities
    "Entity",
    "EntityMention",
    "EntityAlias",
    # relationships & events
    "Relationship",
    "RelationshipEvidence",
    "TemporalSpan",
    "Event",
    "Case",
    # evidence & reasoning
    "EvidenceItem",
    "Observation",
    "Inference",
    "Hypothesis",
    "Prediction",
    "CounterEvidence",
    # graph / investigation
    "GraphSnapshot",
    "Investigation",
    "Finding",
    "ModelRunRecord",
]