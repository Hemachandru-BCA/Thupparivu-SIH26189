"""
analysis/knowledge_gaps.py
--------------------------
Investigative Knowledge Gap Engine ("What Thupparivu Does Not Know").

Discovers:
  - Unverified phone/account ownerships
  - Single-source uncorroborated allegations
  - Missing temporal stamps or locations
  - Contradictory witness statements
  - Low-confidence entity linkages

Every gap answers the central question:

    "What information would most reduce uncertainty?"

rather than merely "missing information".  Each gap carries an uncertainty
reduction impact score, the hypothesis it distinguishes between, and the
types of evidence that could close it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

GAP_NAMESPACE = uuid.UUID("0f7c21e4-9f3d-4b8a-9e52-1db8e0c31495")

GAP_TYPES = (
    "UNVERIFIED_IDENTIFIER",      # phone/account ownership uncorroborated
    "UNCORROBORATED_CLAIM",       # single-source allegation
    "MISSING_TIMESTAMP",          # event without temporal anchor
    "MISSING_LOCATION",
    "CONFLICTING_ACCOUNTS",       # sources disagree
    "UNKNOWN_RELATIONSHIP_DIRECTION",
    "UNKNOWN_ACCOUNT_CONTROLLER",
    "NO_DIRECT_COMMUNICATION",    # coordination not established
    "LOW_CONFIDENCE_LINKAGE",
)

SEVERITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


@dataclass
class KnowledgeGap:
    """An identified gap in investigative evidence.

    ``uncertainty_reduction_impact`` (0..1) estimates how much closing this
    gap would reduce uncertainty — it is an information-value score, not a
    suspicion score.
    """

    gap_id: str
    gap_type: str        # one of GAP_TYPES
    subject_id: str
    description: str
    severity: str        # HIGH | MEDIUM | LOW
    recommended_action: str
    uncertainty_reduction_impact: float = 0.5
    distinguishes_between: List[str] = field(default_factory=list)
    potential_evidence: List[str] = field(default_factory=list)
    source_documents: List[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "gap_type": self.gap_type,
            "subject_id": self.subject_id,
            "description": self.description,
            "severity": self.severity,
            "uncertainty_reduction_impact": round(self.uncertainty_reduction_impact, 4),
            "distinguishes_between": self.distinguishes_between,
            "potential_evidence": self.potential_evidence,
            "recommended_action": self.recommended_action,
            "source_documents": self.source_documents,
        }


def make_gap_id(gap_type: str, subject_id: str, salt: str = "") -> str:
    return "GAP-" + str(uuid.uuid5(GAP_NAMESPACE, f"{gap_type}|{subject_id}|{salt}"))


def gap_priority_key(gap: KnowledgeGap) -> tuple:
    """Sort gaps by information value: impact first, then severity."""
    return (-gap.uncertainty_reduction_impact, -SEVERITY_RANK.get(gap.severity, 2))


def rank_gaps(gaps: List[KnowledgeGap]) -> List[KnowledgeGap]:
    """Rank gaps by uncertainty-reduction value (highest impact first)."""
    return sorted(gaps, key=gap_priority_key)


class KnowledgeGapEngine:
    """Generates and ranks knowledge gaps from structured analysis state.

    This is an informational engine: it describes *what evidence would help*
    and never recommends enforcement actions.
    """

    def __init__(self) -> None:
        pass

    def from_hypothesis(
        self,
        hypothesis: Any,
        supporting: List[str],
        counter: List[str],
        unknowns: List[str],
    ) -> List[KnowledgeGap]:
        """Derive gaps that would discriminate between competing hypotheses."""
        gaps: List[KnowledgeGap] = []
        for unknown in unknowns:
            gaps.append(KnowledgeGap(
                gap_id=make_gap_id("UNKNOWN_RELATIONSHIP_DIRECTION", str(hypothesis.id)),
                gap_type="UNKNOWN_RELATIONSHIP_DIRECTION",
                subject_id=str(hypothesis.subject),
                description=unknown,
                severity="HIGH" if counter else "MEDIUM",
                recommended_action=f"Collect evidence addressing: {unknown}",
                uncertainty_reduction_impact=0.8 if counter else 0.5,
                distinguishes_between=[
                    "intermediary hypothesis",
                    "incidental connection hypothesis",
                ],
                potential_evidence=["call records", "message metadata", "CCTV", "transaction records"],
            ))
        return gaps

    def unverified_identifier(self, subject_id: str, identifier: str, identifier_type: str) -> KnowledgeGap:
        return KnowledgeGap(
            gap_id=make_gap_id("UNVERIFIED_IDENTIFIER", subject_id, identifier),
            gap_type="UNVERIFIED_IDENTIFIER",
            subject_id=subject_id,
            description=f"Ownership of {identifier_type} '{identifier}' for {subject_id} is uncorroborated.",
            severity="HIGH",
            recommended_action="Cross-verify subscriber / ownership registry.",
            uncertainty_reduction_impact=0.9,
            distinguishes_between=["registered owner hypothesis", "third-party user hypothesis"],
            potential_evidence=["subscriber registry", "KYC records", "service provider data"],
        )

    def uncorroborated_claim(self, subject_id: str, claim: str, source: str) -> KnowledgeGap:
        return KnowledgeGap(
            gap_id=make_gap_id("UNCORROBORATED_CLAIM", subject_id, claim[:40]),
            gap_type="UNCORROBORATED_CLAIM",
            subject_id=subject_id,
            description=f"Single-source claim ('{claim}') from {source} lacks independent corroboration.",
            severity="MEDIUM",
            recommended_action="Seek an independent source for the claim.",
            uncertainty_reduction_impact=0.7,
            potential_evidence=["independent witness statement", "corroborating records"],
            source_documents=[source],
        )

    def missing_timestamp(self, subject_id: str, event_description: str) -> KnowledgeGap:
        return KnowledgeGap(
            gap_id=make_gap_id("MISSING_TIMESTAMP", subject_id, event_description[:40]),
            gap_type="MISSING_TIMESTAMP",
            subject_id=subject_id,
            description=f"Event '{event_description}' has no temporal anchor.",
            severity="MEDIUM",
            recommended_action="Obtain timestamp for the event to support temporal analysis.",
            uncertainty_reduction_impact=0.6,
            potential_evidence=["call detail records", "transaction logs", "CCTV timestamps", "travel records"],
        )

    def conflicting_accounts(self, subject_id: str, claim_a: str, claim_b: str) -> KnowledgeGap:
        return KnowledgeGap(
            gap_id=make_gap_id("CONFLICTING_ACCOUNTS", subject_id, f"{claim_a[:20]}|{claim_b[:20]}"),
            gap_type="CONFLICTING_ACCOUNTS",
            subject_id=subject_id,
            description=f"Sources conflict: '{claim_a}' vs '{claim_b}'. The disagreement is preserved, not resolved silently.",
            severity="HIGH",
            recommended_action="Review both source documents and collect disambiguating evidence.",
            uncertainty_reduction_impact=0.85,
            distinguishes_between=[claim_a, claim_b],
            source_documents=[claim_a[:80], claim_b[:80]],
        )

    def no_direct_communication(self, subject_id: str, other_id: str) -> KnowledgeGap:
        return KnowledgeGap(
            gap_id=make_gap_id("NO_DIRECT_COMMUNICATION", subject_id, other_id),
            gap_type="NO_DIRECT_COMMUNICATION",
            subject_id=subject_id,
            description=f"No direct communication evidence establishes coordination between {subject_id} and {other_id}.",
            severity="HIGH",
            recommended_action="Check communication metadata for direct contact.",
            uncertainty_reduction_impact=0.9,
            distinguishes_between=[
                "direct coordination hypothesis",
                "incidental / legitimate relationship hypothesis",
            ],
            potential_evidence=["call records", "message metadata", "meeting records"],
        )
