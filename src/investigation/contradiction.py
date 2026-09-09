"""
investigation/contradiction.py
------------------------------
Evidence contradiction detection (Phase 5, requirement 4).

When two sources conflict, the system does NOT silently choose one.  It
represents:

* SUPPORTS   — evidence agrees with the hypothesis
* CONTRADICTS — evidence conflicts
* UNKNOWN    — insufficient / ambiguous

The detector builds an *evidence polarity map* for a hypothesis by
comparing evidence excerpts against the hypothesis claim.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

SUPPORTS = "SUPPORTS"
CONTRADICTS = "CONTRADICTS"
UNKNOWN = "UNKNOWN"


@dataclass
class EvidencePolarity:
    """Polarity of one evidence item toward a hypothesis."""

    evidence_id: str
    polarity: str = UNKNOWN
    strength: float = 0.0          # 0..1
    reason: str = ""
    excerpt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "polarity": self.polarity,
            "strength": round(self.strength, 4),
            "reason": self.reason,
        }


@dataclass
class ContradictionReport:
    """Aggregate polarity summary for a hypothesis."""

    hypothesis_id: str
    supporting: List[EvidencePolarity] = field(default_factory=list)
    contradicting: List[EvidencePolarity] = field(default_factory=list)
    unknown: List[EvidencePolarity] = field(default_factory=list)
    net_support: float = 0.0          # sum of strengths
    has_conflict: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "supporting": [p.to_dict() for p in self.supporting],
            "contradicting": [p.to_dict() for p in self.contradicting],
            "unknown": [p.to_dict() for p in self.unknown],
            "net_support": round(self.net_support, 4),
            "has_conflict": self.has_conflict,
            "verdict": "CONTRADICTED" if self.has_conflict else (
                "SUPPORTED" if self.net_support > 0 else "UNKNOWN"),
        }


#: negation cues that flip polarity
_NEGATION_RE = re.compile(
    r"\b(no|not|never|denied|denies|didn't|doesn't|refused|rejected|false|"
    r"untrue|wrong|unrelated|no evidence|no link|no connection)\b",
    re.IGNORECASE,
)

_AFFIRMATION_RE = re.compile(
    r"\b(confirmed|admitted|acknowledged|verified|stated|reported|found|"
    r"observed|evidence|recorded|seen|matched|called|met|transferred)\b",
    re.IGNORECASE,
)


def _extract_claim_terms(hypothesis_text: str) -> List[str]:
    """Key terms in the hypothesis claim (entity names, relations)."""
    terms = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", hypothesis_text):
        t = token.lower()
        if t not in {"the", "and", "for", "with", "between", "from", "that",
                     "this", "these", "those", "would", "could", "should",
                     "has", "have", "had", "was", "were", "is", "are", "not"}:
            terms.append(t)
    return sorted(set(terms))


def analyse_evidence(excerpt: str, hypothesis_text: str) -> Tuple[str, float]:
    """Polarity + strength of one excerpt toward a claim."""
    if not excerpt or not hypothesis_text:
        return UNKNOWN, 0.0
    lowered = excerpt.lower()
    terms = _extract_claim_terms(hypothesis_text)
    matches = sum(1 for t in terms if t in lowered)

    if _NEGATION_RE.search(lowered):
        neg_signals = len(_NEGATION_RE.findall(lowered))
        strength = min(1.0, (0.4 + 0.2 * neg_signals) if matches else 0.3)
        return CONTRADICTS, strength
    if _AFFIRMATION_RE.search(lowered) and matches > 0:
        strength = min(1.0, 0.4 + 0.15 * matches)
        return SUPPORTS, strength
    if matches > 0:
        return SUPPORTS, min(0.6, 0.3 + 0.1 * matches)
    return UNKNOWN, 0.0


class EvidenceContradictionDetector:
    """Assigns SUPPORTS / CONTRADICTS / UNKNOWN to evidence for a claim."""

    def __init__(self, evidence_store: Optional[Any] = None) -> None:
        self.store = evidence_store   # EvidenceStore-like: get_evidence(id)

    def analyse(self, hypothesis_id: str, claim_text: str,
                evidence_ids: Sequence[str],
                excerpt_overrides: Optional[Dict[str, str]] = None) -> ContradictionReport:
        """Analyse the polarity of each evidence id against the claim."""
        report = ContradictionReport(hypothesis_id=hypothesis_id)
        report_excerpts: Dict[str, str] = {}
        for eid in evidence_ids:
            excerpt = None
            if excerpt_overrides and eid in excerpt_overrides:
                excerpt = excerpt_overrides[eid]
            elif self.store is not None:
                rec = self.store.get_evidence(eid)
                if rec is not None:
                    excerpt = getattr(rec, "excerpt", "") or ""
            if excerpt is None:
                report.unknown.append(EvidencePolarity(
                    evidence_id=eid, polarity=UNKNOWN, strength=0.0,
                    reason="no excerpt available"))
                continue
            polarity, strength = analyse_evidence(excerpt, claim_text)
            pol = EvidencePolarity(
                evidence_id=eid,
                polarity=polarity,
                strength=strength,
                reason=f"matched claim terms; negation={'yes' if polarity == CONTRADICTS else 'no'}",
                excerpt=excerpt[:200],
            )
            if polarity == SUPPORTS:
                report.supporting.append(pol)
            elif polarity == CONTRADICTS:
                report.contradicting.append(pol)
            else:
                report.unknown.append(pol)
            report_excerpts[eid] = excerpt[:200]

        report.net_support = (
            sum(p.strength for p in report.supporting)
            - sum(p.strength for p in report.contradicting)
        )
        report.has_conflict = bool(report.supporting and report.contradicting)
        return report