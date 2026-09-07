"""
test_generator.py
------------------
Unit tests for the synthetic data generator, including the critical
"hidden coordinator never directly contacts a gang member" invariant.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.generator.config import SimulationConfig
from src.generator.dataset_generator import DatasetGenerator


class SmallConfig(SimulationConfig):
    """A tiny config so tests run fast."""
    NUM_GANGS = 4
    NUM_PEOPLE = 200
    NUM_CALLS = 800
    NUM_TRANSACTIONS = 300
    NUM_MEETINGS = 100
    NUM_HIDDEN_COORDINATORS = 3
    RANDOM_SEED = 7


class TestDatasetGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.config = SmallConfig(OUTPUT_DIR=cls.tmpdir)
        cls.generator = DatasetGenerator(cls.config, output_dir=cls.tmpdir)
        cls.summary = cls.generator.run()

    def test_counts_match_config(self):
        self.assertEqual(len(self.generator.gangs), self.config.NUM_GANGS)
        self.assertEqual(len(self.generator.people), self.config.NUM_PEOPLE)
        self.assertEqual(len(self.generator.calls), self.config.NUM_CALLS)
        self.assertEqual(len(self.generator.transactions), self.config.NUM_TRANSACTIONS)

    def test_hidden_coordinators_exist_and_are_unaffiliated(self):
        coordinators = [p for p in self.generator.people if p.is_hidden_coordinator]
        self.assertEqual(len(coordinators), self.config.NUM_HIDDEN_COORDINATORS)
        for c in coordinators:
            self.assertIsNone(c.gang_id)

    def test_coordinators_influence_multiple_gangs(self):
        topology = self.generator.topology
        for coord_id in topology.links:
            gangs_touched = topology.gangs_for(coord_id)
            self.assertGreaterEqual(
                len(gangs_touched), self.config.MIN_GANGS_PER_COORDINATOR
            )

    def test_coordinators_never_call_regular_members_directly(self):
        """
        Core invariant: a hidden coordinator's person_id must NEVER appear
        in a call record paired with a regular gang member (role in
        member/associate) or with anyone who isn't one of their designated
        lieutenant proxies.
        """
        topology = self.generator.topology
        coordinator_ids = {p.person_id for p in self.generator.people if p.is_hidden_coordinator}
        allowed_partners = topology.all_proxy_person_ids()

        violations = []
        for call in self.generator.calls:
            parties = {call.caller_id, call.receiver_id}
            touched_coordinators = parties & coordinator_ids
            if not touched_coordinators:
                continue
            other_party = (parties - touched_coordinators)
            # if a coordinator calls another coordinator that's out of scope here,
            # but if the other party is a regular (non-proxy) person, that's a violation.
            for other in other_party:
                if other not in allowed_partners and other not in coordinator_ids:
                    violations.append(call)

        self.assertEqual(
            len(violations), 0,
            f"Found {len(violations)} calls where a coordinator directly "
            f"contacted a non-lieutenant."
        )

    def test_coordinators_never_transact_with_regular_members_directly(self):
        topology = self.generator.topology
        coordinator_ids = {p.person_id for p in self.generator.people if p.is_hidden_coordinator}
        allowed_partners = topology.all_proxy_person_ids()

        violations = []
        for txn in self.generator.transactions:
            parties = {txn.sender_id, txn.receiver_id}
            touched_coordinators = parties & coordinator_ids
            if not touched_coordinators:
                continue
            other_party = parties - touched_coordinators
            for other in other_party:
                if other not in allowed_partners and other not in coordinator_ids:
                    violations.append(txn)

        self.assertEqual(len(violations), 0)

    def test_csv_files_created(self):
        for filename in ["persons.csv", "calls.csv", "transactions.csv", "meetings.csv"]:
            path = os.path.join(self.tmpdir, filename)
            self.assertTrue(os.path.exists(path), f"{filename} was not created")
            self.assertGreater(os.path.getsize(path), 0)

    def test_person_ids_unique(self):
        ids = [p.person_id for p in self.generator.people]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_gang_has_a_boss(self):
        for gang in self.generator.gangs:
            roles = [
                p.role for p in self.generator.people
                if p.gang_id == gang.gang_id
            ]
            self.assertIn("boss", roles)


if __name__ == "__main__":
    unittest.main()
