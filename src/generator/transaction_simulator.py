"""
transaction_simulator.py
--------------------------
Generates Transaction entities (financial flows). Mirrors the same "no
direct coordinator link" rule as CommunicationSimulator: money from a
coordinator only ever flows to/from their lieutenant proxies, never
straight to rank-and-file members.
"""

import random
from typing import List, Dict
from datetime import datetime, timedelta

from src.generator.entities import Person, Transaction
from src.generator.hidden_coordinator import HiddenCoordinatorTopology

_CHANNELS = ["bank_transfer", "cash", "crypto", "mobile_wallet"]
_CURRENCIES = ["USD", "EUR", "GBP"]


class TransactionSimulator:
    def __init__(self, rng: random.Random, start_date: datetime = None):
        self._rng = rng
        self._start_date = start_date or datetime(2025, 1, 1)

    def generate_transactions(
        self,
        people: List[Person],
        topology: HiddenCoordinatorTopology,
        num_transactions: int,
    ) -> List[Transaction]:
        by_gang: Dict[str, List[Person]] = {}
        for p in people:
            if p.gang_id:
                by_gang.setdefault(p.gang_id, []).append(p)
        all_ids = [p.person_id for p in people if not p.is_hidden_coordinator]

        coordinator_pairs = [
            (coord, lt)
            for coord, gang_map in topology.links.items()
            for lieutenants in gang_map.values()
            for lt in lieutenants
        ]

        coord_budget = int(num_transactions * 0.05) if coordinator_pairs else 0
        regular_budget = num_transactions - coord_budget

        txns: List[Transaction] = []
        idx = 1

        # Coordinator funding: larger, crypto/bank-heavy amounts to lieutenants only.
        for _ in range(coord_budget):
            sender_id, receiver_id = self._rng.choice(coordinator_pairs)
            if self._rng.random() < 0.5:
                sender_id, receiver_id = receiver_id, sender_id
            amount = round(self._rng.uniform(5000, 100000), 2)
            channel = self._rng.choice(["crypto", "bank_transfer"])
            account_id = f"ACC-{sender_id}"
            # Coordinator-linked transfers share a stable route account across all gangs they influence.
            for coord_id, gang_map in topology.links.items():
                if sender_id == coord_id or receiver_id in [lt for lts in gang_map.values() for lt in lts]:
                    account_id = f"ACC-COORD-{coord_id}"
                    break
            txns.append(self._make_txn(idx, sender_id, receiver_id, amount, channel, account_id))
            idx += 1

        # Regular gang-internal / civilian transactions.
        for _ in range(regular_budget):
            if by_gang and self._rng.random() < 0.8:
                gang_id = self._rng.choice(list(by_gang.keys()))
                members = by_gang[gang_id]
                if len(members) < 2:
                    continue
                sender, receiver = self._rng.sample(members, 2)
                sender_id, receiver_id = sender.person_id, receiver.person_id
                amount = round(self._rng.uniform(50, 20000), 2)
            else:
                sender_id, receiver_id = self._rng.sample(all_ids, 2)
                amount = round(self._rng.uniform(10, 5000), 2)

            channel = self._rng.choice(_CHANNELS)
            account_id = f"ACC-{sender_id}-{idx:07d}"
            txns.append(self._make_txn(idx, sender_id, receiver_id, amount, channel, account_id))
            idx += 1

        return txns

    def _make_txn(self, idx, sender_id, receiver_id, amount, channel, account_id="") -> Transaction:
        return Transaction(
            transaction_id=f"T{idx:07d}",
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            currency=self._rng.choice(_CURRENCIES),
            timestamp=self._random_timestamp().isoformat(),
            channel=channel,
            account_id=account_id,
        )

    def _random_timestamp(self) -> datetime:
        offset_days = self._rng.randint(0, 364)
        offset_seconds = self._rng.randint(0, 86399)
        return self._start_date + timedelta(days=offset_days, seconds=offset_seconds)
