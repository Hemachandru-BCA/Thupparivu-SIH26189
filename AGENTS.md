# AGENTS.md

## Purpose
This repository is a deterministic, explainable criminal-network intelligence sandbox. It generates synthetic data, ingests evidence, builds a graph, infers ghost nodes, and produces XAI findings and dossier drafts without automatically recommending enforcement actions.

## Project overview
- Python app and data pipeline under `src/`
- Frontend app under `frontend/`
- Tests under `tests/`
- Data artifacts under `data/`
- Docs and reporting in the repo root and `docs/`

## Core safety rules
- Treat all findings and dossiers as `DRAFT_FOR_HUMAN_REVIEW`.
- Keep observed, inferred, unknown, and contradicted claims separated.
- Never treat ghost candidates as identities or guilt probabilities.
- Preserve evidence provenance and verification; validate finding IDs before presenting them.
- Simulation outputs must remain advisory and not enforcement recommendations.

## Local setup
```bash
cd sentinelgraph-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Normal workflow
1. Run the smallest relevant test or validation before and after changes.
2. Prefer focused modifications over broad rewrites.
3. Keep new code consistent with the repository’s existing patterns and naming style.
4. Prefer deterministic behavior and seed-based outputs where relevant.

## Useful commands
```bash
# full demo
python run_demo.py

# stage-based pipeline
python run_stage.py generate
python run_stage.py preprocess
python run_stage.py extract
python run_stage.py graph
python run_stage.py ghosts
python run_stage.py evidence
python run_stage.py findings

# tests
python -m pytest tests/ -q
python -m pytest tests/ -q -m "not slow"

# frontend
cd frontend && npm install && npm run build
```

## Key directories
- `src/ingestion/`: CSV/API/PDF ingestion
- `src/preprocessing/`: cleaning, OCR, translation, standardization
- `src/extraction/`: NER, relation extraction, event extraction, pipeline
- `src/resolution/`: entity resolution and matching
- `src/graph/`: graph build, analytics, ghost inference, simulations
- `src/xai/`: evidence tracing, finding generation, dossier generation
- `src/api/`: FastAPI routes and services
- `tests/`: pytest coverage for API, pipeline, extraction, and validation
- `frontend/src/`: React + Vite investigator UI

## When editing
- Update or add tests for behavior changes when practical.
- Keep outputs reproducible and deterministic for seeded synthetic data.
- Maintain schema validation and evidence linking where applicable.
- For optional adapters, prefer lazy imports and clear configuration errors instead of auto-enabling them.

## Default repository expectations
- Python 3.12 is recommended.
- Use pytest for validation.
- Prefer targeted, repo-native solutions rather than introducing unrelated libraries.
- Keep any generated outputs in the expected data directories and avoid breaking the local demo flow.
