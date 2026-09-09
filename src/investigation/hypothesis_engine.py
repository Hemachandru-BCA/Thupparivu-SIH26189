"""
investigation/hypothesis_engine.py
----------------------------------
Structured investigative hypothesis generation (Phase 5, requirement 1).

Every hypothesis carries:

    hypothesis_id | type | subject | confidence | supporting_evidence |
    counter_evidence | model_signals | temporal_scope | graph_scope |
    explanation | status

Hypothesis types:

* POTENTIAL_HIDDEN_INTERMEDIARY
* POTENTIAL_MISSING_LINK
* COMMUNITY_BRIDGE
* UNUSUAL_COORDINATOR
* ENTITY_COLLISION
* ANOMALOUS_ACTIVITY
* EMERGING_CLUSTER
* NETWORK_FRAGMENTATION_POINT

Lifecycle:

    OPEN → SUPPORTED | WEAKENED → CONTRADICTED | RESOLVED | REQUIRES_REVIEW

The engine NEVER makes guilt/arrest/enforcement claims — every hypothesis
is a structural observation with evidence and counter-evidence.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import networkx as nx

from src.domain.models import Hypothesis
from src.domain.scoring import Signal, SignalBundle
from src.graph.temporal_graph import TemporalMultilayerGraph

logger = logging.getLogger(__name__)

HYPOTHESIS_NAMESPACE = uuid.UUID("8b31d5a9-3c9e-4f62-aa47-01d4ef51f2c3")

HYPOTHESIS_TYPES = [
    "POTENTIAL_HIDDEN_INTERMEDIARY",
    "POTENTIAL_MISSING_LINK",
    "COMMUNITY_BRIDGE",
    "UNUSUAL_COORDINATOR",
    "ENTITY_COLLISION",
    "ANOMALOUS_ACTIVITY",
    "EMERGING_CLUSTER",
    "NETWORK_FRAGMENTATION_POINT",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_hypothesis_id(hyp_type: str, subject: str, salt: str = "") -> str:
    return "H-" + str(uuid.uuid5(HYPOTHESIS_NAMESPACE, f"{hyp_type}|{subject}|{salt}"))


class HypothesisEngine:
    """Generates structured hypotheses from graph + ML signals."""

    def __init__(self, graph: nx.MultiDiGraph,
                 temporal_graph: Optional[TemporalMultilayerGraph] = None) -> None:
        self.graph = graph
        self.temporal = temporal_graph or TemporalMultilayerGraph(graph)

    # ------------------------------------------------------------------ #
    def generate_all(self, ghost_candidates: Sequence[Any] = (),
                     predicted_links: Sequence[Any] = ()) -> List[Hypothesis]:
        """Run all hypothesis generators and return the full set."""
        hypotheses: List[Hypothesis] = []
        hypotheses.extend(self.from_ghosts(ghost_candidates))
        hypotheses.extend(self.from_predicted_links(predicted_links))
        hypotheses.extend(self.community_bridges())
        hypotheses.extend(self.unusual_coordinators())
        hypotheses.extend(self.network_fragmentation_points())
        hypotheses.extend(self.entity_collisions())
        return sorted(hypotheses, key=lambda h: -h.confidence)

    # ------------------------------------------------------------------ #
    def from_ghosts(self, ghost_candidates: Sequence[Any]) -> List[Hypothesis]:
        out: List[Hypothesis] = []
        for ghost in ghost_candidates:
            gid = ghost.ghost_id if hasattr(ghost, "ghost_id") else str(ghost.get("ghost_id", ""))
            score = ghost.ghost_score if hasattr(ghost, "ghost_score") else float(
                ghost.get("ghost_score", ghost.get("confidence", 0.0)))
            bundle = SignalBundle()
            for name, value in _signals_of(ghost).items():
                family = _signal_family(name)
                bundle.add(Signal(name, family, float(value), 1.0,
                                  f"ghost signal {name}"))
            confidence = bundle.to_confidence()
            out.append(Hypothesis(
                id=_make_hypothesis_id("POTENTIAL_HIDDEN_INTERMEDIARY", gid),
                hypothesis_type="POTENTIAL_HIDDEN_INTERMEDIARY",
                subject=gid,
                confidence=round(max(0.0, min(1.0, score)), 4),
                confidence_score=confidence,
                supporting_evidence_ids=list(ghost_evidence(ghost))[:20],
                counter_evidence_ids=list(ghost_counter_evidence(ghost))[:10],
                model_signals=dict(_signals_of(ghost)),
                explanation=ghost.explanation if hasattr(ghost, "explanation") else str(
                    ghost.get("explanation", "")),
                status="OPEN",
            ))
        return out

    # ------------------------------------------------------------------ #
    def from_predicted_links(self, predicted_links: Sequence[Any]) -> List[Hypothesis]:
        out: List[Hypothesis] = []
        for link in predicted_links:
            src = link.candidate_source if hasattr(link, "candidate_source") else str(
                link.get("candidate", ["", ""])[0])
            tgt = link.candidate_target if hasattr(link, "candidate_target") else str(
                link.get("candidate", ["", ""])[1])
            prob = link.probability if hasattr(link, "probability") else float(
                link.get("probability", 0.0))
            subject = f"{src}→{tgt}"
            out.append(Hypothesis(
                id=_make_hypothesis_id("POTENTIAL_MISSING_LINK", subject),
                hypothesis_type="POTENTIAL_MISSING_LINK",
                subject=subject,
                confidence=round(max(0.0, min(1.0, prob)), 4),
                supporting_evidence_ids=list(link.supporting_evidence)[:20]
                if hasattr(link, "supporting_evidence") else [],
                counter_evidence_ids=list(link.counter_evidence)[:10]
                if hasattr(link, "counter_evidence") else [],
                model_signals={"probability": prob,
                               "status": _status_str(getattr(link, "status", ""))},
                explanation=link.explanation if hasattr(link, "explanation") else "",
                status="OPEN",
            ))
        return out

    # ------------------------------------------------------------------ #
    def community_bridges(self) -> List[Hypothesis]:
        """Nodes whose removal would split the graph (bridge/articulation)."""
        out: List[Hypothesis] = []
        undirected = self.graph.to_undirected()
        try:
            articulations = list(nx.articulation_points(undirected))
        except Exception:
            return out
        # bridge-edge centrality ranking
        betweenness = nx.betweenness_centrality(
            undirected, k=min(256, undirected.number_of_nodes()), seed=42, normalized=True)
        for node in articulations[:50]:
            label = self.graph.nodes[node].get("canonical_name", str(node))
            btw = betweenness.get(node, 0.0)
            bundle = SignalBundle()
            bundle.add(Signal("articulation", "structural", 1.0, 0.6,
                              "node is an articulation point"))
            bundle.add(Signal("betweenness", "structural", min(btw * 10, 1.0), 0.4,
                              "normalized betweenness centrality"))
            out.append(Hypothesis(
                id=_make_hypothesis_id("COMMUNITY_BRIDGE", str(node)),
                hypothesis_type="COMMUNITY_BRIDGE",
                subject=str(node),
                confidence=bundle.to_confidence().value,
                confidence_score=bundle.to_confidence(),
                model_signals={"is_articulation": True,
                               "betweenness": round(btw, 4),
                               "entity_type": self.graph.nodes[node].get("entity_type", "")},
                explanation=(
                    f"Node '{label}' (guid {node}) is an articulation point: "
                    f"removing it would disconnect the network. "
                    f"This is a structural observation, not an accusation."
                ),
                graph_scope={"node": str(node), "neighbors": [
                    str(n) for n in undirected.neighbors(node)][:10]},
                status="OPEN",
            ))
        return out

    # ------------------------------------------------------------------ #
    def unusual_coordinators(self) -> List[Hypothesis]:
        """Nodes with unexpectedly high betweenness vs degree (gatekeepers)."""
        out: List[Hypothesis] = []
        undirected = self.graph.to_undirected()
        if undirected.number_of_nodes() < 10:
            return out
        betweenness = nx.betweenness_centrality(
            undirected, k=min(256, undirected.number_of_nodes()), seed=42, normalized=True)
        degree = dict(undirected.degree())
        scores: List[tuple] = []
        for node, btw in betweenness.items():
            deg = degree.get(node, 0)
            if deg < 2:
                continue
            ratio = btw / max(deg, 1)  # gatekeeper-ness
            if ratio > 0.05 and btw > 0.01:
                scores.append((ratio, node))
        scores.sort(reverse=True)
        for ratio, node in scores[:30]:
            bundle = SignalBundle()
            bundle.add(Signal("betweenness_ratio", "structural", min(ratio * 20, 1.0), 0.7,
                              "betweenness-to-degree ratio"))
            bundle.add(Signal("observed_degree", "behavioral",
                              min(degree.get(node, 0) / 20.0, 1.0), 0.3,
                              "degree"))
            confidence = bundle.to_confidence().value
            out.append(Hypothesis(
                id=_make_hypothesis_id("UNUSUAL_COORDINATOR", str(node)),
                hypothesis_type="UNUSUAL_COORDINATOR",
                subject=str(node),
                confidence=confidence,
                confidence_score=bundle.to_confidence(),
                model_signals={"betweenness": round(betweenness[node], 4),
                               "degree": degree.get(node, 0),
                               "ratio": round(ratio, 4)},
                explanation=(
                    f"Node '{self.graph.nodes[node].get('canonical_name', node)}' "
                    f"has {degree.get(node, 0)} neighbors but betweenness "
                    f"{betweenness[node]:.3f} — it sits on many shortest paths "
                    f"despite modest observed connectivity. Structural observation only."
                ),
                status="OPEN",
            ))
        return out

    # ------------------------------------------------------------------ #
    def network_fragmentation_points(self) -> List[Hypothesis]:
        """Nodes whose removal maximizes network fragmentation (top-k)."""
        out: List[Hypothesis] = []
        undirected = self.graph.to_undirected()
        if undirected.number_of_nodes() > 500:
            return out  # expensive; skip on huge graphs
        components_before = nx.number_connected_components(undirected)
        candidates = list(undirected.nodes())[:200]
        scored: List[tuple] = []
        for node in candidates:
            g2 = undirected.copy()
            g2.remove_node(node)
            n_components = nx.number_connected_components(g2)
            delta = n_components - components_before
            if delta > 0:
                scored.append((delta, node))
        scored.sort(reverse=True)
        for delta, node in scored[:10]:
            out.append(Hypothesis(
                id=_make_hypothesis_id("NETWORK_FRAGMENTATION_POINT", str(node)),
                hypothesis_type="NETWORK_FRAGMENTATION_POINT",
                subject=str(node),
                confidence=round(min(1.0, delta * 0.4), 4),
                model_signals={"fragmentation_delta": delta},
                explanation=(
                    f"Removing this node increases the number of connected "
                    f"components by {delta}. It is a structural fragility point."
                ),
                status="OPEN",
            ))
        return out

    # ------------------------------------------------------------------ #
    def entity_collisions(self) -> List[Hypothesis]:
        """Nodes with suspiciously many aliases that could be distinct entities."""
        out: List[Hypothesis] = []
        for node, data in self.graph.nodes(data=True):
            aliases = data.get("aliases", []) or []
            mention_count = int(data.get("mention_count", 0) or 0)
            if len(aliases) >= 3 and mention_count >= 4:
                bundle = SignalBundle()
                bundle.add(Signal("alias_count", "entity_resolution",
                                  min(len(aliases) / 6.0, 1.0), 0.6,
                                  "many aliases on one node"))
                bundle.add(Signal("mention_count", "entity_resolution",
                                  min(mention_count / 20.0, 1.0), 0.4,
                                  "high mention count"))
                out.append(Hypothesis(
                    id=_make_hypothesis_id("ENTITY_COLLISION", str(node)),
                    hypothesis_type="ENTITY_COLLISION",
                    subject=str(node),
                    confidence=bundle.to_confidence().value,
                    confidence_score=bundle.to_confidence(),
                    model_signals={"alias_count": len(aliases),
                                   "mention_count": mention_count},
                    explanation=(
                        f"Entity '{data.get('canonical_name', node)}' carries "
                        f"{len(aliases)} aliases across {mention_count} mentions. "
                        f"Possible over-merge — may actually be multiple people."
                    ),
                    status="REQUIRES_REVIEW",
                ))
        return out


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _signals_of(ghost: Any) -> Dict[str, float]:
    if hasattr(ghost, "signals"):
        return ghost.signals
    return dict(ghost.get("confidence_breakdown", {}) or {})


def _signal_family(name: str) -> str:
    if "temporal" in name:
        return "temporal"
    if "embedding" in name or "semantic" in name:
        return "semantic"
    if "behavior" in name:
        return "behavioral"
    if "evidence" in name:
        return "evidence"
    return "structural"


def _status_str(status: Any) -> str:
    """Coerce a status (enum or string) into a plain string."""
    if hasattr(status, "value"):
        return str(status.value)
    return str(status or "")


def ghost_evidence(ghost: Any) -> List[str]:
    if hasattr(ghost, "shared_infrastructure"):
        return [f"infra:{x}" for x in ghost.shared_infrastructure]
    anchors = ghost.get("evidence", []) or []
    return [str(a.get("anchor_guid", a.get("anchor_name", ""))) for a in anchors]


def ghost_counter_evidence(ghost: Any) -> List[str]:
    sigs = _signals_of(ghost)
    penalty = float(sigs.get("contradiction_penalty", 0.0))
    if penalty > 0:
        return [f"COUNTER:contradiction_penalty:{penalty}"]
    return []