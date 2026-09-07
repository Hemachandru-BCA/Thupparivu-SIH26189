# SentinelGraph AI — Architecture

## 1. Conceptual pipeline

```text
DATA SOURCES
   |
   +-- CSV (synthetic generator output)
   +-- API pages (api_loader, paged + retry)
   +-- PDF documents (pdf_loader, optional pypdf)
   |
   v
INGESTION                src/ingestion/
   |
   v
PREPROCESSING            src/preprocessing/
   +-- cleaning, normalization, dedupe
   +-- OCR pipeline (image docs)
   +-- translation abstractions
   +-- FIR / intelligence-report simulation
   |
   v
EXTRACTION               src/extraction/
   +-- NER: gazetteer + regex + spaCy statistical layer
   +-- relation extraction (rule + pattern)
   +-- event extraction
   |
   v
ENTITY RESOLUTION        src/resolution/
   +-- token alignment / Soundex / Levenshtein
   +-- clustering (similarity graph, canonical assignment)
   +-- deterministic GUID generation (uuid5 namespace)
   |
   v
GRAPH CONSTRUCTION       src/graph/graph_builder.py
   +-- nodes: guid, canonical_name, aliases, entity_type, attributes, metrics
   +-- edges: deterministic ids, relation, source record reference
   +-- evidence references (edge.attributes.record_id -> provenance)
   |
   +---------------------------+
   |                           |
   v                           v
GRAPH ANALYTICS          GHOST INFERENCE
(src/graph/analytics.py,   (src/graph/ghost_nodes.py)
 graph_embeddings.py)        +-- structural holes
   +-- PageRank              +-- shared anchors
   +-- betweenness           +-- temporal affinity
   +-- Louvain communities   +-- attribute affinity
   +-- embeddings            +-- confidence breakdown (components + weights)
   |
   +------------+--------------+
                |
                v
        EVIDENCE / XAI LAYER        src/xai/
                |
     +----------+-----------+
     |                      |
     v                      v
DOSSIER API            SIMULATION API
(src/xai/dossier_generator.py)  (src/graph/simulation.py)
     |                      |
     +----------+-----------+
                |
                v
       FASTAPI                  src/api/
                |
                v
   REACT INVESTIGATOR UI       frontend/ (Cytoscape explorer)
```

## 2. Implemented now vs adapter vs simulated

| Component | Class | Notes |
|---|---|---|
| Generator, ingestion, preprocessing, extraction, resolution, graph build | **implemented** | fully local, seeded |
| Analytics (PageRank/betweenness/Louvain/embeddings) | **implemented** | sampled guards for large graphs |
| Ghost inference | **implemented (heuristic inference)** | explicitly not a trained GNN; confidence = weighted components |
| Evidence layer | **implemented** | local JSON/in-memory index; `EvidenceBackend` protocol for future backends |
| Findings / dossiers | **implemented** | bounded-context RAG; `MockLLMProvider` default; LLM never source of truth |
| Counterfactual simulation | **implemented (simulation)** | counterfactual graph statistics, NOT real-world prediction |
| GraphStore | **implemented locally + adapter** | NetworkX default; Neo4j adapter optional |
| SourceRepository / DocumentStore / EventStream | **adapter interfaces** | PostgreSQL / S3 / Kafka optional, disabled by default; local FS + in-memory implementations included |
| LLM | **adapter** | mock default; OpenAI-compatible optional via env key |
| Airflow DAG | **example adapter** | shells out to the same `run_stage.py` stages |

## 3. Evidence provenance design

* `EvidenceRecord`: `evidence_id` (deterministic `EV-` uuid5), `source_type`
  (CALL / TRANSACTION / MEETING / FIR / INTELLIGENCE_REPORT / PERSON_PROFILE /
  TRIPLET / DOCUMENT), `source_record_id`, `source_uri`, `timestamp`,
  `text_excerpt`, `structured_fields`, sha256 `hash`, `provenance`
  (`observed_record` | `generated_synthetic`), `confidence`, `subject_ids`.
* `EvidenceStore` indexes records **and** their links to graph nodes
  (by guid, name tokens, person/account ids), graph edges (via
  `edge.attributes.record_id`) and findings.
* Evidence semantics: the index contains what the *system observed*
  (cleaned records + triplets), not the simulator's ground truth; raw
  synthetic CSVs are used for id↔name mapping and benchmarks only.
* Ghost anchors bind ghost hypotheses to real records.

## 4. XAI finding flow

```text
ghost prediction
  -> FindingBuilder.from_ghost()
       observed claims   (bound to evidence ids; unbindable anchors -> UNKNOWN)
       inferred claims   (predicted edges, probabilities)
       unknown claims    (identity, real-world existence, direction)
       counter-evidence  (aggregate direct-edge signals, validated store refs)
       graph signals     (shared anchors, community bridge)
       confidence components (attribute/temporal/embedding/structural-hole/weights)
  -> validate_finding(finding, store)
       - every evidence id exists
       - every observed claim cites evidence
       - labels valid, components present, unknowns listed
       - human review required, model version recorded
  -> findings.json + /api/findings/*
```

## 5. Dossier generation flow

