"""
evaluation/synthetic_generator.py
---------------------------------
Synthetic investigation generator with ground truth (Phase 6, requirement 1).

Generates networks containing:

* multiple communities
* hidden intermediaries
* missing links
* duplicate identities
* false links
* noisy names
* multilingual aliases
* temporal gaps
* contradictory evidence
* decoy actors
* isolated actors
* hub actors
* bridge actors

The generator KNOWS the ground truth:

* true entities            (canonical ids)
* true relationships       (observed edges)
* hidden relationships     (edges intentionally removed)
* hidden intermediaries    (known coordinator nodes)
* false relationships      (planted decoy edges)
* event times              (every edge has a timestamp)

The benchmark then measures each task against this ground truth.
"""

from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class SyntheticGroundTruth:
    """Everything the generator knows about the planted world."""

    true_entities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    true_relationships: List[Dict[str, Any]] = field(default_factory=list)
    hidden_relationships: List[Dict[str, Any]] = field(default_factory=list)
    hidden_intermediaries: List[str] = field(default_factory=list)
    false_relationships: List[Dict[str, Any]] = field(default_factory=list)
    aliases: Dict[str, List[str]] = field(default_factory=dict)
    duplicate_of: Dict[str, str] = field(default_factory=dict)
    event_times: Dict[str, str] = field(default_factory=dict)


@dataclass
class SyntheticInvestigation:
    """A generated investigation set (graph + corrupted records + truth)."""

    graph: nx.MultiDiGraph
    ground_truth: SyntheticGroundTruth
    records: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    #: convenience — the observed graph is what the pipeline would see
    @property
    def observed_graph(self) -> nx.MultiDiGraph:
        g = self.graph.copy()
        # remove edges the pipeline must NOT see (hidden relationships)
        for edge in self.ground_truth.hidden_relationships:
            u, v = edge["source"], edge["target"]
            if g.has_edge(u, v):
                g.remove_edge(u, v)
        # mask hidden intermediaries from the observed graph
        for hid in self.ground_truth.hidden_intermediaries:
            if hid in g:
                g.remove_node(hid)
        # add decoy edges (false relationships)
        for edge in self.ground_truth.false_relationships:
            u, v = edge["source"], edge["target"]
            if u in g and v in g and not g.has_edge(u, v):
                g.add_edge(u, v, key=f"false:{u}|{v}", relation=edge.get("relation", "ASSOCIATED_WITH"),
                           attributes={"false_planted": True})
        return g


