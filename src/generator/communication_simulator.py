"""
communication_simulator.py
---------------------------
Generates CallRecord and Meeting entities.

Key rule enforced here (per requirements):
    Hidden coordinators NEVER appear as a direct caller/receiver with a
    regular gang member. Their influence is only visible as calls between
    the coordinator and their designated lieutenant proxies. All gang-internal
    chatter happens normally among ordinary members.
"""

import random
from typing import List, Dict
from datetime import datetime, timedelta

from src.generator.entities import Person, CallRecord, Meeting
from src.generator.hidden_coordinator import HiddenCoordinatorTopology


class CommunicationSimulator:
    def __init__(self, rng: random.Random, start_date: datetime = None):
        self._rng = rng
        self._start_date = start_date or datetime(2025, 1, 1)
        self._towers = [f"TWR-{i:03d}" for i in range(1, 41)]

    # ------------------------------------------------------------------ #
    # Calls
    # ------------------------------------------------------------------ #
    def generate_calls(
        self,
        people: List[Person],
        topology: HiddenCoordinatorTopology,
        num_calls: int,
    ) -> List[CallRecord]:
        by_gang: Dict[str, List[Person]] = {}
        for p in people:
            if p.gang_id:
                by_gang.setdefault(p.gang_id, []).append(p)

        civilians = [p for p in people if not p.gang_id and not p.is_hidden_coordinator]
        coordinators = [p for p in people if p.is_hidden_coordinator]
        all_normal_ids = [p.person_id for p in people if not p.is_hidden_coordinator]

        # Reserve ~5% of call volume specifically for coordinator<->lieutenant links
        coordinator_call_budget = int(num_calls * 0.05) if coordinators else 0
        regular_call_budget = num_calls - coordinator_call_budget

        calls: List[CallRecord] = []
        call_idx = 1

        # 1) Coordinator <-> lieutenant calls ONLY (never a regular member).
        coordinator_pairs = []
        for coord_id, gang_map in topology.links.items():
            for gang_id, lieutenants in gang_map.items():
                for lt in lieutenants:
                    coordinator_pairs.append((coord_id, lt))

        if coordinator_pairs:
            for _ in range(coordinator_call_budget):
                caller_id, receiver_id = self._rng.choice(coordinator_pairs)
                if self._rng.random() < 0.5:
                    caller_id, receiver_id = receiver_id, caller_id
                calls.append(self._make_call(call_idx, caller_id, receiver_id))
                call_idx += 1
        else:
            regular_call_budget = num_calls  # no coordinators, all calls are regular

        # 2) Regular traffic: within-gang calls + occasional gang<->civilian calls.
        #    Coordinators are explicitly excluded from this pool.
        for _ in range(regular_call_budget):
            if by_gang and self._rng.random() < 0.85:
                gang_id = self._rng.choice(list(by_gang.keys()))
                members = by_gang[gang_id]
                if len(members) < 2:
                    continue
                caller, receiver = self._rng.sample(members, 2)
                caller_id, receiver_id = caller.person_id, receiver.person_id
            else:
                # a gang member calling a civilian (informant, family, etc.)
                pool = all_normal_ids
                caller_id, receiver_id = self._rng.sample(pool, 2)

            calls.append(self._make_call(call_idx, caller_id, receiver_id))
            call_idx += 1

        return calls

    def _make_call(self, idx: int, caller_id: str, receiver_id: str) -> CallRecord:
        return CallRecord(
            call_id=f"C{idx:07d}",
            caller_id=caller_id,
            receiver_id=receiver_id,
            timestamp=self._random_timestamp().isoformat(),
            duration_sec=self._rng.randint(5, 1800),
            tower_location=self._rng.choice(self._towers),
        )

    # ------------------------------------------------------------------ #
    # Meetings
    # ------------------------------------------------------------------ #
    def generate_meetings(
        self,
        people: List[Person],
        topology: HiddenCoordinatorTopology,
        num_meetings: int,
    ) -> List[Meeting]:
        """
        Meetings represent physical get-togethers. Coordinators still avoid
        appearing WITH regular members: when a coordinator attends, only
        their designated lieutenants for that gang are present, plus
        optionally other coordinators/lieutenants -- never rank-and-file.
        """
        by_gang: Dict[str, List[Person]] = {}
        for p in people:
            if p.gang_id:
                by_gang.setdefault(p.gang_id, []).append(p)

        locations = [
            "Warehouse District", "Riverside Docks", "Downtown Cafe",
            "Abandoned Factory", "Private Villa", "Parking Garage B",
            "Backroom - Lucky Star Bar", "Storage Facility 12",
        ]

        meetings: List[Meeting] = []
        coordinator_meeting_budget = int(num_meetings * 0.05) if topology.links else 0
        regular_budget = num_meetings - coordinator_meeting_budget

        idx = 1
        # Coordinator meetings: coordinator + their lieutenants for ONE gang only.
        coord_gang_pairs = [
            (coord, gang_id)
            for coord, gang_map in topology.links.items()
            for gang_id in gang_map
        ]
        for _ in range(coordinator_meeting_budget):
            if not coord_gang_pairs:
                break
            coord_id, gang_id = self._rng.choice(coord_gang_pairs)
            lieutenants = topology.lieutenants_for(coord_id, gang_id)
            attendees = [coord_id] + lieutenants
            meetings.append(self._make_meeting(idx, locations, attendees))
            idx += 1

        # Regular gang meetings among ordinary members.
        for _ in range(regular_budget):
            if not by_gang:
                break
            gang_id = self._rng.choice(list(by_gang.keys()))
            members = by_gang[gang_id]
            if len(members) < 2:
                continue
            k = min(len(members), self._rng.randint(2, 6))
            attendees = [p.person_id for p in self._rng.sample(members, k)]
            meetings.append(self._make_meeting(idx, locations, attendees))
            idx += 1

        return meetings

    def _make_meeting(self, idx: int, locations: List[str], attendees: List[str]) -> Meeting:
        return Meeting(
            meeting_id=f"M{idx:06d}",
            location=self._rng.choice(locations),
            timestamp=self._random_timestamp().isoformat(),
            attendee_ids=attendees,
        )

    def _random_timestamp(self) -> datetime:
        offset_days = self._rng.randint(0, 364)
        offset_seconds = self._rng.randint(0, 86399)
        return self._start_date + timedelta(days=offset_days, seconds=offset_seconds)
