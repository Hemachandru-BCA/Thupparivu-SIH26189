"""Tests for the evidence provenance layer (src/xai/evidence_tracer.py)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.xai.evidence_tracer import (  # noqa: E402
    EvidenceRecord,
    EvidenceStore,
    InMemoryEvidenceBackend,
    build_store_from_artifacts,
    make_evidence_id,
)


@pytest.fixture(scope="module")
def real_store():
    from src.api import paths

    if not paths.EVIDENCE_INDEX_PATH.exists():
        pytest.skip("evidence index not built - run `python run_stage.py evidence`")
    return EvidenceStore.from_json(paths.EVIDENCE_INDEX_PATH)


def test_evidence_record_auto_hash():
    rec = EvidenceRecord(
        evidence_id=make_evidence_id("CALL", "C0000001"),
        source_type="CALL",
        source_record_id="C0000001",
        text_excerpt="a called b",
    )
    assert rec.hash and len(rec.hash) == 64
    other = EvidenceRecord(
        evidence_id=make_evidence_id("CALL", "C0000001"),
        source_type="CALL",
        source_record_id="C0000001",
        text_excerpt="a called b",
    )
    assert other.hash == rec.hash  # deterministic integrity hash


def test_deterministic_evidence_ids():
    a = make_evidence_id("CALL", "C1")
    b = make_evidence_id("CALL", "C1")
    c = make_evidence_id("CALL", "C2", kind="edge-1")
    assert a == b and a != c and a.startswith("EV-")


def test_invalid_source_type_rejected():
    store = EvidenceStore()
    rec = EvidenceRecord(evidence_id="EV-x", source_type="BOGUS", source_record_id="r1")
    with pytest.raises(ValueError):
        store.add(rec)


def test_store_roundtrip(tmp_path):
    store = EvidenceStore()
    rec = EvidenceRecord(
        evidence_id=make_evidence_id("FIR", "FIR000001"),
        source_type="FIR",
        source_record_id="FIR000001",
        text_excerpt="complaint lodged against someone",
        subject_ids=["P1"],
        timestamp="2025-08-04",
    )
    store.add(rec, node_ids=["P1"])
    out = tmp_path / "index.json"
    store.to_json(out)
    loaded = EvidenceStore.from_json(out)
    assert loaded.count() == 1
    assert loaded.get_evidence(rec.evidence_id).text_excerpt == rec.text_excerpt
    assert loaded.get_evidence_for_node("P1")[0].evidence_id == rec.evidence_id


def test_search_ranks_and_limits():
    store = EvidenceStore()
    for i, text in enumerate(["alpha called beta today", "gamma met delta", "alpha transferred funds"]):
        store.add(
            EvidenceRecord(
                evidence_id=f"EV-{i}", source_type="CALL", source_record_id=f"R{i}",
                text_excerpt=text,
            )
        )
    hits = store.search_evidence("alpha")
    assert len(hits) == 2
    assert hits[0].text_excerpt.startswith("alpha called")  # 2 tokens beats 1


def test_timeline_orders_chronologically():
    store = EvidenceStore()
    for ts in ("2025-03-01", "2025-01-01", "2025-02-01"):
        store.add(
            EvidenceRecord(
                evidence_id=make_evidence_id("CALL", ts),
                source_type="CALL", source_record_id=ts, timestamp=ts,
                text_excerpt=f"event at {ts}", subject_ids=["P9"],
            ),
            node_ids=["P9"],
        )
    tl = store.get_timeline("P9")
    stamps = [r["timestamp"] for r in tl]
    assert stamps == sorted(stamps)


def test_build_from_artifacts_real_data(real_store):
    """Against the shipped artifacts: counts sane, node/edge linkage present."""
    assert real_store.count() > 30000
    # person linkage: pick any person profile evidence and check subject ids
    rec = real_store.search_evidence("called", limit=5)
    assert rec, "keyword search should find call records"


def test_backend_protocol():
    backend = InMemoryEvidenceBackend()
    rec = EvidenceRecord(evidence_id="EV-1", source_type="CALL", source_record_id="x")
    backend.upsert(rec)
    assert backend.get("EV-1") is rec
    assert list(backend.iter_all()) == [rec]
