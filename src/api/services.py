"""
services.py
-----------
Lazily-instantiated shared singletons for the API layer: the knowledge
graph, the evidence index, the simulation context, and the evidence-index
builder.  Everything is cached per artifact file (path + mtime) so a
pipeline re-run invalidates automatically.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, Optional

from pathlib import Path

import networkx as nx

from src.api import paths

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = int(os.environ.get("SENTINELGRAPH_MAX_UPLOAD_BYTES", 2 * 1024 * 1024))
DEFAULT_MAX_NODES = int(os.environ.get("SENTINELGRAPH_MAX_NODES", 5000))

_lock = threading.Lock()


def _mtime(path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


class _Cached:
    """mtime-keyed lazy cache."""

    def __init__(self) -> None:
        self._value: Any = None
        self._key: Optional[tuple] = None
        self._lock = threading.Lock()

    def get(self, path, builder):
        key = (str(path), _mtime(path))
        with self._lock:
            if self._value is None or self._key != key:
                self._value = builder(path)
                self._key = key
                logger.info("cache populated for %s", path)
            return self._value


_cache_graph = _Cached()
_cache_graph_doc = _Cached()
_cache_evidence = _Cached()
_cache_sim_context = _Cached()
_cache_ghost_doc = _Cached()


def load_graph() -> nx.MultiDiGraph:
    """The pickled knowledge graph (raises FileNotFoundError if not built)."""
    if not paths.GRAPH_PKL_PATH.exists():
        raise FileNotFoundError(
            f"graph artifact missing at {paths.GRAPH_PKL_PATH}. "
            "Run POST /api/pipeline/graph first."
        )
    return _cache_graph.get(paths.GRAPH_PKL_PATH, _load_pkl)


def _load_pkl(path) -> nx.MultiDiGraph:
    import pickle

    with open(path, "rb") as fh:
        return pickle.load(fh)


def _load_json(path):
    return json.loads(Path(path).read_text())


def graph_document() -> Dict[str, Any]:
    """The serialized graph_data.json document."""
    if not paths.GRAPH_DATA_PATH.exists():
        raise FileNotFoundError(
            f"graph data missing at {paths.GRAPH_DATA_PATH}. "
            "Run POST /api/pipeline/graph first."
        )
    return _cache_graph_doc.get(paths.GRAPH_DATA_PATH, _load_json)


def evidence_store():
    """The evidence index (builds it on first use if not on disk)."""
    if not paths.EVIDENCE_INDEX_PATH.exists():
        build_evidence_index()
    from src.xai.evidence_tracer import EvidenceStore

    return _cache_evidence.get(paths.EVIDENCE_INDEX_PATH, EvidenceStore.from_json)


def ghost_document() -> Dict[str, Any]:
    if not paths.GHOST_PREDICTIONS_PATH.exists():
        raise FileNotFoundError(
            f"ghost predictions missing at {paths.GHOST_PREDICTIONS_PATH}. "
            "Run POST /api/pipeline/ghosts first."
        )
    return _cache_ghost_doc.get(paths.GHOST_PREDICTIONS_PATH, _load_json)


def simulation_context() -> Dict[str, Any]:
    """Precomputed baseline context for counterfactual simulations."""
    graph = load_graph()
    from src.graph.simulation import build_simulation_context

    key_path = paths.GRAPH_PKL_PATH
    return _cache_sim_context.get(
        key_path,
        lambda _p: build_simulation_context(graph, new_broker_sample=150),
    )


def build_evidence_index() -> int:
    """(Re)build the evidence index from current artifacts. Returns count."""
    with _lock:
        from src.xai.evidence_tracer import build_store_from_artifacts

        store = build_store_from_artifacts(
            persons_csv=paths.PERSONS_CSV,
            calls_csv=paths.CALLS_CSV,
            transactions_csv=paths.TRANSACTIONS_CSV,
            meetings_csv=paths.MEETINGS_CSV,
            cleaned_records_path=paths.CLEANED_RECORDS_PATH,
            triplets_path=paths.GRAPH_TRIPLETS_PATH,
            graph_data_path=paths.GRAPH_DATA_PATH if paths.GRAPH_DATA_PATH.exists() else None,
            ghost_predictions_path=(
                paths.GHOST_PREDICTIONS_PATH
                if paths.GHOST_PREDICTIONS_PATH.exists()
                else None
            ),
        )
        store.to_json(paths.EVIDENCE_INDEX_PATH)
        return store.count()
