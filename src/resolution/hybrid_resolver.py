"""
resolution/hybrid_resolver.py
-----------------------------
Hybrid entity resolution engine (Phase 3).

The existing :mod:`src.resolution.entity_matcher` solves name matching.
This module layers a **hybrid pipeline** on top:

    CANDIDATE GENERATION
      → DETERMINISTIC MATCHING
      → FUZZY MATCHING
      → SEMANTIC MATCHING
      → CONTEXTUAL SCORING
      → GRAPH-CONSISTENCY SCORING
      → FINAL DECISION (MATCH | POSSIBLE_MATCH | NON_MATCH | UNKNOWN)

Two records that *look* different linguistically may become more likely to
refer to the same entity when their behavioural / graph context strongly
matches (graph-aware resolution).

This module NEVER forces a match: output is one of the four decision
classes above, and every decision carries a per-feature breakdown.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from src.resolution.entity_matcher import (
    compare_names,
    levenshtein_similarity,
    normalize_name,
    soundex,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Decision semantics
# --------------------------------------------------------------------------- #

MATCH = "MATCH"
POSSIBLE_MATCH = "POSSIBLE_MATCH"
NON_MATCH = "NON_MATCH"
UNKNOWN = "UNKNOWN"

DECISIONS = {MATCH, POSSIBLE_MATCH, NON_MATCH, UNKNOWN}


# --------------------------------------------------------------------------- #
# Typed records
# --------------------------------------------------------------------------- #

@dataclass
class ResolvableRecord:
    """A partial record that needs to be resolved to a canonical entity."""

    record_id: str
    name: str = ""
    entity_type: str = "PERSON"
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    organization: Optional[str] = None
    identifiers: Dict[str, str] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    contacts: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "organization": self.organization,
            "identifiers": dict(self.identifiers),
            "events": list(self.events),
            "locations": list(self.locations),
            "contacts": list(self.contacts),
            "attributes": dict(self.attributes),
        }


@dataclass
class PairwiseFeatures:
    """Feature breakdown for one pairwise comparison."""

    name_similarity: float = 0.0
    phone_similarity: float = 0.0
    email_similarity: float = 0.0
    address_similarity: float = 0.0
    organization_similarity: float = 0.0
    shared_identifiers: float = 0.0
    shared_events: float = 0.0
    shared_locations: float = 0.0
    shared_contacts: float = 0.0
    temporal_compatibility: float = 0.0
    graph_neighborhood_similarity: float = 0.0
    #: entity-type agreement (1.0 if same type, else 0.0)
    type_agreement: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "name_similarity": round(self.name_similarity, 4),
            "phone_similarity": round(self.phone_similarity, 4),
            "email_similarity": round(self.email_similarity, 4),
            "address_similarity": round(self.address_similarity, 4),
            "organization_similarity": round(self.organization_similarity, 4),
            "shared_identifiers": round(self.shared_identifiers, 4),
            "shared_events": round(self.shared_events, 4),
            "shared_locations": round(self.shared_locations, 4),
            "shared_contacts": round(self.shared_contacts, 4),
            "temporal_compatibility": round(self.temporal_compatibility, 4),
            "graph_neighborhood_similarity": round(self.graph_neighborhood_similarity, 4),
            "type_agreement": round(self.type_agreement, 4),
        }


@dataclass
class ResolutionDecision:
    """Final output of the hybrid resolution for one record pair."""

    left_id: str
    right_id: str
    decision: str = UNKNOWN        # MATCH | POSSIBLE_MATCH | NON_MATCH | UNKNOWN
    score: float = 0.0
    features: PairwiseFeatures = field(default_factory=PairwiseFeatures)
    weights: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "left_id": self.left_id,
            "right_id": self.right_id,
            "decision": self.decision,
            "score": round(self.score, 4),
            "features": self.features.to_dict(),
            "weights": dict(self.weights),
            "explanation": self.explanation,
        }


@dataclass
class HybridResolverConfig:
    """Knobs for the hybrid resolution pipeline."""

    match_threshold: float = 0.78
    possible_threshold: float = 0.55
    #: fall back to UNKNOWN below this score instead of NON_MATCH
    unknown_threshold: float = 0.20
    #: weights for the combined score (name is dominant, context adds lift)
    name_weight: float = 0.35
    phone_weight: float = 0.15
    email_weight: float = 0.10
    address_weight: float = 0.05
    organization_weight: float = 0.05
    identifier_weight: float = 0.10
    context_weight: float = 0.10
    graph_weight: float = 0.10
    #: strong-evidence gates
    exact_identifier_match: bool = True
    exact_phone_match_boost: float = 0.15
    #: when entity types differ, cap the score at possible_threshold
    strict_type_separation: bool = True


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return str(email).strip().lower()


def _token_set(text: Optional[str]) -> Set[str]:
    if not text:
        return set()
    return set(normalize_name(text).split())


def _jaccard_set(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0   # both empty → identical (vacuously)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --------------------------------------------------------------------------- #
# The hybrid pipeline
# --------------------------------------------------------------------------- #

class HybridEntityResolver:
    """Multi-signal entity resolution over partial records.

    Stage 1 — candidate generation (blocking on normalized phone / email /
    identifier, then token-overlap name blocking).
    Stage 2 — deterministic matching (exact identifiers, exact phone).
    Stage 3 — fuzzy matching (name similarity, phone similarity).
    Stage 4 — semantic + contextual scoring (shared events, locations,
    contacts, organization, temporal compatibility).
    Stage 5 — graph-consistency scoring (neighborhood overlap).
    Stage 6 — final decision with thresholds.
    """

    def __init__(self, config: Optional[HybridResolverConfig] = None,
                 neighborhood: Optional[Mapping[str, Sequence[str]]] = None) -> None:
        self.config = config or HybridResolverConfig()
        #: node id → neighbour ids (graph-consistency context)
        self.neighborhood = neighborhood or {}

    # ------------------------------------------------------------------ #
    # 1. Candidate generation
    # ------------------------------------------------------------------ #
    def candidates(self, records: Sequence[ResolvableRecord]) -> List[Tuple[int, int]]:
        """Blocking: only compare records that could plausibly be the same."""
        pairs: Set[Tuple[int, int]] = set()

        # exact phone / email / identifier blocking
        phone_index: Dict[str, List[int]] = {}
        email_index: Dict[str, List[int]] = {}
        id_index: Dict[str, List[int]] = {}
        for i, rec in enumerate(records):
            phone = normalize_phone(rec.phone)
            if phone:
                phone_index.setdefault(phone, []).append(i)
            email = normalize_email(rec.email)
            if email:
                email_index.setdefault(email, []).append(i)
            for _k, v in (rec.identifiers or {}).items():
                if v:
                    id_index.setdefault(str(v).lower(), []).append(i)

        for index in (phone_index, email_index, id_index):
            for group in index.values():
                for a in range(len(group)):
                    for b in range(a + 1, len(group)):
                        pairs.add(tuple(sorted((group[a], group[b]))))

        # name token blocking
        token_index: Dict[str, List[int]] = {}
        for i, rec in enumerate(records):
            for tok in _token_set(rec.name):
                token_index.setdefault(tok, []).append(i)
        for group in token_index.values():
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    if (group[a], group[b]) not in pairs:
                        pairs.add((min(group[a], group[b]), max(group[a], group[b])))

        # limits: warn if the full matrix would be compared anyway
        n = len(records)
        if len(pairs) > n * n // 2:
            logger.info("Candidate blocking generated %d candidate pairs from %d records",
                        len(pairs), n)
        return sorted(pairs)

    # ------------------------------------------------------------------ #
    # 2-5. Feature computation
    # ------------------------------------------------------------------ #
    def compute_features(self, a: ResolvableRecord, b: ResolvableRecord) -> PairwiseFeatures:
        cfg = self.config
        feat = PairwiseFeatures()

        name_a = normalize_name(a.name)
        name_b = normalize_name(b.name)
        if name_a and name_b:
            match = compare_names(a.name, b.name)
            feat.name_similarity = max(0.0, min(1.0, match.score))
        else:
            feat.name_similarity = 0.0

        ph_a = normalize_phone(a.phone)
        ph_b = normalize_phone(b.phone)
        if ph_a and ph_b:
            feat.phone_similarity = 1.0 if ph_a == ph_b else 0.0

        em_a = normalize_email(a.email)
        em_b = normalize_email(b.email)
        if em_a and em_b:
            feat.email_similarity = 1.0 if em_a == em_b else 0.0

        if a.address and b.address:
            feat.address_similarity = _jaccard_set(_token_set(a.address), _token_set(b.address))

        if a.organization and b.organization:
            feat.organization_similarity = _jaccard_set(
                _token_set(a.organization), _token_set(b.organization))

        feat.shared_identifiers = _jaccard_set(
            set(str(v).lower() for v in (a.identifiers or {}).values()),
            set(str(v).lower() for v in (b.identifiers or {}).values()),
        )

        feat.shared_events = _jaccard_set(set(a.events or []), set(b.events or []))
        feat.shared_locations = _jaccard_set(set(a.locations or []), set(b.locations or []))
        feat.shared_contacts = _jaccard_set(set(a.contacts or []), set(b.contacts or []))

        # temporal compatibility: non-overlapping date ranges weaken the match
        t_a = a.attributes.get("valid_to") or a.attributes.get("last_seen")
        t_b = b.attributes.get("valid_from") or b.attributes.get("first_seen")
        if t_a and t_b:
            try:
                from datetime import datetime
                ta = datetime.fromisoformat(str(t_a).replace("Z", "+00:00"))
                tb = datetime.fromisoformat(str(t_b).replace("Z", "+00:00"))
                # compatible if A's last_seen >= B's first_seen (overlapping timelines)
                feat.temporal_compatibility = 1.0 if ta >= tb else 0.0
            except ValueError:
                feat.temporal_compatibility = 0.5  # unknown → neutral
        else:
            feat.temporal_compatibility = 0.5

        # graph-neighborhood similarity
        feat.graph_neighborhood_similarity = self._neighborhood_similarity(a, b)

        feat.type_agreement = 1.0 if a.entity_type == b.entity_type else 0.0
        return feat

    def _neighborhood_similarity(self, a: ResolvableRecord,
                                 b: ResolvableRecord) -> float:
        """Jaccard over graph neighbours of the two records' canonical ids."""
        neigh_a = self.neighborhood.get(a.record_id, []) or []
        neigh_b = self.neighborhood.get(b.record_id, []) or []
        set_a, set_b = set(neigh_a), set(neigh_b)
        if not set_a and not set_b:
            return 0.0   # no graph context → no lift, no penalty
        return len(set_a & set_b) / len(set_a | set_b)

    # ------------------------------------------------------------------ #
    # 6. Final decision
    # ------------------------------------------------------------------ #
    def decide(self, a: ResolvableRecord, b: ResolvableRecord,
               features: Optional[PairwiseFeatures] = None) -> ResolutionDecision:
        cfg = self.config
        feat = features or self.compute_features(a, b)

        # gate 1: type separation
        if cfg.strict_type_separation and feat.type_agreement < 1.0:
            return ResolutionDecision(
                left_id=a.record_id,
                right_id=b.record_id,
                decision=NON_MATCH,
                score=0.0,
                features=feat,
                explanation="Entity types differ and strict separation is enabled.",
            )

        # gate 2: exact identifier / phone match is an extremely strong signal
        strong_match = False
        id_a = set(str(v).lower() for v in (a.identifiers or {}).values())
        id_b = set(str(v).lower() for v in (b.identifiers or {}).values())
        if cfg.exact_identifier_match and id_a and id_b and len(id_a & id_b) > 0:
            strong_match = True
        ph_a, ph_b = normalize_phone(a.phone), normalize_phone(b.phone)
        if cfg.exact_phone_match_boost > 0 and ph_a and ph_b and ph_a == ph_b:
            strong_match = True

        # gate 3: identical normalized names (without honorifics) are a match
        name_eq = False
        na, nb = normalize_name(a.name), normalize_name(b.name)
        if na and nb and na == nb:
            name_eq = True
            strong_match = True

        # weighted blend
        weights = {
            "name": cfg.name_weight,
            "phone": cfg.phone_weight,
            "email": cfg.email_weight,
            "address": cfg.address_weight,
            "organization": cfg.organization_weight,
            "identifier": cfg.identifier_weight,
            "context": cfg.context_weight,
            "graph": cfg.graph_weight,
        }
        wsum = sum(weights.values())
        score = (
            weights["name"] * feat.name_similarity
            + weights["phone"] * feat.phone_similarity
            + weights["email"] * feat.email_similarity
            + weights["address"] * feat.address_similarity
            + weights["organization"] * feat.organization_similarity
            + weights["identifier"] * feat.shared_identifiers
            + weights["context"] * (
                (feat.shared_events + feat.shared_locations + feat.shared_contacts) / 3.0
            )
            + weights["graph"] * feat.graph_neighborhood_similarity
        ) / wsum

        if strong_match:
            score = max(score, cfg.match_threshold + 0.05)
            if name_eq and not (ph_a and ph_b and ph_a == ph_b):
                # identical names with no contradicting identifiers
                score = max(score, 0.85)
        if ph_a and ph_b and ph_a == ph_b:
            score = min(1.0, score + cfg.exact_phone_match_boost)

        # decision
        if score >= cfg.match_threshold:
            decision = MATCH
        elif score >= cfg.possible_threshold:
            decision = POSSIBLE_MATCH
        elif score >= cfg.unknown_threshold:
            decision = UNKNOWN
        else:
            decision = NON_MATCH

        explanation = self._explain(decision, score, feat, strong_match)
        return ResolutionDecision(
            left_id=a.record_id,
            right_id=b.record_id,
            decision=decision,
            score=round(score, 4),
            features=feat,
            weights=weights,
            explanation=explanation,
        )

    def _explain(self, decision: str, score: float, feat: PairwiseFeatures,
                 strong_match: bool) -> str:
        if strong_match:
            base = "Strong-evidence gate (exact identifier/phone) raised the score."
        else:
            base = "No strong-evidence gate fired."
        parts = [
            f"name={feat.name_similarity:.2f}",
            f"phone={feat.phone_similarity:.2f}",
            f"graph={feat.graph_neighborhood_similarity:.2f}",
        ]
        return f"{base} Features: {', '.join(parts)}. Decision={decision} ({score:.2f})."

    # ------------------------------------------------------------------ #
    def compare(self, a: ResolvableRecord, b: ResolvableRecord) -> ResolutionDecision:
        return self.decide(a, b)

    def resolve_all(self, records: Sequence[ResolvableRecord],
                    min_score: float = 0.0) -> List[ResolutionDecision]:
        """Compare every candidate pair and return all decisions.

        Deterministic: candidate pairs are sorted before comparison.
        """
        decisions: List[ResolutionDecision] = []
        for i, j in self.candidates(records):
            a, b = records[i], records[j]
            decision = self.decide(a, b)
            if decision.score >= min_score or decision.decision in (MATCH, POSSIBLE_MATCH):
                decisions.append(decision)
        return sorted(decisions, key=lambda d: -d.score)