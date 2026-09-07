"""event_extractor.py tests - pure Python, no spaCy model required."""

from src.extraction.ner import Entity
from src.extraction.relation_extractor import  Triplet
from src.extraction.event_extractor import  EventExtractor


def test_transaction_event_from_required_example():
    transfer = Triplet(
        source="Ramesh", source_type="PERSON", relation="TRANSFERRED_FUNDS",
        target="Akash", target_type="PERSON", amount=5000,
        record_id="R001", evidence="Ramesh transferred 5000 to Akash",
        sentence_index=0)
    events, linking = EventExtractor().extract([], [transfer],
                                               record={"record_id": "R001"})

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "TRANSACTION"
    assert event.event_id == "EVT-R001-01"
    assert event.attributes["amount"] == 5000
    assert {p["name"] for p in event.participants} == {"Ramesh", "Akash"}

    edges = {(t.source, t.relation, t.target) for t in linking}
    assert ("Ramesh", "PARTICIPATED_IN", "EVT-R001-01") in edges
    assert ("Akash", "PARTICIPATED_IN", "EVT-R001-01") in edges
    assert ("EVT-R001-01", "EVENT_TYPE", "TRANSACTION") in edges


def test_meeting_event_consolidates_pairwise_edges():
    meeting_edges = [
        Triplet("Deepak", "PERSON", "MET", "Farhan", "PERSON", record_id="R002",
                sentence_index=0, attributes={"location": "Warehouse District"}),
        Triplet("Deepak", "PERSON", "MET", "Gita", "PERSON", record_id="R002",
                sentence_index=0, attributes={"location": "Warehouse District"}),
        Triplet("Farhan", "PERSON", "MET", "Gita", "PERSON", record_id="R002",
                sentence_index=0, attributes={"location": "Warehouse District"}),
    ]
    events, linking = EventExtractor().extract([], meeting_edges,
                                               record={"record_id": "R002"})

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "MEETING"
    assert {p["name"] for p in event.participants} == {"Deepak", "Farhan", "Gita"}
    assert event.location == "Warehouse District"

    participated = [t for t in linking if t.relation == "PARTICIPATED_IN"]
    assert len(participated) == 3
    assert any(t.relation == "OCCURRED_AT" and t.target == "Warehouse District"
               for t in linking)


def test_call_event_uses_record_timestamp():
    call = Triplet("Priya", "PERSON", "CALLED", "Sunil", "PERSON", record_id="R003",
                   attributes={"duration_sec": 300, "location": "TWR-012"})
    events, _ = EventExtractor().extract([], [call], record={
        "record_id": "R003", "timestamp": "2025-03-05T09:10:00"})
    event = events[0]
    assert event.event_type == "CALL"
    assert event.timestamp == "2025-03-05T09:10:00"
    assert event.location == "TWR-012"
    assert event.attributes["duration_sec"] == 300


def test_metadata_fallback_event():
    entities = [
        Entity(text="Ramesh", label="PERSON", start_char=0, end_char=6),
        Entity(text="Akash", label="PERSON", start_char=25, end_char=30),
    ]
    events, _ = EventExtractor().extract(
        entities, [], record={"record_id": "R004", "record_type": "transaction",
                              "text": "Ramesh ... Akash"})
    assert len(events) == 1
    assert events[0].event_type == "TRANSACTION"
    assert events[0].attributes["source"] == "record_metadata"
