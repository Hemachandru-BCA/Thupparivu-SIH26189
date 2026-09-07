"""
schemas.py -- API request/response contracts (Pydantic v2).

Includes:
* the original pipeline trigger request bodies (preserved), and
* the shared domain models for the XAI layer (Phase B):
  GraphNode, GraphEdge, GhostCandidate, Finding, SimulationRequest /
  SimulationResult, DossierRequest, CaseWorkspace models.

Every request body forbids extra fields so a typo in the React form fails
fast with a clear 422 instead of silently being ignored.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Pipeline trigger requests (existing behaviour preserved)
# --------------------------------------------------------------------------- #


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    NUM_GANGS: Optional[int] = None
    NUM_PEOPLE: Optional[int] = None
    NUM_CALLS: Optional[int] = None
    NUM_TRANSACTIONS: Optional[int] = None
    NUM_MEETINGS: Optional[int] = None
    NUM_HIDDEN_COORDINATORS: Optional[int] = None
    RANDOM_SEED: Optional[int] = None


class PreprocessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_firs: Optional[int] = None
    ocr_sample_size: Optional[int] = None
    random_seed: Optional[int] = None


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spacy_model: Optional[str] = None
    infer_co_occurrence: Optional[bool] = None
    max_records: Optional[int] = None


class GraphBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_analytics: Optional[bool] = None
    graph_name: Optional[str] = None


class GhostDetectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_embeddings: Optional[bool] = None
    use_graphsage: Optional[bool] = None
    confidence_threshold: Optional[float] = None
    attribute_affinity_threshold: Optional[float] = None
    seed: Optional[int] = None


class RunAllRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generate: Optional[GenerateRequest] = None
    preprocess: Optional[PreprocessRequest] = None
    extract: Optional[ExtractRequest] = None
    graph: Optional[GraphBuildRequest] = None
    ghosts: Optional[GhostDetectRequest] = None
    run_ghost_detection: bool = True


# --------------------------------------------------------------------------- #
# Shared domain models (Phase B)
# --------------------------------------------------------------------------- #


class GraphNode(BaseModel):
    id: str
    type: str = "UNKNOWN"
    label: str = ""
    display_name: str = ""
    community_id: Optional[int] = None
    pagerank: Optional[float] = None
    betweenness: Optional[float] = None
    risk_indicators: List[str] = Field(default_factory=list)
    is_ghost: bool = False
    confidence: Optional[float] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "RELATED_TO"
    weight: float = 1.0
    timestamp: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    inferred: bool = False


class GhostCandidate(BaseModel):
    id: str
    type: Literal["GHOST"] = "GHOST"
    label: str = ""
    subtype: str = ""
    confidence: float = 0.0
    status: Literal["HYPOTHESIS"] = "HYPOTHESIS"
    supporting_communities: List[int] = Field(default_factory=list)
    predicted_edges: List[Dict[str, Any]] = Field(default_factory=list)
    shared_anchors: List[Dict[str, Any]] = Field(default_factory=list)
    temporal_signals: List[Dict[str, Any]] = Field(default_factory=list)
    structural_signals: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    explanation: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class FindingModel(BaseModel):
    """Public shape of an XAI finding (mirrors src.xai.findings.Finding)."""

    id: str
    finding_type: str
    subject_id: str
    subject_label: str = ""
    confidence: float
    status: str = "HYPOTHESIS"
    method: str
    generated_at: str
    model_version: str
    observed: List[Dict[str, Any]] = Field(default_factory=list)
    inferred: List[Dict[str, Any]] = Field(default_factory=list)
    unknown: List[Dict[str, Any]] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    graph_signals: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    human_review: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Simulation (Phase J / M)
# --------------------------------------------------------------------------- #


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    depth: int = Field(default=2, ge=1, le=4)
    include_reranking: bool = True


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_ids: List[str] = Field(min_length=1, max_length=5)


# --------------------------------------------------------------------------- #
# Dossiers (Phase F)
# --------------------------------------------------------------------------- #


class DossierRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1)
    finding_ids: Optional[List[str]] = None
    max_evidence: int = Field(default=40, ge=1, le=200)


class DossierReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1)
    decision: Literal["endorsed", "rejected", "changes_requested"]
    note: str = ""


# --------------------------------------------------------------------------- #
# Case workspace (Phase Q)
# --------------------------------------------------------------------------- #


class CaseItemRef(BaseModel):
    kind: Literal["entity", "path", "evidence", "finding", "simulation"]
    ref_id: str
    note: str = ""


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    investigator: str = "anonymous"


class CaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    add_item: Optional[CaseItemRef] = None
    remove_item: Optional[CaseItemRef] = None
    note: Optional[str] = None


# --------------------------------------------------------------------------- #
# Pagination envelope
# --------------------------------------------------------------------------- #


class PaginatedResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