```text
subject -> findings (subject-bound)
        -> evidence retrieval (node-linked records)
        -> timeline (chronological)
        -> counter-evidence
        -> bounded context (capped excerpts, explicit sections)
        -> LLMProvider.generate(prompt WITH prohibitions, context)
             parse -> DossierLLMOutput (Pydantic)   # strict
             invalid -> retry once -> deterministic non-LLM fallback
        -> Dossier (validated): executive summary, OBSERVED/INFERRED/
           UNKNOWN/CONTRADICTED sections, timeline, methodology,
           limitations, human_review {required: true}
        -> validate_dossier() (all cited ids exist, labels valid,
           status locked to DRAFT_FOR_HUMAN_REVIEW)
        -> data/exports/dossiers/DOSSIER-*.json
```

Prompt prohibitions (enforced for real providers): no invented evidence,
identities, timestamps or relationships; no guilt assertions; hypotheses
stay hypotheses; no fabricated citations.

## 6. Counterfactual simulation design

`counterfactual_node_removal(graph, node, depth, include_reranking)`:

1. **baseline context** (cached per artifact via `build_simulation_context`):
   snapshot metrics, Louvain partition, sampled betweenness;
2. **ego context**: depth-limited neighborhood (affected nodes) + incident
   edges (affected edges);
3. **removal**: rebuild projection + snapshot metrics on the damaged graph;
4. **deltas**: fragmentation, connectivity (relative efficiency loss), GCC
   loss, modularity, NMI, split/merged communities;
5. **new brokers**: sampled betweenness gain ranking (top 10);
6. **rerouting (Phase K)**: sampled former-neighbour pairs, alternate
   shortest paths after removal, `rerouting_score` = reconnected fraction;
7. every payload carries `method="NODE_REMOVAL_COUNTERFACTUAL"`, `warnings`
   and the **not-an-enforcement-recommendation** disclaimer.

Performance guards mirror the existing module: exact global efficiency/APL
below 1,500 nodes, seeded pair sampling above; sampled betweenness with
k=150–300. Full-graph request latency: ~26 s cold (baseline context build),
~12–28 s warm.

## 7. API organization (Phase R)

```text
/api/pipeline/*   generate | preprocess | extract | graph/build | ghosts | jobs
/api/data/*       persons | calls | transactions | meetings | records | summary
/api/graph/*      info | metadata | entities | nodes | triplets | edges |
                  ghosts | ghosts/{id}/evidence | metrics | data |
                  neighbors/{label} | subgraph | paths/{source}/{target}
/api/evidence/*   {id} | for-node | for-edge | for-finding | search |
                  timeline | stats/summary
/api/findings/*   list | {id} | generate
/api/simulation/* node-removal | compare | results
/api/dossiers/*   list | {id} | generate | {id}/review
/api/cases/*      list | create | {id} | patch | delete
/api/search       global search (nodes + ghosts + evidence)
/api/audit        recent audit entries
/api/health
```

Conventions: Pydantic request models with `extra="forbid"`, pagination
envelope `{items,total,page,page_size}`, query limits (page_size ≤ 500,
depth 1–4, max_nodes ≤ 5000), deterministic ordering, consistent
`{detail}` errors + `ARTIFACT_NOT_FOUND` envelope, request-size guard
(`SENTINELGRAPH_MAX_UPLOAD_BYTES`), append-only audit log.

## 8. Frontend architecture

* React 19 + Vite + Tailwind tokens + wouter + @tanstack/react-query.
* `frontend/src/components/cytoscape-graph.jsx` — Cytoscape.js explorer:
  pan/zoom/fit, selection, community coloring, PageRank sizing, dashed
  translucent ghost nodes (round-hexagon, `HYP` label), dashed inferred
  edges, evidence-highlighted edges, counterfactual overlay (removed=red,
  affected=amber border, brokers=cyan double border, others dimmed).
* `frontend/src/pages/explorer-page.jsx` — Phase W layout
  (filters | graph | inspector + evidence timeline).
* `frontend/src/pages/intelligence-pages.jsx` — Findings, Finding detail,
  Dossiers (+review), Evidence register, Simulation sandbox (+comparison),
  Global search.
* Legacy radial explorer preserved at `/network-legacy`.
* Server-side subgraph (`/api/graph/subgraph`) replaces client-side
  truncation; lazy expansion via depth/node-cap controls.

## 9. Data artifacts (data/)

| Path | Producer | Consumers |
|---|---|---|
| `synthetic/*.csv` | generator | preprocessing, benchmarks |
| `processed/cleaned_records.json` | preprocessing | extraction, evidence index |
| `processed/graph_triplets.json` | extraction | graph build, evidence index |
| `exports/graph.pkl` | graph build | API, simulation, adapters |
| `exports/graph_data.json` | graph build | API subgraph/paths, evidence linkage |
| `exports/graph_metrics.json` | analytics | API metrics |
| `exports/ghost_predictions.json` | ghost inference | API, findings builder |
| `exports/evidence_index.json` | `run_stage.py evidence` | evidence/findings/dossiers |
| `exports/findings.json` | `run_stage.py findings` or `POST /api/findings/generate` | dossiers, UI |
| `exports/dossiers/` | dossier API | UI, review |
| `exports/audit_log.jsonl` | audit middleware | `/api/audit` |
| `cases/*.json` | case API | UI |

## 10. Security / privacy posture (Phase AC)

* No secrets in source; all credentials via env (`.env.example`).
* Input validation everywhere (`extra="forbid"`, bounded query params).
* Request size limits + graph query limits (depth/node caps).
* Audit log records action + timestamp + object ids, never raw payloads.
* Case files, dossiers and findings carry explicit disclaimers; human-review
  status visible on every artifact.
