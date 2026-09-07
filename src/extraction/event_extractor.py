"""
event_extractor.py
------------------
Aggregates relation triplets into typed events (MEETING / CALL / TRANSACTION)
and emits the triplets that link those events into the graph:

    (person, PARTICIPATED_IN, event)
    (event,  EVENT_TYPE,     "TRANSACTION")
    (event,  OCCURRED_AT,    location)
    (event,  OCCURRED_ON,    timestamp)

This keeps graph_triplets.json a single homogeneous triplet list while events
remain first-class nodes (standard reification pattern for link-analysis
graphs). If a record carries metadata (record_type / timestamp) that the text
itself does not reveal, a skeleton event is still created from the metadata so
no known call/meeting/transaction record is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.extraction.ner import Entity
from src.extraction.relation_extractor import Triplet

__all__ = ["Event", "EventExtractor", "EVENT_TYPES"]

EVENT_TYPES = ("MEETING", "CALL", "TRANSACTION")

_METADATA_TYPE_MAP = {"call": "CALL", "meeting": "MEETING", "transaction": "TRANSACTION"}


@dataclass
class Event:
    event_id: str
    event_type: str
    record_id: str
    participants: List[Dict[str, str]] = field(default_factory=list)
    location: Optional[str] = None
    timestamp: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    evidence: str = ""
    sentence_index: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "record_id": self.record_id,
            "participants": self.participants,
            "location": self.location,
            "timestamp": self.timestamp,
            "attributes": self.attributes,
            "evidence": self.evidence,
            "sentence_index": self.sentence_index,
        }

    def participant_names(self) -> List[str]:
        return [p["name"] for p in self.participants]


class EventExtractor:

    def extract(self, entities: Sequence[Entity], triplets: Sequence[Triplet],
                record: Optional[Dict[str, Any]] = None
                ) -> Tuple[List[Event], List[Triplet]]:
        record = record or {}
        record_id = str(record.get("record_id") or "")
        record_ts = record.get("timestamp")

        events: List[Event] = []
        linking: List[Triplet] = []
        counter = {"seq": 0}

        def add_event(event_type: str, participants: List[Dict[str, str]],
                      location: Optional[str] = None, timestamp: Optional[str] = None,
                      attributes: Optional[Dict[str, Any]] = None,
                      evidence: str = "", sent_idx: int = -1) -> None:
            counter["seq"] += 1
            suffix = f"{record_id}-{counter['seq']:02d}" if record_id else f"{counter['seq']:04d}"
            event = Event(
                event_id=f"EVT-{suffix}",
                event_type=event_type,
                record_id=record_id,
                participants=self._dedupe(participants),
                location=location,
                timestamp=timestamp or record_ts,
                attributes=attributes or {},
                evidence=evidence,
                sentence_index=sent_idx,
            )
            events.append(event)
            linking.extend(self._linking_triplets(event))

        # 1) MEETING: consolidate pairwise MET edges from the same sentence.
        meetings: Dict[int, List[Triplet]] = {}
        for t in triplets:
            if t.relation == "MET":
                meetings.setdefault(t.sentence_index, []).append(t)
        for sent_idx in sorted(meetings):
            group = meetings[sent_idx]
            participants: List[Dict[str, str]] = []
            for t in group:
                participants.append({"name": t.source, "type": t.source_type})
                participants.append({"name": t.target, "type": t.target_type})
            t0 = group[0]
            attrs = {k: v for k, v in t0.attributes.items()
                     if k not in ("location", "timestamp")}
            add_event("MEETING", participants,
                      location=t0.attributes.get("location"),
                      timestamp=t0.attributes.get("timestamp"),
                      attributes=attrs, evidence=t0.evidence, sent_idx=sent_idx)

        # 2) one-to-one relations.
        for t in triplets:
            participants = [{"name": t.source, "type": t.source_type},
                            {"name": t.target, "type": t.target_type}]
            attrs = {k: v for k, v in t.attributes.items()
                     if k not in ("location", "timestamp")}
            if t.relation == "TRANSFERRED_FUNDS":
                if t.amount is not None:
                    attrs["amount"] = t.amount
                add_event("TRANSACTION", participants,
                          location=t.attributes.get("location"),
                          timestamp=t.attributes.get("timestamp"),
                          attributes=attrs, evidence=t.evidence,
                          sent_idx=t.sentence_index)
            elif t.relation == "CALLED":
                add_event("CALL", participants,
                          location=t.attributes.get("location"),
                          timestamp=t.attributes.get("timestamp"),
                          attributes=attrs, evidence=t.evidence,
                          sent_idx=t.sentence_index)
            elif t.relation == "ATTENDED_MEETING_AT":
                add_event("MEETING", participants[:1],
                          location=t.target,
                          timestamp=t.attributes.get("timestamp"),
                          evidence=t.evidence, sent_idx=t.sentence_index)

        # 3) metadata fallback for terse records.
        rec_type = str(record.get("record_type") or "").lower()
        if rec_type in _METADATA_TYPE_MAP and not any(
                e.event_type == _METADATA_TYPE_MAP[rec_type] for e in events):
            persons = [e for e in entities if e.label == "PERSON"]
            if persons:
                add_event(_METADATA_TYPE_MAP[rec_type],
                          [{"name": p.text, "type": "PERSON"} for p in persons[:2]],
                          attributes={"source": "record_metadata"},
                          evidence=str(record.get("text") or "").strip())

        return events, linking

    @staticmethod
    def _dedupe(participants: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
        seen, out = set(), []
        for p in participants:
            key = (p["name"], p["type"])
            if key not in seen:
                seen.add(key)
                out.append(dict(p))
        return out

    @staticmethod
    def _linking_triplets(event: Event) -> List[Triplet]:
        trips: List[Triplet] = []
        for participant in event.participants:
            trips.append(Triplet(
                source=participant["name"], source_type=participant["type"],
                relation="PARTICIPATED_IN", target=event.event_id, target_type="EVENT",
                record_id=event.record_id, evidence=event.evidence,
                sentence_index=event.sentence_index, confidence=1.0))
        trips.append(Triplet(
            source=event.event_id, source_type="EVENT",
            relation="EVENT_TYPE", target=event.event_type, target_type="EVENT_TYPE",
            record_id=event.record_id, evidence=event.evidence,
            sentence_index=event.sentence_index, confidence=1.0))
        if event.location:
            trips.append(Triplet(
                source=event.event_id, source_type="EVENT",
                relation="OCCURRED_AT", target=event.location, target_type="LOCATION",
                record_id=event.record_id, evidence=event.evidence,
                sentence_index=event.sentence_index, confidence=1.0))
        if event.timestamp:
            trips.append(Triplet(
                source=event.event_id, source_type="EVENT",
                relation="OCCURRED_ON", target=event.timestamp, target_type="DATETIME",
                record_id=event.record_id, evidence=event.evidence,
                sentence_index=event.sentence_index, confidence=1.0))
        return trips
