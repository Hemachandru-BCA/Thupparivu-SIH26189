"""
hidden_coordinator.py
----------------------
Models the "hidden coordinator" pattern requested:

  * A small set of people secretly influence MULTIPLE gangs.
  * They NEVER communicate directly with rank-and-file gang members.
  * Influence is only ever exercised through 1-2 trusted lieutenants per gang
    (an indirect hop). This is exactly the kind of structure link-analysis /
    social-network-analysis tooling is built to surface -- the coordinator
    has no direct edges to the gangs they control, only indirect ones
    through intermediaries, so naive "who talks to whom" queries miss them.

This module only computes the *topology* (which lieutenants act as proxies
for which coordinator/gang pair). The actual call/transaction generation is
handled by CommunicationSimulator and TransactionSimulator, which consult
this topology to decide who is and is not allowed to contact whom.
"""

import random
from typing import Dict, List
from collections import defaultdict

from src.generator.config import SimulationConfig
from src.generator.entities import Person, Gang


class HiddenCoordinatorTopology:
    """
    coordinator_id -> {gang_id -> [lieutenant_person_ids]}
    """

    def __init__(self):
        self.links: Dict[str, Dict[str, List[str]]] = defaultdict(dict)

    def add_link(self, coordinator_id: str, gang_id: str, lieutenants: List[str]):
        self.links[coordinator_id][gang_id] = lieutenants

    def gangs_for(self, coordinator_id: str) -> List[str]:
        return list(self.links.get(coordinator_id, {}).keys())

    def lieutenants_for(self, coordinator_id: str, gang_id: str) -> List[str]:
        return self.links.get(coordinator_id, {}).get(gang_id, [])

    def all_proxy_person_ids(self) -> set:
        proxies = set()
        for gang_map in self.links.values():
            for lieutenants in gang_map.values():
                proxies.update(lieutenants)
        return proxies


class HiddenCoordinatorEngine:
    def __init__(self, rng: random.Random, config: SimulationConfig):
        self._rng = rng
        self._config = config

    def build_topology(
        self, people: List[Person], gangs: List[Gang]
    ) -> HiddenCoordinatorTopology:
        topology = HiddenCoordinatorTopology()

        coordinators = [p for p in people if p.is_hidden_coordinator]
        lieutenants_by_gang = self._index_lieutenants(people)

        for coordinator in coordinators:
            num_gangs = self._rng.randint(
                self._config.MIN_GANGS_PER_COORDINATOR,
                min(self._config.MAX_GANGS_PER_COORDINATOR, len(gangs)),
            )
            controlled_gangs = self._rng.sample(gangs, k=num_gangs)

            for gang in controlled_gangs:
                candidates = lieutenants_by_gang.get(gang.gang_id, [])
                if not candidates:
                    continue
                k = min(len(candidates), self._rng.randint(1, 2))
                chosen_lieutenants = self._rng.sample(candidates, k=k)
                topology.add_link(coordinator.person_id, gang.gang_id, chosen_lieutenants)

        return topology

    @staticmethod
    def _index_lieutenants(people: List[Person]) -> Dict[str, List[str]]:
        index: Dict[str, List[str]] = defaultdict(list)
        for p in people:
            if p.gang_id and p.role in ("lieutenant", "boss"):
                index[p.gang_id].append(p.person_id)
        return index
