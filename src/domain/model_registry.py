"""
domain/model_registry.py
------------------------
Model run registry (Phase 1, requirement 6).

Every ML/AI execution in the system should record:

* model name + version
* configuration
* input dataset / version
* timestamp
* random seed
* metrics
* output ids

The registry is a lightweight JSON-backed store (deterministic, no heavy
infrastructure).  It also exposes a capability matrix so the API can answer
``GET /models`` and ``GET /model-runs``.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.domain.models import ModelRun, ModelRunRecord

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = "data/exports/model_registry.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelRegistry:
    """JSON-backed registry of model definitions and completed runs."""

    def __init__(self, path: str | Path = DEFAULT_REGISTRY_PATH) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._runs: Dict[str, ModelRunRecord] = {}
        self._models: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if not self.path.exists():
            self._seed_default_models()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            runs = data.get("runs") or []
            for run in runs:
                try:
                    rec = ModelRunRecord(**run)
                    self._runs[rec.run_id] = rec
                except Exception:  # pragma: no cover - defensive
                    logger.warning("Skipping malformed model-run record")
            self._models = data.get("models") or {}
            if not self._models:
                self._seed_default_models()
        except Exception:
            logger.warning("Could not load model registry at %s", self.path)
            self._seed_default_models()

    def _seed_default_models(self) -> None:
        """Seed standard Thupparivu analytical models into registry."""
        default_cards = [
            {
                "name": "thupparivu_ensemble_link_predictor",
                "version": "1.0.0",
                "description": "Multi-model link predictor: baselines + Node2Vec + GradientBoosting + LightGNN",
                "capabilities": ["link_prediction", "missing_relationship_detection"],
                "metadata": {"calibration": "isotonic", "disagreement_threshold": 0.20},
            },
            {
                "name": "burt_structural_hole_detector",
                "version": "1.0.0",
                "description": "Burt constraint + cross-community bridge detection for hidden intermediaries",
                "capabilities": ["ghost_node_detection", "hidden_intermediary_detection"],
                "metadata": {"temporal_window_days": 14},
            },
            {
                "name": "temporal_multilayer_graph_engine",
                "version": "2.0.0",
                "description": "Temporal point-in-time graph engine with strict no-leakage guarantees",
                "capabilities": ["temporal_snapshots", "graph_diff", "community_evolution"],
                "metadata": {"layers": ["COMMUNICATION", "FINANCIAL", "LOCATION", "ORGANIZATIONAL", "SOCIAL"]},
            },
            {
                "name": "counterfactual_intervention_engine",
                "version": "1.0.0",
                "description": "Counterfactual node/edge removal, entity merge/split and resilience simulation",
                "capabilities": ["counterfactual_analysis", "network_resilience"],
                "metadata": {"all_outputs_labelled": "HYPOTHETICAL"},
            },
            {
                "name": "hybrid_entity_resolver",
                "version": "1.0.0",
                "description": "6-stage entity resolution: deterministic -> fuzzy -> semantic -> graph-consistency",
                "capabilities": ["entity_resolution", "alias_resolution"],
                "metadata": {"algorithm": "complete-linkage-union-find"},
            },
        ]
        for c in default_cards:
            self._models[c["name"]] = {
                "name": c["name"],
                "latest_version": c["version"],
                "description": c["description"],
                "capabilities": c["capabilities"],
                "metadata": c["metadata"],
                "updated_at": _utcnow(),
            }
        try:
            self._persist()
        except Exception:
            pass

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        payload = {
            "models": self._models,
            "runs": [r.model_dump(mode="json") for r in sorted(
                self._runs.values(), key=lambda r: r.started_at)],
        }
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ------------------------------------------------------------------ #
    # Model definitions
    # ------------------------------------------------------------------ #
    def register_model(self, name: str, version: str,
                       description: str = "",
                       capabilities: List[str] | None = None,
                       metadata: Dict[str, Any] | None = None) -> None:
        with self._lock:
            self._models[name] = {
                "name": name,
                "latest_version": version,
                "description": description,
                "capabilities": capabilities or [],
                "metadata": metadata or {},
                "updated_at": _utcnow(),
            }
            self._persist()

    def get_model(self, name: str) -> Optional[Dict[str, Any]]:
        return self._models.get(name)

    def list_models(self) -> List[Dict[str, Any]]:
        return list(self._models.values())

    # ------------------------------------------------------------------ #
    # Runs
    # ------------------------------------------------------------------ #
    def start_run(self, model_name: str, model_version: str,
                  config: Dict[str, Any] | None = None,
                  dataset_version: str | None = None,
                  seed: int | None = None,
                  tags: List[str] | None = None) -> ModelRunRecord:
        run = ModelRunRecord(
            run_id=ModelRun(model_name=model_name, model_version=model_version).run_id,
            model=model_name,
            version=model_version,
            config=config or {},
            dataset_version=dataset_version,
            started_at=_utcnow(),
            seed=seed,
            status="RUNNING",
            tags=tags or [],
        )
        with self._lock:
            self._runs[run.run_id] = run
            self._persist()
        return run

    def finish_run(self, run_id: str, metrics: Dict[str, Any],
                   outputs: List[str] | None = None,
                   status: str = "COMPLETED") -> Optional[ModelRunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.metrics = metrics
            run.outputs = outputs or []
            run.status = status
            run.finished_at = _utcnow()
            self._persist()
            return run

    def record(self, run: ModelRun, outputs: List[str] | None = None) -> ModelRunRecord:
        """One-shot convenience: record a completed run."""
        rec = ModelRunRecord(
            run_id=run.run_id,
            model=run.model_name,
            version=run.model_version,
            config=run.configuration,
            dataset_version=run.input_dataset_version,
            started_at=run.timestamp,
            finished_at=_utcnow(),
            seed=run.random_seed,
            metrics=run.metrics,
            outputs=outputs or run.output_ids,
            status=run.status,
        )
        with self._lock:
            self._runs[rec.run_id] = rec
            self._persist()
        return rec

    def get_run(self, run_id: str) -> Optional[ModelRunRecord]:
        return self._runs.get(run_id)

    def list_runs(self, model: str | None = None,
                  limit: int = 100) -> List[ModelRunRecord]:
        runs = sorted(self._runs.values(), key=lambda r: r.started_at, reverse=True)
        if model:
            runs = [r for r in runs if r.model == model]
        return runs[:limit]

    # ------------------------------------------------------------------ #
    def to_json(self) -> Dict[str, Any]:
        return {
            "models": self._models,
            "runs": [r.model_dump(mode="json") for r in self._runs.values()],
        }


# Global registry (lazy singleton; safe for the demo's single-process use)
_REGISTRY: Optional[ModelRegistry] = None


def get_registry(path: str | Path = DEFAULT_REGISTRY_PATH) -> ModelRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ModelRegistry(path)
    return _REGISTRY