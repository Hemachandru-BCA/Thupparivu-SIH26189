"""
domain/scoring.py
-----------------
Unified signal + scoring abstraction (Phase 1, requirement 5).

Instead of scattering confidence calculations across modules, every
intelligence component emits *signals*, bundles them, and converts them
into a :class:`ConfidenceScore` with explanations.

Example producer flow::

    engine = LinkPredictionEngine(...)
    bundle = engine.raw_signals(source, target)          # SignalBundle
    score = bundle.to_confidence()                        # ConfidenceScore
    output = {"probability": score.value,
              "score": score.to_dict(),
              "explanation": bundle.explain()}

Signals are:

* decomposed into families (structural / temporal / semantic / behavioral /
  evidence / entity-resolution),
* each with a value in [0, 1] and a weight,
* plus an optional evidence link and a human description.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.domain.models import ConfidenceExplanation, ConfidenceScore


@dataclass
class Signal:
    """One raw measurement produced by an intelligence component.

    ``family`` selects which ConfidenceScore slot the signal feeds:

    structural | temporal | semantic | behavioral | evidence | entity_resolution
    """

    name: str
    family: str = "structural"
    value: float = 0.0
    weight: float = 1.0
    description: str = ""
    evidence_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.value = round(max(0.0, min(1.0, float(self.value))), 4)
        self.weight = round(max(0.0, float(self.weight)), 4)


FAMILY_SLOT = {
    "structural": "structural_score",
    "temporal": "temporal_score",
    "semantic": "semantic_score",
    "behavioral": "behavioral_score",
    "evidence": "evidence_score",
    "entity_resolution": "entity_resolution_score",
}


@dataclass
class SignalBundle:
    """A collection of signals that together justify one prediction."""

    signals: List[Signal] = field(default_factory=list)
    counter_evidence_penalty: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add(self, signal: Signal) -> "SignalBundle":
        self.signals.append(signal)
        return self

    # ------------------------------------------------------------------ #
    def _family_aggregates(self) -> Dict[str, List[Signal]]:
        agg: Dict[str, List[Signal]] = {}
        for sig in self.signals:
            agg.setdefault(sig.family, []).append(sig)
        return agg

    def to_confidence(self) -> ConfidenceScore:
        """Weighted per-family aggregation into a ConfidenceScore."""
        scores: Dict[str, float] = {
            "structural": 0.0,
            "temporal": 0.0,
            "semantic": 0.0,
            "behavioral": 0.0,
            "evidence": 0.0,
            "entity_resolution": 0.0,
        }
        weights: Dict[str, float] = {
            "structural": 0.0,
            "temporal": 0.0,
            "semantic": 0.0,
            "behavioral": 0.0,
            "evidence": 0.0,
            "entity_resolution": 0.0,
        }
        explanations: List[ConfidenceExplanation] = []
        for family, sigs in self._family_aggregates().items():
            weighted = sum(s.value * s.weight for s in sigs)
            wsum = sum(s.weight for s in sigs)
            if wsum > 0:
                scores[family] = weighted / wsum
                weights[family] = wsum
            for s in sigs:
                explanations.append(
                    ConfidenceExplanation(
                        component=s.name,
                        value=s.value,
                        weight=s.weight,
                        description=s.description,
                        evidence_ids=s.evidence_ids,
                    )
                )
        return ConfidenceScore(
            structural_score=scores["structural"],
            temporal_score=scores["temporal"],
            semantic_score=scores["semantic"],
            behavioral_score=scores["behavioral"],
            evidence_score=scores["evidence"],
            entity_resolution_score=scores["entity_resolution"],
            counter_evidence_penalty=self.counter_evidence_penalty,
            explanations=explanations,
            weights=weights,
        )

    def explain(self) -> str:
        """Compact human-readable explanation of the bundle."""
        parts = []
        for family, sigs in self._family_aggregates().items():
            top = max(sigs, key=lambda s: s.value * s.weight)
            n = len(sigs)
            parts.append(
                f"{family}: {top.value:.2f} ({top.name}"
                + (f" +{n-1} more" if n > 1 else "") + ")"
            )
        base = "; ".join(parts) or "no signals"
        if self.counter_evidence_penalty > 0:
            base += f"; counter-evidence penalty -{self.counter_evidence_penalty:.2f}"
        return base


def percentile_rank(value: float, distribution: List[float]) -> float:
    """Percentile rank of ``value`` within a distribution (0..1)."""
    if not distribution:
        return 0.5
    below = sum(1 for v in distribution if v <= value)
    return round(below / len(distribution), 4)