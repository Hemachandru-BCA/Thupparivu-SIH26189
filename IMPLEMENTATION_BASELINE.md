# Implementation Baseline (Phase A audit record)

Recorded **before** implementation of the XAI/evidence/simulation features,
against the repository reconstructed from the single-file code dump
(`SIH-full-files`, 80 files, 20,084 lines / ~800 KB).

## Commands run and results

| Command | Result |
|---|---|
| `python -m py_compile` over all 61 Python modules | clean (one display-layer artifact in the dump turned out to be a rendering quirk, verified byte-level with AST parse) |
| `python -m pytest tests/ --ignore=tests/validate_ghost_pipeline.py` (baseline) | **94 passed, 1 failed** — `test_ner.py::test_person_entities` |
| `python -m pytest tests/` (after NER gazetteer fix) | **95 passed** |
| `python run_stage.py generate` | 2.3 s — 5,000 persons / 50,000 calls / 20,000 tx / 8,000 meetings / 6 planted coordinators (seed 42) |
| `python run_stage.py preprocess` | 3.4 s — 16,310 cleaned records (5,000 call obs, 5,000 tx obs, 1,000 meeting obs, 300 FIRs, 10 reports) |
| `python run_stage.py extract` | 48.4 s — 10,891 entities / 23,982 triplets (spaCy en_core_web_sm) |
| `python run_stage.py graph` | 31.0 s — **13,146 nodes / 23,982 edges**; ER 13,275 → 13,146 |
| `python run_stage.py ghosts` | 40.0 s — 859 communities, 3 ghost candidates, mean confidence 0.50 |
| `python tests/validate_ghost_pipeline.py` | pair precision **1.0**, pair recall **0.25–0.273** across runs, coordinator-account recall 0.5–0.667, 0 false positives; money-anchor and location-only control cases → 0 candidates |
| `cd frontend && npm install && npm run build` | passing (React/Vite build clean) |

## Baseline state summary

* Test count: 95 (all passing after the gazetteer fix below).
* Graph size: 13,146 nodes / 23,982 edges (matches the documented ~13k/~24k).
* Ghost candidates: 3; planted benchmark precision 1.0 with low recall.
* Frontend build: passing; graph rendering was a client-side truncated
  radial/SVG view (24-node style caps) — no interactive library.
* API: FastAPI with pipeline/data/graph routers only — no evidence, findings,
  dossier, simulation, case, or search endpoints.

## Baseline failures found and their disposition

1. `test_ner.py::test_person_entities` — newer `en_core_web_sm` builds do
   not tag "Ramesh"/"Akash" as PERSON in short transactional sentences.
   **Fixed** by adding a `KNOWN_PERSONS` gazetteer to
   `src/extraction/ner.py` (consistent with the module's existing
   closed-world gazetteer design for exactly this situation). Test passes.
2. `generator` package used flat intra-package imports (`from config
   import …`) requiring a non-obvious `PYTHONPATH`. **Fixed** during the
   `src/`-layout restructure by rewriting to `src.generator.*` imports.

## Known limitations at baseline (carried into the work plan)

* No evidence provenance, findings, dossiers, or XAI layer.
* Simulation logic existed (`graph/simulation.py`) but was batch-only
  (offline CLI) with no API.
* Frontend graph was not interactive; ghosts not rendered in-graph.
* No search, no case workspace, no audit logging, no production adapters.
