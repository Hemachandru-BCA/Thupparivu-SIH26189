"""
ml/calibration.py
-----------------
Model calibration + ranking metrics (Phase 4, requirement 9).

Measures:

* Brier score        — mean squared error of predicted probability vs label
* calibration curve  — binned reliability (and ECE)
* precision@k / recall@k
* F1
* ROC-AUC / PR-AUC   (via sklearn when available; trapezoid fallback)

Nothing here claims a model is calibrated — it computes the numbers so the
system can SAY so honestly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Core metrics
# --------------------------------------------------------------------------- #

def brier_score(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    """Brier score: mean squared error between probability and label."""
    if not y_true:
        return 0.0
    n = len(y_true)
    return sum((p - y) ** 2 for p, y in zip(y_prob, y_true)) / n


def expected_calibration_error(y_true: Sequence[int], y_prob: Sequence[float],
                               n_bins: int = 10) -> float:
    """Expected Calibration Error over probability bins."""
    if not y_true:
        return 0.0
    bins: Dict[int, List[Tuple[int, float]]] = {i: [] for i in range(n_bins)}
    for y, p in zip(y_true, y_prob):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((y, p))
    total = len(y_true)
    ece = 0.0
    for idx, group in bins.items():
        if not group:
            continue
        acc = sum(y for y, _ in group) / len(group)
        conf = sum(p for _, p in group) / len(group)
        ece += (len(group) / total) * abs(acc - conf)
    return ece


def precision_at_k(y_true: Sequence[int], y_prob: Sequence[float], k: int) -> float:
    """Precision of the top-k (by predicted probability) labels."""
    if not y_true or k <= 0:
        return 0.0
    order = sorted(range(len(y_prob)), key=lambda i: -y_prob[i])
    topk = order[:k]
    hits = sum(1 for i in topk if y_true[i] == 1)
    return hits / min(k, len(order))


def recall_at_k(y_true: Sequence[int], y_prob: Sequence[float], k: int) -> float:
    """Recall of the top-k (fraction of all positives recovered)."""
    total_pos = sum(1 for v in y_true if v == 1)
    if total_pos == 0 or k <= 0:
        return 0.0
    order = sorted(range(len(y_prob)), key=lambda i: -y_prob[i])
    topk = order[:k]
    hits = sum(1 for i in topk if y_true[i] == 1)
    return hits / total_pos


def f1_at_threshold(y_true: Sequence[int], y_prob: Sequence[float],
                    threshold: float = 0.5) -> Dict[str, float]:
    """Precision / recall / F1 at a fixed threshold."""
    tp = fp = fn = 0
    for y, p in zip(y_true, y_prob):
        pred = 1 if p >= threshold else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
        elif pred == 0 and y == 1:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _roc_curve(y_true: Sequence[int], y_prob: Sequence[float]) -> List[Tuple[float, float]]:
    """ROC curve via ranking (sklearn-free)."""
    thresholds = sorted(set(y_prob), reverse=True)
    thresholds = [1.0] + thresholds + [0.0]
    curve: List[Tuple[float, float]] = []
    total_pos = sum(1 for v in y_true if v == 1)
    total_neg = len(y_true) - total_pos
    for t in thresholds:
        tp = sum(1 for y, p in zip(y_true, y_prob) if p >= t and y == 1)
        fp = sum(1 for y, p in zip(y_true, y_prob) if p >= t and y == 0)
        tpr = tp / total_pos if total_pos else 0.0
        fpr = fp / total_neg if total_neg else 0.0
        curve.append((fpr, tpr))
    return curve


def _pr_curve(y_true: Sequence[int], y_prob: Sequence[float]) -> List[Tuple[float, float]]:
    """PR curve via ranking (sklearn-free)."""
    thresholds = sorted(set(y_prob), reverse=True)
    thresholds = [1.0] + thresholds + [0.0]
    curve: List[Tuple[float, float]] = []
    total_pos = sum(1 for v in y_true if v == 1)
    for t in thresholds:
        tp = sum(1 for y, p in zip(y_true, y_prob) if p >= t and y == 1)
        fp = sum(1 for y, p in zip(y_true, y_prob) if p >= t and y == 0)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / total_pos if total_pos else 0.0
        curve.append((recall, precision))
    return curve


def _auc(curve: List[Tuple[float, float]]) -> float:
    """Trapezoid area under a curve (x ascending)."""
    if len(curve) < 2:
        return 0.0
    area = 0.0
    for i in range(1, len(curve)):
        x1, y1 = curve[i - 1]
        x2, y2 = curve[i]
        area += (x2 - x1) * (y1 + y2) / 2.0
    return area


def roc_auc(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    """ROC-AUC (sklearn preferred, trapezoid fallback)."""
    try:
        from sklearn.metrics import roc_auc_score
        return round(float(roc_auc_score(y_true, y_prob)), 4)
    except Exception:
        return round(_auc(_roc_curve(y_true, y_prob)), 4)


def pr_auc(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    """PR-AUC (sklearn preferred, trapezoid fallback)."""
    try:
        from sklearn.metrics import average_precision_score
        return round(float(average_precision_score(y_true, y_prob)), 4)
    except Exception:
        return round(_auc(_pr_curve(y_true, y_prob)), 4)


def full_metrics(y_true: Sequence[int], y_prob: Sequence[float],
                 threshold: float = 0.5) -> Dict[str, Any]:
    """Complete evaluation metrics for a (labels, probabilities) pair."""
    if not y_true:
        return {}
    f1d = f1_at_threshold(y_true, y_prob, threshold)
    out: Dict[str, Any] = {
        "n": len(y_true),
        "positive_fraction": round(sum(y_true) / len(y_true), 4),
        "brier": round(brier_score(y_true, y_prob), 4),
        "ece": round(expected_calibration_error(y_true, y_prob), 4),
        "roc_auc": roc_auc(y_true, y_prob),
        "pr_auc": pr_auc(y_true, y_prob),
        **f1d,
    }
    # precision@k / recall@k for a few k values
    total_pos = sum(y_true)
    ks = [1, 5, 10, min(50, len(y_true))]
    for k in dict.fromkeys(ks):
        out[f"precision@{k}"] = round(precision_at_k(y_true, y_prob, k), 4)
        out[f"recall@{k}"] = round(recall_at_k(y_true, y_prob, k), 4)
    if total_pos:
        out[f"recall@{total_pos}"] = round(recall_at_k(y_true, y_prob, total_pos), 4)
    return out


# --------------------------------------------------------------------------- #
# Ablation framework (Phase 4, requirement 13)
# --------------------------------------------------------------------------- #

def run_ablation(
    evaluate: Any,
    feature_groups: Dict[str, List[str]],
    baseline_features: List[str],
    y: Sequence[int],
) -> Dict[str, Dict[str, Any]]:
    """Run an ablation study over feature groups.

    ``evaluate`` is a callable ``(feature_subset) -> metrics_dict``.
    ``feature_groups`` maps group name → feature names.
    Returns a table of metrics per ablation (baseline + each group dropped).
    """
    results: Dict[str, Dict[str, Any]] = {}
    baseline_metrics = evaluate(baseline_features)
    results["all_features"] = baseline_metrics
    for group_name, group_feats in feature_groups.items():
        subset = [f for f in baseline_features if f not in group_feats]
        try:
            results[f"without_{group_name}"] = evaluate(subset)
        except Exception as exc:  # pragma: no cover
            results[f"without_{group_name}"] = {"error": str(exc)}
    return results