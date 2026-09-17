"""
xai/embeddings_store.py
-----------------------
Evidence embeddings store with sentence-transformers / TF-IDF / n-gram fallback.

Builds and caches embeddings for evidence records.  Supports:
  Priority 1: sentence-transformers (paraphrase-MiniLM-L6-v2, CPU only)
  Priority 2: TF-IDF vectorization (sklearn)
  Priority 3: character n-gram bag-of-words (pure numpy)
"""

from __future__ import annotations

import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDINGS_PATH = Path("data/exports/evidence_embeddings.npy")
MAPPING_PATH = Path("data/exports/evidence_embeddings_meta.json")


class EvidenceEmbeddingsStore:
    """Builds and queries evidence embeddings with multi-tier fallback."""

    def __init__(self, evidence_path: str = "data/exports/evidence_index.json"):
        self.evidence_path = Path(evidence_path)
        self._records: Optional[List[Dict[str, Any]]] = None
        self._embeddings: Optional[np.ndarray] = None
        self._id_to_idx: Dict[str, int] = {}
        self._model: Any = None
        self._model_name: str = "unknown"
        self._built = False
        self._built_at: Optional[str] = None

    @property
    def built(self) -> bool:
        return self._built and self._embeddings is not None

    @property
    def model_used(self) -> str:
        return self._model_name

    @property
    def record_count(self) -> int:
        return len(self._records) if self._records else 0

    def _load_evidence(self) -> List[Dict[str, Any]]:
        if not self.evidence_path.exists():
            return []
        data = json.loads(self.evidence_path.read_text())
        records = data.get("records", data) if isinstance(data, dict) else data
        return records

    def build(self) -> None:
        """Build embeddings index and persist to disk."""
        self._records = self._load_evidence()
        if not self._records:
            logger.warning("No evidence records to embed")
            self._built = True
            return

        texts = [r.get("text_excerpt", r.get("text_summary", "")) for r in self._records]
        texts = [t if isinstance(t, str) else str(t) for t in texts]

        self._id_to_idx = {r["evidence_id"]: i for i, r in enumerate(self._records)}

        t0 = time.time()
        self._init_model()
        self._embeddings = self._encode(texts)
        elapsed = time.time() - t0

        # Persist
        EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(EMBEDDINGS_PATH), self._embeddings)
        meta = {
            "model": self._model_name,
            "record_count": len(self._records),
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dimensions": int(self._embeddings.shape[1]) if self._embeddings.ndim > 1 else 0,
        }
        MAPPING_PATH.write_text(json.dumps(meta, indent=2))
        self._built = True
        self._built_at = meta["built_at"]
        logger.info("Built embeddings: %d records, %s model, %.1fs",
                     len(self._records), self._model_name, elapsed)

    def load(self) -> bool:
        """Load persisted embeddings. Returns True if loaded successfully."""
        if EMBEDDINGS_PATH.exists() and MAPPING_PATH.exists():
            self._embeddings = np.load(str(EMBEDDINGS_PATH))
            meta = json.loads(MAPPING_PATH.read_text())
            self._model_name = meta.get("model", "unknown")
            self._built_at = meta.get("built_at")
            self._records = self._load_evidence()
            self._id_to_idx = {r["evidence_id"]: i for i, r in enumerate(self._records)}
            self._built = True
            return True
        return False

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text using the same model as the corpus."""
        if self._model is None:
            self._init_model()
        return self._encode_single(text)

    def top_k(self, query_text: str, k: int = 20,
              filter_entity_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Find top-k most similar evidence records."""
        if not self.built:
            if not self.load():
                return []

        query_emb = self.embed(query_text)

        # Compute similarities
        if self._embeddings.ndim == 1:
            return []
        sims = np.dot(self._embeddings, query_emb) / (
            np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-10
        )

        # Apply entity filter
        if filter_entity_ids:
            filter_set = set(filter_entity_ids)
            valid_mask = np.zeros(len(self._records), dtype=bool)
            for i, r in enumerate(self._records):
                subjects = set(r.get("subject_ids", []))
                if subjects & filter_set:
                    valid_mask[i] = True
            sims = sims * valid_mask + (-1) * (~valid_mask)

        # Top-k indices
        top_idx = np.argsort(sims)[::-1][:k]

        results = []
        for idx in top_idx:
            if idx < len(self._records):
                rec = dict(self._records[idx])
                rec["relevance_score"] = float(sims[idx])
                results.append(rec)
        return results

    # ---- Model initialization ----

    def _init_model(self):
        """Try to initialize the best available embedding model."""
        # Priority 1: sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
            self._model_name = "sentence-transformers"
            return
        except (ImportError, Exception) as e:
            logger.info("sentence-transformers not available: %s", e)

        # Priority 2: sklearn TF-IDF
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._model = "tfidf"
            self._model_name = "tfidf"
            return
        except ImportError:
            pass

        # Priority 3: n-gram bag of words (pure numpy)
        self._model = "ngram"
        self._model_name = "ngram"

    def _encode(self, texts: List[str]) -> np.ndarray:
        # _model_name is set by _init_model(); route accordingly
        if self._model_name == "sentence-transformers":
            return self._model.encode(texts, show_progress_bar=False, device="cpu")
        elif self._model_name == "tfidf":
            return self._encode_tfidf(texts)
        else:
            return self._encode_ngram(texts)

    def _encode_single(self, text: str) -> np.ndarray:
        if self._model_name == "sentence-transformers":
            return self._model.encode([text], device="cpu")[0]
        elif self._model_name == "tfidf":
            if hasattr(self, '_tfidf_vectorizer'):
                return self._tfidf_vectorizer.transform([text]).toarray()[0]
            return np.zeros(1)
        else:
            return self._ngram_encode(text)

    def _encode_tfidf(self, texts: List[str]) -> np.ndarray:
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._tfidf_vectorizer = TfidfVectorizer(
            max_features=1024, analyzer="word", ngram_range=(1, 2),
            sublinear_tf=True
        )
        return self._tfidf_vectorizer.fit_transform(texts).toarray()

    def _encode_ngram(self, texts: List[str]) -> np.ndarray:
        """Character n-gram bag of words (pure numpy fallback)."""
        vocab: Dict[str, int] = {}
        ngram_size = 3
        max_vocab = 2048

        # Build vocabulary
        for text in texts:
            for i in range(len(text) - ngram_size + 1):
                ng = text[i:i + ngram_size].lower()
                if ng not in vocab:
                    vocab[ng] = len(vocab)
                if len(vocab) >= max_vocab:
                    break
            if len(vocab) >= max_vocab:
                break

        self._ngram_vocab = vocab

        # Encode
        result = np.zeros((len(texts), len(vocab)), dtype=np.float32)
        for i, text in enumerate(texts):
            for j in range(len(text) - ngram_size + 1):
                ng = text[j:j + ngram_size].lower()
                idx = vocab.get(ng)
                if idx is not None:
                    result[i, idx] += 1.0
            # L2 normalize
            norm = np.linalg.norm(result[i])
            if norm > 0:
                result[i] /= norm
        return result

    def _ngram_encode(self, text: str) -> np.ndarray:
        if not hasattr(self, '_ngram_vocab'):
            return np.zeros(1)
        vocab = self._ngram_vocab
        ngram_size = 3
        result = np.zeros(len(vocab), dtype=np.float32)
        for j in range(len(text) - ngram_size + 1):
            ng = text[j:j + ngram_size].lower()
            idx = vocab.get(ng)
            if idx is not None:
                result[idx] += 1.0
        norm = np.linalg.norm(result)
        if norm > 0:
            result /= norm
        return result
