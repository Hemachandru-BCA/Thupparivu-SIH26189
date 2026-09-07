"""
gang_factory.py
---------------
Creates the fixed set of criminal gangs used across the simulation.
"""

import random
from typing import List

from src.generator.entities import Gang
from src.generator.fake_provider import FakeDataProvider

_GANG_NAME_POOL = [
    "Iron Serpents", "Black Tide", "Red Hollow", "Silver Wolves", "Night Vultures",
    "Crimson Circuit", "Ashfall Crew", "Obsidian League", "Stormline Cartel",
    "Wraith Syndicate", "Golden Fang", "Broken Anchor", "Grey Ledger",
    "Ember Pact", "Hollow Point Boys",
]


class GangFactory:
    def __init__(self, provider: FakeDataProvider, rng: random.Random):
        self._provider = provider
        self._rng = rng

    def create_gangs(self, count: int) -> List[Gang]:
        names = self._rng.sample(_GANG_NAME_POOL, k=min(count, len(_GANG_NAME_POOL)))
        while len(names) < count:  # in case count > pool size
            names.append(f"Unnamed Faction {len(names) + 1}")

        gangs = []
        for i in range(count):
            gang = Gang(
                gang_id=f"G{i + 1:03d}",
                name=names[i],
                region=self._provider.city(),
            )
            gangs.append(gang)
        return gangs
