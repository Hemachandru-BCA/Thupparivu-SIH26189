"""
services_intel.py
-----------------
Lazily-instantiated shared singletons for the deeper intelligence engines
(hypothesis engine, temporal graph, link predictor, hidden-intermediary
detector, contradiction detector, model registry).  Each is cached per
artifact file (path + mtime) so a pipeline re-run invalidates automatically.

These engines are expensive to build, so we never rebuild them per request.

All objects here are ANALYTICAL: every output is an inference/hypothesis
with evidence references, never an enforcement recommendation.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import networkx as nx

from src.api import services
from src.domain.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _mtime(path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


class _IntCached:
    """mtime-keyed lazy cache with a graph-pkl dependency key.

    The cache key combines graph.pkl mtime (the underlying data) with an
    optional extra key component (e.g. an engine version) so engines are
    rebuilt exactly when the source graph changes.
    """

    def __init__(self) -> None:
        self._value: Any = None
        self._key: Optional[tuple] = None

    def get(self, key_path, builder, extra: Any = None):
        key = (_mtime(key_path), extra)
        if self._value is None or self._key != key:
            self._value = builder()
            self._key = key
        return self._value


_cache_temporal = _IntCached()
_cache_hypothesis = _IntCached()
_cache_link = _IntCached()
_cache_ghost_detector = _IntCached()
_registry: Optional[ModelRegistry] = None
_registry_lock = threading.Lock()


def temporal_graph() -> Any:
    """The TemporalMultilayerGraph wrapper (indexed once per graph.pkl)."""
    from src.graph.temporal_graph import TemporalMultilayerGraph

    pkl = services.load_graph()
    return _cache_temporal.get(
        services.paths.GRAPH_PKL_PATH,
        lambda: TemporalMultilayerGraph(pkl),
    )


def hypothesis_engine() -> Any:
    """Preconfigured HypothesisEngine over the current graph."""
    from src.investigation.hypothesis_engine import HypothesisEngine

    pkl = services.load_graph()
    return _cache_hypothesis.get(
        services.paths.GRAPH_PKL_PATH,
        lambda: HypothesisEngine(pkl, temporal_graph=temporal_graph()),
    )


def link_engine() -> Any:
    """Multi-model LinkPredictionEngine (embeddings + temporal + supervised)."""
    from src.ml.link_prediction_engine import LinkPredictionEngine

    return _cache_link.get(
        services.paths.GRAPH_PKL_PATH,
        lambda: LinkPredictionEngine(seed=42),
    )


def hidden_intermediary_detector() -> Any:
    """HiddenIntermediaryDetector fitted on the current graph."""
    from src.ml.hidden_intermediary import HiddenIntermediaryDetector

    pkl = services.load_graph()
    return _cache_ghost_detector.get(
        services.paths.GRAPH_PKL_PATH,
        lambda: HiddenIntermediaryDetector(seed=42).fit(pkl),
    )


def model_registry() -> ModelRegistry:
    """Single shared ModelRegistry (JSON-backed, thread-safe)."""
    global _registry
    with _registry_lock:
        if _registry is None:
            from src.api import paths as api_paths

            _registry = ModelRegistry(api_paths.GRAPH_OUTPUT_DIR / "model_registry.json")
        return _registry