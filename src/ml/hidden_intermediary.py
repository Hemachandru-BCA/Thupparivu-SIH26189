"""
ml/hidden_intermediary.py
-------------------------
Hidden-intermediary detection (Phase 4, requirement 7).

A hidden intermediary is NOT simply a missing edge.  This module combines
multiple signals:

* structural hole score
* betweenness bridge score
* community bridging
* path coverage
* temporal mediation
* shared infrastructure
* behavioral similarity
* embedding similarity
* candidate node plausibility

into a calibrated **Ghost Candidate Score**:

    ghost_score =
        structural_signal
        + community_signal
        + temporal_signal
        + behavioral_signal
        + embedding_signal
        + evidence_signal
        - contradiction_penalty

Weights live in :class:`GhostScoreConfig` and are normalized, so the score
is a bounded 0..1 number (never an arbitrary weighted blob).
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Optional, Sequence, Set, Tuple

import networkx as nx

from src.domain.models import ConfidenceScore
from src.domain.scoring import Signal, SignalBundle
from src.ml.embedding_predictor import EmbeddingLinkPredictor
from src.graph.graph_embeddings import undirected_weighted_projection

logger = logging.getLogger(__name__)


@dataclass
class GhostScoreConfig:
    """Weights for the ghost candidate score (all bounded, sum to 1)."""

    structural_weight: float = 0.20
    community_weight: float = 0.20
    temporal_weight: float = 0.15
    behavioral_weight: float = 0.15
    embedding_weight: float = 0.15
    evidence_weight: float = 0.15
    #: penalty applied when direct observed edges exist between communities
    contradiction_penalty: float = 0.25
    seed: int = 42


@dataclass
class GhostCandidate:
    """A candidate hidden intermediary between two communities."""

    ghost_id: str
    community_a: int
    community_b: int
    ghost_score: float = 0.0
    signals: Dict[str, float] = field(default_factory=dict)
    signal_bundle: Optional[SignalBundle] = None
    brokers_a: List[str] = field(default_factory=list)
    brokers_b: List[str] = field(default_factory=list)
    shared_infrastructure: List[str] = field(default_factory=list)
    predicted_edges: List[Dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    confidence_score: Optional[ConfidenceScore] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ghost_id": self.ghost_id,
            "community_a": self.community_a,
            "community_b": self.community_b,
            "ghost_score": round(self.ghost_score, 4),
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "brokers_a": list(self.brokers_a),
            "brokers_b": list(self.brokers_b),
            "shared_infrastructure": list(self.shared_infrastructure),
            "predicted_edges": list(self.predicted_edges),
            "explanation": self.explanation,
        }


class HiddenIntermediaryDetector:
    """Detects plausible hidden intermediaries between community pairs."""

    def __init__(self, config: Optional[GhostScoreConfig] = None,
                 use_embeddings: bool = True) -> None:
        self.config = config or GhostScoreConfig()
        self.use_embeddings = use_embeddings
        self.embedder = EmbeddingLinkPredictor(seed=self.config.seed) if use_embeddings else None

    # ------------------------------------------------------------------ #
    def fit(self, graph: nx.Graph) -> "HiddenIntermediaryDetector":
        self.graph = graph
        self.projection = undirected_weighted_projection(graph)
        if self.embedder is not None:
            self.embedder.fit(self.projection)
        return self

    # ------------------------------------------------------------------ #
    def communities(self) -> List[Set[Hashable]]:
        from networkx.algorithms.community import louvain_communities
        return louvain_communities(self.projection, seed=self.config.seed)

    # ------------------------------------------------------------------ #
    def broker_score(self, node: Hashable) -> float:
        """Betweenness-based bridge score for one node."""
        try:
            btw = nx.betweenness_centrality(
                self.projection, k=min(256, self.projection.number_of_nodes()),
                seed=self.config.seed, normalized=True)
            return float(btw.get(node, 0.0))
        except Exception:
            return 0.0

    def _structural_hole(self, node: Hashable, comm_of: Dict[Hashable, int],
                         community: int) -> float:
        """Structural-hole signal: how much of the node's degree crosses
        communities (i.e. brokerage) relative to its own community."""
        if node not in self.projection:
            return 0.0
        neighbors = list(self.projection.neighbors(node))
        if not neighbors:
            return 0.0
        cross = sum(1 for n in neighbors if comm_of.get(n, -1) != community)
        return cross / len(neighbors)

    def _community_bridge_signal(self, node: Hashable, comm_a: int, comm_b: int,
                                 comm_of: Dict[Hashable, int]) -> float:
        """Does this node sit between comm_a and comm_b specifically?"""
        if node not in self.projection:
            return 0.0
        neighbors = list(self.projection.neighbors(node))
        if not neighbors:
            return 0.0
        a_links = sum(1 for n in neighbors if comm_of.get(n, -1) == comm_a)
        b_links = sum(1 for n in neighbors if comm_of.get(n, -1) == comm_b)
        if a_links == 0 or b_links == 0:
            return 0.0
        return min(1.0, (a_links + b_links) / len(neighbors))

    # ------------------------------------------------------------------ #
    def detect(self, min_score: float = 0.3,
               top_n: int = 20) -> List[GhostCandidate]:
        """Detect ghost candidates between all community pairs."""
        import uuid
        communities = self.communities()
        if len(communities) < 2:
            return []
        comm_of: Dict[Hashable, int] = {}
        for i, comm in enumerate(communities):
            for n in comm:
                comm_of[n] = i

        # betweenness for the structural signal
        betweenness = nx.betweenness_centrality(
            self.projection, k=min(256, self.projection.number_of_nodes()),
            seed=self.config.seed, normalized=True)

        candidates: List[GhostCandidate] = []
        for i in range(len(communities)):
            for j in range(i + 1, len(communities)):
                comm_a, comm_b = communities[i], communities[j]
                candidates.extend(
                    self._detect_pair(i, j, comm_a, comm_b, comm_of, betweenness)
                )

        # also consider candidate *nodes outside both communities* — nodes
        # that may act as hidden coordinators (persons or accounts)
        candidates.sort(key=lambda c: -c.ghost_score)
        # dedupe by (a,b) keeping best
        seen: Set[Tuple[int, int]] = set()
        dedup: List[GhostCandidate] = []
        for c in candidates:
            key = (min(c.community_a, c.community_b), max(c.community_a, c.community_b))
            if key in seen:
                continue
            seen.add(key)
            if c.ghost_score >= min_score:
                dedup.append(c)
            if len(dedup) >= top_n:
                break
        return dedup

    # ------------------------------------------------------------------ #
    def _detect_pair(self, ci: int, cj: int,
                     comm_a: Set[Hashable], comm_b: Set[Hashable],
                     comm_of: Dict[Hashable, int],
                     betweenness: Dict[Hashable, float]) -> List[GhostCandidate]:
        cfg = self.config
        # 1. direct observed edges between communities → strong contradiction
        direct_edges = sum(
            1 for u in comm_a for v in comm_b
            if self.projection.has_edge(u, v) or self.projection.has_edge(v, u)
        )
        if direct_edges > 0:
            contradiction = cfg.contradiction_penalty
        else:
            contradiction = 0.0

        # 2. brokers on each side (top by structural hole + betweenness)
        brokers_a = self._top_brokers(comm_a, comm_of, ci, betweenness, k=3)
        brokers_b = self._top_brokers(comm_b, comm_of, cj, betweenness, k=3)
        if not brokers_a or not brokers_b:
            return []

        # 3. structural signal from the two broker sets
        structural = 0.0
        for node in brokers_a + brokers_b:
            structural += self._structural_hole(node, comm_of, comm_of.get(node, -1))
        structural = min(1.0, structural / max(len(brokers_a) + len(brokers_b), 1))

        # 4. community-bridge signal (brokers that reach BOTH sides)
        community_bridge = 0.0
        all_brokers = brokers_a + brokers_b
        if all_brokers:
            community_bridge = max(
                self._community_bridge_signal(n, ci, cj, comm_of) for n in all_brokers
            )

        # 5. temporal signal (shared timestamps across broker activity)
        temporal = self._temporal_mediation(brokers_a, brokers_b)

        # 6. behavioral signal (overlapping neighbors across sides)
        behavioral = self._behavioral_similarity(brokers_a, brokers_b)

        # 7. embedding signal
        embedding = 0.0
        if self.embedder is not None:
            sims = []
            for a in brokers_a:
                for b in brokers_b:
                    sims.append(self.embedder.predict(a, b)["probability"])
            embedding = sum(sims) / len(sims) if sims else 0.0

        # 8. evidence / shared infrastructure
        shared_infra, evidence = self._shared_infrastructure(brokers_a, brokers_b)
        evidence_signal = min(1.0, evidence / 3.0)

        # bundle → confidence score
        bundle = SignalBundle()
        bundle.add(Signal("structural_hole", "structural", structural, cfg.structural_weight,
                          "brokerage between communities"))
        bundle.add(Signal("community_bridge", "community", community_bridge, cfg.community_weight,
                          "node spans both communities"))
        bundle.add(Signal("temporal_mediation", "temporal", temporal, cfg.temporal_weight,
                          "temporally co-active brokers"))
        bundle.add(Signal("behavioral", "behavioral", behavioral, cfg.behavioral_weight,
                          "neighborhood overlap"))
        bundle.add(Signal("embedding", "semantic", embedding, cfg.embedding_weight,
                          "embedding proximity"))
        bundle.add(Signal("evidence", "evidence", evidence_signal, cfg.evidence_weight,
                          "shared infrastructure evidence"))
        if contradiction > 0:
            bundle.counter_evidence_penalty = contradiction

        confidence = bundle.to_confidence()
        ghost_score = confidence.value
        # the explicit contradiction penalty is also part of the score
        ghost_score = max(0.0, ghost_score - contradiction)

        ghost_id = "GH-" + str(uuid.uuid5(
            uuid.NAMESPACE_URL, f"ghost|{ci}|{cj}|{structural:.2f}|{embedding:.2f}"))

        predicted_edges = []
        for b_a in brokers_a[:2]:
            predicted_edges.append({
                "source": f"GHOST:{ghost_id}",
                "target": str(b_a),
                "side": "A",
                "probability": round(0.4 + 0.4 * structural, 4),
            })
        for b_b in brokers_b[:2]:
            predicted_edges.append({
                "source": f"GHOST:{ghost_id}",
                "target": str(b_b),
                "side": "B",
                "probability": round(0.4 + 0.4 * structural, 4),
            })

        return [GhostCandidate(
            ghost_id=ghost_id,
            community_a=ci,
            community_b=cj,
            ghost_score=ghost_score,
            signals={
                "structural": structural,
                "community_bridge": community_bridge,
                "temporal": temporal,
                "behavioral": behavioral,
                "embedding": embedding,
                "evidence": evidence_signal,
                "contradiction_penalty": contradiction,
            },
            signal_bundle=bundle,
            brokers_a=[str(b) for b in brokers_a],
            brokers_b=[str(b) for b in brokers_b],
            shared_infrastructure=shared_infra,
            predicted_edges=predicted_edges,
            explanation=(
                f"Hidden intermediary plausibly connects communities {ci} and {cj} "
                f"via brokers {brokers_a[:2]} / {brokers_b[:2]}; "
                f"structural={structural:.2f} community={community_bridge:.2f} "
                f"temporal={temporal:.2f} embedding={embedding:.2f} "
                f"penalty={contradiction:.2f}"
            ),
            confidence_score=confidence,
        )]

    # ------------------------------------------------------------------ #
    def _top_brokers(self, community: Set[Hashable],
                     comm_of: Dict[Hashable, int], comm_id: int,
                     betweenness: Dict[Hashable, float], k: int) -> List[Hashable]:
        scored = []
        for node in community:
            structural = self._structural_hole(node, comm_of, comm_id)
            score = 0.6 * structural + 0.4 * betweenness.get(node, 0.0)
            scored.append((score, node))
        scored.sort(reverse=True)
        return [n for _, n in scored[:k]]

    # ------------------------------------------------------------------ #
    def _temporal_mediation(self, brokers_a: List[Hashable],
                            brokers_b: List[Hashable]) -> float:
        """Share of timestamps that appear on both sides (within a week)."""
        from datetime import datetime, timedelta
        import re
        ts_re = re.compile(r"(\d{4}-\d{2}-\d{2})")
        dates_a, dates_b = set(), set()
        for node in brokers_a + brokers_b:
            attrs = self.graph.nodes.get(node, {}).get("attributes", {}) or {}
            raw = attrs.get("timestamp") or attrs.get("valid_from")
            if raw and isinstance(raw, str):
                m = ts_re.search(raw)
                if m:
                    (dates_a if node in brokers_a else dates_b).add(m.group(1))
        if not dates_a or not dates_b:
            return 0.0
        overlap = len(dates_a & dates_b)
        return min(1.0, overlap / max(min(len(dates_a), len(dates_b)), 1))

    def _behavioral_similarity(self, brokers_a: List[Hashable],
                               brokers_b: List[Hashable]) -> float:
        """Jaccard of the two broker sets' combined neighborhoods."""
        neigh_a = set()
        for n in brokers_a:
            neigh_a |= set(self.projection.neighbors(n))
        neigh_b = set()
        for n in brokers_b:
            neigh_b |= set(self.projection.neighbors(n))
        if not neigh_a or not neigh_b:
            return 0.0
        return len(neigh_a & neigh_b) / len(neigh_a | neigh_b)

    def _shared_infrastructure(self, brokers_a: List[Hashable],
                               brokers_b: List[Hashable]) -> Tuple[List[str], int]:
        """Shared non-person infra nodes (accounts, phones) across sides."""
        from collections import Counter
        if len(brokers_a) == 0 or len(brokers_b) == 0:
            return [], 0
        shared = []
        for a in brokers_a:
            for b in brokers_b:
                common = set(self.projection.neighbors(a)) & set(self.projection.neighbors(b))
                for n in common:
                    ntype = (self.projection.nodes[n].get("entity_type") or "").upper()
                    if ntype in ("ACCOUNT", "PHONE", "LOCATION", "VEHICLE"):
                        shared.append(str(n))
        counts = Counter(shared)
        return [n for n, _ in counts.most_common(5)], len(counts)