"""
case_dna.py
-----------
Case Fingerprinting & Network DNA similarity engine (P2.4).

Creates compact structural representations of each case for:
  - Case fingerprint generation
  - Similarity computation across cases
  - Detailed comparison between two cases
  - Explanation of similarity differences

Features used in fingerprinting:
  entity count, relationship count, community count, average degree,
  centralization, bridge count, motif distribution, financial flow patterns,
  temporal activity patterns, entity-type composition, network density,
  component structure, cycle prevalence, fan-in/fan-out prevalence.

Similarity is structural + contextual, NOT based on personal identifiers.
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "case-dna-1.0.0"


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class CaseFingerprint(BaseModel):
    case_id: str
    entity_count: int = 0
    relationship_count: int = 0
    community_count: int = 0
    avg_degree: float = 0.0
    degree_std: float = 0.0
    centralization: float = 0.0       # max degree / (n-1)
    bridge_count: int = 0
    motif_distribution: Dict[str, int] = Field(default_factory=dict)
    entity_type_composition: Dict[str, float] = Field(default_factory=dict)
    network_density: float = 0.0
    component_count: int = 0
    cycle_count: int = 0
    fan_in_count: int = 0
    fan_out_count: int = 0
    financial_edge_count: int = 0
    communication_edge_count: int = 0
    temporal_burst_index: float = 0.0
    avg_edge_confidence: float = 0.0
    features: Dict[str, float] = Field(default_factory=dict)  # flat vector for comparison
    algorithm_version: str = ALGORITHM_VERSION


class SimilarityResult(BaseModel):
    case_id: str
    similarity: float = 0.0
    structural: float = 0.0
    financial: float = 0.0
    temporal: float = 0.0
    entity_composition: float = 0.0
    motif_similarity: float = 0.0
    why_similar: List[str] = Field(default_factory=list)
    differences: List[str] = Field(default_factory=list)


class CaseComparison(BaseModel):
    case_a: str
    case_b: str
    similarity: float = 0.0
    dimensions: Dict[str, float] = Field(default_factory=dict)
    shared_entities: List[Dict[str, str]] = Field(default_factory=list)
    shared_relationships: List[Dict[str, str]] = Field(default_factory=list)
    a_only: Dict[str, Any] = Field(default_factory=dict)
    b_only: Dict[str, Any] = Field(default_factory=dict)
    why_similar: List[str] = Field(default_factory=list)
    differences: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Fingerprint engine
# --------------------------------------------------------------------------- #

class CaseDNAEngine:
    """Generate case fingerprints and compute similarity."""

    def __init__(self, graph: nx.MultiDiGraph, case_id: str = "CASE-0421") -> None:
        self.graph = graph
        self.case_id = case_id
        self.ug = graph.to_undirected()

    def _community_map(self) -> Dict[str, int]:
        try:
            from networkx.algorithms.community import louvain_communities
            comms = louvain_communities(self.ug, seed=42)
            out = {}
            for i, c in enumerate(comms):
                for n in c:
                    out[n] = i
            return out
        except Exception:
            out = {}
            for i, c in enumerate(nx.connected_components(self.ug)):
                for n in c:
                    out[n] = i
            return out

    def generate_fingerprint(self) -> CaseFingerprint:
        """Generate a structural fingerprint for the current graph."""
        n = self.graph.number_of_nodes()
        m = self.graph.number_of_edges()
        if n == 0:
            return CaseFingerprint(case_id=self.case_id)

        # Basic metrics
        degrees = dict(self.ug.degree())
        deg_vals = list(degrees.values())
        avg_deg = statistics.mean(deg_vals) if deg_vals else 0
        deg_std = statistics.stdev(deg_vals) if len(deg_vals) > 1 else 0
        centralization = max(deg_vals) / max(n - 1, 1) if deg_vals else 0
        density = nx.density(self.ug)

        # Components
        components = list(nx.connected_components(self.ug))
        component_count = len(components)

        # Communities
        comm_map = self._community_map()
        community_count = len(set(comm_map.values())) if comm_map else 0

        # Bridges (betweenness > 0.1)
        betweenness = nx.betweenness_centrality(self.ug, k=min(256, n))
        bridge_count = sum(1 for b in betweenness.values() if b > 0.1)

        # Entity type composition
        type_counts: Counter = Counter()
        for _, d in self.graph.nodes(data=True):
            t = d.get("entity_type") or "UNKNOWN"
            type_counts[t] += 1
        entity_comp = {t: c / max(n, 1) for t, c in type_counts.items()}

        # Edge type counts
        financial = 0
        communication = 0
        for _, _, d in self.graph.edges(data=True):
            rel = d.get("relation", "")
            if rel in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS", "USES_ACCOUNT"):
                financial += 1
            elif rel in ("CALLED", "SMS", "WHATSAPP", "COMMUNICATED_WITH"):
                communication += 1

        # Cycles
        try:
            cycles = list(nx.simple_cycles(self.graph))
            cycle_count = len([c for c in cycles if 3 <= len(c) <= 6])
        except Exception:
            cycle_count = 0

        # Fan-in / fan-out
        fan_in = sum(1 for _, d in self.graph.in_degree() if d >= 3)
        fan_out = sum(1 for _, d in self.graph.out_degree() if d >= 3)

        # Edge confidence
        confs = []
        for _, _, d in self.graph.edges(data=True):
            a = d.get("attributes") or {}
            c = a.get("confidence")
            if c is not None:
                try:
                    confs.append(float(c))
                except (TypeError, ValueError):
                    pass
        avg_conf = statistics.mean(confs) if confs else 0.0

        # Temporal burst index: variance in monthly activity
        monthly: Dict[str, int] = defaultdict(int)
        for _, _, d in self.graph.edges(data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")
            if ts:
                month = str(ts)[:7]
                monthly[month] += 1
        if monthly:
            vals = list(monthly.values())
            burst = statistics.stdev(vals) / max(statistics.mean(vals), 1) if len(vals) > 1 else 0
        else:
            burst = 0

        # Motif distribution (simple structural patterns)
        motif_dist = {
            "HUB": sum(1 for d in deg_vals if d >= avg_deg + 2 * deg_std) if deg_vals else 0,
            "BROKER": bridge_count,
            "FAN_IN": fan_in,
            "FAN_OUT": fan_out,
            "RING": cycle_count,
        }

        # Build flat feature vector for comparison
        features = {
            "entity_count": min(n / 500, 1.0),
            "relationship_count": min(m / 2000, 1.0),
            "community_count": min(community_count / 20, 1.0),
            "avg_degree": min(avg_deg / 20, 1.0),
            "centralization": centralization,
            "bridge_ratio": bridge_count / max(n, 1),
            "density": density,
            "component_ratio": component_count / max(n, 1),
            "cycle_ratio": cycle_count / max(n, 1),
            "fan_in_ratio": fan_in / max(n, 1),
            "fan_out_ratio": fan_out / max(n, 1),
            "financial_ratio": financial / max(m, 1),
            "communication_ratio": communication / max(m, 1),
            "temporal_burst": min(burst, 2.0),
            "avg_confidence": avg_conf,
        }
        # Add entity type ratios
        for t, ratio in entity_comp.items():
            features[f"type_{t}"] = ratio

        return CaseFingerprint(
            case_id=self.case_id,
            entity_count=n,
            relationship_count=m,
            community_count=community_count,
            avg_degree=round(avg_deg, 4),
            degree_std=round(deg_std, 4),
            centralization=round(centralization, 4),
            bridge_count=bridge_count,
            motif_distribution=motif_dist,
            entity_type_composition=entity_comp,
            network_density=round(density, 6),
            component_count=component_count,
            cycle_count=cycle_count,
            fan_in_count=fan_in,
            fan_out_count=fan_out,
            financial_edge_count=financial,
            communication_edge_count=communication,
            temporal_burst_index=round(burst, 4),
            avg_edge_confidence=round(avg_conf, 4),
            features=features,
        )


# --------------------------------------------------------------------------- #
# Similarity engine
# --------------------------------------------------------------------------- #

def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity between two feature vectors."""
    all_keys = set(a.keys()) | set(b.keys())
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in all_keys)
    norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _dimension_similarity(a_finger: CaseFingerprint, b_finger: CaseFinger, dimension: str) -> float:
    """Compute similarity for a specific dimension."""
    a_feat = a_finger.features
    b_feat = b_finger.features

    if dimension == "structural":
        keys = ["entity_count", "relationship_count", "community_count",
                "avg_degree", "centralization", "bridge_ratio", "density",
                "component_ratio", "cycle_ratio", "fan_in_ratio", "fan_out_ratio"]
        a_sub = {k: a_feat.get(k, 0) for k in keys}
        b_sub = {k: b_feat.get(k, 0) for k in keys}
        return _cosine_similarity(a_sub, b_sub)

    elif dimension == "financial":
        a_fin = a_finger.financial_edge_count / max(a_finger.relationship_count, 1)
        b_fin = b_finger.financial_edge_count / max(b_finger.relationship_count, 1)
        return 1.0 - abs(a_fin - b_fin)

    elif dimension == "temporal":
        return max(0, 1.0 - abs(a_finger.temporal_burst_index - b_finger.temporal_burst_index) / 2.0)

    elif dimension == "entity_composition":
        return _cosine_similarity(
            {k: a_feat.get(f"type_{k}", v) for k, v in a_finger.entity_type_composition.items()},
            {k: b_feat.get(f"type_{k}", v) for k, v in b_finger.entity_type_composition.items()},
        )

    elif dimension == "motif":
        a_motifs = {k: v / max(a_finger.entity_count, 1) for k, v in a_finger.motif_distribution.items()}
        b_motifs = {k: v / max(b_finger.entity_count, 1) for k, v in b_finger.motif_distribution.items()}
        return _cosine_similarity(a_motifs, b_motifs)

    return 0.0