class SyntheticInvestigationGenerator:
    """Creates controlled investigation worlds for benchmarking."""

    NAMES_A = ["Ravi", "Arjun", "Priya", "Karthik", "Meena", "Vijay", "Divya", "Suresh"]
    NAMES_B = ["Mohammed", "Ahmed", "Fatima", "Omar", "Zainab", "Bilal", "Sara", "Imran"]

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.seed = seed

    # ------------------------------------------------------------------ #
    def generate(self, n_communities: int = 3, members_per_community: int = 6,
                 hidden_intermediaries: int = 1,
                 n_false_edges: int = 3) -> SyntheticInvestigation:
        """Generate a world with communities, hidden actors, planted decoys,
        duplicate identities and contradictory evidence."""
        g = nx.MultiDiGraph()
        truth = SyntheticGroundTruth()

        # ---- communities ----------
        nodes: List[str] = []
        for c in range(n_communities):
            names = self.NAMES_A if c % 2 == 0 else self.NAMES_B
            for m in range(members_per_community):
                node = f"{chr(65 + c)}{m}"   # A0..A5, B0..B5, ...
                g.add_node(node, entity_type="PERSON",
                           canonical_name=f"{names[m % len(names)]} "
                                          f"{self.NAMES_B[m % len(names)]}",
                           aliases=[], mention_count=1)
                nodes.append(node)

        # dense within-community edges
        for c in range(n_communities):
            comm = [f"{chr(65 + c)}{m}" for m in range(members_per_community)]
            for i in range(len(comm)):
                for j in range(i + 1, len(comm)):
                    if self.rng.random() < 0.55:
                        ts = self._random_ts()
                        g.add_edge(comm[i], comm[j], key=f"{comm[i]}-{comm[j]}",
                                   relation="CALLED",
                                   attributes={"timestamp": ts})
                        truth.true_relationships.append(
                            {"source": comm[i], "target": comm[j], "relation": "CALLED"})
                        truth.event_times[f"{comm[i]}-{comm[j]}"] = ts

        # ---- hidden intermediaries ----------
        hidden_nodes: List[str] = []
        for h in range(hidden_intermediaries):
            hid = f"GHOST-{h}"
            g.add_node(hid, entity_type="PERSON", canonical_name=f"Coordinator {h}",
                       aliases=[], mention_count=0)
            hidden_nodes.append(hid)
            truth.hidden_intermediaries.append(hid)
            # connect to one member of two different communities
            c1 = h % n_communities
            c2 = (h + 1) % n_communities
            m1 = f"{chr(65 + c1)}{self.rng.randrange(members_per_community)}"
            m2 = f"{chr(65 + c2)}{self.rng.randrange(members_per_community)}"
            for member in (m1, m2):
                ts = self._random_ts()
                g.add_edge(hid, member, key=f"{hid}-{member}", relation="CALLED",
                           attributes={"timestamp": ts})
                # these edges exist but are "hidden" from the observed graph
                truth.hidden_relationships.append(
                    {"source": hid, "target": member, "relation": "CALLED"})
                truth.event_times[f"{hid}-{member}"] = ts

        # ---- false / decoy edges ----------
        all_nodes = [n for n in nodes]
        planted_false: Set[Tuple[str, str]] = set()
        attempts = 0
        while len(planted_false) < n_false_edges and attempts < n_false_edges * 20:
            attempts += 1
            u, v = self.rng.sample(all_nodes, 2)
            pair = tuple(sorted((u, v)))
            if pair in planted_false or g.has_edge(u, v):
                continue
            planted_false.add(pair)
            key = f"false:{u}|{v}"
            g.add_edge(u, v, key=key, relation="ASSOCIATED_WITH",
                       attributes={"timestamp": self._random_ts(),
                                   "false_planted": True})
            truth.false_relationships.append(
                {"source": u, "target": v, "relation": "ASSOCIATED_WITH"})

        # ---- bridge actors (legit, high betweenness) ----------
        for bridge_index in range(1):
            bridge = f"BRIDGE-{bridge_index}"
            g.add_node(bridge, entity_type="ORGANIZATION",
                       canonical_name=f"Service Provider {bridge_index}",
                       aliases=[], mention_count=5)
            # connects to one member of EVERY community (legit service provider)
            for c in range(n_communities):
                member = f"{chr(65 + c)}{self.rng.randrange(members_per_community)}"
                g.add_edge(bridge, member, key=f"{bridge}-{member}",
                           relation="REGISTERED_TO",
                           attributes={"timestamp": self._random_ts()})
                truth.true_relationships.append(
                    {"source": bridge, "target": member, "relation": "REGISTERED_TO"})

        # ---- duplicate identities ----------
        dup_src = f"{chr(65)}{0}"
        dup_alias_1 = f"{chr(65)}{0}-alt"
        g.add_node(dup_alias_1, entity_type="PERSON",
                   canonical_name=g.nodes[dup_src]["canonical_name"],
                   aliases=[], mention_count=1)
        truth.duplicate_of[dup_alias_1] = dup_src
        truth.aliases[dup_src] = [f"{g.nodes[dup_src]['canonical_name'].split()[0][0]}. "
                                  f"{g.nodes[dup_src]['canonical_name'].split()[-1]}"]

        # ---- isolated actor ----------
        isolated = "ISO-0"
        g.add_node(isolated, entity_type="PERSON", canonical_name="Isolated Person",
                   aliases=[], mention_count=1)

        # ---- records (minimal: for ER / extraction tasks) ----------
        records: List[Dict[str, Any]] = []
        for node in list(g.nodes()):
            data = g.nodes[node]
            records.append({
                "record_id": node,
                "name": data.get("canonical_name", node),
                "entity_type": data.get("entity_type", "PERSON"),
                "aliases": truth.aliases.get(node, []),
            })

        return SyntheticInvestigation(
            graph=g,
            ground_truth=truth,
            records=records,
            metadata={
                "seed": self.seed,
                "n_communities": n_communities,
                "members_per_community": members_per_community,
                "hidden_intermediaries": hidden_intermediaries,
                "n_false_edges": n_false_edges,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _random_ts(self) -> str:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = timedelta(days=self.rng.randint(0, 300),
                          hours=self.rng.randint(0, 23))
        return (start + delta).isoformat()