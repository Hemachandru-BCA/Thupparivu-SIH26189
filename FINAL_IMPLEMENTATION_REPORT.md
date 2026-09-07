# SentinelGraph AI — Final Implementation Report

**Project:** SIH26189 → `sentinelgraph-ai` — completing the investigation
graph prototype into an end-to-end, explainable intelligence sandbox.

**Deliverable shape:** the repository was restructured into the requested
`sentinelgraph-ai/` tree (`src/` layout) while preserving all working
modules, tests, data formats and pipeline semantics, then extended with the
three major missing capabilities: **evidence-grounded XAI, dossiers, and
interactive counterfactual simulation**, plus the interactive Cytoscape
explorer.

---

## 1. Implemented (complete)

### Backend core (preserved + verified)
- Synthetic generator (seeded, planted hidden coordinators), CSV/API
  ingestion, preprocessing (cleaner/OCR/standardizer/FIR+report
  simulation/translation abstractions), NER + relation + event extraction,
  entity resolution, NetworkX graph build, PageRank/betweenness/Louvain
  analytics, embeddings, ghost inference — all ported into `src/`, all 95
  original tests pass.
- `IMPLEMENTATION_BASELINE.md` records the actual Phase-A audit
  (commands + numbers + the one baseline test failure and its fix).

### Phase B — shared domain models
- `src/api/schemas.py`: `GraphNode`, `GraphEdge`, `GhostCandidate`,
  `FindingModel`, `SimulationRequest/ComparisonRequest`,
  `DossierRequest/DossierReviewRequest`, case models — Pydantic v2 with
  `extra="forbid"`.

### Phase C/D — evidence provenance + retrieval
- `src/xai/evidence_tracer.py`: `EvidenceRecord` (deterministic `EV-` ids,
  sha256 hash, provenance flags, structured fields), `EvidenceStore` +
  `EvidenceBackend` protocol (PostgreSQL/OpenSearch-ready), 40,292-record
  index over observed artifacts, node/edge/finding linkage, ranked search,
  chronological timelines, JSON persistence.
- API: `/api/evidence/{id}|for-node|for-edge|for-finding|search|timeline|stats`.

### Phase E — real XAI pipeline
- `src/xai/findings.py`: `Finding` with OBSERVED/INFERRED/UNKNOWN claims,
  counter-evidence, graph signals, confidence components + weights, model
  version, human-review gate. `validate_finding()` enforces the integrity
  contract (existence of every cited id, evidence-bound observed claims,
  label validity, component consistency, unknowns listed). Unbindable
  anchors are demoted to UNKNOWN instead of fabricating references.

### Phase F — LLM/RAG dossier generation
- `src/xai/llm_providers.py`: `LLMProvider` protocol, offline
  `MockLLMProvider` (default, deterministic), optional
  `OpenAICompatProvider` (env-keyed), `provider_from_env()`.
- `src/xai/dossier_generator.py`: bounded-context RAG (findings, evidence,
  timeline, counter-evidence), prohibited-actions prompt, strict
  `DossierLLMOutput` validation with one retry + deterministic fallback,
  `Dossier` schema with sections labelled OBSERVED/INFERRED/UNKNOWN/
  CONTRADICTED, methodology, limitations, `DRAFT_FOR_HUMAN_REVIEW` status,
  `validate_dossier()` + review endpoint.

### Phase G — dossier UI
- Dossiers page: generation form, cards with confidence/status, expandable
  labelled sections with clickable evidence chips, limitations, review
  recording.

### Phase H/I — interactive graph + ghost visualization
- `frontend/src/components/cytoscape-graph.jsx`: Cytoscape.js (lazy chunk);
  pan/zoom/fit, node/edge selection, search+focus, depth/node-cap expansion
  via the **server-side subgraph API**, community coloring, PageRank sizing,
  edge-type styling, evidence highlighting, ghost nodes as dashed
  translucent round-hexagon hypotheses with confidence labels, inferred-edge
  dashes, counterfactual overlay (removed/affected/brokers/dimmed), legend.
- `/network` now serves the explorer; the legacy radial view is preserved at
  `/network-legacy`.

### Phase J/K/L/M — counterfactual simulation + rerouting + UI + sandbox
- `counterfactual_node_removal()`: baseline vs counterfactual metrics,
  deltas, fragmentation/connectivity scores, community NMI/split/merge,
  new brokers (betweenness gain), alternate paths + `rerouting_score`
  (Phase K), affected nodes/edges, warnings, `method` label and the
  "NOT AN ENFORCEMENT RECOMMENDATION" disclaimer.
- `build_simulation_context()` caches the expensive baseline per artifact.
- `compare_interventions()` — Phase M comparison sandbox with
  `network_effect_rank`.
