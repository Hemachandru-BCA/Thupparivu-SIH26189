# SentinelGraph AI — API Reference

Base URL (local demo): `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs` (Swagger UI)

All list endpoints return the pagination envelope:

```json
{ "items": [...], "total": 123, "page": 1, "page_size": 50 }
```

Errors: FastAPI `{"detail": "..."}` for validation/route errors; missing
pipeline artifacts return `404 {"error": "ARTIFACT_NOT_FOUND", "detail": "..."}`
or `{"detail": ...}` depending on the raise site; request bodies above
`SENTINELGRAPH_MAX_UPLOAD_BYTES` return `413`.

---

## Health

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | liveness + version |

## Pipeline triggers (`/api/pipeline/*`)

| Method | Path | Body | Description |
|---|---|---|---|
| POST | `/api/pipeline/generate` | `GenerateRequest` (all optional: NUM_GANGS, NUM_PEOPLE, NUM_CALLS, NUM_TRANSACTIONS, NUM_MEETINGS, NUM_HIDDEN_COORDINATORS, RANDOM_SEED) | synthetic dataset generation |
| POST | `/api/pipeline/preprocess` | `PreprocessRequest` | cleaning / FIRs / OCR sample |
| POST | `/api/pipeline/extract` | `ExtractRequest` | NLP extraction → graph_triplets.json |
| POST | `/api/pipeline/graph/build` | `GraphBuildRequest` | resolution + graph + analytics |
| POST | `/api/pipeline/ghosts` | `GhostDetectRequest` | hidden-intermediary inference |
| POST | `/api/pipeline/run-all` | `RunAllRequest` | full chain |
| GET | `/api/pipeline/jobs` | — | async job status list |
| GET | `/api/pipeline/jobs/{job_id}` | — | one job |

Extra fields are rejected (`422`) so typos fail fast.

## Raw data (`/api/data/*`)

`GET /api/data/{persons|calls|transactions|meetings|records|summary}` with
`page`, `page_size` and per-type filters.

## Graph (`/api/graph/*`)

| Method | Path | Params | Description |
|---|---|---|---|
| GET | `/api/graph/info` | — | artifact flags + counts (dashboard polling) |
| GET | `/api/graph/metadata` | — | extraction metadata block |
| GET | `/api/graph/entities` | `page,page_size,type,min_mentions` | extracted entities |
| GET | `/api/graph/nodes` | `page,page_size` | nodes vocabulary alias |
| GET | `/api/graph/triplets` | `relation,source,target,min_confidence` | extracted triplets |
| GET | `/api/graph/edges` | `relation` | edges vocabulary alias |
| GET | `/api/graph/events` | `entity_id` | events from triplets file |
| GET | `/api/graph/ghosts` | `page,page_size` | ghost predictions |
| GET | `/api/graph/ghosts/{ghost_id}/evidence` | — | one ghost + full evidence payload |
| GET | `/api/graph/metrics` | — | graph-level metrics (404 if not built) |
| GET | `/api/graph/data` | — | full node-link document |
| GET | `/api/graph/neighbors/{node_label}` | — | incident edges by label |
| GET | `/api/graph/subgraph` | `node_id` (required), `depth` (1–4, default 2), `max_nodes` (1–5000, default 500), `entity_type`, `include_ghosts` | **server-side subgraph extraction** with hard caps; edges carry `evidence_ids`; response has `method: SERVER_SIDE_SUBGRAPH` and `truncated` flag |
| GET | `/api/graph/paths/{source}/{target}` | `k` (1–5) | **path explainer**: top-k simple paths with edge relations, `evidence_ids` per edge and articulation-point `bottleneck_nodes` |

## Evidence (`/api/evidence/*`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/evidence/{evidence_id}` | one record (excerpt, hash, provenance, structured fields) |
| GET | `/api/evidence/for-node/{node_id}` | evidence linked to a node/ghost (paged) |
| GET | `/api/evidence/for-edge/{edge_id}` | evidence supporting one edge |
| GET | `/api/evidence/for-finding/{finding_id}` | evidence bound to a finding |
| GET | `/api/evidence/search` | `q` (min 2 chars), `source_type`, `limit` — ranked keyword search |
| GET | `/api/evidence/timeline/{subject_id}` | chronological evidence for a subject |
| GET | `/api/evidence/stats/summary` | total + counts by source type |

Evidence record shape:

```json
{
  "evidence_id": "EV-2f7e758e-…",
  "source_type": "CALL",
  "source_record_id": "C0003589",
  "source_uri": "data/processed/cleaned_records.json#C0003589",
  "timestamp": "2025-10-23T20:08:56",
  "ingested_at": "2026-09-06T…",
  "text_excerpt": "Aaron Abbott called Kari Johnson for 113 seconds …",
  "structured_fields": { "…": "…" },
  "hash": "sha256…",
  "provenance": "generated_synthetic",
  "confidence": 0.53,
  "subject_ids": ["P002561", "P000027"]
}
```

