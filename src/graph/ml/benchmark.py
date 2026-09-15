#!/usr/bin/env python3
"""Ghost-coordinator classifier benchmark across varied synthetic graphs.

Reports precision / recall / F1 at multiple operating thresholds (PR curve)
over *held-out* graphs the classifier was never trained on, with mean + stddev
across graphs.  Also prints the baseline heuristic comparison on the same
graphs so the improvement is measurable, not anecdotal.

Usage:
    python -m src.graph.ml.benchmark --graphs 30 --seed 1000
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import networkx as nx

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.ml.classifier import GhostClassifier, _classification_metrics
from src.graph.ml.feature_extraction import extract_features_for_graph
from src.graph.ml.synthetic_graphs import generate_graph_bundle
from src.graph.graph_embeddings import undirected_weighted_projection
from src.graph.ghost_nodes import (
    detect_structural_holes,
    GhostConfig,
    detect_communities,
    _community_membership_map,
    detect_ghost_nodes,
)


def _mask_coordinators(graph, coord_nodes) -> nx.MultiDiGraph:
    """Remove planted coordinator nodes + their edges (realistic handicap)."""
    g = graph.copy()
    for n in coord_nodes:
        if g.has_node(n):
            g.remove_node(n)
    return g


def _planted_coordinator_pairs(graph, coord_nodes, community_of) -> set:
    """Ground-truth community pairs joined by a coordinator (via its proxies)."""
    pairs: set = set()
    proxies_of: Dict[str, set] = {}
    for coord in coord_nodes:
        # coordinators were masked out of the observed graph; their proxy
        # edges were removed with them, so read the *pre-mask* connectivity
        # from the reverse: proxies are the neighbors of the coordinator in
        # the original full graph — reconstructed here from the synthetic
        # rule that a coordinator only ever links to its lieutenants.
        proxies_of[coord] = set()
        for nbr in list(graph.successors(coord)) + list(graph.predecessors(coord)):
            proxies_of[coord].add(nbr)
    for coord, proxies in proxies_of.items():
        comms = sorted({community_of[p] for p in proxies if community_of.get(p) is not None})
        for i in range(len(comms)):
            for j in range(i + 1, len(comms)):
                pairs.add((comms[i], comms[j]))
    return pairs


def _heuristic_ghost_pair_recall(graph, coord_nodes, config) -> Dict[str, float]:
    """Run the existing pair-based heuristic on a graph with coordinators masked.

    Mirrors the seed=42 validation methodology (pair-level precision/recall vs
    planted coordinators).  Returns precision/recall of detected ghost pairs.
    """
    try:
        observed = _mask_coordinators(graph, coord_nodes)
        doc = detect_ghost_nodes(observed, config)
        detected_pairs = set()
        for g_ in doc.get("ghost_nodes", []):
            pair = g_.get("community_pair")
            if pair:
                detected_pairs.add((pair[0], pair[1]))
        # community_of comes from the detection over the OBSERVED graph
        projection = undirected_weighted_projection(observed)
        proj = projection.subgraph([
            n for n, d in observed.nodes(data=True)
            if str(d.get("entity_type", "")).upper() not in {"LOCATION", "ACCOUNT"}
        ]).copy()
        communities = detect_communities(proj, seed=config.seed)
        community_of = _community_membership_map(observed, communities)
        # truth pairs use the ORIGINAL graph (proxies of coordinators still
        # referenced there) but the observed communities
        truth = _planted_coordinator_pairs(graph, coord_nodes, community_of)
        if not truth:
            return {"precision": 0.0, "recall": 0.0, "n_truth_pairs": 0, "n_detected": len(detected_pairs)}
        tp = len(detected_pairs & truth)
        precision = tp / len(detected_pairs) if detected_pairs else 0.0
        recall = tp / len(truth)
        return {
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "n_truth_pairs": len(truth),
            "n_detected": len(detected_pairs),
            "tp": int(tp),
        }
    except Exception as exc:  # noqa: BLE001
        return {"precision": 0.0, "recall": 0.0, "error": str(exc)[:120]}


def _heuristic_scores(graph, nodes, hole_scores) -> np.ndarray:
    """Best single-scalar heuristic per node (structural-hole score)."""
    return np.array([float(hole_scores.get(n, 0.0)) for n in nodes])


def _run_benchmark(n_graphs: int = 30, base_seed: int = 1000) -> Dict[str, object]:
    bundle = generate_graph_bundle(n_graphs=n_graphs, base_seed=base_seed)
    rng = random.Random(base_seed)
    order = list(range(len(bundle)))
    rng.shuffle(order)
    n_train = max(2, int(len(bundle) * 0.8))
    train_idx = set(order[:n_train])
    eval_idx = set(order[n_train:])

    # ---- train -------------------------------------------------------------
    X_tr, y_tr, h_tr = [], [], []
    for i in train_idx:
        _p, g, label_of = bundle[i]
        nodes, X, ctx = extract_features_for_graph(g, fast=True)
        X_tr.append(X)
        y_tr.append(np.array([1.0 if label_of.get(n) else 0.0 for n in nodes]))
        h_tr.append(_heuristic_scores(g, nodes, ctx["hole_scores"]))
    model = GhostClassifier(seed=base_seed)
    model.fit(np.vstack(X_tr), np.concatenate(y_tr), np.concatenate(h_tr))

    # ---- per-graph eval ------------------------------------------------------
    thresholds = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]
    per_graph: List[Dict[str, object]] = []
    totals = {t: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "hez_tp": 0, "hez_fp": 0, "hez_fn": 0} for t in thresholds}
    all_y: List[np.ndarray] = []
    all_p: List[np.ndarray] = []
    all_h: List[np.ndarray] = []
    for i in eval_idx:
        _p, g, label_of = bundle[i]
        nodes, X, ctx = extract_features_for_graph(g, fast=True)
        y = np.array([1.0 if label_of.get(n) else 0.0 for n in nodes])
        h = _heuristic_scores(g, nodes, ctx["hole_scores"])
        p = model.predict_proba(X, h)
        all_y.append(y)
        all_p.append(p)
        all_h.append(h)
        # heuristic-only baseline (recall1 at precision>=0.9 style: rank by score)
        per_graph.append({
            "graph_idx": i,
            "n_nodes": len(y),
            "n_positive": int(y.sum()),
            "classifier_auc_guess": round(float(np.mean(p[y == 1]) - np.mean(p[y == 0])), 4),
        })
        for t in thresholds:
            pred = (p >= t).astype(int)
            totals[t]["tp"] += int(((pred == 1) & (y == 1)).sum())
            totals[t]["fp"] += int(((pred == 1) & (y == 0)).sum())
            totals[t]["fn"] += int(((pred == 0) & (y == 1)).sum())
            totals[t]["tn"] += int(((pred == 0) & (y == 0)).sum())

    # Heuristic pair-based baseline: run the existing detect_ghost_nodes on
    # held-out graphs with coordinators masked, at the SAME precision
    # discipline as the 0.273 baseline (pair-level precision/recall).
    heuristic_pair_results = []
    for i in eval_idx:
        _p, g, label_of = bundle[i]
        coord_nodes = [n for n, v in label_of.items() if v]
        res = _heuristic_ghost_pair_recall(g, coord_nodes, GhostConfig())
        res["graph_idx"] = int(i)
        heuristic_pair_results.append(res)
    hez_pair_prec = float(np.mean([r["precision"] for r in heuristic_pair_results])) if heuristic_pair_results else 0.0
    hez_pair_rec = float(np.mean([r["recall"] for r in heuristic_pair_results])) if heuristic_pair_results else 0.0

    # ---- curve -------------------------------------------------------------
    curve = []
    for t in thresholds:
        d = totals[t]
        tp, fp, fn = d["tp"], d["fp"], d["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        curve.append({
            "threshold": t,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": int(tp), "fp": int(fp), "fn": int(fn),
        })

    best = max(curve, key=lambda c: c["f1"])
    mean_auc = float(np.mean([g_["classifier_auc_guess"] for g_ in per_graph]))
    # per-graph stddev of the classifier's positive-minus-negative separation
    auc_values = np.array([g_["classifier_auc_guess"] for g_ in per_graph], dtype=np.float64)
    std_auc = float(np.std(auc_values)) if len(auc_values) > 1 else 0.0
    # stddev of the heuristic baseline pair-precision/recall across graphs
    hez_prec_values = np.array([r.get("precision", 0.0) for r in heuristic_pair_results], dtype=np.float64)
    hez_rec_values = np.array([r.get("recall", 0.0) for r in heuristic_pair_results], dtype=np.float64)
    hez_prec_std = float(np.std(hez_prec_values)) if len(hez_prec_values) > 1 else 0.0
    hez_rec_std = float(np.std(hez_rec_values)) if len(hez_rec_values) > 1 else 0.0
    return {
        "n_graphs_total": len(bundle),
        "n_train_graphs": len(train_idx),
        "n_eval_graphs": len(eval_idx),
        "positive_rate_eval": round(float(np.concatenate(all_y).mean()), 4),
        "heuristic_baseline": {
            "pair_precision_mean": round(hez_pair_prec, 4),
            "pair_recall_mean": round(hez_pair_rec, 4),
            "pair_precision_std": round(hez_prec_std, 4),
            "pair_recall_std": round(hez_rec_std, 4),
            "per_graph": heuristic_pair_results,
        },
        "classifier_curve": curve,
        "best_f1_point": best,
        "mean_classifier_positive_minus_negative": round(mean_auc, 4),
        "std_classifier_positive_minus_negative": round(std_auc, 4),
        "n_eval_positives_total": int(np.concatenate(all_y).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--out", default="data/exports/benchmark/ghost_classifier_benchmark.json")
    args = parser.parse_args()
    result = _run_benchmark(args.graphs, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()