def compute_similarity(
    a: CaseFingerprint,
    b: CaseFingerprint,
    weights: Optional[Dict[str, float]] = None,
) -> SimilarityResult:
    """Compute weighted similarity between two case fingerprints."""
    if weights is None:
        weights = {
            "structural": 0.35,
            "financial": 0.20,
            "temporal": 0.15,
            "entity_composition": 0.15,
            "motif": 0.15,
        }

    dims = {}
    for dim in weights:
        dims[dim] = round(_dimension_similarity(a, b, dim), 4)

    total_weight = sum(weights.values())
    overall = sum(dims.get(d, 0) * w for d, w in weights.items()) / max(total_weight, 1)

    # Explanations
    why_similar = []
    differences = []
    if dims.get("structural", 0) > 0.75:
        why_similar.append("Similar broker and community structure")
    if dims.get("financial", 0) > 0.75:
        why_similar.append("Similar financial flow topology")
    if dims.get("temporal", 0) > 0.75:
        why_similar.append("Similar temporal activity patterns")
    if dims.get("entity_composition", 0) > 0.75:
        why_similar.append("Similar entity-type composition")
    if dims.get("motif", 0) > 0.75:
        why_similar.append("Similar motif distribution")

    if dims.get("structural", 0) < 0.5:
        differences.append("Different network structure")
    if dims.get("financial", 0) < 0.5:
        differences.append("Different financial flow patterns")
    if dims.get("temporal", 0) < 0.5:
        differences.append("Different temporal activity patterns")
    if abs(a.entity_count - b.entity_count) > max(a.entity_count, b.entity_count) * 0.3:
        differences.append(f"Different scale: {a.entity_count} vs {b.entity_count} entities")

    return SimilarityResult(
        case_id=b.case_id,
        similarity=round(overall, 4),
        structural=round(dims.get("structural", 0), 4),
        financial=round(dims.get("financial", 0), 4),
        temporal=round(dims.get("temporal", 0), 4),
        entity_composition=round(dims.get("entity_composition", 0), 4),
        motif_similarity=round(dims.get("motif", 0), 4),
        why_similar=why_similar,
        differences=differences,
    )


