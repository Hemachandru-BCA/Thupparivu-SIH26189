"""
graph/ml/classifier.py
----------------------
Offline-trainsable, checkpointed ghost-coordinator classifier.

Design constraints (SentinelGraph Task 1):

* **Zero new dependencies** — the offline demo must run with no GPU and no
  extra installs.  Instead of XGBoost/LightGBM, this module implements a
  small gradient-boosted decision tree (numpy only) plus a logistic-regression
  stacker.  It gives interpretable feature importance like XGBoost and needs
  only ``numpy``/``networkx`` already present.
* **Checkpointed** — ``save()``/``load()`` write a versioned pickle under
  ``data/models/ghost_classifier.pkl``; model loads lazily.
* **Ensemble** — the hand-written heuristic score remains an input feature;
  the classifier output is fused with the heuristic via a small logistic
  stacker so domain knowledge is never discarded, just reweighted.
* **Graceful fallback** — if no model file exists, callers fall back to the
  pure heuristic (never hard-fail).

API mirrors the requested ``train() / predict() / load() / save()``.
"""

from __future__ import annotations

import json
import logging
import pickle
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from src.graph.ml.feature_extraction import FEATURE_COLUMNS, N_FEATURES
from src.graph.ml.synthetic_graphs import generate_graph_bundle
from src.graph.ml.structural_propagation import StructuralPropagationModel

logger = logging.getLogger(__name__)

MODEL_VERSION = "ghost-classifier-v1"
MODEL_PATH = Path("data/models/ghost_classifier.pkl")


