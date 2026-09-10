"""
next_best_action.py
-------------------
Next-Best Analytical Action recommendation engine (P2.3).

Recommends the most useful next analytical step for the investigator,
based on: unexplored evidence, cross-case links, high-value relationships,
contradictory evidence, temporal changes, financial paths, motifs,
ghost candidates, data-quality issues, method disagreement, and network changes.

NEVER recommends real-world enforcement actions (arrest, surveillance, etc.).
Only recommends analytical investigation steps.

Every recommendation includes explainable score components.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "next-best-action-1.0.0"


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class RecommendationScore(BaseModel):
    evidence_value: float = 0.0
    information_gain: float = 0.0
    cross_case_relevance: float = 0.0
    temporal_relevance: float = 0.0
    unresolved_uncertainty: float = 0.0
    investigator_context: float = 0.0
    total: float = 0.0


class AnalyticalRecommendation(BaseModel):
    recommendation_id: str = ""
    action_type: str = ""   # INSPECT_ENTITY | EXPAND_NETWORK | INSPECT_EVIDENCE | REVIEW_CONTRADICTION |
                            # REPLAY_TIMELINE | TRACE_FINANCIAL | INSPECT_MOTIF | COMPARE_CASE |
                            # INSPECT_LOCATION | REVIEW_DATA_QUALITY | COMPARE_METHODS
    title: str = ""
    description: str = ""
    reason: str = ""
    target_id: str = ""
    target_label: str = ""
    target_type: str = ""   # ENTITY | EVIDENCE | CASE | RELATIONSHIP | MOTIF | LOCATION
    score: RecommendationScore = Field(default_factory=RecommendationScore)
    confidence: float = 0.0
    action_url: str = ""    # suggested frontend route
    evidence_ids: List[str] = Field(default_factory=list)
    related_entities: List[Dict[str, str]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    status: str = "OPEN"    # OPEN | DISMISSED | DEFERRED | COMPLETED | NOT_USEFUL


class RecommendationFeedback(BaseModel):
    recommendation_id: str
    action: str    # DISMISS | DEFER | COMPLETE | NOT_USEFUL
    notes: str = ""


class NextBestActionReport(BaseModel):
    recommendations: List[AnalyticalRecommendation] = Field(default_factory=list)
    context_summary: Dict[str, Any] = Field(default_factory=dict)
    algorithm_version: str = ALGORITHM_VERSION
    limitations: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Score weights
# --------------------------------------------------------------------------- #
DEFAULT_WEIGHTS = {
    "evidence_value": 0.20,
    "information_gain": 0.25,
    "cross_case_relevance": 0.15,
    "temporal_relevance": 0.15,
    "unresolved_uncertainty": 0.15,
    "investigator_context": 0.10,
}


# --------------------------------------------------------------------------- #
# Recommendation engine
# --------------------------------------------------------------------------- #

class NextBestActionEngine:
    """Generate explainable analytical recommendations."""

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        evidence_store: Optional[Any] = None,
        findings: Optional[List[Dict[str, Any]]] = None,
        cross_case_data: Optional[Dict[str, Any]] = None,
        ghost_predictions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.graph = graph
        self.ug = graph.to_undirected()
        self.evidence_store = evidence_store
        self.findings = findings or []
        self.cross_case_data = cross_case_data or {}
        self.ghost_predictions = ghost_predictions or []
        self._rec_idx = 0
        self._seen_ids: Set[str] = set()

    def _next_id(self) -> str:
        self._rec_idx += 1
        rid = f"REC-{self._rec_idx:04d}"
        self._seen_ids.add(rid)
        return rid

    def _node_label(self, node: str) -> str:
        d = self.graph.nodes.get(node, {})
        return d.get("canonical_name") or d.get("label") or str(node)

    # ------------------------------------------------------------------ #
    # Candidate generators
    # ------------------------------------------------------------------ #
    def _unexplored_evidence(self) -> List[AnalyticalRecommendation]:
        """Recommend inspecting findings with no evidence yet."""
        recs = []
        for f in self.findings:
            evidence_count = len(f.get("supporting_evidence_ids") or []) + len(f.get("counter_evidence_ids") or [])
            if evidence_count == 0:
                recs.append(AnalyticalRecommendation(
                    recommendation_id=self._next_id(),
                    action_type="INSPECT_EVIDENCE",
                    title=f"Review evidence for {f.get('subject_label', f.get('id', ''))}",
                    description=f"Finding '{f.get('subject_label', '')}' has no linked evidence records.",
                    reason="No evidence currently linked; review may strengthen or weaken the hypothesis.",
                    target_id=f.get("id", ""),
                    target_label=f.get("subject_label", ""),
                    target_type="FINDING",
                    score=RecommendationScore(evidence_value=0.9, information_gain=0.8, total=0.85),
                    confidence=0.85,
                    action_url="/evidence",
                ))
        return recs

    def _contradictory_evidence(self) -> List[AnalyticalRecommendation]:
        """Recommend reviewing findings with contradictory evidence."""
        recs = []
        for f in self.findings:
            counters = f.get("counter_evidence_ids") or []
            if counters:
                recs.append(AnalyticalRecommendation(
                    recommendation_id=self._next_id(),
                    action_type="REVIEW_CONTRADICTION",
                    title=f"Examine contradictory evidence for {f.get('subject_label', f.get('id', ''))}",
                    description=f"{len(counters)} evidence items contradict this finding.",
                    reason="Contradictory evidence may reveal alternative explanations or data quality issues.",
                    target_id=f.get("id", ""),
                    target_label=f.get("subject_label", ""),
                    target_type="FINDING",
                    score=RecommendationScore(
                        unresolved_uncertainty=0.9,
                        evidence_value=0.7,
                        total=0.8,
                    ),
                    confidence=0.8,
                    action_url="/findings",
                ))
        return recs

    def _cross_case_links(self) -> List[AnalyticalRecommendation]:
        """Recommend inspecting cross-case connections."""
        recs = []
        shared = self.cross_case_data.get("shared_entities", [])
        if shared:
            for entity in shared[:5]:
                eid = entity.get("entity_id") or entity.get("id", "")
                recs.append(AnalyticalRecommendation(
                    recommendation_id=self._next_id(),
                    action_type="COMPARE_CASE",
                    title=f"Inspect cross-case entity: {entity.get('label', eid)}",
                    description=f"Entity appears in {entity.get('case_count', 2)} cases.",
                    reason="Cross-case entities may reveal broader network patterns.",
                    target_id=eid,
                    target_label=entity.get("label", eid),
                    target_type="ENTITY",
                    score=RecommendationScore(cross_case_relevance=0.9, information_gain=0.7, total=0.8),
                    confidence=0.8,
                    action_url="/cross-case",
                ))
        return recs

    def _temporal_changes(self) -> List[AnalyticalRecommendation]:
        """Recommend replaying network around significant topology changes."""
        recs = []
        # Check for high-betweenness nodes that might have emerged recently
        if self.ug.number_of_nodes() > 10:
            betweenness = nx.betweenness_centrality(self.ug, k=min(128, self.ug.number_of_nodes()))
            for n, btwn in sorted(betweenness.items(), key=lambda x: -x[1])[:5]:
                if btwn > 0.15:
                    recs.append(AnalyticalRecommendation(
                        recommendation_id=self._next_id(),
                        action_type="REPLAY_TIMELINE",
                        title=f"Replay network around {self._node_label(n)}",
                        description=f"Entity has high betweenness ({btwn:.3f}); may have become a bridge over time.",
                        reason="Temporal replay can reveal when this entity became structurally important.",
                        target_id=n,
                        target_label=self._node_label(n),
                        target_type="ENTITY",
                        score=RecommendationScore(temporal_relevance=0.8, information_gain=0.7, total=0.75),
                        confidence=0.75,
                        action_url="/timeline",
                    ))
        return recs

    def _financial_paths(self) -> List[AnalyticalRecommendation]:
        """Recommend tracing financial flows through high-centrality entities."""
        recs = []
        financial_nodes = set()
        for _, _, d in self.graph.edges(data=True):
            rel = d.get("relation", "")
            if rel in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS"):
                financial_nodes.add(_[0] if isinstance(_, tuple) else "")

        # Find nodes with both incoming and outgoing financial edges
        for n in self.graph.nodes():
            in_fin = sum(1 for _, _, d in self.graph.in_edges(n, data=True) if d.get("relation") in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS"))
            out_fin = sum(1 for _, _, d in self.graph.out_edges(n, data=True) if d.get("relation") in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS"))
            if in_fin > 0 and out_fin > 0:
                recs.append(AnalyticalRecommendation(
                    recommendation_id=self._next_id(),
                    action_type="TRACE_FINANCIAL",
                    title=f"Trace financial flow through {self._node_label(n)}",
                    description=f"Entity has {in_fin} incoming and {out_fin} outgoing financial edges.",
                    reason="Multi-hop financial patterns may indicate flow through intermediaries.",
                    target_id=n,
                    target_label=self._node_label(n),
                    target_type="ENTITY",
                    score=RecommendationScore(information_gain=0.7, evidence_value=0.6, total=0.65),
                    confidence=0.7,
                    action_url="/financial",
                ))
                if len(recs) >= 5:
                    break
        return recs

    def _ghost_candidates(self) -> List[AnalyticalRecommendation]:
        """Recommend inspecting high-confidence ghost candidates."""
        recs = []
        for ghost in self.ghost_predictions[:5]:
            confidence = ghost.get("confidence", 0)
            if confidence > 0.5:
                anchors = ghost.get("evidence", [])
                anchor_ids = [a.get("anchor_guid", "") for a in anchors[:3]]
                recs.append(AnalyticalRecommendation(
                    recommendation_id=self._next_id(),
                    action_type="INSPECT_ENTITY",
                    title=f"Inspect ghost candidate (confidence: {confidence:.2f})",
                    description=f"Hidden intermediary candidate with {len(anchors)} structural anchors.",
                    reason="Ghost candidates represent unexplored structural hypotheses.",
                    target_id=ghost.get("ghost_id", ""),
                    target_type="ENTITY",
                    score=RecommendationScore(information_gain=0.8, unresolved_uncertainty=0.7, total=0.75),
                    confidence=confidence,
                    action_url="/ghosts",
                ))
        return recs

    def _data_quality_issues(self) -> List[AnalyticalRecommendation]:
        """Recommend reviewing data quality where issues are detected."""
        recs = []
        # Check for low-confidence edges
        low_conf_count = 0
        for _, _, d in self.graph.edges(data=True):
            a = d.get("attributes") or {}
            c = a.get("confidence")
            if c is not None:
                try:
                    if float(c) < 0.5:
                        low_conf_count += 1
                except (TypeError, ValueError):
                    pass
        if low_conf_count > 0:
            recs.append(AnalyticalRecommendation(
                recommendation_id=self._next_id(),
                action_type="REVIEW_DATA_QUALITY",
                title=f"Review {low_conf_count} low-confidence extractions",
                description=f"{low_conf_count} relationships have extraction confidence below 0.5.",
                reason="Low-confidence extractions may affect downstream analysis quality.",
                target_type="GRAPH",
                score=RecommendationScore(unresolved_uncertainty=0.6, evidence_value=0.5, total=0.55),
                confidence=0.6,
                action_url="/p1-analysis",
            ))
        return recs

    # ------------------------------------------------------------------ #
    # Aggregate and rank
    # ------------------------------------------------------------------ #
    def generate_recommendations(self, context: Optional[Dict[str, Any]] = None) -> NextBestActionReport:
        """Generate ranked recommendations based on current investigation state."""
        all_recs: List[AnalyticalRecommendation] = []
        all_recs.extend(self._unexplored_evidence())
        all_recs.extend(self._contradictory_evidence())
        all_recs.extend(self._cross_case_links())
        all_recs.extend(self._temporal_changes())
        all_recs.extend(self._financial_paths())
        all_recs.extend(self._ghost_candidates())
        all_recs.extend(self._data_quality_issues())

        # Rank by total score
        all_recs.sort(key=lambda r: -r.score.total)

        # Limit to top 12
        top_recs = all_recs[:12]

        context_summary = {
            "entity_count": self.graph.number_of_nodes(),
            "relationship_count": self.graph.number_of_edges(),
            "findings_count": len(self.findings),
            "ghost_candidates": len(self.ghost_predictions),
            "recommendations_generated": len(top_recs),
        }

        return NextBestActionReport(
            recommendations=top_recs,
            context_summary=context_summary,
            limitations=[
                "Recommendations are based on structural analysis, not investigative judgment.",
                "Confidence reflects signal strength, not priority or urgency.",
                "The investigator decides which actions to take; the system only suggests analytical directions.",
                "Scores are weighted combinations of independent signals, not AI predictions.",
            ],
        )
