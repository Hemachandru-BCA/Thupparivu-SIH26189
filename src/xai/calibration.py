"""
xai/calibration.py
------------------
Confidence calibration for SentinelGraph.

Turns raw confidence scores (weighted blends of graph signals) into calibrated
probabilities that track observed outcome frequency — the reliability
requirement: "a 0.7 confidence score should be right ~70% of the time".

Approach (Task 2 of the Tier-1 accuracy directive):

* **Isotonic regression** (pool-adjacent violators, pure numpy — zero new
  dependencies, robust for small/noisy data) as the default calibrator.
* **Platt scaling** (logistic fit on logit of the raw score) as the
  alternative, selectable via ``method=``.
* ``fit_calibration()`` learns a monotone map raw -> calibrated on
  (predicted_confidence, actual_outcome) pairs from the varied synthetic
  graphs; ``apply_calibration()`` maps new raw confidence values.
* **Does NOT change epistemic labels** (OBSERVED/INFERRED/UNKNOWN stays
  exactly as before) and **does NOT touch evidence validation** — it only
  adjusts the numeric confidence value.

Also produces a **reliability diagram** — predicted-confidence bucket vs
observed accuracy — plus Expected Calibration Error (ECE), which is the
artifact that proves calibration worked.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Hashable, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = Path("data/models/confidence_calibrator.pkl")


# --------------------------------------------------------------------------- #
# isotonic regression (PAVA)
# --------------------------------------------------------------------------- #

def _isotonic_fit(
    x: np.ndarray,
    y: np.ndarray,
    weight: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Pool-adjacent-violators isotonic regression.

    Returns ``(xs, ys)`` — the monotone non-decreasing step function mapping
    raw scores to calibrated probabilities.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if weight is None:
        weight = np.ones_like(y)
    weight = np.asarray(weight, dtype=np.float64)

    order = np.argsort(x)
    xs = x[order]
    ys = y[order]
    ws = weight[order]

    # PAVA: merge adjacent blocks that violate monotonicity
    blocks_x: List[float] = [float(xs[0])]
    blocks_y: List[float] = [float(ys[0])]
    blocks_w: List[float] = [float(ws[0])]
    for i in range(1, len(xs)):
        blocks_x.append(float(xs[i]))
        blocks_y.append(float(ys[i]))
        blocks_w.append(float(ws[i]))
        while len(blocks_y) >= 2 and blocks_y[-1] < blocks_y[-2]:
            w1, w2 = blocks_w[-2], blocks_w[-1]
            blocks_y[-2] = (w1 * blocks_y[-2] + w2 * blocks_y[-1]) / (w1 + w2)
            blocks_w[-2] = w1 + w2
            blocks_x[-2] = (blocks_x[-1] + blocks_x[-2]) / 2.0
            blocks_x.pop()
            blocks_y.pop()
            blocks_w.pop()
    return np.array(blocks_x), np.array(blocks_y)


def _isotonic_apply(xs: np.ndarray, ys: np.ndarray, new_x: np.ndarray) -> np.ndarray:
    """Evaluate the isotonic step function at new points (clamped)."""
    new_x = np.clip(np.asarray(new_x, dtype=np.float64), xs[0], xs[-1])
    idx = np.searchsorted(xs, new_x, side="right") - 1
    idx = np.clip(idx, 0, len(ys) - 1)
    return ys[idx]


def _platt_fit(
    x: np.ndarray,
    y: np.ndarray,
    max_iter: int = 500,
    lr: float = 0.1,
) -> Tuple[float, float]:
    """Simple logistic (Platt) scaling: sigmoid(a * x + b)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    a = 1.0
    b = 0.0
    for _ in range(max_iter):
        z = a * x + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        grad_a = float(np.mean((p - y) * x))
        grad_b = float(np.mean(p - y))
        a -= lr * grad_a
        b -= lr * grad_b
    return float(a), float(b)


def _platt_apply(a: float, b: float, new_x: np.ndarray) -> np.ndarray:
    z = a * np.asarray(new_x, dtype=np.float64) + b
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #

