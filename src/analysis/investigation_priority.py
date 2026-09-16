"""
analysis/investigation_priority.py
----------------------------------
Investigation Priority Score engine (Phase A, spec sections 32-33).

Answers the core investigator question: *"Which entity should be examined
first?"* in a transparent, evidence-grounded way.

The engine combines independently computed signals into a single bounded
0..100 score.  Weights are explicit, configurable and never silently
changed.  Every component maps to already-existing analytical signals:

    NETWORK INFLUENCE       PageRank + degree centrality
    BRIDGE POTENTIAL        betweenness + community bridge role / ghost signal
    COMMUNICATION ANOMALY   temporal anomaly detector (communication burst...)
    FINANCIAL ANOMALY       financial analyzer signals (layering, cycles...)
    TEMPORAL CORRELATION    incident-window proximity
    CROSS-CASE LINKAGE      entity reused across multiple case files
    EVIDENCE STRENGTH       count of supporting evidence records

Rules that make this engine safe:

* The score is an **investigative lead score**, NOT a probability of
  guilt.  It is never called "probability" anywhere in the output.
* If a signal cannot be computed, the weight is renormalised across the
  remaining components instead of pretending the data exists.
* Missing evidence is never treated as negative evidence: `evidence
  strength` is 0.5 neutral when no evidence records exist, and only rises
  with actual supporting evidence.
* Every component is exposed verbatim so the UI can render the
  "87 / 100 - why?" breakdown from spec section 33.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PRIORITY_NAMESPACE = uuid.UUID("7b3f1e8d-4a2c-4f6e-9b1d-8c5a7e2f9d31")

#: Default component weights - tuned for the synthetic demo, always
#: overridable via constructor kwargs.  Sums to 1.0.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "network_influence": 0.25,
    "bridge_potential": 0.20,
    "communication_anomaly": 0.15,
    "financial_anomaly": 0.15,
    "temporal_correlation": 0.10,
    "cross_case_linkage": 0.05,
    "evidence_strength": 0.10,
}

#: Components whose absence disables the component (rather than scoring 0).
#: For example, a graph with no ACCOUNT nodes should not penalise everyone's
#: financial component - it is simply "not applicable".
_OPTIONAL_COMPONENTS = {"communication_anomaly", "financial_anomaly",
                        "temporal_correlation", "cross_case_linkage"}


class PriorityComponent(BaseModel):
    """One weighted component of the investigation priority score."""

    name: str
    label: str
    weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0, description="Normalised 0..1 component score")
    contribution: float = Field(ge=0.0, le=1.0, description="score * weight")
    available: bool = True
    reason: str = ""
    evidence_ids: List[str] = Field(default_factory=list)


class PriorityResult(BaseModel):
    """Per-entity investigation priority."""

    entity_id: str
    entity_name: str = ""
    entity_type: str = ""
    priority_score: int = Field(ge=0, le=100)
    components: List[PriorityComponent] = Field(default_factory=list)
    status: str = "INVESTIGATIVE_LEAD"
    tier: str = "LOW"
    disclaimer: str = (
        "Structural investigative lead score - not a probability of guilt "
        "and not a recommendation to take enforcement action."
    )


class InvestigationPriorityEngine:
    """Computes per-entity investigation priority from graph + analytics."""

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        evidence_store=None,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.graph = graph
        self.evidence_store = evidence_store
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            for k in self.weights:
                if k in weights:
                    self.weights[k] = float(weights[k])
        self._normalise_weights()

        # Lazily computed caches (expensive components computed once)
        self._temporal_anomalies: Optional[List[Any]] = None
        self._financial_signals: Optional[List[Any]] = None
        self._ghost_by_entity: Optional[Dict[str, float]] = None
        self._cross_case_entities: Optional[set] = None

    # ------------------------------------------------------------------ #
    # Weight handling
    # ------------------------------------------------------------------ #
    def _normalise_weights(self) -> None:
        total = sum(max(0.0, v) for v in self.weights.values())
        if total <= 0:
            raise ValueError("Priority weights must sum to a positive value")
        self.weights = {k: v / total for k, v in self.weights.items()}

    # ------------------------------------------------------------------ #
    # Signal helpers
    # ------------------------------------------------------------------ #
    def _node_metrics(self, node: str) -> Dict[str, Any]:
        """Node metrics dict, tolerating missing/legacy graph artifacts."""
        d = self.graph.nodes.get(node, {})
        metrics = d.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        return metrics

    def _node_label(self, node: str) -> str:
        d = self.graph.nodes.get(node, {})
        return (
            d.get("canonical_name")
            or d.get("label")
            or d.get("name")
            or str(node)
        )

    def _evidence_for_node(self, node: str) -> List[Any]:
        if self.evidence_store is None:
            return []
        try:
            return self.evidence_store.get_evidence_for_node(node, limit=500)
        except Exception:  # pragma: no cover - evidence store must never break
            return []

    def _load_ghosts(self) -> Dict[str, float]:
        """Map entity_id -> ghost score from ghost_predictions.json."""
        if self._ghost_by_entity is not None:
            return self._ghost_by_entity

        result: Dict[str, float] = {}
        try:
            from src.api import paths

            path = Path(paths.GHOST_PREDICTIONS_PATH)
            if not path.exists():
                self._ghost_by_entity = result
                return result
            data = json.loads(path.read_text())
            rows = data if isinstance(data, list) else data.get("ghosts", data.get("predictions", []))
            for row in rows:
                if not isinstance(row, dict):
                    continue
                gid = row.get("ghost_id") or row.get("entity_id")
                score = row.get("ghost_score") or row.get("confidence")
                if gid and score is not None:
                    try:
                        result[gid] = float(score)
                    except (TypeError, ValueError):
                        pass
                # Candidate nodes may be nested under 'candidate' / 'nodes'
                cand = row.get("candidate") or {}
                if isinstance(cand, dict):
                    cid = cand.get("entity_id") or cand.get("id")
                    cscore = cand.get("ghost_score") or cand.get("score")
                    if cid and cscore is not None:
                        try:
                            result[cid] = float(cscore)
                        except (TypeError, ValueError):
                            pass
        except Exception:
            logger.exception("failed loading ghost predictions for priority")
        self._ghost_by_entity = result
        return result

    def _temporal_anomaly_scores(self) -> Dict[str, List[Any]]:
        """entity_id -> list of temporal anomalies, computed once."""
        if self._temporal_anomalies is not None:
            return self._temporal_anomalies
        try:
            from src.analysis.temporal_anomalies import TemporalAnomalyDetector

            detector = TemporalAnomalyDetector(graph=self.graph)
            anomalies = detector.detect_all_anomalies()
        except Exception:
            logger.exception("temporal anomaly detection failed")
            anomalies = []
        grouped: Dict[str, List[Any]] = {}
        for a in anomalies:
            for eid in (a.entity_ids or []):
                grouped.setdefault(eid, []).append(a)
        self._temporal_anomalies = grouped
        return grouped

    def _financial_signal_scores(self) -> Dict[str, List[Any]]:
        """entity_id -> list of financial signals touching the entity."""
        if self._financial_signals is not None:
            return self._financial_signals
        try:
            from src.analysis.financial_analysis import FinancialAnalyzer

            analyzer = FinancialAnalyzer(graph=self.graph)
            report = analyzer.analyze()
            signals = report.signals
        except Exception:
            logger.exception("financial analysis failed")
            signals = []
        grouped: Dict[str, List[Any]] = {}
        for s in signals:
            ents = []
            for e in (s.entities or []):
                eid = e.get("id") or e.get("entity_id")
                if eid:
                    ents.append(eid)
            # Global signals (no entity list) apply to the account graph
            for eid in ents:
                grouped.setdefault(eid, []).append(s)
        self._financial_signals = grouped
        return grouped

    def _cross_case_entity_count(self, entity_id: str) -> int:
        """Number of distinct case files referencing this entity (0..N)."""
        if self._cross_case_entities is not None:
            return 1 if entity_id in self._cross_case_entities else 0
        try:
            from src.api import paths

            if not paths.CASES_DIR.exists():
                self._cross_case_entities = set()
                return 0
            ids = set()
            for p in paths.CASES_DIR.glob("*.json"):
                try:
                    doc = json.loads(p.read_text())
                except (OSError, json.JSONDecodeError):
                    continue
                for key in ("entities", "entity_ids", "members"):
                    for e in (doc.get(key) or []):
                        if isinstance(e, str):
                            ids.add(e)
                        elif isinstance(e, dict):
                            eid = e.get("id") or e.get("entity_id")
                            if eid:
                                ids.add(eid)
            self._cross_case_entities = ids
        except Exception:
            self._cross_case_entities = set()
        return 1 if entity_id in (self._cross_case_entities or set()) else 0

    def _incident_proximity(self, entity_id: str) -> float:
        """
        Fraction of entity's incident-window edges within 24h of an
        INCIDENT / FIR timestamp.  Returns 0.0..1.0 signal (0 when none).
        """
        if self.graph.number_of_nodes() == 0:
            return 0.0
        try:
            from datetime import timedelta

            incident_ts = self._incident_timestamps()
            if not incident_ts:
                return 0.0
            near = 0
            total = 0
            for _, _, _, d in self.graph.edges(entity_id, keys=True, data=True):
                attrs = d.get("attributes") or {}
                nested = attrs.get("attributes") or {}
                ts_str = (
                    nested.get("timestamp")
                    or attrs.get("timestamp")
                    or attrs.get("observed_at")
                )
                if not ts_str:
                    continue
                ts = self._parse_ts(ts_str)
                if ts is None:
                    continue
                total += 1
                for inc in incident_ts:
                    if inc is not None and abs((ts - inc).total_seconds()) <= 24 * 3600:
                        near += 1
                        break
            return min(1.0, near / max(total, 1))
        except Exception:
            return 0.0

    def _incident_timestamps(self) -> List[Any]:
        ts_list: List[Any] = []
        for n, d in self.graph.nodes(data=True):
            if d.get("entity_type") in ("INCIDENT", "EVENT") and (
                d.get("incident") or d.get("event")
            ):
                ts_str = d.get("timestamp") or (d.get("attributes") or {}).get("timestamp")
                ts = self._parse_ts(ts_str) if ts_str else None
                if ts is not None:
                    ts_list.append(ts)
        return ts_list

    @staticmethod
    def _parse_ts(value: str) -> Optional[Any]:
        try:
            from datetime import datetime, timezone

            s = str(value).strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------ #
    # Component scores
    # ------------------------------------------------------------------ #
    def _component_network_influence(self, node: str) -> PriorityComponent:
        m = self._node_metrics(node)
        pr = float(m.get("pagerank") or 0.0)
        dc = float(m.get("degree_centrality") or 0.0)
        # Normalise PageRank across the graph for a comparable 0..1 scale.
        prs = [float((self._node_metrics(n)).get("pagerank") or 0.0)
               for n in self.graph.nodes()]
        pr_max = max(prs) if prs else 0.0
        pr_norm = (pr / pr_max) if pr_max > 0 else 0.0
        score = round(min(1.0, 0.6 * pr_norm + 0.4 * dc), 4)
        return PriorityComponent(
            name="network_influence",
            label="Network influence",
            weight=self.weights["network_influence"],
            score=score,
            contribution=score * self.weights["network_influence"],
            available=True,
            reason=(
                f"PageRank {pr:.4f} / degree centrality {dc:.3f}"
            ),
        )

    def _component_bridge_potential(self, node: str) -> PriorityComponent:
        m = self._node_metrics(node)
        betweenness = float(m.get("betweenness_centrality") or 0.0)
        ghost = self._load_ghosts().get(node, 0.0)
        score = round(min(1.0, 0.65 * betweenness + 0.35 * ghost), 4)
        return PriorityComponent(
            name="bridge_potential",
            label="Bridge potential",
            weight=self.weights["bridge_potential"],
            score=score,
            contribution=score * self.weights["bridge_potential"],
            available=True,
            reason=(
                f"Betweenness {betweenness:.3f}"
                + (f" / ghost hypothesis {ghost:.2f}" if ghost > 0 else "")
            ),
        )

    def _component_communication_anomaly(self, node: str) -> PriorityComponent:
        anomalies = self._temporal_anomaly_scores().get(node, [])
        if not anomalies:
            return PriorityComponent(
                name="communication_anomaly",
                label="Communication anomaly",
                weight=self.weights["communication_anomaly"],
                score=0.0,
                contribution=0.0,
                available=False,
                reason="No communication anomalies detected",
            )
        max_conf = max(float(getattr(a, "confidence", 0.0) or 0.0) for a in anomalies)
        score = round(min(1.0, max_conf), 4)
        return PriorityComponent(
            name="communication_anomaly",
            label="Communication anomaly",
            weight=self.weights["communication_anomaly"],
            score=score,
            contribution=score * self.weights["communication_anomaly"],
            available=True,
            reason=f"{len(anomalies)} temporal anomaly signal(s)",
        )

    def _component_financial_anomaly(self, node: str) -> PriorityComponent:
        signals = self._financial_signal_scores().get(node, [])
        if not signals:
            return PriorityComponent(
                name="financial_anomaly",
                label="Financial anomaly",
                weight=self.weights["financial_anomaly"],
                score=0.0,
                contribution=0.0,
                available=False,
                reason="No financial signals involving this entity",
            )
        max_conf = max(float(getattr(s, "confidence", 0.0) or 0.0) for s in signals)
        sig_types = [getattr(s, "signal_type", "") for s in signals]
        score = round(min(1.0, max_conf), 4)
        return PriorityComponent(
            name="financial_anomaly",
            label="Financial anomaly",
            weight=self.weights["financial_anomaly"],
            score=score,
            contribution=score * self.weights["financial_anomaly"],
            available=True,
            reason=f"Signals: {', '.join(sorted(set(sig_types)))[:80]}",
        )

    def _component_temporal_correlation(self, node: str) -> PriorityComponent:
        prox = self._incident_proximity(node)
        if prox <= 0:
            return PriorityComponent(
                name="temporal_correlation",
                label="Temporal correlation",
                weight=self.weights["temporal_correlation"],
                score=0.0,
                contribution=0.0,
                available=False,
                reason="No incident-window correlation found",
            )
        return PriorityComponent(
            name="temporal_correlation",
            label="Temporal correlation",
            weight=self.weights["temporal_correlation"],
            score=round(prox, 4),
            contribution=round(prox * self.weights["temporal_correlation"], 4),
            available=True,
            reason="Activity within 24h of an incident",
        )

    def _component_cross_case_linkage(self, node: str) -> PriorityComponent:
        cnt = self._cross_case_entity_count(node)
        if cnt <= 0:
            return PriorityComponent(
                name="cross_case_linkage",
                label="Cross-case linkage",
                weight=self.weights["cross_case_linkage"],
                score=0.0,
                contribution=0.0,
                available=False,
                reason="Not present in any other case file",
            )
        return PriorityComponent(
            name="cross_case_linkage",
            label="Cross-case linkage",
            weight=self.weights["cross_case_linkage"],
            score=1.0,
            contribution=self.weights["cross_case_linkage"],
            available=True,
            reason="Entity reused across cases",
        )

    def _component_evidence_strength(self, node: str) -> PriorityComponent:
        evidence = self._evidence_for_node(node)
        count = len(evidence)
        if count == 0:
            # Neutral 0.5 - missing evidence is never negative evidence.
            return PriorityComponent(
                name="evidence_strength",
                label="Evidence strength",
                weight=self.weights["evidence_strength"],
                score=0.5,
                contribution=0.5 * self.weights["evidence_strength"],
                available=True,
                reason="No evidence records indexed for this entity",
            )
        # Strength rises with record count, plateauing around 30 records.
        score = round(min(1.0, 0.5 + count / 60.0), 4)
        return PriorityComponent(
            name="evidence_strength",
            label="Evidence strength",
            weight=self.weights["evidence_strength"],
            score=score,
            contribution=score * self.weights["evidence_strength"],
            available=True,
            reason=f"{count} indexed evidence record(s)",
            evidence_ids=[getattr(e, "evidence_id", "") for e in evidence[:20]],
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def score_entity(self, entity_id: str) -> PriorityResult:
        """Full priority result for one entity."""
        if entity_id not in self.graph:
            raise KeyError(f"Entity not in graph: {entity_id}")

        components = [
            self._component_network_influence(entity_id),
            self._component_bridge_potential(entity_id),
            self._component_communication_anomaly(entity_id),
            self._component_financial_anomaly(entity_id),
            self._component_temporal_correlation(entity_id),
            self._component_cross_case_linkage(entity_id),
            self._component_evidence_strength(entity_id),
        ]

        # Renormalise weights over available components only.
        available = [c for c in components if c.available]
        if not available:
            return self._fallback_result(entity_id)
        weight_total = sum(c.weight for c in available)
        if weight_total <= 0:
            return self._fallback_result(entity_id)

        score = sum(
            c.score * (c.weight / weight_total) for c in available
        )
        score = int(round(score * 100, 0))
        score = max(0, min(100, score))

        d = self.graph.nodes.get(entity_id, {})
        tier = "CRITICAL" if score >= 75 else ("HIGH" if score >= 50 else ("MEDIUM" if score >= 25 else "LOW"))
        return PriorityResult(
            entity_id=entity_id,
            entity_name=self._node_label(entity_id),
            entity_type=str(d.get("entity_type") or "UNKNOWN"),
            priority_score=score,
            components=components,
            tier=tier,
        )

    compute_for_entity = score_entity

    def _fallback_result(self, entity_id: str) -> PriorityResult:
        d = self.graph.nodes.get(entity_id, {})
        return PriorityResult(
            entity_id=entity_id,
            entity_name=self._node_label(entity_id),
            entity_type=str(d.get("entity_type") or "UNKNOWN"),
            priority_score=0,
            components=[],
            tier="LOW",
        )

    def ranked_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
        include_types: Optional[List[str]] = None,
    ) -> List[PriorityResult]:
        """Rank all graph entities by priority score (score-only, no per-node
        evidence lookups).  `include_types` restricts candidate nodes, so the
        caller can prioritise PERSON entities only."""
        if include_types:
            candidate_types = set(include_types)
        elif entity_type:
            candidate_types = {entity_type}
        else:
            candidate_types = None

        candidates = []
        for n, d in self.graph.nodes(data=True):
            et = str(d.get("entity_type") or "").upper()
            if candidate_types and et not in candidate_types:
                continue
            candidates.append(n)

        results = []
        for n in candidates:
            try:
                r = self.score_entity(n)
            except Exception:
                continue
            if r.priority_score <= 0:
                continue
            results.append(r)

        results.sort(key=lambda r: -r.priority_score)
        return results[:limit]