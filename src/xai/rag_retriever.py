"""
xai/rag_retriever.py
--------------------
Hybrid RAG retrieval for dossier generation (Phase 6 / Task 14).

Combines semantic embeddings + recency bias to retrieve the most
relevant evidence records for a given subject and query.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from src.xai.embeddings_store import EvidenceEmbeddingsStore

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Hybrid RAG retriever combining semantic + recency signals."""

    def __init__(self, embeddings_store: Optional[EvidenceEmbeddingsStore] = None):
        self._store = embeddings_store or EvidenceEmbeddingsStore()
        self._use_rag = self._store.load()
        self._last_count = 0

    @property
    def retrieval_method(self) -> str:
        return "rag" if self._use_rag else "full"

    @property
    def embeddings_model(self) -> str:
        return self._store.model_used if self._use_rag else "none"

    @property
    def evidence_retrieved_count(self) -> int:
        return self._last_count

    def retrieve_for_dossier(
        self,
        subject_id: str,
        query: str,
        evidence_store: Any = None,
        max_evidence: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve evidence for a dossier using hybrid RAG.

        A. Semantic retrieval via embeddings (top-k by cosine similarity)
        B. Recency retrieval (top-5 most recent for subject)
        C. Merge, deduplicate, sort by (relevance * 0.6 + recency * 0.4)
        """
        if not self._use_rag:
            return self._fallback_retrieval(subject_id, evidence_store, max_evidence)

        # A. Semantic retrieval
        filter_ids = self._get_linked_entity_ids(subject_id, evidence_store)
        semantic_results = self._store.top_k(
            query, k=max_evidence, filter_entity_ids=filter_ids
        )

        # B. Recency retrieval — top 5 most recent
        recency_results = self._get_recent_evidence(subject_id, evidence_store, limit=5)

        # C. Merge and deduplicate
        seen_ids: Set[str] = set()
        merged: List[Dict[str, Any]] = []

        # Add semantic results first (they have relevance_score)
        for rec in semantic_results:
            eid = rec.get("evidence_id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                rec["source_signal"] = "semantic"
                merged.append(rec)

        # Add recency results with recency score
        now = datetime.now(timezone.utc)
        for rec in recency_results:
            eid = rec.get("evidence_id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                ts_str = rec.get("timestamp", "")
                recency_score = 1.0
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        days_ago = max(1, (now - ts).days)
                        recency_score = 1.0 / days_ago
                    except (ValueError, TypeError):
                        pass
                rec["relevance_score"] = rec.get("relevance_score", 0.0)
                rec["recency_score"] = recency_score
                rec["source_signal"] = "recency"
                merged.append(rec)

        # Sort: relevance * 0.6 + recency * 0.4
        def sort_key(rec):
            rel = rec.get("relevance_score", 0.0)
            rec_score = rec.get("recency_score", 0.0)
            return -(rel * 0.6 + rec_score * 0.4)

        merged.sort(key=sort_key)
        result = merged[:max_evidence]
        self._last_count = len(result)
        return result

    def _get_linked_entity_ids(self, subject_id: str, evidence_store: Any) -> List[str]:
        """Get entity IDs linked to subject from evidence store."""
        ids = [subject_id]
        if evidence_store and hasattr(evidence_store, 'get_evidence_for_node'):
            try:
                records = evidence_store.get_evidence_for_node(subject_id, limit=50)
                for r in records:
                    for sid in getattr(r, 'subject_ids', []):
                        if sid != subject_id:
                            ids.append(sid)
            except Exception:
                pass
        return list(set(ids))

    def _get_recent_evidence(self, subject_id: str, evidence_store: Any,
                              limit: int = 5) -> List[Dict[str, Any]]:
        """Get most recent evidence records for a subject."""
        if evidence_store and hasattr(evidence_store, 'get_evidence_for_node'):
            try:
                records = evidence_store.get_evidence_for_node(subject_id, limit=limit)
                return [
                    {
                        "evidence_id": getattr(r, 'evidence_id', ''),
                        "timestamp": getattr(r, 'timestamp', ''),
                        "text_excerpt": getattr(r, 'text_excerpt', ''),
                        "subject_ids": getattr(r, 'subject_ids', []),
                    }
                    for r in records
                ]
            except Exception:
                pass
        return []

    def _fallback_retrieval(self, subject_id: str, evidence_store: Any,
                             max_evidence: int) -> List[Dict[str, Any]]:
        """Fallback to full-context retrieval when embeddings not available."""
        logger.warning("RAG fallback: using full-context retrieval for %s", subject_id)
        if evidence_store and hasattr(evidence_store, 'get_evidence_for_node'):
            try:
                records = evidence_store.get_evidence_for_node(subject_id, limit=max_evidence)
                return [
                    {
                        "evidence_id": getattr(r, 'evidence_id', ''),
                        "timestamp": getattr(r, 'timestamp', ''),
                        "text_excerpt": getattr(r, 'text_excerpt', ''),
                        "subject_ids": getattr(r, 'subject_ids', []),
                        "relevance_score": 0.5,
                        "recency_score": 0.5,
                        "source_signal": "full_context",
                    }
                    for r in records
                ]
            except Exception:
                pass
        return []
