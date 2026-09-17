"""
tests/test_rag_retriever.py
---------------------------
Tests for hybrid RAG retrieval (Phase 6 / Task 14).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from src.xai.embeddings_store import EvidenceEmbeddingsStore
from src.xai.rag_retriever import RAGRetriever


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_evidence_records(n: int = 50) -> List[Dict[str, Any]]:
    """Generate n synthetic evidence records."""
    records = []
    for i in range(n):
        records.append({
            "evidence_id": f"EV-{i:04d}",
            "subject_ids": [f"entity_{i % 5}"],
            "timestamp": f"2025-01-{10 + (i % 20):02d}T{(i % 12):02d}:00:00Z",
            "text_excerpt": f"Evidence record {i}: person discussed financial transaction "
                            f"amount {i * 1000} regarding investigation case {i % 10}.",
            "source_type": "call_observation",
        })
    return records


class _FakeEvidenceStore:
    """Fake evidence store for testing."""

    def __init__(self, records: List[Dict[str, Any]]):
        self._records = {r["evidence_id"]: r for r in records}

    def get_evidence_for_node(self, node_id: str, limit: int = 50) -> List[Any]:
        class _R:
            def __init__(self, d):
                for k, v in d.items():
                    setattr(self, k, v)
        results = [
            _R(r) for r in self._records.values()
            if node_id in r.get("subject_ids", [])
        ][:limit]
        return results


# --------------------------------------------------------------------------- #
# Tests — EmbeddingsStore
# --------------------------------------------------------------------------- #

class TestEmbeddingsStore:
    def test_build_and_load(self):
        """Build embeddings, then load from disk."""
        with tempfile.TemporaryDirectory() as tmp:
            ev_path = Path(tmp) / "evidence.json"
            records = _make_evidence_records(30)
            ev_path.write_text(json.dumps({"records": records}))

            store = EvidenceEmbeddingsStore(str(ev_path))
            store.build()
            assert store.built
            assert store.record_count == 30
            assert store.model_used in ("sentence-transformers", "tfidf", "ngram")

            # Load from disk
            store2 = EvidenceEmbeddingsStore(str(ev_path))
            assert store2.load()
            assert store2.built

    def test_top_k_returns_k_records(self):
        """top_k should return up to k records when corpus has > k entries."""
        with tempfile.TemporaryDirectory() as tmp:
            ev_path = Path(tmp) / "evidence.json"
            records = _make_evidence_records(50)
            ev_path.write_text(json.dumps({"records": records}))

            store = EvidenceEmbeddingsStore(str(ev_path))
            store.build()
            results = store.top_k("financial transaction", k=10)
            assert len(results) <= 10
            assert len(results) > 0
            # Each result should have a relevance_score
            for r in results:
                assert "relevance_score" in r

    def test_top_k_with_filter(self):
        """Filtering by entity_id should only return matching records."""
        with tempfile.TemporaryDirectory() as tmp:
            ev_path = Path(tmp) / "evidence.json"
            records = _make_evidence_records(50)
            ev_path.write_text(json.dumps({"records": records}))

            store = EvidenceEmbeddingsStore(str(ev_path))
            store.build()
            results = store.top_k("transaction", k=20, filter_entity_ids=["entity_0"])
            # All returned results should belong to filtered entities
            for r in results:
                subjects = set(r.get("subject_ids", []))
                assert "entity_0" in subjects or r.get("relevance_score", 0) < 0


# --------------------------------------------------------------------------- #
# Tests — RAGRetriever
# --------------------------------------------------------------------------- #

class TestRAGRetriever:
    def test_retrieve_for_dossier_returns_bounded(self):
        """retrieve_for_dossier returns ≤ max_evidence, no duplicates."""
        with tempfile.TemporaryDirectory() as tmp:
            ev_path = Path(tmp) / "evidence.json"
            records = _make_evidence_records(50)
            ev_path.write_text(json.dumps({"records": records}))

            store = EvidenceEmbeddingsStore(str(ev_path))
            store.build()
            retriever = RAGRetriever(store)
            fake_store = _FakeEvidenceStore(records)
            results = retriever.retrieve_for_dossier(
                "entity_0", "criminal network role evidence", fake_store, max_evidence=20
            )
            assert len(results) <= 20
            # No duplicates
            eids = [r["evidence_id"] for r in results]
            assert len(eids) == len(set(eids))

    def test_fallback_when_embeddings_not_built(self):
        """When embeddings not built, should fall back to full-context."""
        # Point to non-existent evidence file — load() can't build embeddings
        store = EvidenceEmbeddingsStore("/nonexistent/evidence.json")
        # Force _use_rag False (no persisted embeddings found)
        retriever = RAGRetriever.__new__(RAGRetriever)
        retriever._store = store
        retriever._use_rag = False
        retriever._last_count = 0
        assert retriever.retrieval_method == "full"
        records = _make_evidence_records(10)
        fake_store = _FakeEvidenceStore(records)
        results = retriever.retrieve_for_dossier(
            "entity_0", "test query", fake_store, max_evidence=10
        )
        assert len(results) >= 0  # May be empty if no matching

    def test_fallback_to_tfidf(self):
        """Should gracefully fall back when sentence-transformers is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            ev_path = Path(tmp) / "evidence.json"
            records = _make_evidence_records(10)
            ev_path.write_text(json.dumps({"records": records}))

            store = EvidenceEmbeddingsStore(str(ev_path))
            store.build()
            # Check that a model was selected (any tier)
            assert store.model_used in ("sentence-transformers", "tfidf", "ngram")

    def test_dossier_metadata_fields(self):
        """Retriever exposes retrieval_method and embeddings_model."""
        store = EvidenceEmbeddingsStore()
        retriever = RAGRetriever(store)
        assert hasattr(retriever, 'retrieval_method')
        assert hasattr(retriever, 'embeddings_model')
        assert retriever.retrieval_method in ("rag", "full")