def compare_cases(a: CaseFingerprint, b: CaseFingerprint) -> CaseComparison:
    """Detailed comparison between two cases."""
    sim = compute_similarity(a, b)

    # Shared vs unique stats
    a_only = {
        "entity_count": a.entity_count,
        "communities": a.community_count,
        "bridges": a.bridge_count,
        "financial_edges": a.financial_edge_count,
        "cycles": a.cycle_count,
        "density": a.network_density,
        "temporal_burst": a.temporal_burst_index,
    }
    b_only = {
        "entity_count": b.entity_count,
        "communities": b.community_count,
        "bridges": b.bridge_count,
        "financial_edges": b.financial_edge_count,
        "cycles": b.cycle_count,
        "density": b.network_density,
        "temporal_burst": b.temporal_burst_index,
    }

    return CaseComparison(
        case_a=a.case_id,
        case_b=b.case_id,
        similarity=sim.similarity,
        dimensions={
            "structural": sim.structural,
            "financial": sim.financial,
            "temporal": sim.temporal,
            "entity_composition": sim.entity_composition,
            "motif": sim.motif_similarity,
        },
        a_only=a_only,
        b_only=b_only,
        why_similar=sim.why_similar,
        differences=sim.differences,
        limitations=[
            "Similarity is computed from structural features, not behavioral similarity.",
            "Similar structure does not imply similar criminal activity.",
            "Weights are adjustable; different investigators may prioritize different dimensions.",
        ],
    )
