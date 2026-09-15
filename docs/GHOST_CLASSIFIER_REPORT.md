# Ghost Classifier Report — SentinelGraph AI

**Date:** 2026-09-12
**Status:** Trained and wired into production pipeline

---

## Problem

The original ghost-node detection in `src/graph/ghost_nodes.py` used a
heuristic **structural-hole pair proposal** that achieved **precision 1.0**
but **recall 0.273** (seed 42 graph) — missing ~73% of hidden coordinators
because the heuristic only proposes candidates within each community, and
low-engagement coordinators get assigned to their own singleton communities.

## Solution: Trained GBM + Logistic Stacker

A **pure-Python gradient-boosted classifier** (no new pip dependencies)
that operates on **per-node 20-feature vectors** and produces a single
affinity score blended into the existing confidence formula.

### Architecture

```
┌─────────────────────────────────────────────┐
│  Synthetic Graph Generator (multi-seed)     │
│  varied: community sizes, bridge rates,     │
│  engagement tiers, anchor types             │
├─────────────────────────────────────────────┤
│  Feature Extraction (20 features)           │
│  degree/constraint/betweenness + anchor     │
│  overlap + heuristic score as input         │
├─────────────────────────────────────────────┤
│  Gradient Boosted Classifier (40 trees)     │
│  max_depth=3, lr=0.1, column subsample 0.8 │
├─────────────────────────────────────────────┤
│  Logistic Stacker (weights raw + boosting)  │
│  output: affinity ∈ [0, 1]                  │
├─────────────────────────────────────────────┤
│  Ghost Detection (blended score)            │
│  confidence = w₁·heuristic + w₂·classifier │
│  transparent component, never replaces base │
└─────────────────────────────────────────────┘
```

### Files

| File | Purpose |
|---|---|
| `src/graph/ml/synthetic_graphs.py` | Multi-seed graph generator with planted coordinators |
| `src/graph/ml/feature_extraction.py` | 20-feature per-node extraction (fast Burt approx) |
| `src/graph/ml/classifier.py` | GBM + logistic stacker (train/predict/load/save) |
| `src/graph/ml/benchmark.py` | Precision/recall/F1 + pair-based heuristic baseline |
| `src/graph/ml/pr_curve.py` | ASCII PR curve renderer |
| `data/models/ghost_classifier.pkl` | Trained model artifact (40 trees) |
| `tests/test_ghost_classifier.py` | 14 test cases |

### Feature Vector (20 features)

| # | Feature | Category |
|---|---------|----------|
| 0 | degree | Structural |
| 1 | in_degree | Structural |
| 2 | out_degree | Structural |
| 3 | neighbor_count | Structural |
| 4 | structural_hole_score | Structural |
| 5 | constraint | Structural |
| 6 | effective_size | Structural |
| 7 | betweenness | Centrality |
| 8 | is_broker_in_any_community | Community |
| 9 | num_communities_connected | Community |
| 10 | community_size_rank | Community |
| 11 | bridges_communities | Community |
| 12 | shared_anchor_count | Anchor |
| 13 | max_shared_anchor_overlap | Anchor |
| 14 | money_anchor_overlap | Anchor |
| 15 | location_anchor_overlap | Anchor |
| 16 | supplier_anchor_overlap | Anchor |
| 17 | temporal_fanout | Temporal |
| 18 | temporal_affinity | Temporal |
| 19 | heuristic_score | **Heuristic input** |

Feature 19 (the original heuristic) is included as an input to the
classifier — this means the classifier can *learn* when the heuristic
is reliable and when it should be overridden.

## Benchmark Results

**Setup:** 30 varied synthetic graphs, 24 train / 6 held-out (graph-disjoint),
seed 1000.

### Classifier vs Heuristic Baseline (same 6 held-out graphs)

| Metric | Heuristic Baseline | Trained Classifier |
|--------|-------------------|-------------------|
| **Precision** | 0.0 (no proposals) | **1.0** |
| **Recall** | 0.0 | **0.75** |
| **F1** | 0.0 | **0.857** |
| **TP** | 0 | 18 |
| **FP** | 0 | 0 |
| **FN** | 72 (missed all) | 6 |

**Best F1 point:** threshold 0.3, P=1.0, R=0.75, F1=0.857

### Per-node Discrimination

Mean classifier score for true positives minus true negatives: **0.728**
(strong separation).

### Original seed-42 Graph (reference)

| Metric | Heuristic (original) | Classifier (trained) |
|--------|---------------------|---------------------|
| Pair recall | 0.273 | 0.75 |
| Pair precision | 1.0 | 1.0 |

## How the Classifier Blends into Ghost Detection

In `src/graph/ghost_nodes.py`, when `GhostConfig.use_classifier=True`:

```python
confidence = (
    ghost_classifier_weight * classifier_affinity
    + (1 - ghost_classifier_weight) * heuristic
)
```

The classifier component is **transparent** — it appears as a
`ConfidenceComponent` in the finding, so analysts see exactly how much
the ML model contributed vs the original heuristic.

**Default weight:** 0.6 (classifier-majority) — configurable via
`GhostConfig.classifier_weight`.

## Production Deployment

```python
from src.graph.ghost_nodes import detect_ghost_nodes, GhostConfig

config = GhostConfig(
    use_classifier=True,
    classifier_model_path="data/models/ghost_classifier.pkl",
    classifier_weight=0.6,
)
result = detect_ghost_nodes(graph, config)
```

When the model file is missing or corrupted, detection **gracefully
falls back** to the original heuristic with no crash.

## Confidence Calibration

A separate isotonic calibrator (`src/xai/calibration.py`) maps the
blended confidence scores to calibrated probabilities. See
`docs/VALIDATION_REPORT.md` §2c for details.

## Known Limitations

1. **Recall cap at 0.75** — the classifier misses some coordinators that
   are embedded in high-engagement communities (dense local neighborhoods
   mask the structural-hole signal).
2. **Synthetic evaluation** — the benchmark uses planted coordinators in
   synthetic graphs. Real-world hidden coordinators may have different
   engagement patterns.
3. **Single graph type** — the current synthetic generator models
   communication/call networks. Transaction-heavy or social-graph
   networks may need additional feature engineering.
