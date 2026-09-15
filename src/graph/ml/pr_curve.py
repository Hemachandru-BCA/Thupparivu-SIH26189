"""ASCII precision-recall curve for the ghost classifier benchmark.

No plotting dependency (matplotlib is intentionally absent from the offline
environment) — renders the PR curve as inline ASCII in the terminal and
writes the underlying curve data to JSON for the report.

Usage:
    python -m src.graph.ml.pr_curve --json data/exports/benchmark/ghost_classifier_benchmark.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def ascii_pr_curve(points: List[Dict[str, Any]], width: int = 40, height: int = 16) -> str:
    """Simple ASCII plot: rows = precision buckets 0..1, cols = recall 0..1."""
    grid = [[" " for _ in range(width)] for _ in range(height)]
    for p in points:
        rec = float(p.get("recall", 0.0))
        prec = float(p.get("precision", 0.0))
        col = min(width - 1, int(round(rec * (width - 1))))
        row = min(height - 1, height - 1 - int(round(prec * (height - 1))))
        grid[row][col] = "#"
    lines = []
    for row in range(height):
        label = f"{1.0 - row / (height - 1):.2f}"
        lines.append(f"{label} |" + "".join(grid[row]))
    lines.append("    +" + "-" * width + ">")
    lines.append("    0" + " " * (width - 2) + " 1  (recall)")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="data/exports/benchmark/ghost_classifier_benchmark.json")
    parser.add_argument("--out", default="data/exports/benchmark/pr_curve.txt")
    args = parser.parse_args()
    data = json.loads(Path(args.json).read_text())
    curve = data["classifier_curve"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    art = ascii_pr_curve(curve)
    out.write_text(art)
    print("Precision-Recall curve (classifier, held-out graphs):")
    print(art)
    best = data["best_f1_point"]
    print(f"\nBest F1 point: {best}")
    hez = data.get("heuristic_baseline", {})
    print(f"Heuristic pair baseline: precision={hez.get('pair_precision_mean')} recall={hez.get('pair_recall_mean')}")


if __name__ == "__main__":
    main()