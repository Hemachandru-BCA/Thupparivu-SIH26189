"""
ml/supervised_link_predictor.py
-------------------------------
Level 3 — supervised link prediction (Phase 4).

Edge features built from:

* common neighbors               (raw + normalized)
* shortest path length
* Jaccard
* Adamic-Adar
* degree / betweenness / pagerank of endpoints
* community similarity           (same/different)
* embedding similarity
* temporal overlap               (when a TemporalMultilayerGraph is supplied)
* shared evidence / identifiers
* interaction frequency

Models (lightweight first):

* Logistic Regression        (sklearn, optional)
* Random Forest              (sklearn, optional)
* Gradient Boosting          (sklearn, optional)
* Pure-Python Logistic Regression fallback (no sklearn)

The ``fit`` method accepts an ordered (X, y) train set; the caller decides
how to construct it (with proper temporal train/val/test separation).
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Hashable, List, Optional, Sequence, Tuple

import networkx as nx

from src.graph.temporal_features import FEATURE_NAMES, TemporalFeatureEngine

logger = logging.getLogger(__name__)

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

    _HAS_SKLEARN = True
except ImportError:  # pragma: no cover
    _HAS_SKLEARN = False


# --------------------------------------------------------------------------- #
# Pure-Python logistic regression (fallback + lightweight mode)
# --------------------------------------------------------------------------- #

class NumpyLogisticRegression:
    """Gradient-descent logistic regression on numpy arrays (no sklearn)."""

    def __init__(self, lr: float = 0.1, epochs: int = 200, l2: float = 1e-3,
                 seed: int = 42) -> None:
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self.seed = seed
        self.weights: Optional[Any] = None
        self.bias: float = 0.0

    def fit(self, X: Any, y: Any) -> "NumpyLogisticRegression":
        import numpy as np
        rng = np.random.default_rng(self.seed)
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        n, d = X.shape
        self.weights = rng.normal(0, 0.01, d)
        self.bias = 0.0
        for _ in range(self.epochs):
            logits = X @ self.weights + self.bias
            probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))
            grad_w = (X.T @ (probs - y)) / n + self.l2 * self.weights
            grad_b = float(np.mean(probs - y))
            self.weights -= self.lr * grad_w
            self.bias -= self.lr * grad_b
        return self

    def predict_proba(self, X: Any) -> List[float]:
        import numpy as np
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        logits = X @ self.weights + self.bias
        return (1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))).reshape(-1).tolist()

    def predict(self, X: Any) -> List[int]:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


# --------------------------------------------------------------------------- #
# Supervised link predictor
# --------------------------------------------------------------------------- #

class SupervisedLinkPredictor:
    """Feature-vector link predictor with sklearn or numpy fallback."""

    MODEL_KINDS = {
        "logistic": "LogisticRegression",
        "random_forest": "RandomForestClassifier",
        "gradient_boosting": "GradientBoostingClassifier",
        "numpy_logistic": "NumpyLogisticRegression",
    }

    def __init__(self, model_kind: str = "logistic", seed: int = 42) -> None:
        if model_kind not in self.MODEL_KINDS:
            raise ValueError(f"unknown model kind: {model_kind}")
        if model_kind != "numpy_logistic" and not _HAS_SKLEARN:
            logger.warning("sklearn unavailable; using numpy logistic fallback")
            model_kind = "numpy_logistic"
        self.model_kind = model_kind
        self.seed = seed
        self._model = None
        self.feature_names = list(FEATURE_NAMES)

    # ------------------------------------------------------------------ #
    def _make_model(self):
        if self.model_kind == "logistic":
            return LogisticRegression(max_iter=1000, random_state=self.seed)
        if self.model_kind == "random_forest":
            return RandomForestClassifier(
                n_estimators=100, max_depth=8, random_state=self.seed, n_jobs=-1)
        if self.model_kind == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=100, max_depth=3, random_state=self.seed)
        return NumpyLogisticRegression(seed=self.seed)

    # ------------------------------------------------------------------ #
    def fit(self, X: Sequence[Sequence[float]],
            y: Sequence[int]) -> "SupervisedLinkPredictor":
        if len(X) == 0:
            raise ValueError("empty training set")
        self._model = self._make_model()
        self._model.fit(X, y)
        return self

    def predict_proba(self, X: Sequence[Sequence[float]]) -> List[float]:
        if self._model is None:
            raise RuntimeError("call fit() first")
        raw = self._model.predict_proba(X)
        # sklearn returns [[p0, p1], ...]; numpy fallback returns [p1, ...]
        if raw and isinstance(raw[0], (list, tuple)):
            return [float(r[1]) for r in raw]
        return [float(p) for p in raw]

    def predict(self, X: Sequence[Sequence[float]]) -> List[int]:
        probs = self.predict_proba(X)
        return [1 if p >= 0.5 else 0 for p in probs]

    # ------------------------------------------------------------------ #
    def feature_importance(self) -> Dict[str, float]:
        """Expose model-agnostic feature importance (if available)."""
        if self._model is None:
            return {}
        if hasattr(self._model, "coef_"):
            coef = [float(c) for c in self._model.coef_[0]]
            return dict(zip(self.feature_names, coef))
        if hasattr(self._model, "feature_importances_"):
            return dict(zip(self.feature_names,
                            [float(v) for v in self._model.feature_importances_]))
        if hasattr(self._model, "weights") and self._model.weights is not None:
            import numpy as np
            return dict(zip(self.feature_names,
                            [float(v) for v in np.asarray(self._model.weights).reshape(-1)]))
        return {}

    # ------------------------------------------------------------------ #
    def score(self, X: Sequence[Sequence[float]],
              y: Sequence[int]) -> Dict[str, float]:
        """Accuracy (cheap; full metrics live in the evaluation layer)."""
        preds = self.predict(X)
        correct = sum(1 for p, t in zip(preds, y) if p == t)
        return {"accuracy": correct / len(y) if y else 0.0}