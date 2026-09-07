"""
build_evidence.py
-----------------
CLI entrypoint that builds (or rebuilds) the evidence index from the
current pipeline artifacts and writes it to ``data/exports/evidence_index.json``.

Usage:
    python -m src.xai.build_evidence
"""

from __future__ import annotations

import logging
import sys

from src.api import paths
from src.xai.evidence_tracer import build_store_from_artifacts

logger = logging.getLogger(__name__)


def build_evidence_index() -> int:
    store = build_store_from_artifacts(
        persons_csv=paths.PERSONS_CSV,
        calls_csv=paths.CALLS_CSV,
        transactions_csv=paths.TRANSACTIONS_CSV,
        meetings_csv=paths.MEETINGS_CSV,
        cleaned_records_path=paths.CLEANED_RECORDS_PATH,
        triplets_path=paths.GRAPH_TRIPLETS_PATH,
        graph_data_path=paths.GRAPH_DATA_PATH if paths.GRAPH_DATA_PATH.exists() else None,
        ghost_predictions_path=(
            paths.GHOST_PREDICTIONS_PATH if paths.GHOST_PREDICTIONS_PATH.exists() else None
        ),
    )
    out = store.to_json(paths.EVIDENCE_INDEX_PATH)
    print(f"Evidence index: {store.count()} records -> {out}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(build_evidence_index())
