"""
method_agreement.py
-------------------
Multi-method analytical agreement analysis (P1.5).

Compares rankings from different analytical methods to show investigators
whether a signal is robust across methods or depends on a single approach.

Methods compared (where available):
  - Degree centrality
  - Betweenness centrality
  - PageRank
  - Community importance (intra-community degree)
  - Ghost inference score
  - Temporal activity level
  - Financial activity level

Agreement categories:
  - STRONG: multiple independent methods agree
  - MODERATE: several methods agree but some disagree
  - WEAK: only one or two methods support the signal
  - DISAGREEMENT: methods produce substantially different rankings
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MethodRanking(BaseModel):
    method: str
    rank: int
    score: float
    percentile: float = 0.0


class EntityMethodAgreement(BaseModel):
    entity_id: str
    entity_label: str = ""
    rankings: List[MethodRanking] = Field(default_factory=list)
    agreement_score: float = 0.0     # 0.0 – 1.0
    agreement_level: str = "UNKNOWN"  # STRONG | MODERATE | WEAK | DISAGREEMENT
    interpretation: str = ""
    limitations: List[str] = Field(default_factory=list)


class MethodDisagreement(BaseModel):
    entity_id: str
    entity_label: str = ""
    high_method: str = ""
    high_rank: int = 0
    low_method: str = ""
    low_rank: int = 0
    explanation: str = ""
    possible_explanation: str = ""


class MethodAgreementReport(BaseModel):
    entities: List[EntityMethodAgreement] = Field(default_factory=list)
    disagreements: List[MethodDisagreement] = Field(default_factory=list)
    methods_compared: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class MethodAgreementAnalyzer:
    """Compare analytical rankings across multiple methods."""

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        ghost_predictions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.graph = graph
        self.ug = graph.to_undirected()
        self.ghost_predictions = ghost_predictions or []
        self._rankings: Dict[str, Dict[str, Tuple[int, float]]] = {}

    def _node_label(self, node: str) -> str:
        d = self.graph.nodes.get(node, {})
        return d.get("canonical_name") or d.get("label") or str(node)

    def _compute_all_rankings(self) -> Dict[str, Dict[str, Tuple[int, float]]]:
        """Compute rankings for all available methods."""
        if self._rankings:
            return self._rankings

        nodes = list(self.graph.nodes())
        if not nodes:
            return {}

        rankings: Dict[str, Dict[str, Tuple[int, float]]] = {}

        # Degree centrality
        degree = {n: self.ug.degree(n) for n in nodes}
        rankings["Degree"] = self._to_ranking(degree)

        # Betweenness centrality
        if self.ug.number_of_nodes() > 2:
            betweenness = nx.betweenness_centrality(self.ug, k=min(256, len(nodes)))
            rankings["Betweenness"] = self._to_ranking(betweenness)

        # PageRank
        try:
            pagerank = nx.pagerank(self.graph, alpha=0.85, max_iter=100)
            rankings["PageRank"] = self._to_ranking(pagerank)
        except Exception:
            pass

        # Community importance: degree within own community
        try:
            from networkx.algorithms.community import louvain_communities
            comms = louvain_communities(self.ug, seed=42)
            node_comm = {}
            for i, c in enumerate(comms):
                for n in c:
                    node_comm[n] = i
            community_degree = {}
            for n in nodes:
                comm = node_comm.get(n, -1)
                internal = sum(1 for nb in self.ug.neighbors(n) if node_comm.get(nb) == comm)
                community_degree[n] = internal
            rankings["Community"] = self._to_ranking(community_degree)
        except Exception:
            pass

        # Ghost inference
        if self.ghost_predictions:
            ghost_scores = {}
            for gp in self.ghost_predictions:
                for anchor in gp.get("evidence", []):
                    guid = anchor.get("anchor_guid", "")
                    if guid and guid in self.graph:
                        ghost_scores[guid] = max(ghost_scores.get(guid, 0), gp.get("confidence", 0))
            if ghost_scores:
                # Fill in zeros for nodes not in ghost scores
                for n in nodes:
                    if n not in ghost_scores:
                        ghost_scores[n] = 0.0
                rankings["Ghost"] = self._to_ranking(ghost_scores)

        self._rankings = rankings
        return rankings

    def _to_ranking(self, scores: Dict[str, float]) -> Dict[str, Tuple[int, float]]:
        """Convert scores to (rank, percentile) pairs. Rank 1 = highest score."""
        sorted_nodes = sorted(scores.items(), key=lambda x: -x[1])
        total = len(sorted_nodes)
        result = {}
        for rank_idx, (node, score) in enumerate(sorted_nodes):
            rank = rank_idx + 1
            percentile = 1.0 - (rank / max(total, 1))
            result[node] = (rank, round(percentile, 4))
        return result

    def analyze_entity(self, entity_id: str) -> Optional[EntityMethodAgreement]:
        """Multi-method agreement analysis for one entity."""
        if entity_id not in self.graph:
            return None

        rankings = self._compute_all_rankings()
        if not rankings:
            return None

        methods: List[MethodRanking] = []
        total_nodes = self.graph.number_of_nodes()

        for method_name, method_rankings in rankings.items():
            if entity_id in method_rankings:
                rank, percentile = method_rankings[entity_id]
                methods.append(MethodRanking(
                    method=method_name,
                    rank=rank,
                    score=round(1.0 - percentile, 4),  # inverted for display
                    percentile=percentile,
                ))

        if not methods:
            return None

        # Agreement: how consistent are the percentiles?
        percentiles = [m.percentile for m in methods]
        if len(percentiles) < 2:
            agreement_score = 0.5
        else:
            import statistics
            mean_p = statistics.mean(percentiles)
            std_p = statistics.stdev(percentiles) if len(percentiles) > 1 else 0.0
            # High agreement = all percentiles are similarly high or all similarly low
            # Low agreement = some very high, some very low
            agreement_score = max(0.0, 1.0 - std_p * 3)

        # Agreement level
        if agreement_score >= 0.8:
            level = "STRONG"
            interpretation = "Multiple independent methods produce consistent rankings."
        elif agreement_score >= 0.5:
            level = "MODERATE"
            interpretation = "Several methods agree but some produce different rankings."
        elif agreement_score >= 0.25:
            level = "WEAK"
            interpretation = "Only one or two methods support this ranking."
        else:
            level = "DISAGREEMENT"
            interpretation = "Methods produce substantially different rankings for this entity."

        # Build interpretation detail
        high_methods = [m for m in methods if m.percentile >= 0.8]
        low_methods = [m for m in methods if m.percentile < 0.3]
        if high_methods and low_methods:
            interpretation += (
                f" High: {', '.join(m.method for m in high_methods)}."
                f" Low: {', '.join(m.method for m in low_methods)}."
            )

        return EntityMethodAgreement(
            entity_id=entity_id,
            entity_label=self._node_label(entity_id),
            rankings=methods,
            agreement_score=round(agreement_score, 4),
            agreement_level=level,
            interpretation=interpretation,
            limitations=[
                "Agreement is computed from normalised centrality rankings, not raw scores.",
                "Different methods measure different aspects of network position.",
                "Low agreement does not mean the entity is unimportant — it means methods disagree on *how*.",
            ],
        )

    def find_disagreements(self, top_n: int = 10) -> List[MethodDisagreement]:
        """Find entities with the largest method disagreements."""
        rankings = self._compute_all_rankings()
        method_names = list(rankings.keys())
        if len(method_names) < 2:
            return []

        disagreements = []
        for node in self.graph.nodes():
            ranks = {}
            for mn in method_names:
                if node in rankings[mn]:
                    ranks[mn] = rankings[mn][node][0]
            if len(ranks) < 2:
                continue
            max_rank_method = max(ranks, key=ranks.get)
            min_rank_method = min(ranks, key=ranks.get)
            spread = ranks[max_rank_method] - ranks[min_rank_method]
            if spread > 0:
                disagreements.append(MethodDisagreement(
                    entity_id=node,
                    entity_label=self._node_label(node),
                    high_method=max_rank_method,
                    high_rank=ranks[max_rank_method],
                    low_method=min_rank_method,
                    low_rank=ranks[min_rank_method],
                    explanation=(
                        f"{max_rank_method} ranks this entity #{ranks[max_rank_method]}, "
                        f"but {min_rank_method} ranks it #{ranks[min_rank_method]}."
                    ),
                ))

        disagreements.sort(key=lambda d: -(d.high_rank - d.low_rank))
        return disagreements[:top_n]

    def analyze(self, entity_ids: Optional[List[str]] = None, top_n: int = 20) -> MethodAgreementReport:
        """Full method agreement report."""
        self._compute_all_rankings()

        entities = []
        if entity_ids:
            for eid in entity_ids[:top_n]:
                ea = self.analyze_entity(eid)
                if ea:
                    entities.append(ea)
        else:
            # Auto-select top entities by betweenness
            betweenness = nx.betweenness_centrality(self.ug, k=min(128, self.ug.number_of_nodes())) if self.ug.number_of_nodes() > 2 else {}
            top_entities = sorted(betweenness.items(), key=lambda x: -x[1])[:top_n]
            for eid, _ in top_entities:
                ea = self.analyze_entity(eid)
                if ea:
                    entities.append(ea)

        return MethodAgreementReport(
            entities=entities,
            disagreements=self.find_disagreements(top_n),
            methods_compared=list(self._rankings.keys()),
            limitations=[
                "Rankings are based on the current graph snapshot; temporal changes are not reflected.",
                "Community importance uses Louvain resolution 1.0.",
                "Ghost scores are only available if ghost detection has been run.",
            ],
        )
