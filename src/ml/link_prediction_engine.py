"""
ml/link_prediction_engine.py
----------------------------
Unified LinkPredictionEngine (Phase 4, requirement 5).

Combines:

* Level 1 — classical baselines (Common Neighbors, Jaccard, Adamic-Adar,
  Resource Allocation, Preferential Attachment, Katz, Personalized PageRank)
* Level 2 — graph embeddings (Node2Vec / spectral / GraphSAGE-style)
* Level 3 — supervised link prediction (logistic / RF / GBM, or numpy
  fallback)
* Level 4 — optional GNN backend (registered via ``register_gnn`` so
  PyTorch Geometric is never a hard dependency)

Every prediction returns:

    candidate | probability | model | features | supporting_evidence |
    counter_evidence | explanation | status | confidence_score

The engine distinguishes link types:

* OBSERVED_LINK          — edge exists in the graph
* INFERRED_LINK          — model concluded it (hidden)
* PREDICTED_FUTURE_LINK  — model predicts it will happen
* HYPOTHETICAL_LINK      — candidate not yet observed, low confidence

These are NEVER conflated.  Model disagreement is surfaced explicitly and
lowers overall confidence (MODEL_DISAGREEMENT).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Hashable, List, Optional, Sequence, Tuple

import networkx as nx

from src.domain.models import (
    ConfidenceScore,
    Prediction,
    RelationshipStatus,
)
from src.domain.scoring import Signal, SignalBundle
from src.ml.embedding_predictor import EmbeddingLinkPredictor
from src.ml.link_baselines import BASELINE_NAMES, baseline_scores
from src.ml.supervised_link_predictor import SupervisedLinkPredictor
from src.graph.temporal_features import FEATURE_NAMES, TemporalFeatureEngine

logger = logging.getLogger(__name__)


class LinkType(str, Enum):
    OBSERVED = "OBSERVED_LINK"
    INFERRED = "INFERRED_LINK"
    PREDICTED_FUTURE = "PREDICTED_FUTURE_LINK"
    HYPOTHETICAL = "HYPOTHETICAL_LINK"


MODEL_DISAGREEMENT = "MODEL_DISAGREEMENT"


@dataclass
class EnsembleWeight:
    model: str
    weight: float
    calibrated: bool = False


@dataclass
class LinkPredictionResult:
    """One candidate link evaluation."""

    candidate_source: str
    candidate_target: str
    probability: float = 0.0
    model: str = "thupparivu_ensemble"
    features: Dict[str, Any] = field(default_factory=dict)
    supporting_evidence: List[str] = field(default_factory=list)
    counter_evidence: List[str] = field(default_factory=list)
    confidence_score: ConfidenceScore = field(default_factory=ConfidenceScore)
    explanation: str = ""
    status: LinkType = LinkType.HYPOTHETICAL
    model_scored: Dict[str, float] = field(default_factory=dict)
    model_disagreement: float = 0.0
    timestamp: str = field(default_factory=lambda: __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat())
    model_version: str = "thupparivu-1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": [self.candidate_source, self.candidate_target],
            "probability": round(self.probability, 4),
            "model": self.model,
            "model_version": self.model_version,
            "status": self.status.value,
            "features": dict(self.features),
            "supporting_evidence": list(self.supporting_evidence),
            "counter_evidence": list(self.counter_evidence),
            "confidence_score": self.confidence_score.to_dict(),
            "model_scores": dict(self.model_scored),
            "model_disagreement": round(self.model_disagreement, 4),
            "explanation": self.explanation,
        }


class LinkPredictionEngine:
    """Multi-model link prediction with ensemble + disagreement handling."""

    def __init__(self, use_embeddings: bool = True,
                 use_supervised: bool = True,
                 use_temporal: bool = True,
                 seed: int = 42,
                 ensemble_threshold: float = 0.5,
                 disagreement_threshold: float = 0.2,
                 rank_pool_size: int = 300) -> None:
        self.use_embeddings = use_embeddings
        self.use_supervised = use_supervised
        self.use_temporal = use_temporal
        self.seed = seed
        self.ensemble_threshold = ensemble_threshold
        self.disagreement_threshold = disagreement_threshold
        self.rank_pool_size = rank_pool_size

        self.baseline = None                    # fitted lazily
        self.embedding = None
        self.supervised = None
        self.temporal_engine = None
        self._gnn_backend = None
        self._gnn_name = None

        #: candidate pairs pre-computed from the observed graph
        self.candidates: List[Tuple[str, str]] = []

    # ------------------------------------------------------------------ #
    # GNN backend registration (optional — never a hard dependency)
    # ------------------------------------------------------------------ #
    def register_gnn(self, backend: Callable[[str, str], float],
                     name: str = "gnn") -> None:
        """Register an optional GNN scoring function ``(u, v) -> prob``."""
        self._gnn_backend = backend
        self._gnn_name = name

    # ------------------------------------------------------------------ #
    def fit(self, graph: nx.Graph,
            supervised_training: Optional[Tuple[Sequence[Sequence[float]],
                                                Sequence[int]]] = None,
            as_of: Optional[str] = None) -> "LinkPredictionEngine":
        """Fit all enabled models on the observed graph.

        ``supervised_training`` is an (X, y) pair already constructed with
        proper train/time separation — the engine never splits edges itself.
        """
        self.graph = graph
        projection = None

        # baseline
        from src.ml.link_baselines import BaselineLinkPredictor
        self.baseline = BaselineLinkPredictor(metric="adamic_adar",
                                              ensemble=BASELINE_NAMES)
        self.baseline.fit(graph)

        # embeddings
        if self.use_embeddings:
            self.embedding = EmbeddingLinkPredictor(seed=self.seed)
            self.embedding.fit(graph)

        # supervised
        if self.use_supervised and supervised_training is not None:
            X, y = supervised_training
            self.supervised = SupervisedLinkPredictor(
                model_kind="gradient_boosting" if _has_sklearn() else "numpy_logistic",
                seed=self.seed,
            )
            self.supervised.fit(X, y)
        elif self.use_supervised:
            logger.info("no supervised training set supplied; skipping supervised model")

        # temporal engine
        if self.use_temporal and as_of:
            self.temporal_engine = TemporalFeatureEngine.from_graph(graph, as_of)

        # candidate pool
        self._build_candidates()
        return self

    def _build_candidates(self) -> None:
        """Non-observed pairs with shared neighbors, ranked by heuristics."""
        projection = self.baseline.graph if self.baseline else None
        if projection is None:
            self.candidates = []
            return
        nodes = list(projection.nodes())
        observed = set()
        for u, v in projection.edges():
            observed.add(tuple(sorted((u, v))))
        scored: List[Tuple[float, str, str]] = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                u, v = nodes[i], nodes[j]
                if (u, v) in observed or (v, u) in observed:
                    continue
                common = set(projection.neighbors(u)) & set(projection.neighbors(v))
                if not common:
                    continue
                ra = sum(1.0 / max(projection.degree(n), 1e-9) for n in common)
                scored.append((ra, str(u), str(v)))
        scored.sort(reverse=True)
        self.candidates = [(u, v) for _, u, v in scored[:self.rank_pool_size]]

    # ------------------------------------------------------------------ #
    def predict_links(self, graph: Optional[nx.Graph] = None,
                      candidates: Optional[Sequence[Tuple[str, str]]] = None,
                      as_of: Optional[str] = None) -> List[LinkPredictionResult]:
        """Predict links for candidate pairs (or the built-in pool)."""
        if graph is not None and self.baseline is None:
            self.fit(graph, as_of=as_of)
        pool = list(candidates) if candidates is not None else self.candidates
        results = []
        for u, v in pool:
            results.append(self.predict_link(u, v))
        results.sort(key=lambda r: -r.probability)
        return results

    # ------------------------------------------------------------------ #
    def predict_link(self, source: str, target: str,
                     as_of: Optional[str] = None) -> LinkPredictionResult:
        """Score a single candidate pair with all models + ensemble."""
        observed = self.graph.has_edge(source, target) or self.graph.has_edge(target, source)

        model_scores: Dict[str, float] = {}
        bundle = SignalBundle()

        # Level 1: baselines
        if self.baseline is not None:
            proj = self.baseline.graph
            raw = baseline_scores(proj, source, target)
            # relative ranking: sigmoid over the raw score for a probability
            for name in BASELINE_NAMES:
                score = raw.get(name, 0.0)
                model_scores[f"baseline:{name}"] = round(1.0 / (1.0 + math.exp(-min(score, 20.0))), 4)
            cn = raw.get("common_neighbors", 0.0)
            jac = raw.get("jaccard", 0.0)
            aa = raw.get("adamic_adar", 0.0)
            bundle.add(Signal("common_neighbors", "structural", min(cn / 5.0, 1.0), 0.4,
                              "number of shared neighbours"))
            bundle.add(Signal("jaccard", "structural", jac, 0.3, "neighborhood overlap"))
            bundle.add(Signal("adamic_adar", "structural", min(aa, 1.0), 0.5,
                              "AA score for shared neighbours"))
            # normalize the strong positive baseline by a sigmoid → 0..1 probability
            baseline_prob = 1.0 / (1.0 + math.exp(-aa * 2.0))
            model_scores["baseline_ensemble"] = round(baseline_prob, 4)

        # Level 2: embeddings
        if self.embedding is not None:
            emb = self.embedding.predict(source, target)
            model_scores["embedding"] = emb["probability"]
            model_scores["embedding_similarity"] = emb["embedding_similarity"]
            bundle.add(Signal("embedding_similarity", "semantic",
                              emb["embedding_similarity"], 0.5,
                              "cosine similarity of node embeddings"))

        # Level 3: supervised model
        if self.supervised is not None and self.temporal_engine is not None:
            try:
                vec = self.temporal_engine.feature_vector(source, target)
                prob = self.supervised.predict_proba([vec])[0]
                model_scores["supervised"] = round(prob, 4)
                bundle.add(Signal("supervised_probability", "behavioral", prob, 0.4,
                                  "supervised model output"))
                if self.supervised.feature_importance():
                    self._last_importance = self.supervised.feature_importance()
            except Exception as exc:  # pragma: no cover
                logger.warning("supervised prediction failed: %s", exc)

        # Level 4: GNN backend
        if self._gnn_backend is not None:
            try:
                gnn_prob = float(self._gnn_backend(source, target))
                model_scores["gnn"] = round(max(0.0, min(1.0, gnn_prob)), 4)
                bundle.add(Signal("gnn_score", "semantic", gnn_prob, 0.4,
                                  "GNN backend output"))
            except Exception as exc:  # pragma: no cover
                logger.warning("GNN backend failed: %s", exc)

        # evidence signals
        evidence_ids = self._shared_evidence(source, target)
        if evidence_ids:
            bundle.add(Signal("shared_evidence", "evidence", min(len(evidence_ids) / 3.0, 1.0),
                              0.6, "shared evidence across both entities",
                              evidence_ids=list(evidence_ids)[:10]))

        # ensemble + disagreement
        numeric = [v for k, v in model_scores.items()
                   if isinstance(v, (int, float)) and k != "baseline_ensemble"]
        if numeric:
            ensemble_prob = sum(numeric) / len(numeric)
        else:
            ensemble_prob = 0.5
        disagreement = self._disagreement(model_scores)

        # counter-evidence penalty
        counter_ids = self._counter_evidence(source, target)
        penalty = min(0.5, 0.2 + disagreement) if counter_ids else disagreement
        bundle.counter_evidence_penalty = round(penalty, 4)

        # status
        if observed:
            status = LinkType.OBSERVED
        elif ensemble_prob >= self.ensemble_threshold:
            status = LinkType.INFERRED
        else:
            status = LinkType.PREDICTED_FUTURE if ensemble_prob >= 0.35 else LinkType.HYPOTHETICAL

        confidence = bundle.to_confidence()
        # disagreement lowers the reported probability slightly
        prob = max(0.0, min(1.0, ensemble_prob - disagreement * 0.5))

        explanation = (
            f"{len(model_scores)} models scored this pair; ensemble={ensemble_prob:.2f}, "
            f"disagreement={disagreement:.2f}; {bundle.explain()}."
        )
        if disagreement >= self.disagreement_threshold:
            explanation += f" Status={MODEL_DISAGREEMENT}."

        return LinkPredictionResult(
            candidate_source=source,
            candidate_target=target,
            probability=prob,
            features={k: v for k, v in model_scores.items()},
            supporting_evidence=sorted(evidence_ids)[:20],
            counter_evidence=sorted(counter_ids)[:20],
            confidence_score=confidence,
            explanation=explanation,
            status=status,
            model_scored=model_scores,
            model_disagreement=disagreement,
        )

    # ------------------------------------------------------------------ #
    def _disagreement(self, model_scores: Dict[str, float]) -> float:
        """Model disagreement = spread of the per-model probabilities.

        Uses the mean absolute deviation from the ensemble mean, scaled to
        a 0..1 value (bounded at 0.5).
        """
        numeric = [v for v in model_scores.values() if isinstance(v, (int, float))]
        if len(numeric) < 2:
            return 0.0
        mean = sum(numeric) / len(numeric)
        mad = sum(abs(v - mean) for v in numeric) / len(numeric)
        return round(min(0.5, mad), 4)

    # ------------------------------------------------------------------ #
    def _shared_evidence(self, source: str, target: str) -> set:
        ev = set()
        for n in (source, target):
            if n in self.graph:
                attrs = self.graph.nodes[n].get("attributes", {}) or {}
                ev |= set(attrs.get("evidence_ids", []) or [])
        return ev

    # ------------------------------------------------------------------ #
    def _counter_evidence(self, source: str, target: str) -> List[str]:
        """Evidence that weakens the link: source/target in different
        communities with no observed interaction history."""
        counter: List[str] = []
        if self.temporal_engine is not None:
            snap = self.temporal_engine.snapshot
            if source in snap and target in snap:
                try:
                    from networkx.algorithms.community import louvain_communities
                    comms = louvain_communities(snap, seed=42)
                    comm_of = {}
                    for i, c in enumerate(comms):
                        for n in c:
                            comm_of[n] = i
                    if source in comm_of and target in comm_of and comm_of[source] != comm_of[target]:
                        if not snap.has_edge(source, target) and not snap.has_edge(target, source):
                            counter.append(f"COUNTER:different_communities:{comm_of[source]}:{comm_of[target]}")
                except Exception:
                    pass
        return counter


def _has_sklearn() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False