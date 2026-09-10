"""
motif_detector.py
-----------------
Network motif / structural-pattern detection for P1.

Identifies recurring structural patterns that may help investigators
prioritise analytical attention.  This is **structural pattern detection**,
NOT automated criminal classification.

Supported motifs:
  - HUB: entity with unusually high connectivity
  - BROKER / BRIDGE: entity connecting weakly-connected communities
  - CHAIN: A → B → C → …
  - FAN_IN: multiple sources → single target
  - FAN_OUT: single source → multiple targets
  - RING / CYCLE: closed loop
  - MULTI_COMMUNITY_CONNECTOR: entity in 3+ communities
  - TEMPORAL_BURST: motif active unusually quickly

Every motif carries confidence, evidence_count, and limitations.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class MotifMatch(BaseModel):
    """One detected structural pattern."""
    motif_id: str = ""
    motif_type: str          # HUB | BROKER | CHAIN | FAN_IN | FAN_OUT | RING | MULTI_COMMUNITY_CONNECTOR | TEMPORAL_BURST
    description: str = ""
    entities: List[Dict[str, str]] = Field(default_factory=list)    # [{id, label, role}]
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    time_range: Optional[Dict[str, str]] = None    # {start, end}
    frequency: int = 1
    evidence_count: int = 0
    confidence: float = 0.0
    communities_involved: List[int] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class MotifReport(BaseModel):
    """Aggregated motif report for a case / graph."""
    motifs: List[MotifMatch] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)   # motif_type → count
    total_entities_covered: int = 0
    limitations: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Detector
# --------------------------------------------------------------------------- #

class MotifDetector:
    """Detect structural motifs in a NetworkX graph."""

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self.ug = graph.to_undirected()
        self._communities: Optional[Dict[str, int]] = None

    # ------------------------------------------------------------------ #
    # Community assignment (cached)
    # ------------------------------------------------------------------ #
    def _community_map(self) -> Dict[str, int]:
        if self._communities is not None:
            return self._communities
        try:
            from networkx.algorithms.community import louvain_communities
            comms = louvain_communities(self.ug, seed=42)
            out: Dict[str, int] = {}
            for i, c in enumerate(comms):
                for n in c:
                    out[n] = i
            self._communities = out
        except Exception:
            out = {}
            for i, c in enumerate(nx.connected_components(self.ug)):
                for n in c:
                    out[n] = i
            self._communities = out
        return self._communities

    def _node_label(self, node: str) -> str:
        d = self.graph.nodes.get(node, {})
        return d.get("canonical_name") or d.get("label") or str(node)

    def _node_type(self, node: str) -> str:
        return self.graph.nodes.get(node, {}).get("entity_type") or "UNKNOWN"

    # ------------------------------------------------------------------ #
    # Hub detection
    # ------------------------------------------------------------------ #
    def detect_hubs(self, top_n: int = 20) -> List[MotifMatch]:
        """Entities with unusually high degree."""
        if self.ug.number_of_nodes() == 0:
            return []
        degrees = dict(self.ug.degree())
        if not degrees:
            return []
        import statistics
        vals = list(degrees.values())
        mean_d = statistics.mean(vals) if vals else 0
        std_d = statistics.stdev(vals) if len(vals) > 1 else 1.0
        threshold = mean_d + 2 * std_d
        hubs = sorted(
            [(n, d) for n, d in degrees.items() if d >= threshold and d >= 5],
            key=lambda x: -x[1],
        )[:top_n]
        motifs = []
        comm_map = self._community_map()
        for rank, (node, deg) in enumerate(hubs, 1):
            neighbors = list(self.ug.neighbors(node))
            communities = list({comm_map.get(n, -1) for n in [node] + neighbors})
            motifs.append(MotifMatch(
                motif_type="HUB",
                description=f"Entity '{self._node_label(node)}' with degree {deg} (threshold: {threshold:.0f})",
                entities=[{"id": node, "label": self._node_label(node), "role": "hub"}],
                relationships=[{"source": node, "target": n, "type": "connected"} for n in neighbors[:20]],
                frequency=deg,
                evidence_count=0,  # caller can enrich
                confidence=min(1.0, deg / max(threshold * 2, 1)),
                communities_involved=communities,
                limitations=["Degree threshold is statistical; context-dependent interpretation required."],
            ))
        return motifs

    # ------------------------------------------------------------------ #
    # Broker / Bridge detection
    # ------------------------------------------------------------------ #
    def detect_brokers(self, top_n: int = 20) -> List[MotifMatch]:
        """Entities with high betweenness centrality connecting communities."""
        if self.ug.number_of_nodes() < 3:
            return []
        betweenness = nx.betweenness_centrality(self.ug, k=min(256, self.ug.number_of_nodes()))
        comm_map = self._community_map()
        brokers = sorted(
            [(n, b) for n, b in betweenness.items() if b > 0],
            key=lambda x: -x[1],
        )[:top_n]
        motifs = []
        for node, btwn in brokers:
            community = comm_map.get(node, -1)
            neighbor_communities = {comm_map.get(nb, -1) for nb in self.ug.neighbors(node)}
            neighbor_communities.discard(community)
            if not neighbor_communities:
                continue
            motifs.append(MotifMatch(
                motif_type="BROKER",
                description=(
                    f"Entity '{self._node_label(node)}' bridges {len(neighbor_communities)} "
                    f"other community(ies) with betweenness {btwn:.4f}"
                ),
                entities=[{"id": node, "label": self._node_label(node), "role": "broker"}],
                relationships=[],
                frequency=1,
                evidence_count=0,
                confidence=min(1.0, btwn * 10),
                communities_involved=[community] + sorted(neighbor_communities),
                limitations=["Betweenness is normalised; high values in sparse graphs may not indicate brokerage."],
            ))
        return motifs

    # ------------------------------------------------------------------ #
    # Chain detection
    # ------------------------------------------------------------------ #
    def detect_chains(self, min_length: int = 3, max_length: int = 6, top_n: int = 30) -> List[MotifMatch]:
        """Linear chains A → B → C → … in the directed graph."""
        motifs: List[MotifMatch] = []
        visited_chains: Set[Tuple[str, ...]] = set()

        def _dfs(start: str, path: List[str], depth: int):
            if len(path) >= min_length:
                key = tuple(path)
                if key not in visited_chains:
                    visited_chains.add(key)
                    entities = [{"id": p, "label": self._node_label(p), "role": "chain_node"} for p in path]
                    rels = [{"source": path[i], "target": path[i + 1], "type": "chain_edge"}
                            for i in range(len(path) - 1)]
                    motifs.append(MotifMatch(
                        motif_type="CHAIN",
                        description=f"Chain of length {len(path)}: {' → '.join(self._node_label(n) for n in path)}",
                        entities=entities,
                        relationships=rels,
                        confidence=min(1.0, len(path) / max_length),
                        limitations=["Chain detection is path-based; does not imply direct causal relationship."],
                    ))
            if depth >= max_length:
                return
            for _, tgt, _ in self.graph.out_edges(path[-1], keys=True):
                if tgt not in path:
                    _dfs(start, path + [tgt], depth + 1)

        # Limit search to high-degree nodes to avoid combinatorial explosion
        candidates = sorted(self.ug.degree(), key=lambda x: -x[1])[:200]
        for node, _ in candidates:
            if len(motifs) >= top_n:
                break
            _dfs(node, [node], 1)
        return motifs[:top_n]

    # ------------------------------------------------------------------ #
    # Fan-in / Fan-out
    # ------------------------------------------------------------------ #
    def detect_fan_in(self, min_sources: int = 3, top_n: int = 20) -> List[MotifMatch]:
        """Multiple sources → single target."""
        in_degree = dict(self.graph.in_degree())
        targets = sorted(
            [(n, d) for n, d in in_degree.items() if d >= min_sources],
            key=lambda x: -x[1],
        )[:top_n]
        motifs = []
        for target, deg in targets:
            sources = list(self.graph.predecessors(target))
            entities = [{"id": target, "label": self._node_label(target), "role": "fan_in_target"}]
            entities.extend([{"id": s, "label": self._node_label(s), "role": "fan_in_source"} for s in sources[:20]])
            rels = [{"source": s, "target": target, "type": "fan_in_edge"} for s in sources[:20]]
            motifs.append(MotifMatch(
                motif_type="FAN_IN",
                description=f"{len(sources)} entities converge on '{self._node_label(target)}'",
                entities=entities,
                relationships=rels,
                confidence=min(1.0, deg / (min_sources * 2)),
                limitations=["Fan-in is structural; does not indicate coordinated activity."],
            ))
        return motifs

    def detect_fan_out(self, min_targets: int = 3, top_n: int = 20) -> List[MotifMatch]:
        """Single source → multiple targets."""
        out_degree = dict(self.graph.out_degree())
        sources = sorted(
            [(n, d) for n, d in out_degree.items() if d >= min_targets],
            key=lambda x: -x[1],
        )[:top_n]
        motifs = []
        for source, deg in sources:
            targets = list(self.graph.successors(source))
            entities = [{"id": source, "label": self._node_label(source), "role": "fan_out_source"}]
            entities.extend([{"id": t, "label": self._node_label(t), "role": "fan_out_target"} for t in targets[:20]])
            rels = [{"source": source, "target": t, "type": "fan_out_edge"} for t in targets[:20]]
            motifs.append(MotifMatch(
                motif_type="FAN_OUT",
                description=f"'{self._node_label(source)}' connects to {len(targets)} entities",
                entities=entities,
                relationships=rels,
                confidence=min(1.0, deg / (min_targets * 2)),
                limitations=["Fan-out is structural; does not indicate distribution or coordination."],
            ))
        return motifs

    # ------------------------------------------------------------------ #
    # Ring / Cycle detection
    # ------------------------------------------------------------------ #
    def detect_rings(self, max_cycle_length: int = 6, top_n: int = 20) -> List[MotifMatch]:
        """Simple directed cycles."""
        try:
            cycles = list(nx.simple_cycles(self.graph))
        except Exception:
            cycles = []
        cycles = [c for c in cycles if 3 <= len(c) <= max_cycle_length]
        cycles.sort(key=lambda c: len(c))
        motifs = []
        for cycle in cycles[:top_n]:
            entities = [{"id": n, "label": self._node_label(n), "role": "cycle_node"} for n in cycle]
            rels = [{"source": cycle[i], "target": cycle[(i + 1) % len(cycle)], "type": "cycle_edge"}
                    for i in range(len(cycle))]
            motifs.append(MotifMatch(
                motif_type="RING",
                description=f"Cycle of length {len(cycle)}: {' → '.join(self._node_label(n) for n in cycle)} → {self._node_label(cycle[0])}",
                entities=entities,
                relationships=rels,
                confidence=min(1.0, len(cycle) / max_cycle_length),
                limitations=["Cycle detection is topological; does not imply financial or communication loop."],
            ))
        return motifs

    # ------------------------------------------------------------------ #
    # Multi-community connector
    # ------------------------------------------------------------------ #
    def detect_multi_community_connectors(self, min_communities: int = 3, top_n: int = 20) -> List[MotifMatch]:
        """Entities connecting 3+ communities."""
        comm_map = self._community_map()
        node_communities: Dict[str, Set[int]] = defaultdict(set)
        for n in self.ug.nodes():
            my_comm = comm_map.get(n, -1)
            node_communities[n].add(my_comm)
            for nb in self.ug.neighbors(n):
                node_communities[n].add(comm_map.get(nb, -1))
        connectors = sorted(
            [(n, comms) for n, comms in node_communities.items() if len(comms) >= min_communities],
            key=lambda x: -len(x[1]),
        )[:top_n]
        motifs = []
        for node, comms in connectors:
            motifs.append(MotifMatch(
                motif_type="MULTI_COMMUNITY_CONNECTOR",
                description=(
                    f"Entity '{self._node_label(node)}' connects {len(comms)} communities: "
                    f"{sorted(comms)}"
                ),
                entities=[{"id": node, "label": self._node_label(node), "role": "connector"}],
                confidence=min(1.0, len(comms) / (min_communities * 2)),
                communities_involved=sorted(comms),
                limitations=["Community boundaries depend on resolution parameter; interpretation requires context."],
            ))
        return motifs

    # ------------------------------------------------------------------ #
    # Aggregate
    # ------------------------------------------------------------------ #
    def detect_all(self, top_n: int = 20) -> MotifReport:
        """Run all motif detectors and produce a unified report."""
        all_motifs: List[MotifMatch] = []
        all_motifs.extend(self.detect_hubs(top_n))
        all_motifs.extend(self.detect_brokers(top_n))
        all_motifs.extend(self.detect_chains(top_n=top_n))
        all_motifs.extend(self.detect_fan_in(top_n=top_n))
        all_motifs.extend(self.detect_fan_out(top_n=top_n))
        all_motifs.extend(self.detect_rings(top_n=top_n))
        all_motifs.extend(self.detect_multi_community_connectors(top_n=top_n))

        summary: Dict[str, int] = defaultdict(int)
        entity_ids: Set[str] = set()
        for m in all_motifs:
            summary[m.motif_type] += 1
            for e in m.entities:
                entity_ids.add(e.get("id", ""))

        # Assign motif IDs
        for i, m in enumerate(all_motifs):
            m.motif_id = f"MOTIF-{i:04d}"

        return MotifReport(
            motifs=all_motifs,
            summary=dict(summary),
            total_entities_covered=len(entity_ids),
            limitations=[
                "Motif detection is structural pattern recognition, not behavioural inference.",
                "Confidence reflects pattern strength, not guilt or criminal intent.",
                "Community boundaries depend on the Louvain resolution parameter.",
            ],
        )
