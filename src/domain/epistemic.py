"""
domain/epistemic.py
-------------------
Epistemic State Harmonization Layer for Thupparivu.

The core epistemic contract of the whole system:

    OBSERVED, INFERRED, POSSIBLE, NEGATED, CONTRADICTED, UNKNOWN

Rules enforced here (see MASTER ENGINEERING DIRECTIVE §5):

* Never upgrade  INFERRED -> OBSERVED
* Never upgrade  POSSIBLE -> FACT/OBSERVED
* Never collapse UNKNOWN -> FALSE/NON_MATCH
* Never present confidence as probability of guilt
* NEGATED statements must never produce positive graph edges

Every layer (NLP, extraction, graph, analytics, LLM) should convert through
this module so the epistemic vocabulary stays consistent.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Optional


class EpistemicStatus(str, Enum):
    """Canonical epistemic vocabulary used across the platform."""

    OBSERVED = "OBSERVED"          # Directly present in evidence
    INFERRED = "INFERRED"          # Derived from patterns / analysis
    POSSIBLE = "POSSIBLE"          # Modal / plausible, not established
    NEGATED = "NEGATED"            # Explicitly negated in source
    CONTRADICTED = "CONTRADICTED"  # Conflicting evidence exists
    UNKNOWN = "UNKNOWN"            # Cannot determine from evidence


# Hard-forbidden upgrades (structure-preserving lattice)
_FORBIDDEN_UPGRADES: Dict[EpistemicStatus, frozenset] = {
    EpistemicStatus.NEGATED: frozenset(
        {EpistemicStatus.OBSERVED, EpistemicStatus.INFERRED, EpistemicStatus.POSSIBLE}
    ),
    EpistemicStatus.UNKNOWN: frozenset(
        {EpistemicStatus.OBSERVED, EpistemicStatus.INFERRED, EpistemicStatus.POSSIBLE, EpistemicStatus.NEGATED}
    ),
    EpistemicStatus.POSSIBLE: frozenset({EpistemicStatus.OBSERVED, EpistemicStatus.INFERRED}),
    EpistemicStatus.INFERRED: frozenset({EpistemicStatus.OBSERVED}),
}

# Allowed transitions for status refinement (strictness-preserving)
_ALLOWED_REFINEMENTS: Dict[EpistemicStatus, frozenset] = {
    EpistemicStatus.OBSERVED: frozenset({EpistemicStatus.OBSERVED}),
    EpistemicStatus.INFERRED: frozenset({EpistemicStatus.INFERRED, EpistemicStatus.POSSIBLE}),
    EpistemicStatus.POSSIBLE: frozenset({EpistemicStatus.POSSIBLE, EpistemicStatus.INFERRED}),
    EpistemicStatus.NEGATED: frozenset({EpistemicStatus.NEGATED}),
    EpistemicStatus.CONTRADICTED: frozenset(
        {EpistemicStatus.CONTRADICTED, EpistemicStatus.OBSERVED, EpistemicStatus.INFERRED}
    ),
    EpistemicStatus.UNKNOWN: frozenset({EpistemicStatus.UNKNOWN}),
}


def coerce(value: Any) -> EpistemicStatus:
    """Coerce any string/enum into a canonical epistemic status."""
    if isinstance(value, EpistemicStatus):
        return value
    if value is None:
        return EpistemicStatus.UNKNOWN
    text = str(value).strip().upper()
    for status in EpistemicStatus:
        if status.value == text:
            return status
    # Map legacy vocabulary from other layers
    mapping = {
        "OBSERVED": EpistemicStatus.OBSERVED,
        "FACTUAL": EpistemicStatus.OBSERVED,
        "CONFIRMED": EpistemicStatus.OBSERVED,
        "VERIFIED": EpistemicStatus.OBSERVED,
        "INFERRED": EpistemicStatus.INFERRED,
        "STATISTICAL_FINDING": EpistemicStatus.INFERRED,
        "MODEL_FINDING": EpistemicStatus.INFERRED,
        "POSSIBLE": EpistemicStatus.POSSIBLE,
        "MAYBE": EpistemicStatus.POSSIBLE,
        "MODAL": EpistemicStatus.POSSIBLE,
        "HYPOTHETICAL": EpistemicStatus.POSSIBLE,
        "SPECULATIVE": EpistemicStatus.POSSIBLE,
        "NEGATED": EpistemicStatus.NEGATED,
        "DENIED": EpistemicStatus.NEGATED,
        "FALSE": EpistemicStatus.NEGATED,
        "CONTRADICTED": EpistemicStatus.CONTRADICTED,
        "CONFLICTED": EpistemicStatus.CONTRADICTED,
        "UNKNOWN": EpistemicStatus.UNKNOWN,
        "UNCERTAIN": EpistemicStatus.UNKNOWN,
        "AMBIGUOUS": EpistemicStatus.UNKNOWN,
        "AM": EpistemicStatus.UNKNOWN,
    }
    return mapping.get(text, EpistemicStatus.UNKNOWN)


def can_refine(current: Any, proposed: Any) -> bool:
    """Whether ``proposed`` is a permitted refinement of ``current``.

    The epistemic lattice forbids upgrading weak states into strong ones
    (UNKNOWN -> OBSERVED, INFERRED -> OBSERVED, ...).
    """
    cur = coerce(current)
    prop = coerce(proposed)
    if cur is prop:
        return True
    if prop in _FORBIDDEN_UPGRADES.get(cur, frozenset()):
        return False
    return prop in _ALLOWED_REFINEMENTS.get(cur, frozenset())


def merge_statuses(statuses: Iterable[Any]) -> EpistemicStatus:
    """Combine multiple epistemic labels for the same fact.

    The most conservative (weakest) truthful label wins. If any label is
    NEGATED and another is OBSERVED, the result is CONTRADICTED.
    """
    coerced = [coerce(s) for s in statuses if s is not None]
    if not coerced:
        return EpistemicStatus.UNKNOWN
    if EpistemicStatus.NEGATED in coerced and EpistemicStatus.OBSERVED in coerced:
        return EpistemicStatus.CONTRADICTED
    # Ranked weakest->strongest; merge to the strongest that all labels agree supports
    rank = {
        EpistemicStatus.UNKNOWN: 0,
        EpistemicStatus.POSSIBLE: 1,
        EpistemicStatus.INFERRED: 2,
        EpistemicStatus.OBSERVED: 3,
        EpistemicStatus.NEGATED: 3,
        EpistemicStatus.CONTRADICTED: 4,
    }
    # Use most conservative of non-UNKNOWN labels
    meaningful = [c for c in coerced if c is not EpistemicStatus.UNKNOWN]
    if not meaningful:
        return EpistemicStatus.UNKNOWN
    minimal = min(meaningful, key=lambda s: rank[s])
    if minimal is EpistemicStatus.NEGATED and len(meaningful) > 1:
        # NEGATED alongside INFERRED/POSSIBLE: keep conservative NEGATED
        pass
    return minimal


def status_rank(status: Any) -> int:
    """Rank of an epistemic status (higher = stronger/less uncertain)."""
    return {
        EpistemicStatus.UNKNOWN: 0,
        EpistemicStatus.POSSIBLE: 1,
        EpistemicStatus.INFERRED: 2,
        EpistemicStatus.NEGATED: 3,
        EpistemicStatus.OBSERVED: 3,
        EpistemicStatus.CONTRADICTED: 4,
    }.get(coerce(status), 0)


def to_fact_status(status: Any) -> str:
    """Convert to the legacy FactStatus vocabulary used by domain.models."""
    coerced = coerce(status)
    mapping = {
        EpistemicStatus.OBSERVED: "OBSERVED",
        EpistemicStatus.INFERRED: "INFERRED",
        EpistemicStatus.POSSIBLE: "HYPOTHETICAL",
        EpistemicStatus.NEGATED: "UNKNOWN",   # explicit negation is not a fact; never OBSERVED
        EpistemicStatus.CONTRADICTED: "CONTRADICTED",
        EpistemicStatus.UNKNOWN: "UNKNOWN",
    }
    return mapping[coerced]


def downgrade_for_missing_evidence(status: Any, has_evidence: bool) -> EpistemicStatus:
    """Never let OBSERVED stand without evidence IDs.

    Explained in MASTER DIRECTIVE §13 / §31: if a claim claims OBSERVED but no
    evidence exists, it must be REJECTED or DOWNGRADED.  This helper applies
    the downgrade path (REJECT is handled by schema validation upstream).
    """
    cur = coerce(status)
    if cur is EpistemicStatus.OBSERVED and not has_evidence:
        return EpistemicStatus.INFERRED
    return cur