- API: `POST /api/simulation/node-removal|compare`, `GET /api/simulation/results`.
- UI: explorer "Counterfactual" button + overlay, dedicated sandbox page
  with depth/reranking controls, metric deltas, alternate paths, scenario
  comparison, loading states, warnings panel.

### Phase N/O — analytics + temporal
- Existing metrics preserved; degree/mention/transaction volumes ride along
  node attributes; evidence **timeline** endpoint + UI panel; composite
  scores expose their weights (existing impact breakdown retained).

### Phase P — path explainer
- `GET /api/graph/paths/{source}/{target}` — top-k simple paths, per-edge
  relations + evidence ids, articulation-point bottlenecks; UI paths panel
  (explorer) + evidence chips.

### Phase Q — case workspace
- `/api/cases` CRUD with items (entity/path/evidence/finding/simulation) and
  notes, local JSON store, explicit "not an official legal record"
  disclaimer; UI page kept from the original plus API-backed store.

### Phase R — API organization + hardening
- Route groups per spec (`/api/graph|evidence|findings|simulation|dossiers|
  cases|search|audit|pipeline|data`), `routes.py` aggregator, `extra=forbid`
  requests, pagination envelope, query limits (depth 1–4, max_nodes ≤5000,
  k ≤5, page_size ≤500), deterministic ordering, structured error envelopes
  + `ARTIFACT_NOT_FOUND`, request-size guard, append-only audit log with
  `/api/audit` view.

### Phase S — large-graph performance
- Server-side subgraph extraction with hard caps and PageRank-ranked
  truncation; lazy 1/2-hop expansion via depth controls in the UI; evidence
  fetched per selection; simulation context cached per artifact.

### Phase T/U/V — production adapters
- `src/adapters/`: `GraphStore` protocol + `NetworkXGraphStore`
  (subgraph/paths/neighbors), `SourceRepository` + PostgreSQL adapter,
  `DocumentStore` + S3 adapter (+ local FS impl), `EventStream` + Kafka
  adapter (+ in-memory impl), Neo4j `GraphStore` adapter with the Phase-U
  label/relationship schema and `inferred` flags, example Airflow DAG.
  All optional, lazy-importing, disabled-by-default, demo unaffected.

### Phase W/X — layout + search
- Explorer implements the filters | graph | inspector layout with timeline
  strip; global search across person/org/phone/account/location/document/
  evidence/ghost ids with type/id/display/confidence/quick-action.

### Phase Z/AB — tests + explainability validation
- 50 new backend tests (evidence, findings/dossier, simulation/adapters,
  API contracts, resolution/ingestion) — **145 passing total**, including
  the original 95.
- Automated `validate_finding`/`validate_dossier` run inside the generation
  endpoints (a malformed dossier cannot be persisted).

### Phase AC/AD — security + human oversight
- `.env.example` (no secrets in source), input validation, request/graph
  limits, safe audit logging; OBSERVED/MODEL-INFERENCE/HYPOTHESIS/
  SIMULATION separation enforced in data models, API payloads and UI copy.

### Phase AE/AF — pipeline monitor + demo mode
- Existing pipeline monitor preserved (per-stage job status via
  `/api/pipeline/jobs`); `run_stage.py` adds evidence/findings stages;
  `run_demo.py` provides the one-click deterministic demo + guided
  scenario (`--scenario`).

### Phase AG — documentation
- `README.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/DEMO_GUIDE.md`,
  `docs/VALIDATION_REPORT.md`, `docs/LIMITATIONS.md`,
  `IMPLEMENTATION_BASELINE.md`, this report; notebooks scaffolded.

---

## 2. Partially implemented

| Item | State | Remaining |
|---|---|---|
| Timeline filters (Phase O) | Evidence timeline per subject + graph events endpoint | cross-graph time-window filtering recomputing the subgraph server-side |
| Counter-evidence mining (Phase E) | aggregate signals (direct-edge counts) + validated store refs | record-level counter-evidence search strategies |
| Frontend automated tests (Phase Z) | production build verified; hooks are thin fetch wrappers over tested API contracts | vitest/react-testing-library suites for graph rendering, ghost selection, simulation launch |
| Pipeline monitor upgrade (Phase AE) | job status list per stage with timings | per-stage records/errors/warnings display + run IDs in the UI panel |
| Node2Vec/GraphSAGE-style embedding path | existing module retained with offline fallbacks | optional torch-geometric backend |

## 3. Not implemented (by design — optional production scope)

- Real PostgreSQL/OpenSearch/vector-backed evidence retrieval (interface ready).
- Live Kafka consumption workers (publisher adapter + topics documented).
- Neo4j live migration pipeline (adapter + import method provided; demo
  never requires it).
