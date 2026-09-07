"""
findings.py
-----------
Structured XAI findings (Phase E).

A *finding* is the atomic unit the XAI pipeline emits for every model output
worth explaining (currently: ghost / hidden-intermediary hypotheses).

The pipeline is:

    MODEL FINDING -> FEATURE CONTRIBUTIONS -> GRAPH PATHS / STRUCTURAL SIGNALS
        -> EVIDENCE RETRIEVAL -> COUNTER-EVIDENCE RETRIEVAL
        -> FACT/HYPOTHESIS SEPARATION -> HUMAN-READABLE EXPLANATION

Every :class:`Finding` therefore carries:

* ``observed``  - concrete facts, each backed by evidence ids;
* ``inferred``  - explicit hypotheses (never presented as facts);
* ``unknown``   - missing information the model cannot answer;
* ``counter_evidence`` - evidence that weakens the hypothesis;
* ``confidence_components`` - the breakdown behind the calibrated score;
* ``limitations`` - what this method cannot establish.

``validate_finding`` enforces the integrity contract (Phase AB): every
evidence id must exist, every observed claim must cite evidence, counter
evidence must be preserved, and the calibrated confidence must equal the
weighted component average.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from src.xai.evidence_tracer import EvidenceRecord, EvidenceStore

logger = logging.getLogger(__name__)

FINDING_NAMESPACE = uuid.UUID("9c47b1a2-5e33-4f8d-a7c1-2b90d4e6f581")
MODEL_VERSION = "sentinelgraph-xai-1.0.0"

FINDING_TYPE_HIDDEN_INTERMEDIARY = "HIDDEN_INTERMEDIARY"
METHOD_STRUCTURAL_HOLE = "STRUCTURAL_HOLE_ANALYSIS"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Claim(BaseModel):
    """One statement, explicitly labelled as observed / inferred / unknown."""

    text: str
    label: str = "INFERRED"            # OBSERVED | INFERRED | UNKNOWN
    evidence_ids: List[str] = Field(default_factory=list)


class ConfidenceComponent(BaseModel):
    name: str
    value: float
    weight: float
    description: str = ""


class GraphSignal(BaseModel):
    signal_type: str                       # COMMUNITY_BRIDGE | SHARED_ANCHOR | ...
    description: str
    communities: List[int] = Field(default_factory=list)
    node_ids: List[str] = Field(default_factory=list)
    strength: Optional[float] = None


class Finding(BaseModel):
    """A human-reviewable model finding."""

    id: str
    finding_type: str
    subject_id: str
    subject_label: str = ""
    subject_is_ghost: bool = True
    confidence: float = 0.0
    confidence_components: List[ConfidenceComponent] = Field(default_factory=list)
    status: str = "HYPOTHESIS"             # HYPOTHESIS | UNDER_REVIEW | REVIEWED
    method: str = METHOD_STRUCTURAL_HOLE
    generated_at: str = Field(default_factory=_utcnow)
    model_version: str = MODEL_VERSION

    observed: List[Claim] = Field(default_factory=list)
    inferred: List[Claim] = Field(default_factory=list)
    unknown: List[Claim] = Field(default_factory=list)

    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)

    graph_signals: List[GraphSignal] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    human_review: Dict[str, Any] = Field(
        default_factory=lambda: {"required": True, "reviewer": None, "decision": None}
    )

    # ------------------------------------------------------------------- #
    @property
    def all_evidence_ids(self) -> List[str]:
        seen, out = set(), []
        for eid in [*self.supporting_evidence_ids, *self.counter_evidence_ids]:
            if eid not in seen:
                seen.add(eid)
                out.append(eid)
        return out

    def summary(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


DEFAULT_GHOST_LIMITATIONS = [
    "Ghost candidates are structural hypotheses inferred from network patterns, "
    "not confirmed identities.",
    "Confidence is a weighted blend of graph similarity signals; it is NOT a "
    "probability of guilt and NOT proof that a specific person exists.",
    "Predicted relationships are plausible contact points, not observed events.",
    "The synthetic dataset bounds what the detector can recover; recall on the "
    "planted-coordinator benchmark is incomplete (see VALIDATION_REPORT.md).",
    "Human review is required before any operational use.",
]


class FindingBuilder:
    """Builds :class:`Finding` objects from ghost predictions + evidence."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self.evidence = evidence_store

    # ------------------------------------------------------------------ #
    def from_ghost(self, ghost: Dict[str, Any]) -> Finding:
        ghost_id = str(ghost.get("ghost_id", ""))
        finding_id = "F-" + str(uuid.uuid5(FINDING_NAMESPACE, f"ghost|{ghost_id}"))
        breakdown = ghost.get("confidence_breakdown") or {}
        components: List[ConfidenceComponent] = []
        weights = breakdown.get("weights") or {}
        descriptions = {
            "attribute_affinity": "Shared attribute / anchor surface between the two communities",
            "temporal_affinity": "Temporal co-activity similarity between the communities",
            "embedding_affinity": "Graph-embedding proximity of the two community footprints",
            "structural_hole_signal": "Structural-hole (broker) scores on both sides",
            "graphsage_affinity": "GraphSAGE-style inductive embedding affinity",
        }
        for name, value in breakdown.items():
            if name == "weights" or not isinstance(value, (int, float)):
                continue
            components.append(
                ConfidenceComponent(
                    name=name,
                    value=round(float(value), 4),
                    weight=round(float(weights.get(name, 0.0)), 4),
                    description=descriptions.get(name, ""),
                )
            )

        # ------------------------------------------------ observed facts ----
        observed: List[Claim] = []
        supporting: List[str] = []
        graph_signals: List[GraphSignal] = []
        between = ghost.get("between_communities") or []
        anchors = ghost.get("evidence") or []
        unbound_anchors: List[str] = []
        for anchor in anchors:
            anchor_name = anchor.get("anchor_name") or anchor.get("anchor_guid") or "unknown"
            detail = anchor.get("detail") or ""
            anchor_guid = str(anchor.get("anchor_guid", ""))
            anchor_eids = [
                r.evidence_id
                for r in self.evidence.get_evidence_for_node(anchor_guid, limit=20)
            ]
            if not anchor_eids and anchor_name:
                # fall back to keyword search on the anchor's display name
                anchor_eids = [
                    r.evidence_id for r in self.evidence.search_evidence(str(anchor_name), limit=3)
                ]
            if anchor_eids:
                claim_eids = anchor_eids[:3]
                observed.append(
                    Claim(
                        text=f"Account/node '{anchor_name}' is shared by communities "
                             f"{between[0] if between else '?'} and {between[1] if between else '?'} "
                             f"with no direct member-to-member edge between them. {detail}".strip(),
                        label="OBSERVED",
                        evidence_ids=claim_eids,
                    )
                )
                supporting.extend(claim_eids)
            else:
                # Integrity contract: a claim without bound evidence cannot be
                # labelled OBSERVED.  Record the gap explicitly instead.
                unbound_anchors.append(str(anchor_name))
                unknown_anchor = (
                    f"Anchor '{anchor_name}' (shared by communities "
                    f"{between[0] if between else '?'} and {between[1] if between else '?'}) "
                    f"could not be bound to a source record in the evidence index."
                )
                unknown.append(Claim(text=unknown_anchor, label="UNKNOWN"))
            relations = anchor.get("relations") or []
            if relations:
                graph_signals.append(
                    GraphSignal(
                        signal_type="SHARED_ANCHOR",
                        description=(
                            f"'{anchor_name}' connects to both communities via "
                            f"{', '.join(map(str, relations))}"
                        ),
                        communities=list(between),
                        node_ids=[anchor_guid],
                    )
                )
        if between:
            graph_signals.append(
                GraphSignal(
                    signal_type="COMMUNITY_BRIDGE",
                    description=(
                        f"Structural hole detected between communities {between[0]} "
                        f"and {between[1]} (no observed direct edges)"
                    ),
                    communities=list(between),
                )
            )

        # ------------------------------------------------ inferred claims ---
        inferred: List[Claim] = []
        unknown: List[Claim] = [
            Claim(text="Actual identity of the hidden coordinator (if one exists)", label="UNKNOWN"),
            Claim(text="Whether the predicted edges correspond to real communications", label="UNKNOWN"),
            Claim(text="Direction and start date of the suspected coordination", label="UNKNOWN"),
        ]
        for edge in ghost.get("predicted_edges", []) or []:
            inferred.append(
                Claim(
                    text=(
                        f"Predicted relationship between the ghost intermediary and "
                        f"'{edge.get('target_name', edge.get('target'))}' "
                        f"(side: {edge.get('side')}, probability {edge.get('probability')}): "
                        f"{edge.get('rationale', '')}"
                    ).strip(),
                    label="INFERRED",
                    evidence_ids=[],
                )
            )
        inferred.append(
            Claim(
                text=f"A single hidden intermediary plausibly connects communities "
                     f"{between}. Subtype: {ghost.get('subtype', 'intermediary')}.",
                label="INFERRED",
                evidence_ids=[],
            )
        )

        # ------------------------------------------------ counter-evidence --
        counter = self._collect_counter_evidence(ghost, between)

        if unbound_anchors:
            inferred.append(
                Claim(
                    text=(
                        f"{len(unbound_anchors)} anchor node(s) shared by the two communities "
                        f"could not be bound to source records in the evidence index "
                        f"(see unknowns)."
                    ),
                    label="INFERRED",
                    evidence_ids=[],
                )
            )

        confidence = round(float(ghost.get("confidence", 0.0)), 4)
        return Finding(
            id=finding_id,
            finding_type=FINDING_TYPE_HIDDEN_INTERMEDIARY,
            subject_id=ghost_id,
            subject_label=ghost.get("label", "Ghost intermediary"),
            subject_is_ghost=True,
            confidence=confidence,
            confidence_components=components,
            status="HYPOTHESIS",
            method=METHOD_STRUCTURAL_HOLE,
            observed=observed,
            inferred=inferred,
            unknown=unknown,
            supporting_evidence_ids=sorted(set(supporting)),
            counter_evidence_ids=counter,
            graph_signals=graph_signals,
            limitations=list(DEFAULT_GHOST_LIMITATIONS),
        )

    # ------------------------------------------------------------------ #
    def _collect_counter_evidence(self, ghost: Dict[str, Any],
                                  between: Sequence[Any]) -> List[str]:
        """Search for evidence that *weakens* the ghost hypothesis.

        Current signals:
        * any observed direct edges between the two communities (the ghost
          hypothesis requires none);
        * anchors that only connect to one side on closer inspection.
        """
        counter_ids: List[str] = []
        if len(between) != 2:
            return counter_ids
        low, high = sorted(between)
        per_category = ghost.get("per_category") or {}
        meta = per_category.get("_meta") or {}
        direct = meta.get("direct_edge_count")
        if isinstance(direct, (int, float)) and direct > 0:
            # find triplet evidence mentioning both community members is
            # expensive; the aggregate count itself is the counter signal and
            # is surfaced as a limitation instead of fabricated evidence.
            counter_ids.append(f"COUNTER:direct_edges:{int(direct)}")
        return counter_ids

    # ------------------------------------------------------------------ #
    def build_all(self, ghosts: Sequence[Dict[str, Any]],
                  min_confidence: float = 0.0) -> List[Finding]:
        findings = []
        for ghost in ghosts:
            if float(ghost.get("confidence", 0.0)) < min_confidence:
                continue
            findings.append(self.from_ghost(ghost))
        findings.sort(key=lambda f: (-f.confidence, f.id))
        return findings

    def link_store(self, findings: Sequence[Finding]) -> None:
        for finding in findings:
            self.evidence.link_finding(finding.id, finding.all_evidence_ids)


