"""
paths.py
--------
Single source of truth for every artifact path the API reads/writes.

Everything is resolved to an absolute path from the project root, so the
API behaves the same no matter which directory `uvicorn` is launched from.

sentinelgraph-ai layout (data lives under data/):

    data/synthetic/    generator output (persons/calls/transactions/meetings)
    data/processed/    preprocessing + extraction output (cleaned_records,
                       graph_triplets)
    data/exports/      graph build + ghost detection + XAI artifacts
    data/raw/          user-supplied source files (optional)
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # .../sentinelgraph-ai

DATA_DIR = PROJECT_ROOT / "data"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
RAW_DIR = DATA_DIR / "raw"

GRAPH_TRIPLETS_PATH = PROCESSED_DIR / "graph_triplets.json"

GRAPH_OUTPUT_DIR = EXPORTS_DIR
GRAPH_PKL_PATH = GRAPH_OUTPUT_DIR / "graph.pkl"
GRAPH_DATA_PATH = GRAPH_OUTPUT_DIR / "graph_data.json"
GRAPH_METRICS_PATH = GRAPH_OUTPUT_DIR / "graph_metrics.json"
GHOST_PREDICTIONS_PATH = GRAPH_OUTPUT_DIR / "ghost_predictions.json"

CLEANED_RECORDS_PATH = PROCESSED_DIR / "cleaned_records.json"

PERSONS_CSV = SYNTHETIC_DIR / "persons.csv"
CALLS_CSV = SYNTHETIC_DIR / "calls.csv"
TRANSACTIONS_CSV = SYNTHETIC_DIR / "transactions.csv"
MEETINGS_CSV = SYNTHETIC_DIR / "meetings.csv"

# --- XAI layer artifacts ---------------------------------------------------- #
EVIDENCE_INDEX_PATH = GRAPH_OUTPUT_DIR / "evidence_index.json"
FINDINGS_PATH = GRAPH_OUTPUT_DIR / "findings.json"
DOSSIERS_DIR = GRAPH_OUTPUT_DIR / "dossiers"
SIMULATION_RESULTS_PATH = GRAPH_OUTPUT_DIR / "simulation_results.json"
CASES_DIR = PROJECT_ROOT / "data" / "cases"
AUDIT_LOG_PATH = GRAPH_OUTPUT_DIR / "audit_log.jsonl"

for _d in (DATA_DIR, SYNTHETIC_DIR, PROCESSED_DIR, GRAPH_OUTPUT_DIR, DOSSIERS_DIR, CASES_DIR):
    _d.mkdir(parents=True, exist_ok=True)
