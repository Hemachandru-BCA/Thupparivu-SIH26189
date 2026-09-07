"""
dataset_generator.py
----------------------
Top-level orchestrator (Facade) for CriminalAnalysis AI's synthetic dataset
generation. Wires together GangFactory, PersonFactory, HiddenCoordinatorEngine,
CommunicationSimulator and TransactionSimulator, then serializes everything
to CSV under the configured output directory.

Usage:
    generator = DatasetGenerator(SimulationConfig())
    summary = generator.run()
    print(summary)
"""

import os
import random
from dataclasses import dataclass
from typing import Dict, List

from src.generator.config import SimulationConfig
from src.generator.fake_provider import FakeDataProvider
from src.generator.gang_factory import GangFactory
from src.generator.person_factory import PersonFactory
from src.generator.hidden_coordinator import HiddenCoordinatorEngine, HiddenCoordinatorTopology
from src.generator.communication_simulator import CommunicationSimulator
from src.generator.transaction_simulator import TransactionSimulator
from src.generator.csv_writer import CsvWriter
from src.generator.entities import Person, Gang, CallRecord, Transaction, Meeting


@dataclass
class GenerationSummary:
    output_dir: str
    num_gangs: int
    num_people: int
    num_calls: int
    num_transactions: int
    num_meetings: int
    num_hidden_coordinators: int
    faker_backend: str

    def __str__(self):
        return (
            f"Synthetic dataset generated in '{self.output_dir}'\n"
            f"  Gangs:               {self.num_gangs}\n"
            f"  People:              {self.num_people}\n"
            f"  Calls:               {self.num_calls}\n"
            f"  Transactions:        {self.num_transactions}\n"
            f"  Meetings:            {self.num_meetings}\n"
            f"  Hidden coordinators: {self.num_hidden_coordinators}\n"
            f"  Name/address backend:{self.faker_backend}"
        )


class DatasetGenerator:
    """
    Facade class. Instantiate with a SimulationConfig and call `run()`.
    """

    def __init__(self, config: SimulationConfig = None, output_dir: str = None):
        self.config = config or SimulationConfig()
        self.output_dir = output_dir or self.config.OUTPUT_DIR

        self._rng = random.Random(self.config.RANDOM_SEED)
        self._provider = FakeDataProvider(seed=self.config.RANDOM_SEED)

        self._gang_factory = GangFactory(self._provider, self._rng)
        self._person_factory = PersonFactory(self._provider, self._rng, self.config)
        self._coordinator_engine = HiddenCoordinatorEngine(self._rng, self.config)
        self._comm_sim = CommunicationSimulator(self._rng)
        self._txn_sim = TransactionSimulator(self._rng)

        # populated after run()
        self.gangs: List[Gang] = []
        self.people: List[Person] = []
        self.calls: List[CallRecord] = []
        self.transactions: List[Transaction] = []
        self.meetings: List[Meeting] = []
        self.topology: HiddenCoordinatorTopology = None

    def run(self) -> GenerationSummary:
        self.gangs = self._gang_factory.create_gangs(self.config.NUM_GANGS)
        self.people = self._person_factory.create_population(self.gangs)
        self.topology = self._coordinator_engine.build_topology(self.people, self.gangs)

        self.calls = self._comm_sim.generate_calls(
            self.people, self.topology, self.config.NUM_CALLS
        )
        self.meetings = self._comm_sim.generate_meetings(
            self.people, self.topology, self.config.NUM_MEETINGS
        )
        self.transactions = self._txn_sim.generate_transactions(
            self.people, self.topology, self.config.NUM_TRANSACTIONS
        )

        self._write_all()

        return GenerationSummary(
            output_dir=self.output_dir,
            num_gangs=len(self.gangs),
            num_people=len(self.people),
            num_calls=len(self.calls),
            num_transactions=len(self.transactions),
            num_meetings=len(self.meetings),
            num_hidden_coordinators=self.config.NUM_HIDDEN_COORDINATORS,
            faker_backend=self._provider.backend,
        )

    def _write_all(self) -> None:
        CsvWriter.write(self.people, os.path.join(self.output_dir, "persons.csv"))
        CsvWriter.write(self.calls, os.path.join(self.output_dir, "calls.csv"))
        CsvWriter.write(self.transactions, os.path.join(self.output_dir, "transactions.csv"))
        CsvWriter.write(self.meetings, os.path.join(self.output_dir, "meetings.csv"))


if __name__ == "__main__":
    gen = DatasetGenerator()
    print(gen.run())
