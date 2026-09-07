"""
person_factory.py
------------------
Builds the population of Person entities:
  - Ordinary gang-affiliated members (boss/lieutenant/member/associate)
  - Unaffiliated civilians (noise in the dataset, realistic for intel data)
  - Hidden coordinators: NOT tagged to any single gang, secretly linked to
    several gangs via lieutenants. They never appear in direct communication
    with rank-and-file members (enforced later by CommunicationSimulator).
"""

import random
from typing import List, Dict

from src.generator.config import SimulationConfig
from src.generator.entities import Person, Gang
from src.generator.fake_provider import FakeDataProvider


class PersonFactory:
    def __init__(self, provider: FakeDataProvider, rng: random.Random, config: SimulationConfig):
        self._provider = provider
        self._rng = rng
        self._config = config

    def create_population(self, gangs: List[Gang]) -> List[Person]:
        """
        Returns the full list of Person objects. Also mutates each Gang's
        member_ids list in place.
        """
        total = self._config.NUM_PEOPLE
        num_coordinators = self._config.NUM_HIDDEN_COORDINATORS

        # Roughly 70% of the population is gang-affiliated, rest are civilians.
        num_affiliated = int(total * 0.7) - num_coordinators
        num_affiliated = max(num_affiliated, len(gangs))  # sanity floor
        num_civilians = total - num_affiliated - num_coordinators

        people: List[Person] = []
        person_counter = 1

        # 1) Gang-affiliated members, distributed across gangs.
        for i in range(num_affiliated):
            gang = gangs[i % len(gangs)]
            role = self._pick_role(is_first_in_gang=len(gang.member_ids) == 0)
            person = self._build_person(person_counter, gang_id=gang.gang_id, role=role)
            gang.member_ids.append(person.person_id)
            people.append(person)
            person_counter += 1

        # 2) Civilians / unaffiliated noise.
        for _ in range(max(num_civilians, 0)):
            person = self._build_person(person_counter, gang_id=None, role=None)
            people.append(person)
            person_counter += 1

        # 3) Hidden coordinators - unaffiliated on paper, influence multiple gangs.
        for _ in range(num_coordinators):
            person = self._build_person(
                person_counter, gang_id=None, role=None, is_hidden_coordinator=True
            )
            people.append(person)
            person_counter += 1

        self._rng.shuffle(people)
        return people

    def _pick_role(self, is_first_in_gang: bool) -> str:
        if is_first_in_gang:
            return "boss"
        # weighted towards regular members/associates
        return self._rng.choices(
            population=self._config.ROLES,
            weights=[0.05, 0.15, 0.5, 0.3],
            k=1,
        )[0]

    def _build_person(self, idx: int, gang_id, role, is_hidden_coordinator: bool = False) -> Person:
        return Person(
            person_id=f"P{idx:06d}",
            full_name=self._provider.full_name(),
            phone_number=self._provider.phone_number(),
            address=self._provider.address(),
            age=self._rng.randint(18, 65),
            gang_id=gang_id,
            role=role,
            is_hidden_coordinator=is_hidden_coordinator,
        )
