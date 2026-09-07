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
    builder = FindingBuilder(store)
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


STAGES = {
    "generate": pipeline_steps.run_generate,
    "preprocess": pipeline_steps.run_preprocess,
    "extract": pipeline_steps.run_extract,
    "graph": pipeline_steps.run_graph_build,
    "ghosts": pipeline_steps.run_ghosts,
    "evidence": run_evidence,
    "findings": run_findings,
}


def main():
    stages = sys.argv[1:] or ["all"]
    if stages == ["all"]:
        stages = ["generate", "preprocess", "extract", "graph", "ghosts", "evidence", "findings"]
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