- Authentication/authorization/multi-tenancy (demo is localhost-only).
- Real (non-synthetic) data connectors and retention policies.

## 4. Original-vs-current mapping (completion)

| Phase | Requirement | Implementation | Completion | Remaining work |
|---|---|---|---|---|
| A | audit + baseline | IMPLEMENTATION_BASELINE.md with real numbers | 100% | — |
| B | shared schemas | src/api/schemas.py | 100% | — |
| C | evidence abstraction | src/xai/evidence_tracer.py | 100% | production backends |
| D | evidence index/retrieval | EvidenceStore + 6 endpoints | 100% (local) | OpenSearch/vector store |
| E | XAI pipeline | src/xai/findings.py + validation | 95% | richer counter-evidence |
| F | LLM/RAG dossiers | dossier_generator + llm_providers | 100% | real-provider prompt tuning |
| G | dossier UI | DossiersPage + review flow | 100% | — |
| H | interactive graph | Cytoscape explorer + subgraph API | 100% | WebGL renderer for 13k+ full-graph view |
| I | ghost visualization | ghost styling + inspector panels | 100% | — |
| J | simulation API | POST /api/simulation/node-removal | 100% | — |
| K | rerouting | alternate paths + rerouting_score | 100% | direction-aware rerouting |
| L | simulation UI | sandbox page + explorer overlay | 100% | — |
| M | comparison sandbox | compare_interventions + UI | 100% | — |
| N | analytics additions | preserved + exposed metrics | 90% | eigenvector centrality toggle |
| O | temporal analytics | evidence timeline + UI | 80% | time-window graph recomputation |
| P | path explainer | /api/graph/paths + UI | 100% | — |
| Q | case workspace | /api/cases + UI | 100% | — |
| R | API org + hardening | routes.py + limits + audit | 100% | — |
| S | large-graph perf | server-side subgraph + caches | 90% | viewport-based streaming for 100k+ |
| T | adapters | 5 interfaces + local impls | 100% | — |
| U | Neo4j path | adapter + schema | 90% | live migration smoke test |
| V | streaming/airflow | DAG example + Kafka adapter | 90% | consumer worker |
| W | layout | explorer 3-pane + timeline | 100% | — |
| X | search | /api/search + UI | 100% | fuzzy ranking |
| Y | visual differentiation | dashed/dimmed/labels/legend | 100% | — |
| Z | tests | 145 passing | 95% | frontend component tests |
| AA | validation benchmark | VALIDATION_REPORT.md, real numbers | 100% | — |
| AB | explainability validation | validate_finding/dossier automated | 100% | — |
| AC | security/privacy | env config, limits, audit log | 90% | auth for multi-user deploys |
| AD | human oversight | labelled hypotheses everywhere | 100% | — |
| AE | pipeline monitor | job status + timings | 80% | richer per-stage UI panel |
| AF | demo mode | run_demo.py + scenario | 100% | — |
| AG | documentation | 8 documents | 100% | — |

## 5. Validation (actual outputs)

* Tests: `145 passed in 35.18s` (`python -m pytest tests/ -q`).
* Ghost benchmark: precision **1.0**, pair recall **0.273** (F1 0.429),
  0 false positives, money/location control cases clean.
* Graph: 13,146 nodes / 23,982 edges; ER 13,275 → 13,146; 859 communities.
* Stage timings: generate 2.3s · preprocess 3.4s · extract 48.4s · graph
  31.0s · ghosts 40.0s · evidence 24.6s · findings ~2s.
* API latency: subgraph ~0.2s · paths 0.16s · evidence search ~0.1s warm ·
  simulation 38s cold / 12–28s warm.
* Frontend build: `✓ built in 3.31s` (cytoscape lazy chunk 444kB).

Full detail: `docs/VALIDATION_REPORT.md`.

## 6. Demo flow (exact)

```bash
python run_demo.py                 # deterministic chain (~2.5 min)
uvicorn src.api.main:app --port 8000 &
cd frontend && npm run dev         # http://localhost:5173
python run_demo.py --scenario      # guided walkthrough with real ids
```

Click path (Step 1–17 of the required journey): see `docs/DEMO_GUIDE.md`
§3 — every step is reachable in the UI; the dossier/simulation steps use
the ids printed by `run_demo.py --scenario`.

## 7. Known limitations

Summarized in `README.md §8`, fully in `docs/LIMITATIONS.md`. The most
important three: ghost recall is ~0.27 at precision 1.0 (synthetic
benchmark); simulation metrics above 1.5k nodes are sampled estimates; all
data and all conclusions are research-prototype grade, permanently labelled
as hypotheses requiring human review.
