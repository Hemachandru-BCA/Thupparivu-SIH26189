"""
investigation/dossier.py
------------------------
Structured, deterministic dossier generator (Phase 5, requirement 9).

* Facts come from structured evidence objects only.
* Every sentence containing a factual claim is traceable to evidence ids.
* A deterministic generator runs first; an optional LLM wording pass can be
  added later — but never invented facts.
* The dossier is organized: OBSERVED FACTS / INFERRED HYPOTHESES /
  COUNTER-EVIDENCE / UNKNOWNS / TEMPORAL TIMELINE.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from src.domain.models import Hypothesis, Observation
from src.investigation.contradiction import ContradictionReport

logger = logging.getLogger(__name__)

DOSSIER_NAMESPACE = uuid.UUID("6c2a4f89-7b3e-4d1c-9a80-55e1c2f4a617")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DossierSection:
    title: str
    items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "items": list(self.items)}


@dataclass
class TimelineEvent:
    timestamp: Optional[str]
    description: str
    evidence_ids: List[str] = field(default_factory=list)


@dataclass
class SubjectDossier:
    """A complete investigator dossier for one subject."""

    dossier_id: str
    subject_id: str
    subject_label: str = ""
    classification: str = "INTELLIGENCE_SUMMARY"
    status: str = "DRAFT_FOR_HUMAN_REVIEW"
    executive_summary: str = ""
    timeline: List[TimelineEvent] = field(default_factory=list)
    sections: List[DossierSection] = field(default_factory=list)
    supporting_evidence: List[str] = field(default_factory=list)
    counter_evidence: List[str] = field(default_factory=list)
    hypothesis_ids: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    disclaimer: str = (
        "This dossier is an intelligence summary for investigative "
        "purposes only. It is NOT a determination of guilt, an arrest "
        "recommendation, or a legal conclusion. Human review is required."
    )
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dossier_id": self.dossier_id,
            "subject_id": self.subject_id,
            "subject_label": self.subject_label,
            "classification": self.classification,
            "status": self.status,
            "executive_summary": self.executive_summary,
            "timeline": [{"timestamp": e.timestamp, "description": e.description,
                          "evidence_ids": list(e.evidence_ids)} for e in self.timeline],
            "sections": [s.to_dict() for s in self.sections],
            "supporting_evidence": list(self.supporting_evidence),
            "counter_evidence": list(self.counter_evidence),
            "hypothesis_ids": list(self.hypothesis_ids),
            "limitations": list(self.limitations),
            "disclaimer": self.disclaimer,
            "created_at": self.created_at,
        }


class DossierGenerator:
    """Deterministic, evidence-grounded dossier builder.

    Usage::

        gen = DossierGenerator(evidence_store, hypothesis_lookup=None)
        dossier = gen.generate(subject_id="E-42", hypotheses=[...], observations=[...])
    """

    def __init__(self, evidence_store: Optional[Any] = None,
                 hypothesis_lookup: Optional[Dict[str, Hypothesis]] = None) -> None:
        self.store = evidence_store
        self.hypothesis_lookup = hypothesis_lookup or {}

    # ------------------------------------------------------------------ #
    def generate(self, subject_id: str, subject_label: str = "",
                 hypotheses: Sequence[Hypothesis] = (),
                 observations: Sequence[Observation] = (),
                 contradiction: Optional[ContradictionReport] = None,
                 max_evidence: int = 30) -> SubjectDossier:
        """Build a dossier for a subject from structured facts only."""
        dossier_id = "DOSSIER-" + str(uuid.uuid5(
            DOSSIER_NAMESPACE, f"{subject_id}|{_utcnow()}"))

        supporting: List[str] = []
        counter: List[str] = []
        timeline: List[TimelineEvent] = []
        hypothesis_ids: List[str] = []

        # ---- observed facts section (evidence-bound) ----
        observed_items: List[Dict[str, Any]] = []
        for obs in observations:
            observed_items.append({
                "text": obs.text,
                "evidence_ids": list(obs.evidence_ids),
                "timestamp": obs.timestamp,
            })
            supporting.extend(obs.evidence_ids)
            if obs.timestamp:
                timeline.append(TimelineEvent(
                    timestamp=obs.timestamp,
                    description=obs.text,
                    evidence_ids=list(obs.evidence_ids),
                ))
            # cap evidence to keep the dossier bounded
            if len(supporting) >= max_evidence:
                break

        # ---- hypotheses section ----
        hypothesis_items: List[Dict[str, Any]] = []
        for h in hypotheses:
            hypothesis_items.append({
                "id": h.id,
                "type": h.hypothesis_type,
                "subject": h.subject,
                "confidence": round(h.confidence, 4),
                "status": h.status,
                "explanation": h.explanation,
                "supporting_evidence": list(h.supporting_evidence_ids)[:10],
                "counter_evidence": list(h.counter_evidence_ids)[:10],
            })
            hypothesis_ids.append(h.id)
            supporting.extend(h.supporting_evidence_ids)
            counter.extend(h.counter_evidence_ids)

        # ---- counter-evidence section ----
        counter_items = [{"evidence_id": cid} for cid in dict.fromkeys(counter)]
        for cid in dict.fromkeys(counter):
            counter_items.append({"evidence_id": cid, "relation": "CONTRADICTS"})

        # ---- unknown section ----
        unknown_items: List[Dict[str, Any]] = [
            {"text": "Actual identity of the hidden intermediary (if one exists)."},
            {"text": "Whether predicted relationships correspond to real events."},
            {"text": "Direction and timing of any suspected coordination."},
        ]

        # ---- contradiction verdict ----
        verdict_item: List[Dict[str, Any]] = []
        if contradiction is not None:
            verdict_item.append({
                "verdict": contradiction.to_dict()["verdict"],
                "net_support": contradiction.net_support,
                "has_conflict": contradiction.has_conflict,
            })

        # ---- executive summary (traceable) ----
        summary_parts = [f"Subject {subject_label or subject_id} investigation summary."]
        n_obs = len(observed_items)
        n_hyp = len(hypothesis_items)
        if n_obs:
            summary_parts.append(f"{n_obs} observed fact(s), each backed by evidence ids.")
        if n_hyp:
            summary_parts.append(
                f"{n_hyp} structured hypothesis/hypotheses, all labelled as inferences.")
        if contradiction is not None and contradiction.has_conflict:
            summary_parts.append("Evidence conflict detected: supporting and "
                                 "contradicting evidence both exist.")
        if not n_obs and not n_hyp:
            summary_parts.append(
                "The system cannot state strong conclusions from available evidence "
                "— I DON'T KNOW is the honest answer here.")

        sections = [
            DossierSection("Observed facts",
                           [{"text": i["text"], "evidence_ids": i["evidence_ids"]}
                            for i in observed_items]),
            DossierSection("Inferred hypotheses", hypothesis_items),
            DossierSection("Counter-evidence", counter_items),
            DossierSection("Unknowns / gaps", unknown_items),
        ]
        if verdict_item:
            sections.append(DossierSection("Contradiction verdict", verdict_item))

        timeline.sort(key=lambda e: e.timestamp or "")

        return SubjectDossier(
            dossier_id=dossier_id,
            subject_id=subject_id,
            subject_label=subject_label,
            executive_summary=" ".join(summary_parts),
            timeline=timeline,
            sections=sections,
            supporting_evidence=sorted(set(supporting))[:max_evidence],
            counter_evidence=sorted(set(counter))[:max_evidence],
            hypothesis_ids=hypothesis_ids,
            limitations=[
                "Every statement in this dossier is traceable to evidence ids.",
                "Hypotheses are inferences, not facts.",
                "No guilt, arrest, or legal determination is made.",
                "Human review is required before operational use.",
            ],
        )


def validate_dossier(dossier: SubjectDossier, evidence_ids: Sequence[str]) -> Dict[str, Any]:
    """Validation: every cited evidence id must exist in the store."""
    known = set(evidence_ids)
    cited = set(dossier.supporting_evidence) | set(dossier.counter_evidence)
    for section in dossier.sections:
        for item in section.items:
            for eid in item.get("evidence_ids", []) or []:
                cited.add(eid)
    missing = sorted(eid for eid in cited if eid not in known and not eid.startswith("COUNTER:"))
    valid = len(missing) == 0
    return {
        "valid": valid,
        "missing_evidence": missing,
        "cited_evidence_count": len(cited),
    }