@dataclass
class ConfidenceCalibrator:
    """Maps raw confidence scores to calibrated probabilities."""

    method: str = "isotonic"          # "isotonic" | "platt"
    xs: np.ndarray = field(default_factory=lambda: np.array([0.0, 1.0]))
    ys: np.ndarray = field(default_factory=lambda: np.array([0.0, 1.0]))
    platt_a: float = 1.0
    platt_b: float = 0.0
    ece_before: float = 0.0
    ece_after: float = 0.0
    n_samples: int = 0

    def fit(self, raw: Sequence[float], outcome: Sequence[int], method: Optional[str] = None) -> "ConfidenceCalibrator":
        """Fit the calibration map on (raw, outcome) pairs.

        ``outcome`` is 1 if the predicted event turned out true (e.g. a ghost
        candidate that really was a planted coordinator), else 0.
        """
        x = np.asarray(raw, dtype=np.float64)
        y = np.asarray(outcome, dtype=np.float64)
        self.method = method or self.method
        self.n_samples = len(x)
        if self.n_samples == 0:
            return self
        if self.method == "platt":
            self.platt_a, self.platt_b = _platt_fit(x, y)
            cal = self.apply(x)
        else:
            xs, ys = _isotonic_fit(x, y)
            self.xs = xs
            self.ys = ys
            cal = self.apply(x)
        self.ece_before = ece(x, y)
        self.ece_after = ece(cal, y)
        return self

    def apply(self, raw: Sequence[float]) -> np.ndarray:
        """Calibrate raw scores -> probabilities in [0, 1]."""
        x = np.asarray(raw, dtype=np.float64)
        if self.method == "platt":
            out = _platt_apply(self.platt_a, self.platt_b, x)
        else:
            out = _isotonic_apply(self.xs, self.ys, x)
        return np.clip(out, 0.0, 1.0)

    # -- transparency helpers ------------------------------------------- #
    def reliability(self, raw: Sequence[float], outcome: Sequence[int], n_bins: int = 10) -> List[Dict[str, Any]]:
        """Reliability diagram: predicted-confidence bucket vs observed accuracy."""
        x = np.asarray(raw, dtype=np.float64)
        y = np.asarray(outcome, dtype=np.float64)
        cal = self.apply(x)
        edges = np.linspace(0.0, 1.0, n_bins + 1)
        rows: List[Dict[str, Any]] = []
        for i in range(n_bins):
            lo, hi = edges[i], edges[i + 1]
            mask = (cal >= lo) & (cal < hi)
            # include the final bin's right edge
            if i == n_bins - 1:
                mask = (cal >= lo) & (cal <= hi)
            if mask.sum() == 0:
                continue
            rows.append({
                "bucket": f"[{lo:.2f}, {hi:.2f})",
                "mean_predicted": round(float(cal[mask].mean()), 4),
                "observed_accuracy": round(float(y[mask].mean()), 4),
                "n": int(mask.sum()),
            })
        return rows

    def save(self, path: Path | str = MODEL_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            import pickle
            pickle.dump(self, fh)
        return path

    @staticmethod
    def load(path: Path | str = MODEL_PATH) -> Optional["ConfidenceCalibrator"]:
        from pathlib import Path as P
        path = P(path)
        if not path.exists():
            return None
        try:
            import pickle
            with path.open("rb") as fh:
                obj = pickle.load(fh)
            return obj if isinstance(obj, ConfidenceCalibrator) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("cannot load calibrator %s: %s", path, exc)
            return None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def ece(pred: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error — mean |predicted - observed| per bucket."""
    pred = np.clip(np.asarray(pred, dtype=np.float64), 0.0, 1.0)
    y = np.asarray(y, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    n = 0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (pred >= lo) & (pred < hi)
        if i == n_bins - 1:
            mask = (pred >= lo) & (pred <= hi)
        if mask.sum() == 0:
            continue
        total += abs(float(pred[mask].mean()) - float(y[mask].mean())) * mask.sum()
        n += int(mask.sum())
    return total / max(1, n)


def reliability_diagram_ascii(rows: List[Dict[str, Any]], width: int = 40) -> str:
    """Render a reliability diagram as ASCII (no plotting dependency)."""
    lines = ["Reliability diagram  (# = predicted frontier, o = observed)"]
    grid = [[" " for _ in range(width)] for _ in range(12)]
    for r in rows:
        col = min(width - 1, int(round(r["mean_predicted"] * (width - 1))))
        row = min(11, 11 - int(round(r["observed_accuracy"] * 11)))
        grid[row][col] = "#"
    for row in range(12):
        label = f"{1.0 - row / 11:.1f}"
        lines.append(f"{label} |" + "".join(grid[row]))
    lines.append("    +" + "-" * width + ">")
    lines.append("    0" + " " * (width - 2) + " 1  (predicted)")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# fit end-to-end from synthetic graphs (reuse Task-1 bundle)
# --------------------------------------------------------------------------- #

def fit_from_generated_graphs(
    n_graphs: int = 20,
    base_seed: int = 1000,
    save_path: Path | str = MODEL_PATH,
) -> Tuple[ConfidenceCalibrator, List[Dict[str, Any]]]:
    """Fit a calibrator on (raw model probability, ground-truth outcome) pairs.

    Uses the same varied synthetic graphs as Task 1 with known ground truth:
    a node that is a planted coordinator is a positive; every other person is
    a negative.  The raw score is the *blended* confidence the detector would
    assign (classifier probability ± heuristic prior, on this graph it's the
    per-node classifier probability); calibration maps it to a probability
    that tracks observed outcome frequency.

    Production wiring: the trained :class:`ConfidenceCalibrator` artifact is
    applied to raw ghost-candidate confidence inside the API / report layer
    (see Tests + sector/summary layer), and the artifact ships in
    ``data/models/confidence_calibrator.pkl``.
    """
    from src.graph.ml.synthetic_graphs import generate_graph_bundle
    from src.graph.ml.feature_extraction import extract_features_for_graph
    from src.graph.ml.classifier import GhostClassifier

    bundle = generate_graph_bundle(n_graphs=n_graphs, base_seed=base_seed)
    raw: List[float] = []
    out: List[int] = []

    # Train a small classifier on a held-out split of the SAME bundle so the
    # probabilities are honest (never fit+apply on identical rows).
    rows_x: List[np.ndarray] = []
    rows_y: List[np.ndarray] = []
    rows_h: List[np.ndarray] = []
    nodes_store: List[List[Hashable]] = []
    label_store: List[dict] = []
    from src.graph.ghost_nodes import detect_structural_holes, GhostConfig
    for _params, g, label_of in bundle:
        nodes, X, ctx = extract_features_for_graph(g, fast=True)
        nodes_store.append(nodes)
        label_store.append(label_of)
        rows_x.append(X)
        rows_y.append(np.array([1.0 if label_of.get(n) else 0.0 for n in nodes]))
        rows_h.append(np.array([float(ctx["hole_scores"].get(n, 0.0)) for n in nodes]))
    # 80/20 split by graph (never same graph in fit & apply)
    rng_s = np.random.RandomState(base_seed)
    idx = rng_s.permutation(len(rows_x))
    n_fit = max(1, int(len(rows_x) * 0.8))
    fit_idx = set(idx[:n_fit].tolist())
    apply_idx = set(idx[n_fit:].tolist())
    X_fit = np.vstack([rows_x[i] for i in fit_idx])
    y_fit = np.concatenate([rows_y[i] for i in fit_idx])
    h_fit = np.concatenate([rows_h[i] for i in fit_idx])
    model = GhostClassifier(seed=base_seed).fit(X_fit, y_fit, h_fit)

    for i in apply_idx:
        nodes = nodes_store[i]
        label_of = label_store[i]
        X = rows_x[i]
        h = rows_h[i]
        proba = model.predict_proba(X, h)
        for n, p, lbl in zip(nodes, proba, [label_of.get(n) for n in nodes]):
            raw.append(float(p))
            out.append(1 if lbl else 0)

    calibrator = ConfidenceCalibrator(method="isotonic")
    if raw:
        calibrator.fit(raw, out)

    rel_before: List[Dict[str, Any]] = []
    rel_after: List[Dict[str, Any]] = []
    if raw:
        x = np.asarray(raw)
        y = np.asarray(out)
        rel_before = calibrator.reliability(x, y)
        rel_after = calibrator.reliability(x, y)

    calibrator.save(save_path)
    summary = {
        "n_pairs": len(raw),
        "positive_rate": round(float(np.mean(out)), 4) if out else 0.0,
        "n_fit_graphs": len(fit_idx),
        "n_apply_graphs": len(apply_idx),
        "ece_before": round(calibrator.ece_before, 4),
        "ece_after": round(calibrator.ece_after, 4),
        "method": calibrator.method,
        "reliability_before": rel_before,
        "reliability_after": rel_after,
        "model_path": str(save_path),
    }
    return calibrator, summary


def report_to_markdown(summary: Dict[str, Any]) -> str:
    """Render the calibration summary as markdown for docs/VALIDATION_REPORT.md."""
    lines = [
        "## Confidence calibration (Task 2)",
        "",
        f"- Method: `{summary.get('method')}` isotonic regression",
        f"- Calibration pairs: `{summary.get('n_pairs')}` (ghost candidates with known outcome)",
        f"- Positive rate: `{summary.get('positive_rate')}`",
        f"- **ECE before:** `{summary.get('ece_before')}`",
        f"- **ECE after:** `{summary.get('ece_after')}`",
        "",
        "### Reliability diagram (calibrated)",
        "",
    ]
    rows = summary.get("reliability_after", [])
    if rows:
        lines.append("| Predicted bucket | Mean predicted | Observed accuracy | n |")
        lines.append("|---|---|---|---|")
        for r in rows:
            lines.append(
                f"| {r['bucket']} | {r['mean_predicted']:.3f} | {r['observed_accuracy']:.3f} | {r['n']} |"
            )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Fit confidence calibration")
    parser.add_argument("--graphs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--save", default=str(MODEL_PATH))
    args = parser.parse_args()
    calibrator, summary = fit_from_generated_graphs(
        n_graphs=args.graphs, base_seed=args.seed, save_path=args.save
    )
    print(json.dumps(summary, indent=2))
    sys.exit(0)