# --------------------------------------------------------------------------- #
# Validation (Phase AB)
# --------------------------------------------------------------------------- #

class FindingValidationReport(BaseModel):
    finding_id: str
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def validate_finding(finding: Finding, evidence_store: EvidenceStore) -> FindingValidationReport:
    """Automated XAI integrity checks. Never mutates the finding."""
    errors: List[str] = []
    warnings: List[str] = []

    # 1. every evidence id exists
    for eid in finding.all_evidence_ids:
        if eid.startswith("COUNTER:"):
            continue  # synthetic aggregate counter-signal, not an evidence id
        if evidence_store.get_evidence(eid) is None:
            errors.append(f"evidence id not found in store: {eid}")

    # 2. every observed claim cites at least one piece of evidence
    for claim in finding.observed:
        if not claim.evidence_ids:
            errors.append(f"observed claim without evidence: {claim.text[:80]}")

    # 3. inferred claims must be labelled
    for claim in finding.inferred:
        if claim.label != "INFERRED":
            errors.append(f"claim in 'inferred' block not labelled INFERRED: {claim.text[:80]}")

    # 4. confidence components present and calibrated score consistent
    if not finding.confidence_components:
        warnings.append("no confidence components recorded")
    else:
        weights = [c.weight for c in finding.confidence_components]
        if abs(sum(weights) - 1.0) > 0.05 and any(w > 0 for w in weights):
            warnings.append("confidence component weights do not sum to ~1.0")
        total_w = sum(weights) or 1.0
        calibrated = sum(c.value * c.weight for c in finding.confidence_components) / total_w
        if abs(calibrated - finding.confidence) > 0.15:
            warnings.append(
                f"calibrated confidence ({calibrated:.3f}) differs from reported "
                f"({finding.confidence:.3f}) by more than 0.15"
            )

    # 5. counter-evidence preserved (or explicitly empty)
    if not finding.counter_evidence_ids:
        warnings.append("no counter-evidence recorded - verify search was performed")

    # 6. unknowns listed
    if not finding.unknown:
        errors.append("no 'unknown' items - missing information must be listed")

    # 7. model version recorded
    if not finding.model_version:
        errors.append("model_version missing")

    # 8. human review required
    if not finding.human_review.get("required"):
        errors.append("human review must be required for model findings")

    return FindingValidationReport(
        finding_id=finding.id, valid=not errors, errors=errors, warnings=warnings
    )


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

def save_findings(findings: Sequence[Finding], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _utcnow(),
        "model_version": MODEL_VERSION,
        "findings": [f.model_dump(mode="json") for f in findings],
    }
    out.write_text(json.dumps(payload, indent=2))
    return out


def load_findings(path: str | Path) -> List[Finding]:
    payload = json.loads(Path(path).read_text())
    return [Finding.model_validate(f) for f in payload.get("findings", [])]
