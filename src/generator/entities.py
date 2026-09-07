"""
entities.py
-----------
Plain data-holding classes (entities) used across the generator.
Kept deliberately simple (dataclasses) so they serialize to CSV rows easily.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Gang:
    gang_id: str
    name: str
    region: str
    member_ids: List[str] = field(default_factory=list)


@dataclass
class Person:
    person_id: str
    full_name: str
    phone_number: str
    address: str
    age: int
    gang_id: Optional[str]      # None => not affiliated with any gang
    role: Optional[str]         # boss/lieutenant/member/associate/None
    is_hidden_coordinator: bool = False

    def to_row(self) -> dict:
        return {
            "person_id": self.person_id,
            "full_name": self.full_name,
            "phone_number": self.phone_number,
            "address": self.address,
            "age": self.age,
            "gang_id": self.gang_id or "",
            "role": self.role or "",
            "is_hidden_coordinator": self.is_hidden_coordinator,
        }


@dataclass
class CallRecord:
    call_id: str
    caller_id: str
    receiver_id: str
    timestamp: str
    duration_sec: int
    tower_location: str

    def to_row(self) -> dict:
        return self.__dict__


@dataclass
class Transaction:
    transaction_id: str
    sender_id: str
    receiver_id: str
    amount: float
    currency: str
    timestamp: str
    channel: str  # bank_transfer, cash, crypto, mobile_wallet
    account_id: str = ""

    def to_row(self) -> dict:
        return self.__dict__


@dataclass
class Meeting:
    meeting_id: str
    location: str
    timestamp: str
    attendee_ids: List[str]

    def to_row(self) -> dict:
        row = self.__dict__.copy()
        row["attendee_ids"] = "|".join(self.attendee_ids)
        return row
