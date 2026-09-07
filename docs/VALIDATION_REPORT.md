# SentinelGraph AI — Validation Report

**Rule: every number below comes from an actual run.** Nothing is hard-coded
or aspirational. Re-run with:

```bash
python -m pytest tests/ -q                 # test suite
python tests/validate_ghost_pipeline.py    # planted-coordinator benchmark
python run_demo.py                         # stage timings
```

---

## 1. Test suite

Command: `python -m pytest tests/ -q`

```text
145 passed in 35.18s
```

Breakdown:

| Suite | Tests | Covers |
|---|---|---|
| Original ported suites (pipeline, standardizer, OCR, ingestion, NER, FIR/reports, generator, cleaner, translator, event extractor) | 95 | pipeline stages |
| `test_xai_evidence.py` | 8 | evidence records, hashing, ids, search, timeline, roundtrip, real-index linkage |
| `test_xai_findings_dossier.py` | 8 | finding structure/labels, validation (incl. fabricated-evidence rejection), dossier generation/validation, broken-LLM fallback, mock determinism |
| `test_simulation_and_adapters.py` | 12 | counterfactual contract, unknown-node error, comparison ranking, precomputed-context equivalence, rerouting bounds, GraphStore protocol, adapter config guards, local document store, in-memory event stream |
| `test_api_routes.py` | 13 | API contracts: evidence/findings/dossiers/cases/search/subgraph/paths/pagination/audit/validation |
| `test_resolution_ingestion.py` | 9 | clustering strategies, deterministic GUIDs, PDF loader guards |
| `tests/validate_ghost_pipeline.py` | (benchmark script) | planted-coordinator recovery |

The single `slow`-marked test (full-graph counterfactual smoke) is included
in the 145; deselect with `-m "not slow"` for a ~20s run.

## 2. Planted hidden-coordinator benchmark

Command: `python tests/validate_ghost_pipeline.py`
(dataset: default generator config, seed 42 → 5,000 persons / 50,000 calls /
20,000 transactions / 8,000 meetings / 6 planted hidden coordinators)

Latest run (`data/exports/validation_results_full.json`):

```json
{
  "hidden_coordinators": 6,
  "ground_truth_pairs": 12,
  "ghost_candidates": 3,
  "true_positive_pairs": 3,
  "false_positive_pairs": 0,
  "pair_precision": 1.0,
  "pair_recall": 0.273,
  "predicted_planted_accounts": 3,
  "coordinator_account_recall": 0.5,
  "detected_accounts": [
    "ACC-COORD-P004995", "ACC-COORD-P004999", "ACC-COORD-P005000"
  ]
}
```

Derived metrics: **F1 = 0.429** (precision 1.0, recall 0.273).

Notes:
* Community detection and betweenness sampling are seeded but the broker
  pool has near-ties, so runs vary slightly: observed pair recall across
  runs: 0.25–0.273, coordinator-account recall 0.5–0.667, and one run
  detected 4 planted accounts. **Precision stayed 1.0 in every observed run
  (0 false positives).**
* The planted money-anchor and common-location control cases correctly
  produce **0 ghost candidates** (no false structure invented).
* Recall is capped by the detector's conservative pair proposals; see
  `docs/LIMITATIONS.md`.

## 3. Graph scale

From the same run (metadata in `graph_data.json`):

```text
nodes: 13,146   edges: 23,982
entity resolution: 13,275 mentions -> 13,146 resolved entities
relation mix: USES_ACCOUNT 8087 · MET 4132 · TRANSFERRED_TO 4049 ·
              LOCATED_AT 5000 · CALLED 2553 · ASSOCIATED_WITH 161
communities detected: 859
```

This matches the documented baseline (~13k nodes / ~24k edges).

## 4. Stage timings (measured, this machine)

| Stage | Wall time | Output |
|---|---|---|
| generate | 2.3 s | 5,000 persons, 50k calls, 20k tx, 8k meetings |
| preprocess | 3.4 s | 16,310 cleaned records (300 FIRs, 10 reports) |
| extract (spaCy en_core_web_sm) | 48.4 s | 10,891 entities / 23,982 triplets |
| graph build + analytics | 31.0 s | 13,146 nodes / 23,982 edges |
| ghost inference | 40.0 s | 859 communities, 3 candidates |
| evidence index build | 24.6 s | 40,292 records |
| findings build | ~2 s | 3 findings (all validate) |
| **end-to-end (`run_demo.py`)** | **~2.5 min** | full XAI chain ready |

## 5. API latency (measured, full 13k-node graph)

| Endpoint | Cold | Warm |
|---|---|---|
| `GET /api/graph/subgraph?depth=2&max_nodes=50` | ~0.2 s | ~0.1 s |
| `GET /api/graph/paths/{a}/{b}?k=2` | 0.16 s | <0.1 s |
| `GET /api/evidence/search?q=called` | ~1.6 s (index load) | ~0.1 s |
| `POST /api/findings/generate` | ~2 s | ~2 s |
| `POST /api/dossiers/generate` | ~2 s | ~2 s |
| `POST /api/simulation/node-removal` (13k graph) | 38 s (incl. 26 s baseline context build) | ~12–28 s |

Notes: sampled metrics (efficiency/APL/betweenness) keep the simulation
bounded; the baseline context is cached per artifact file, so subsequent
requests skip recompute. These are prototype latencies on a shared VM —
treat as indicative only.

## 6. XAI integrity validation (automated)

`validate_finding` / `validate_dossier` run on every generated artifact
(also exposed via the generate endpoints). Latest full run:

```text
findings: 3 generated, 3 valid, 0 invalid
dossiers: generated + validated OK (0 errors, 0 warnings)
```

Checks enforced: evidence ids exist · observed claims cite evidence ·
labels valid · confidence components present and consistent ·
counter-evidence searched · unknowns listed · model version recorded ·
human review required · dossier status locked to DRAFT_FOR_HUMAN_REVIEW.

## 7. Frontend build

```text
npm run build
✓ 1648 modules transformed.
dist/assets/index-*.js           377 kB │ gzip: 107 kB
dist/assets/cytoscape.esm-*.js   444 kB │ gzip: 142 kB   (lazy chunk)
✓ built in 3.3s
```

## 8. Baseline regression check

The pre-existing 95-test suite was run before implementation began
(94 pass / 1 fail on the extracted baseline due to a spaCy
`en_core_web_sm` PERSON-recognition regression; fixed by adding the
`KNOWN_PERSONS` gazetteer in `src/extraction/ner.py`, matching the module's
existing closed-world gazetteer design). After implementation: all 95
original tests still pass unchanged alongside the 50 new ones.