## Findings (XAI) (`/api/findings/*`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/findings` | list (filters: `status`, `min_confidence`) |
| GET | `/api/findings/{finding_id}` | full finding (observed/inferred/unknown, graph signals, components, limitations) |
| POST | `/api/findings/generate` | rebuild findings from ghosts + evidence index (`min_confidence` query) |

Finding shape (abridged): `id`, `finding_type=HIDDEN_INTERMEDIARY`,
`subject_id` (ghost id), `confidence`, `confidence_components[]`,
`status="HYPOTHESIS"`, `method="STRUCTURAL_HOLE_ANALYSIS"`, `observed[]`,
`inferred[]`, `unknown[]`, `supporting_evidence_ids[]`,
`counter_evidence_ids[]`, `graph_signals[]`, `limitations[]`,
`human_review{required:true}`, `model_version`.

## Simulation (`/api/simulation/*`)

| Method | Path | Body | Description |
|---|---|---|---|
| POST | `/api/simulation/node-removal` | `{"node_id": "…", "depth": 2, "include_reranking": true}` | counterfactual node removal |
| POST | `/api/simulation/compare` | `{"node_ids": ["…", …]}` (1–5) | comparison sandbox, ranked by network effect |
| GET | `/api/simulation/results` | `k` | stored batch simulation document |

Response (abridged):

```json
{
  "simulation_id": "SIM-…",
  "target_node_id": "…", "target_name": "…", "depth": 2,
  "baseline": { "nodes": 13146, "fragmentation": 0.10, "…": "…" },
  "counterfactual": { "…": "…" },
  "delta": { "fragmentation_delta": 0.0, "gcc_size_loss": 0, "…": "…" },
  "fragmentation_score": 0.108,
  "connectivity_change": 0.0104,
  "community_changes": { "num_communities_before": 859, "…": "…" },
  "new_brokers": [{ "guid": "…", "betweenness_gain": 0.004 }],
  "alternate_paths": [{ "source": "…", "target": "…", "path": ["…"] }],
  "rerouting_score": 0.76,
  "affected_nodes": ["…"], "affected_edges": ["…"],
  "warnings": ["Counterfactual simulation only: …"],
  "method": "NODE_REMOVAL_COUNTERFACTUAL",
  "disclaimer": "NETWORK EFFECT SCORE - analytical counterfactual, NOT an enforcement recommendation."
}
```

Latency: ~26 s cold (baseline context build per artifact), ~12–28 s warm.

## Dossiers (`/api/dossiers/*`)

| Method | Path | Body | Description |
|---|---|---|---|
| GET | `/api/dossiers` | — | summary list |
| GET | `/api/dossiers/{dossier_id}` | — | full dossier |
| POST | `/api/dossiers/generate` | `{"subject_id": "…", "finding_ids": null, "max_evidence": 40}` | generate + validate (500 if validation fails) |
| POST | `/api/dossiers/{dossier_id}/review` | `{"reviewer": "…", "decision": "endorsed\\|rejected\\|changes_requested", "note": "…"}` | record human review |

Dossier sections label items `OBSERVED | INFERRED | UNKNOWN | CONTRADICTED`;
status is always `DRAFT_FOR_HUMAN_REVIEW` until a human review is recorded
(and even then the note states it is not automatically court-ready).

## Cases (`/api/cases/*`)

| Method | Path | Body | Description |
|---|---|---|---|
| GET | `/api/cases` | — | list |
| POST | `/api/cases` | `{"title": "…", "description": "…"}` | create (disclaimer included) |
| GET | `/api/cases/{case_id}` | — | full case |
| PATCH | `/api/cases/{case_id}` | `{"title"?, "description"?, "add_item"?: {"kind": "entity\\|path\\|evidence\\|finding\\|simulation", "ref_id": "…", "note": ""}, "remove_item"?, "note"?}` | update |
| DELETE | `/api/cases/{case_id}` | — | delete |

## Search & audit

| Method | Path | Description |
|---|---|---|
| GET | `/api/search?q=…&limit=20` | global search over nodes, ghosts, evidence |
| GET | `/api/audit?limit=100` | recent audit entries (`action`, `timestamp`, `object_ids`) |

## Rate / size limits

* `page_size` ≤ 500, `limit` ≤ 500 (evidence timeline).
* `depth` ∈ [1,4]; `max_nodes` ≤ 5000 (subgraph).
* `k` ≤ 5 (paths).
* Request body ≤ `SENTINELGRAPH_MAX_UPLOAD_BYTES` (default 2 MiB).
* Comparison scenarios ≤ 5 nodes.