@dataclass
class GhostClassifier:
    """A pure-Python gradient-boosted tree ensemble with a logistic stacker.

    The primary model is a collection of shallow decision trees (one per
    boosting round), each fit on a weighted residual.  Prediction = sigmoid of
    the sum of tree outputs, then re-scaled through a fitted logistic layer
    that also absorbs the heuristic prior.
    """

    n_estimators: int = 40
    max_depth: int = 3
    learning_rate: float = 0.08
    min_samples_leaf: int = 4
    subsample: float = 0.8          # per-tree row subsampling (bagging)
    feature_fraction: float = 0.8   # per-tree feature subsampling
    seed: int = 42

    trees: List[Dict[str, Any]] = field(default_factory=list)
    stacker: Optional[np.ndarray] = None      # (3,) logistic weights [gbm, heuristic, propagation]
    propagation_model: Optional[StructuralPropagationModel] = None
    feature_importance: Dict[str, float] = field(default_factory=dict)
    classes_: List[int] = field(default_factory=lambda: [0, 1])
    version: str = MODEL_VERSION
    trained_on_features: List[str] = field(default_factory=lambda: list(FEATURE_COLUMNS))

    # ------------------------------------------------------------------ #
    # training
    # ------------------------------------------------------------------ #
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        heuristic_scores: Optional[np.ndarray] = None,
    ) -> "GhostClassifier":
        """Fit the ensemble.

        ``X`` is (n_samples, n_features) ordered by ``FEATURE_COLUMNS``.
        ``heuristic_scores`` (optional) is the per-sample heuristic prior used
        as the stacker's second input.
        """
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        n = len(X)
        if n == 0:
            raise ValueError("cannot fit on empty matrix")

        rng = random.Random(self.seed)
        # class imbalance: coordinators are rare; start predictions at the
        # positive-class prior so trees focus on structure
        prior = float(np.mean(y))
        current = np.full(n, _logit(max(min(prior, 0.99), 0.01)))

        self.trees = []
        for _ in range(self.n_estimators):
            # residual gradient for log-loss
            p = _sigmoid(current)
            grad = p - y
            hess = p * (1.0 - p) + 1e-9

            # subsample rows and features
            n_use = max(8, int(n * self.subsample))
            idx = rng.sample(range(n), n_use)
            n_feat = max(2, int(N_FEATURES * self.feature_fraction))
            feat_idx = rng.sample(range(N_FEATURES), n_feat)

            tree = _fit_tree(
                X[idx][:, feat_idx], grad[idx], hess[idx],
                depth=0, max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
            )
            if tree is None:
                continue
            _scale_tree_leaves(tree, self.learning_rate)
            tree["feature_idx"] = feat_idx
            self.trees.append(tree)

            # update predictions on the logit scale (additive boosting)
            current += _predict_trees(X, self.trees) * 1.0

        # logistic stacker: [gbm, heuristic, propagation] -> prob
        gbm_score = _predict_trees(X, self.trees)
        if heuristic_scores is not None:
            h = np.asarray(heuristic_scores, dtype=np.float64)
        else:
            h = np.zeros(n)
        # placeholder: propagation scores will be added via fit_propagation
        self.stacker = _fit_logistic_stack(gbm_score, h, y, seed=self.seed)

        # feature importance: mean |leaf value| weighted by leaf size
        self.feature_importance = _feature_importance(self.trees, N_FEATURES)
        return self

    def fit_propagation(
        self,
        graphs: List["nx.DiGraph"],
        labels_per_graph: List[Dict[str, int]],
        nodes_per_graph: List[List],
        X_train: Optional[np.ndarray] = None,
        y_train: Optional[np.ndarray] = None,
        h_train: Optional[np.ndarray] = None,
    ) -> None:
        """Train the structural-propagation second signal and **re-fit the
        stacker** on [gbm, heuristic, propagation].

        Caller must pass the training matrices (X_train, y_train) together
        with the list of training graphs and per-graph node orderings so that
        the stacker can be updated with all three signals.
        """
        if not graphs:
            return

        # ── train the linear propagation model ─────────────────────────
        model = StructuralPropagationModel()
        for G, lbls in zip(graphs, labels_per_graph):
            if lbls:
                model.fit(G, lbls)
        self.propagation_model = model

        # ── re-fit stacker on 3 signals ────────────────────────────────
        if (X_train is not None and y_train is not None
                and nodes_per_graph is not None):
            gbm_score = _predict_trees(X_train, self.trees)
            h = np.zeros(len(y_train)) if h_train is None else np.asarray(h_train, dtype=np.float64)
            # Compute propagation scores for every training node
            prop_scores = _propagation_scores_for_training(
                graphs, nodes_per_graph, model
            )
            self.stacker = _fit_logistic_stack(
                gbm_score, h, y_train,
                propagation=prop_scores,
                seed=self.seed,
            )

    # ------------------------------------------------------------------ #
    # prediction
    # ------------------------------------------------------------------ #
    def predict_proba(self, X: np.ndarray, heuristic_scores: Optional[np.ndarray] = None,
                      graph: Optional["nx.MultiDiGraph"] = None,
                      node_order: Optional[List] = None) -> np.ndarray:
        """Return positive-class probabilities in [0, 1].

        When a trained *propagation_model* is present and the caller supplies
        the ``graph`` plus ``node_order`` (matching rows of ``X``), the third
        stacker signal is computed automatically.
        """
        X = np.asarray(X, dtype=np.float64)
        gbm = _predict_trees(X, self.trees)
        if heuristic_scores is not None:
            h = np.asarray(heuristic_scores, dtype=np.float64)
        else:
            h = np.zeros(len(X))
        # propagation signal (3rd stacker input)
        prop = np.zeros(len(X))
        if self.propagation_model is not None and graph is not None and node_order is not None:
            raw = self.propagation_model.predict(graph)
            prop = np.array([raw.get(n, 0.5) for n in node_order], dtype=np.float64)
        if self.stacker is not None:
            # stacker = [gbm_w, heuristic_w, prop_w, bias]
            raw = (self.stacker[0] * gbm + self.stacker[1] * h
                   + self.stacker[2] * prop + self.stacker[3])
            return np.clip(_sigmoid(raw), 0.0, 1.0)
        return np.clip(_sigmoid(gbm), 0.0, 1.0)

    def predict(self, X: np.ndarray, threshold: float = 0.5, heuristic_scores: Optional[np.ndarray] = None) -> np.ndarray:
        return (self.predict_proba(X, heuristic_scores) >= threshold).astype(int)

    # ------------------------------------------------------------------ #
    # persistence
    # ------------------------------------------------------------------ #
    def save(self, path: Path | str = MODEL_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump(self, fh)
        logger.info("saved ghost classifier (version=%s) to %s", self.version, path)
        return path

    @staticmethod
    def load(path: Path | str = MODEL_PATH) -> Optional["GhostClassifier"]:
        path = Path(path)
        if not path.exists():
            return None
        try:
            with path.open("rb") as fh:
                obj = pickle.load(fh)
            if not isinstance(obj, GhostClassifier):
                logger.warning("artifact %s is not a GhostClassifier", path)
                return None
            return obj
        except Exception as exc:  # noqa: BLE001 - corrupt artifact
            logger.warning("cannot load ghost classifier from %s: %s", path, exc)
            return None


# --------------------------------------------------------------------------- #
# logistic helpers
# --------------------------------------------------------------------------- #

def _logit(p: float) -> float:
    return float(np.log(max(p, 1e-12) / max(1.0 - p, 1e-12)))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def _fit_logistic_stack(gbm: np.ndarray, h: np.ndarray, y: np.ndarray,
                        propagation: Optional[np.ndarray] = None,
                        seed: int = 42) -> np.ndarray:
    """Simple logistic regression via gradient descent on [gbm, h, prop, bias].

    If ``propagation`` is ``None``, the third column is zeros (backward
    compatible with the two-signal GBM+heuristic stacker).
    """
    n = len(gbm)
    if propagation is not None:
        prop = np.asarray(propagation, dtype=np.float64)
    else:
        prop = np.zeros(n)
    X = np.column_stack([gbm, h, prop, np.ones(n)])
    w = np.zeros(4)
    lr = 0.5
    for _ in range(200):
        p = _sigmoid(X @ w)
        grad = X.T @ (p - y) / n
        w -= lr * grad
        lr *= 0.995
    return w


# --------------------------------------------------------------------------- #
# decision trees
# --------------------------------------------------------------------------- #

def _fit_tree(
    X: np.ndarray,
    grad: np.ndarray,
    hess: np.ndarray,
    depth: int,
    max_depth: int,
    min_samples_leaf: int,
) -> Optional[Dict[str, Any]]:
    """Fit a single shallow regression tree on (grad, hess) with squared loss.

    Returns nested node dicts: ``{"feature": int, "threshold": float,
    "left": node, "right": node}`` or ``{"leaf": value}``.
    """
    n = len(X)
    total_g = float(grad.sum())
    total_h = float(hess.sum()) + 1e-9
    if depth >= max_depth or n < 2 * min_samples_leaf:
        leaf = -total_g / total_h
        return {"leaf": float(leaf)}

    best = None
    best_gain = 0.0
    n_features = X.shape[1]
    for f in range(n_features):
        order = np.argsort(X[:, f])
        xs = X[order, f]
        gs = grad[order]
        hs = hess[order]
        left_g = 0.0
        left_h = 1e-9
        for i in range(n - 1):
            left_g += gs[i]
            left_h += hs[i]
            if i + 1 < min_samples_leaf:
                continue
            if n - (i + 1) < min_samples_leaf:
                continue
            if xs[i] == xs[i + 1]:
                continue
            right_g = total_g - left_g
            right_h = total_h - left_h
            gain = (left_g * left_g / left_h) + (right_g * right_g / right_h) - (
                total_g * total_g / total_h
            )
            if gain > best_gain:
                best_gain = gain
                best = (f, (xs[i] + xs[i + 1]) / 2.0)

    if best is None:
        leaf = -total_g / total_h
        return {"leaf": float(leaf)}

    f, thr = best
    left_mask = X[:, f] <= thr
    right_mask = ~left_mask
    if left_mask.sum() < min_samples_leaf or right_mask.sum() < min_samples_leaf:
        return {"leaf": float(-total_g / total_h)}

    left = _fit_tree(X[left_mask], grad[left_mask], hess[left_mask],
                     depth + 1, max_depth, min_samples_leaf)
    right = _fit_tree(X[right_mask], grad[right_mask], hess[right_mask],
                      depth + 1, max_depth, min_samples_leaf)
    return {"feature": int(f), "threshold": float(thr), "left": left, "right": right}


def _predict_tree(x: np.ndarray, tree: Dict[str, Any]) -> float:
    if "leaf" in tree:
        return float(tree["leaf"])
    if x[tree["feature"]] <= tree["threshold"]:
        return _predict_tree(x, tree["left"])
    return _predict_tree(x, tree["right"])


def _predict_trees(X: np.ndarray, trees: Sequence[Dict[str, Any]]) -> np.ndarray:
    out = np.zeros(len(X), dtype=np.float64)
    for tree in trees:
        feat_idx = np.asarray(tree["feature_idx"], dtype=int)
        # trees store leaf values already multiplied by learning rate
        raw = np.array([_predict_tree(x[feat_idx], tree) for x in X])
        out += raw
    return out


def _feature_importance(trees: Sequence[Dict[str, Any]], n_features: int) -> Dict[str, float]:
    """Feature importance = sum of |leaf value| per feature, normalized."""
    importance = np.zeros(n_features)
    for tree in trees:
        feat_idx = np.asarray(tree["feature_idx"], dtype=int)
        for node in _walk_tree(tree):
            if "leaf" in node:
                continue
            fi = int(node["feature"])
            importance[feat_idx[fi]] += abs(float(node.get("leaf_gain", 0.0)))
        # simpler: credit the splitting feature with |threshold| difference
    # Walk actual splits:
    importance = np.zeros(n_features)
    for tree in trees:
        feat_idx = np.asarray(tree["feature_idx"], dtype=int)
        def walk(node: Dict[str, Any]) -> None:
            if "leaf" in node or "left" not in node:
                return
            fi = int(node["feature"])
            importance[feat_idx[fi]] += 1.0
            walk(node["left"])
            walk(node["right"])
        walk(tree)
    total = float(importance.sum())
    if total <= 0:
        return {col: 0.0 for col in FEATURE_COLUMNS}
    norm = importance / total
    return {col: float(norm[i]) for i, col in enumerate(FEATURE_COLUMNS)}


def _walk_tree(tree: Dict[str, Any]):
    yield tree
    if "left" in tree:
        yield from _walk_tree(tree["left"])
    if "right" in tree:
        yield from _walk_tree(tree["right"])


def _scale_tree_leaves(tree: Dict[str, Any], lr: float) -> None:
    """Recursively scale all leaf values inside a tree by ``lr``."""
    if "leaf" in tree:
        tree["leaf"] = float(tree["leaf"]) * lr
        return
    if "left" in tree:
        _scale_tree_leaves(tree["left"], lr)
        _scale_tree_leaves(tree["right"], lr)


# --------------------------------------------------------------------------- #
# end-to-end training entry point
# --------------------------------------------------------------------------- #

def train_from_generated_graphs(
    n_graphs: int = 40,
    base_seed: int = 1000,
    save_path: Path | str = MODEL_PATH,
) -> Tuple[GhostClassifier, Dict[str, Any]]:
    """Train the classifier on a bundle of varied synthetic graphs.

    Returns ``(model, metrics)``.  The graphs are split into train/eval by
    seed so the reported metrics come from graphs the model never saw.
    """
    bundle = generate_graph_bundle(n_graphs=n_graphs, base_seed=base_seed)
    rng = random.Random(base_seed)
    order = list(range(len(bundle)))
    rng.shuffle(order)
    n_train = max(2, int(len(bundle) * 0.8))
    train_idx = set(order[:n_train])
    eval_idx = set(order[n_train:])

    X_train, y_train, h_train = [], [], []
    X_eval, y_eval, h_eval = [], [], []

    for i, (_params, graph, label_of) in enumerate(bundle):
        nodes, X, context = _features_for_graph(graph)
        labels = np.array([1.0 if label_of.get(n) else 0.0 for n in nodes], dtype=np.float64)
        hole_scores = context.get("hole_scores", {})
        h = np.array([float(hole_scores.get(n, 0.0)) for n in nodes], dtype=np.float64)
        if i in train_idx:
            X_train.append(X)
            y_train.append(labels)
            h_train.append(h)
        else:
            X_eval.append(X)
            y_eval.append(labels)
            h_eval.append(h)

    X_train = np.vstack(X_train)
    y_train = np.concatenate(y_train)
    h_train = np.concatenate(h_train)
    X_eval = np.vstack(X_eval) if X_eval else np.zeros((0, N_FEATURES))
    y_eval = np.concatenate(y_eval) if y_eval else np.zeros(0)
    h_eval = np.concatenate(h_eval) if len(h_eval) else np.zeros(0)

    model = GhostClassifier(seed=base_seed)
    model.fit(X_train, y_train, h_train)

    # ── train propagation second signal and re-fit stacker ────────────
    train_graphs: List["nx.DiGraph"] = []
    train_labels_per_graph: List[Dict[str, int]] = []
    train_nodes_per_graph: List[List] = []
    for i in train_idx:
        _p, g, label_of = bundle[i]
        nodes = _nodes_for_graph(g)
        train_graphs.append(g)
        train_labels_per_graph.append({n: int(label_of.get(n, 0)) for n in nodes})
        train_nodes_per_graph.append(nodes)
    model.fit_propagation(
        train_graphs, train_labels_per_graph, train_nodes_per_graph,
        X_train=X_train, y_train=y_train, h_train=h_train,
    )

    metrics: Dict[str, Any] = {}
    if len(X_eval) > 0:
        proba = model.predict_proba(X_eval, h_eval)
        metrics = _classification_metrics(y_eval, proba, threshold=0.5)
        metrics["n_train"] = int(len(y_train))
        metrics["n_eval"] = int(len(y_eval))
        metrics["positive_rate_train"] = round(float(y_train.mean()), 4)
        metrics["positive_rate_eval"] = round(float(y_eval.mean()), 4)
        metrics["version"] = model.version
        metrics["importance"] = {
            k: round(v, 4) for k, v in sorted(
                model.feature_importance.items(),
                key=lambda kv: -kv[1],
            )[:10]
        }

    model.save(save_path)
    return model, metrics


def _propagation_scores_for_training(
    graphs: List["nx.DiGraph"],
    nodes_per_graph: List[List],
    model: StructuralPropagationModel,
) -> np.ndarray:
    """Compute per-node propagation probabilities for training graphs.

    ``nodes_per_graph[i]`` is the ordered list of node ids whose rows
    appear in the corresponding slice of the training feature matrix.
    Returns a single concatenated array matching the training row order.
    """
    parts: List[np.ndarray] = []
    for G, nodes in zip(graphs, nodes_per_graph):
        raw = model.predict(G)
        parts.append(np.array([raw.get(n, 0.5) for n in nodes], dtype=np.float64))
    return np.concatenate(parts) if parts else np.zeros(0)


def _features_for_graph(graph: nx.MultiDiGraph):
    from src.graph.ml.feature_extraction import extract_features_for_graph
    # Training-only fast path: lightweight structural-hole approximation
    # (production inference uses fast=False -> authoritative metrics)
    return extract_features_for_graph(graph, fast=True)


def _nodes_for_graph(graph: nx.MultiDiGraph) -> List:
    """Return person-type node ids in the same order as extract_features."""
    from src.graph.ml.feature_extraction import GhostConfig
    config = GhostConfig()
    return [
        n for n, data in graph.nodes(data=True)
        if str(data.get("entity_type", "")).upper() not in {"LOCATION", "ACCOUNT"}
    ]


def _classification_metrics(y: np.ndarray, proba: np.ndarray, threshold: float = 0.5) -> Dict[str, Any]:
    pred = (proba >= threshold).astype(int)
    tp = float(((pred == 1) & (y == 1)).sum())
    fp = float(((pred == 1) & (y == 0)).sum())
    fn = float(((pred == 0) & (y == 1)).sum())
    tn = float(((pred == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / max(1, len(y))
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "threshold": threshold,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Train the ghost coordinator classifier")
    parser.add_argument("--graphs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--save", default=str(MODEL_PATH))
    args = parser.parse_args()
    model, metrics = train_from_generated_graphs(
        n_graphs=args.graphs, base_seed=args.seed, save_path=args.save
    )
    print(json.dumps(metrics, indent=2))
    sys.exit(0)