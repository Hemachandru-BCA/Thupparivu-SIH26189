"""
counter_evidence.py
-------------------
Counter-evidence analysis and visualization support (P1.6).

Ensures investigators can see not only what supports a hypothesis but also
what contradicts it.  Every evidence item can be classified as:

  - SUPPORTING: aligns with the finding/hypothesis
  - CONTRADICTORY: weakens the finding/hypothesis
  - UNKNOWN: cannot be classified

This module provides:
  - Evidence polarity classification
  - Counter-evidence panels per finding
  - Support vs contradiction summaries
  - Evidence-to-finding traceability
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EvidencePolarityItem(BaseModel):
    evidence_id: str
    source_type: str = ""
    source_record_id: str = ""
    timestamp: Optional[str] = None
    entity_id: str = ""
    relationship: str = ""
    observed_claim: str = ""
    polarity: str = "UNKNOWN"   # SUPPORTING | CONTRADICTORY | UNKNOWN
    why: str = ""
    confidence: float = 0.0
    impact: str = ""


class CounterEvidencePanel(BaseModel):
    finding_id: str
    finding_title: str = ""
    hypothesis_text: str = ""
    supporting: List[EvidencePolarityItem] = Field(default_factory=list)
    contradictory: List[EvidencePolarityItem] = Field(default_factory=list)
    unknown: List[EvidencePolarityItem] = Field(default_factory=list)
    support_count: int = 0
    contradiction_count: int = 0
    unknown_count: int = 0
    balance_ratio: float = 0.0    # support / (support + contradiction), 0-1
    summary: str = ""
    limitations: List[str] = Field(default_factory=list)


class CounterEvidenceAnalyzer:
    """Classify and analyze evidence polarity for findings."""

    def __init__(self, evidence_store: Optional[Any] = None) -> None:
        self.evidence_store = evidence_store

    def _get_evidence_detail(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve evidence record details."""
        if not self.evidence_store:
            return None
        try:
            record = self.evidence_store.get_evidence(evidence_id)
            if record:
                return record.model_dump(mode="json") if hasattr(record, "model_dump") else {
                    "evidence_id": record.evidence_id,
                    "source_type": record.source_type,
                    "source_record_id": record.source_record_id,
                    "timestamp": record.timestamp,
                    "text_excerpt": record.text_excerpt,
                    "confidence": record.confidence,
                    "subject_ids": record.subject_ids,
                }
        except Exception:
            pass
        return None

    def _classify_polarity(
        self,
        evidence_id: str,
        finding: Dict[str, Any],
    ) -> EvidencePolarityItem:
        """Classify a single evidence item's polarity relative to a finding."""
        supporting_ids = set(finding.get("supporting_evidence_ids") or [])
        counter_ids = set(finding.get("counter_evidence_ids") or [])

        detail = self._get_evidence_detail(evidence_id)
        source_type = detail.get("source_type", "") if detail else ""
        source_record_id = detail.get("source_record_id", "") if detail else ""
        timestamp = detail.get("timestamp") if detail else None
        text = detail.get("text_excerpt", "") if detail else ""
        confidence = detail.get("confidence", 0.0) if detail else 0.0
        subject_ids = detail.get("subject_ids", []) if detail else []

        if evidence_id in supporting_ids:
            polarity = "SUPPORTING"
            why = "This evidence is listed as supporting the finding."
            impact = "Strengthens the hypothesis."
        elif evidence_id in counter_ids:
            polarity = "CONTRADICTORY"
            why = "This evidence contradicts or weakens the finding."
            impact = "Weakens the hypothesis."
        else:
            polarity = "UNKNOWN"
            why = "This evidence cannot be clearly classified as supporting or contradictory."
            impact = "Uncertain impact on the hypothesis."

        return EvidencePolarityItem(
            evidence_id=evidence_id,
            source_type=source_type,
            source_record_id=source_record_id,
            timestamp=timestamp,
            entity_id=subject_ids[0] if subject_ids else "",
            relationship="",
            observed_claim=text[:200] if text else "",
            polarity=polarity,
            why=why,
            confidence=confidence,
            impact=impact,
        )

    def analyze_finding(self, finding: Dict[str, Any]) -> CounterEvidencePanel:
        """Full counter-evidence analysis for one finding."""
        finding_id = finding.get("id", "")
        finding_title = finding.get("subject_label", finding_id)

        all_evidence_ids = set(
            (finding.get("supporting_evidence_ids") or []) +
            (finding.get("counter_evidence_ids") or [])
        )

        # Also include evidence from observed/inferred claims
        for claim in (finding.get("observed") or []) + (finding.get("inferred") or []):
            for eid in claim.get("evidence_ids", []):
                all_evidence_ids.add(eid)

        items = []
        for eid in all_evidence_ids:
            items.append(self._classify_polarity(eid, finding))

        supporting = [i for i in items if i.polarity == "SUPPORTING"]
        contradictory = [i for i in items if i.polarity == "CONTRADICTORY"]
        unknown = [i for i in items if i.polarity == "UNKNOWN"]

        support_count = len(supporting)
        contradiction_count = len(contradictory)
        total_classified = support_count + contradiction_count
        balance = support_count / max(total_classified, 1)

        # Summary
        if contradiction_count == 0:
            summary = f"All {support_count} evidence items support this finding. No contradictory evidence identified."
        elif support_count == 0:
            summary = f"All {contradiction_count} evidence items contradict this finding. No supporting evidence identified."
        else:
            summary = (
                f"{support_count} supporting vs {contradiction_count} contradictory evidence items "
                f"(balance: {balance:.0%}). {len(unknown)} unclassified."
            )

        return CounterEvidencePanel(
            finding_id=finding_id,
            finding_title=finding_title,
            hypothesis_text=finding.get("observed", [{}])[0].get("text", "") if finding.get("observed") else "",
            supporting=supporting,
            contradictory=contradictory,
            unknown=unknown,
            support_count=support_count,
            contradiction_count=contradiction_count,
            unknown_count=len(unknown),
            balance_ratio=round(balance, 4),
            summary=summary,
            limitations=[
                "Polarity classification is based on the finding's own supporting/counter evidence labels.",
                "UNKNOWN items may be relevant but their relationship to the hypothesis is unclear.",
                "Balance ratio is informational; a low ratio does not mean the finding is wrong.",
            ],
        )

    def analyze_all_findings(self, findings: List[Dict[str, Any]]) -> List[CounterEvidencePanel]:
        """Analyze counter-evidence for all findings."""
        return [self.analyze_finding(f) for f in findings[:50]]
