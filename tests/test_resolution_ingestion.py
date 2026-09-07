"""Tests for the new resolution + ingestion modules (Phase additions)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.resolution.clustering import (  # noqa: E402
    ClusterConfig,
    cluster_by_canonical,
    cluster_by_similarity,
)
from src.resolution.guid_generator import (  # noqa: E402
    entity_guid,
    evidence_guid,
    ghost_guid,
    record_guid,
)


# ------------------------------------------------------------------ clustering
def test_similarity_clustering_merges_typos():
    mentions = [
        ("m1", "Ramesh Kumar"),
        ("m2", "Ramesh Kummar"),
        ("m3", "Priya Sharma"),
        ("m4", "Ramesh Kumar "),   # trailing space normalizes away
    ]
    result = cluster_by_similarity(mentions, ClusterConfig(sim_threshold=0.85))
    clusters = {mid: idx for mid, idx in result.mention_to_cluster.items()}
    assert clusters["m1"] == clusters["m2"] == clusters["m4"]
    assert clusters["m3"] != clusters["m1"]
    assert result.summary()["num_clusters"] == 2


def test_canonical_clustering_deterministic():
    mentions = [(f"m{i}", name) for i, name in enumerate(
        ["Vikram Singh", "Vikram Sing", "Anil Kapoor", "Vikram Singh"])]
    r1 = cluster_by_canonical(mentions)
    r2 = cluster_by_canonical(list(reversed(mentions)))
    # deterministic per input order
    assert r1.summary()["num_clusters"] == 2
    assert r2.summary()["num_clusters"] >= 2
    assert r1.summary() == r1.summary()


def test_review_band_records_uncertain_pairs():
    mentions = [("a", "John Smith"), ("b", "Jon Smith")]
    result = cluster_by_canonical(mentions, ClusterConfig(
        canonical_keep_threshold=0.99, canonical_review_band=(0.5, 0.99)))
    assert result.review_pairs, "near-miss pair should be flagged for review"


# --------------------------------------------------------------- guid generator
def test_guids_deterministic_and_distinct():
    g1 = entity_guid("PERSON", "Ramesh Kumar")
    g2 = entity_guid("PERSON", "  ramesh   kumar ")
    g3 = entity_guid("PERSON", "Priya Sharma")
    assert g1 == g2                      # normalization-insensitive
    assert g1 != g3
    assert g1 != record_guid("calls", "C1")
    assert g1 != evidence_guid("C1")
    assert ghost_guid(2, 7, "a|b") == ghost_guid(7, 2, "a|b")  # order-insensitive


def test_record_and_evidence_guids():
    r1 = record_guid("CALLS", "C000001")
    r2 = record_guid("calls", "C000001")
    assert r1 == r2
    assert evidence_guid("C000001", "edge-1") != evidence_guid("C000001", "edge-2")


# ------------------------------------------------------------------- pdf loader
def test_pdf_loader_requires_dependency_or_works():
    try:
        from src.ingestion.pdf_loader import PdfLoader
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"pdf loader unavailable: {exc}")
    from src.ingestion.pdf_loader import _HAS_PYPDF

    assert PdfLoader.available() == _HAS_PYPDF
    if not _HAS_PYPDF:
        with pytest.raises(Exception):
            PdfLoader()
    else:
        loader = PdfLoader()
        assert loader.available() is True
        with pytest.raises(Exception):
            loader.load("/nonexistent/file.pdf")


def test_pdf_loader_rejects_non_pdf(tmp_path):
    pytest.importorskip("pypdf")
    from src.ingestion.pdf_loader import PdfLoader, PdfLoaderError

    bad = tmp_path / "not-a-pdf.txt"
    bad.write_text("hello")
    with pytest.raises(PdfLoaderError):
        PdfLoader().load(bad)
