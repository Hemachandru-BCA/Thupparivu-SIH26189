#!/usr/bin/env python3
"""Run one or more SentinelGraph pipeline stages and print JSON summaries.

Usage:
    python run_stage.py generate
    python run_stage.py preprocess
    python run_stage.py extract
    python run_stage.py graph
    python run_stage.py ghosts
    python run_stage.py evidence
    python run_stage.py findings
    python run_stage.py all
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.api import pipeline_steps  # noqa: E402
from src.api import paths  # noqa: E402


def run_evidence(_overrides=None):
    from src.xai.build_evidence import build_evidence_index

    count = build_evidence_index()
    return {"evidence_records": count, "output_path": str(paths.EVIDENCE_INDEX_PATH)}


def run_findings(_overrides=None):
    import json

    from src.xai.evidence_tracer import EvidenceStore
    from src.xai.findings import FindingBuilder, save_findings, validate_finding

    store = EvidenceStore.from_json(paths.EVIDENCE_INDEX_PATH)
    ghost_doc = json.loads(paths.GHOST_PREDICTIONS_PATH.read_text())
    ghosts = []
    if isinstance(ghost_doc, dict):
        for key in ("ghost_nodes", "ghosts", "predictions"):
            val = ghost_doc.get(key)
            if isinstance(val, list):
                ghosts = [g for g in val if isinstance(g, dict)]
                break
    elif isinstance(ghost_doc, list):
        ghosts = [g for g in ghost_doc if isinstance(g, dict)]
    builder = FindingBuilder(store, calibrator_path="data/models/confidence_calibrator.pkl")
    findings = builder.build_all(ghosts)
    reports = [validate_finding(f, store) for f in findings]
    builder.link_store(findings)
    out = save_findings(findings, paths.FINDINGS_PATH)
    return {
        "findings": len(findings),
        "valid": sum(1 for r in reports if r.valid),
        "invalid": sum(1 for r in reports if not r.valid),
        "output_path": str(out),
    }


def run_train_ranker(_overrides=None):
    """Train the supervised ghost ranker on synthetic ground truth."""
    import pickle
    from src.ml.ghost_ranker import GhostRanker, SIGNAL_NAMES, DEFAULT_RANKER_PATH

    # Load the graph
    if not paths.GRAPH_PKL_PATH.exists():
        raise FileNotFoundError(f"graph artifact missing at {paths.GRAPH_PKL_PATH}")
    with open(paths.GRAPH_PKL_PATH, "rb") as fh:
        graph = pickle.load(fh)

    # Find hidden coordinator names from persons.csv
    hidden_names = []
    if paths.PERSONS_CSV.exists():
        import csv
        with paths.PERSONS_CSV.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if str(row.get("is_hidden_coordinator", "")).strip().lower() == "true":
                    if row.get("full_name"):
                        hidden_names.append(row["full_name"])

    ranker = GhostRanker()
    X, y = ranker.generate_training_data(graph, hidden_names, n_negatives=5)
    print(f"Training data: {X.shape[0]} samples, {X.shape[1]} features, "
          f"{int(y.sum())} positives, {int((1-y).sum())} negatives")

    ranker.fit(X, y)

    # Cross-validation (5-fold)
    import numpy as np
    from sklearn.model_selection import KFold  # type: ignore
    try:
        kf = KFold(n_splits=min(5, max(2, X.shape[0] // 2)), shuffle=True, random_state=42)
        y_pred = np.zeros_like(y, dtype=float)
        for train_idx, test_idx in kf.split(X):
            ranker_fold = GhostRanker()
            ranker_fold.fit(X[train_idx], y[train_idx])
            for i in test_idx:
                y_pred[i] = ranker_fold.predict_proba(dict(zip(SIGNAL_NAMES, X[i])))

        y_bin = (y_pred > 0.5).astype(int)
        tp = int(((y_bin == 1) & (y == 1)).sum())
        fp = int(((y_bin == 1) & (y == 0)).sum())
        fn = int(((y_bin == 0) & (y == 1)).sum())
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        print(f"5-fold CV: precision={precision:.3f}, recall={recall:.3f}, F1={f1:.3f}")
        ranker.artifact.cv_metrics = {"precision": precision, "recall": recall, "f1": f1}
    except Exception as exc:  # noqa: BLE001
        print(f"Cross-validation skipped ({exc}); training on full set")

    # Calibrate
    if X.shape[0] >= 4:
        split = max(1, int(X.shape[0] * 0.2))
        X_val, y_val = X[:split], y[:split]
        X_tr, y_tr = X[split:], y[split:]
        ranker.fit(X_tr, y_tr)
        brier, ece = ranker.calibrate(X_val, y_val)
        print(f"Calibration: Brier={brier:.4f}, ECE={ece:.4f}")

    from datetime import datetime, timezone
    ranker.artifact.trained_at = datetime.now(timezone.utc).isoformat()
    ranker.fit(X, y)
    out = ranker.save(DEFAULT_RANKER_PATH)
    print(f"Saved to {out}")
    return {
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "positives": int(y.sum()),
        "negatives": int((1-y).sum()),
        "kind": ranker.artifact.kind,
        "output_path": str(out),
        "cv_metrics": ranker.artifact.cv_metrics,
    }


def run_anomalies(_overrides=None):
    """Run temporal anomaly detection on current artifacts."""
    import pickle
    from src.intelligence.temporal_anomaly import run_temporal_anomaly_detection

    if not paths.GRAPH_PKL_PATH.exists():
        raise FileNotFoundError(f"graph artifact missing at {paths.GRAPH_PKL_PATH}")
    with open(paths.GRAPH_PKL_PATH, "rb") as fh:
        graph = pickle.load(fh)

    anomalies = run_temporal_anomaly_detection(graph)
    return {
        "anomaly_count": len(anomalies),
        "output_path": str(paths.EXPORTS_DIR / "temporal_anomalies.json"),
    }


def run_embeddings(_overrides=None):
    """Build evidence embeddings index."""
    from src.xai.embeddings_store import EvidenceEmbeddingsStore

    store = EvidenceEmbeddingsStore()
    store.build()
    return {
        "record_count": store.record_count,
        "model_used": store.model_used,
        "output_path": str(paths.EXPORTS_DIR / "evidence_embeddings.npy"),
    }


def run_financial_patterns(_overrides=None):
    """Run financial intelligence analysis on current artifacts."""
    import pickle
    from src.intelligence.financial import run_financial_intelligence

    if not paths.GRAPH_PKL_PATH.exists():
        raise FileNotFoundError(f"graph artifact missing at {paths.GRAPH_PKL_PATH}")
    with open(paths.GRAPH_PKL_PATH, "rb") as fh:
        graph = pickle.load(fh)

    patterns = run_financial_intelligence(graph)
    return {
        "pattern_count": len(patterns),
        "output_path": str(paths.EXPORTS_DIR / "financial_patterns.json"),
    }


STAGES = {
    "generate": pipeline_steps.run_generate,
    "preprocess": pipeline_steps.run_preprocess,
    "extract": pipeline_steps.run_extract,
    "graph": pipeline_steps.run_graph_build,
    "ghosts": pipeline_steps.run_ghosts,
    "evidence": run_evidence,
    "findings": run_findings,
    "train_ranker": run_train_ranker,
    "anomalies": run_anomalies,
    "embeddings": run_embeddings,
    "financial_patterns": run_financial_patterns,
}


def main():
    stages = sys.argv[1:] or ["all"]
    if stages == ["all"]:
        stages = ["generate", "preprocess", "extract", "graph", "ghosts", "evidence", "findings", "train_ranker", "anomalies", "embeddings", "financial_patterns"]
    results = {}
    for stage in stages:
        t0 = time.time()
        print(f"\n=== STAGE: {stage} ===", flush=True)
        try:
            out = STAGES[stage]()
            results[stage] = {"ok": True, "seconds": round(time.time() - t0, 1), "out": out}
            print(json.dumps(results[stage], indent=2, default=str)[:4000], flush=True)
        except Exception as exc:  # noqa: BLE001
            results[stage] = {"ok": False, "seconds": round(time.time() - t0, 1), "error": repr(exc)}
            print(json.dumps(results[stage], indent=2, default=str)[:4000], flush=True)
            break
    (ROOT / "pipeline_run_results.json").write_text(json.dumps(results, indent=2, default=str))
    print("\nSaved to pipeline_run_results.json", flush=True)


if __name__ == "__main__":
    main()
