#!/usr/bin/env python3
"""
run_demo.py -- one-click demo flow (Phase AF).

    python run_demo.py            # full chain: generate -> ... -> findings
    python run_demo.py --scenario # print the guided demo walkthrough

Deterministic: the generator uses RANDOM_SEED=42 by default, so the demo
reproduces the same dataset, graph and ghost candidates on every run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.api import paths  # noqa: E402

CHAIN = [
    ("generate", "Generate dataset"),
    ("preprocess", "Preprocess / clean / OCR / standardize"),
    ("extract", "NER + relation + event extraction"),
    ("graph", "Entity resolution + graph build + analytics"),
    ("ghosts", "Ghost (hidden intermediary) inference"),
    ("evidence", "Evidence provenance index"),
    ("findings", "XAI findings with evidence binding"),
]


def demo_scenario() -> dict:
    """Build the guided demo scenario from current artifacts."""
    import csv

    scenario = {"steps": [
        "Open the investigator UI (http://localhost:5173)",
        "Network explorer -> pick a ghost hypothesis (dashed node) or search an entity",
        "Ghost candidates -> inspect confidence breakdown + evidence",
        "Counterfactual sandbox -> simulate node removal (loading state ~30s)",
        "Findings (XAI) -> open a finding: observed / inferred / unknown are separated",
        "Dossiers -> generate for the finding's subject, review the draft",
    ]}

    ghosts = []
    if paths.GHOST_PREDICTIONS_PATH.exists():
        doc = json.loads(paths.GHOST_PREDICTIONS_PATH.read_text())
        ghosts = doc.get("ghost_nodes") or doc.get("ghosts") or []
    if ghosts:
        top = max(ghosts, key=lambda g: g.get("confidence", 0.0))
        scenario["ghost"] = {
            "ghost_id": top.get("ghost_id"),
            "label": top.get("label"),
            "confidence": top.get("confidence"),
            "between_communities": top.get("between_communities"),
            "subtype": top.get("subtype"),
            "note": "HYPOTHESIS - not a confirmed identity",
        }
        targets = (top.get("predicted_edges") or [])
        if targets:
            scenario["simulation_suggestion"] = targets[0].get("target")

    findings = []
    if paths.FINDINGS_PATH.exists():
        findings = json.loads(paths.FINDINGS_PATH.read_text()).get("findings", [])
    if findings:
        scenario["finding_id"] = findings[0]["id"]
        scenario["dossier_subject"] = findings[0]["subject_id"]

    coordinators = []
    if paths.PERSONS_CSV.exists():
        with paths.PERSONS_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if str(row.get("is_hidden_coordinator", "")).lower() == "true":
                    coordinators.append({"person_id": row["person_id"],
                                         "name": row["full_name"],
                                         "gang": row.get("gang_id")})
    scenario["planted_hidden_coordinators"] = coordinators[:6]
    scenario["ground_truth_note"] = (
        "For benchmarking only - in demo mode you may reveal the planted "
        "coordinators to compare with ghost hypotheses. Never do this with "
        "real casework data."
    )
    return scenario


def main() -> int:
    parser = argparse.ArgumentParser(description="SentinelGraph one-click demo")
    parser.add_argument("--scenario", action="store_true",
                        help="print the guided demo scenario from current artifacts")
    parser.add_argument("--skip-generate", action="store_true",
                        help="reuse existing synthetic data")
    args = parser.parse_args()

    if args.scenario:
        print(json.dumps(demo_scenario(), indent=2))
        return 0

    from run_stage import STAGES

    stages = CHAIN[1:] if args.skip_generate else CHAIN
    print("SentinelGraph AI - deterministic demo run")
    for key, label in stages:
        print(f"\n=== {label} ===", flush=True)
        out = STAGES[key]()
        print(json.dumps(out, indent=2, default=str)[:1500], flush=True)

    print("\nDemo data ready. Start the API + UI:")
    print("  uvicorn src.api.main:app --port 8000")
    print("  cd frontend && npm run dev")
    print("\nGuided walkthrough: python run_demo.py --scenario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
