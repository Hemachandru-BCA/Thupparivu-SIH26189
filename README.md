# SentinelGraph AI

An end-to-end, explainable criminal-network intelligence sandbox:
synthetic data generation → ingestion → preprocessing (OCR / translation) →
NER + relation + event extraction → entity resolution → knowledge graph →
graph analytics → hidden-intermediary ("ghost") inference → **evidence
provenance → XAI findings → dossiers → counterfactual simulation →
investigator UI**.

> **Safety posture.** Observed data, model inference, hypotheses and
> simulations are labelled separately everywhere. Confidence values are
> weighted blends of graph signals — never probabilities of guilt. Ghost
> candidates are structural hypotheses, not identities. Dossiers are always
> `DRAFT_FOR_HUMAN_REVIEW`. The system never recommends enforcement actions.

---

## 1. What is implemented

| Area | Status |
|---|---|
| Synthetic dataset generator (gangs, persons, calls, transactions, meetings, planted hidden coordinators) | ✅ implemented (deterministic, seeded) |
| Ingestion — CSV loader, API loader (paged, retries), **PDF loader (pypdf, optional)** | ✅ |
| Preprocessing — cleaning, dedupe, standardizer, OCR pipeline, translation abstractions, FIR/report simulation | ✅ |
| Extraction — rule+statistical NER (spaCy), relation extraction, event extraction | ✅ |
| Entity resolution — token alignment, Soundex, Levenshtein, closed-world gazetteer + **clustering strategies + deterministic GUID generation** | ✅ |
| Graph — NetworkX MultiDiGraph build, artifacts (`graph.pkl` / `graph_data.json` / `graph_metrics.json`) | ✅ |
| Analytics — PageRank, betweenness, degree, community detection (Louvain), embeddings (Node2Vec-style) | ✅ |
| Ghost inference — structural holes, shared anchors, temporal affinity, community bridging, confidence breakdown | ✅ |
| **Evidence provenance layer** — normalized records, deterministic ids, sha256 hashes, provenance flags, node/edge/finding linkage, search, timelines | ✅ |
| **XAI findings** — OBSERVED / INFERRED / UNKNOWN separation, counter-evidence, confidence components, automated validation | ✅ |
| **Dossier generation** — RAG-style bounded context, offline `MockLLMProvider` (default) + optional OpenAI-compatible adapter, schema validation, deterministic fallback | ✅ |
| **Counterfactual simulation** — node removal with baseline/counterfactual metrics, community changes, new brokers, rerouting/alternate paths, comparison sandbox | ✅ |
| **Interactive graph explorer** — Cytoscape.js, server-side subgraph extraction, ghost rendering, evidence highlighting, simulation overlay | ✅ |
| Case workspace — local JSON-backed investigator collections | ✅ |
| Global search — nodes, ghosts, evidence in one endpoint | ✅ |
| API hardening — Pydantic validation, pagination, query limits, structured errors, audit log, request-size guard | ✅ |
| Production adapters — PostgreSQL / S3 / Kafka / Neo4j / Airflow (optional, disabled by default) | ✅ interfaces + local implementations |
| Tests — 145 passing (unit + integration + API contracts) | ✅ |

See `FINAL_IMPLEMENTATION_REPORT.md` for the full phase-by-phase mapping and
`LIMITATIONS.md` for what is explicitly *not* implemented.

---

## 2. Project structure

```text
sentinelgraph-ai/
├── data/
│   ├── raw/                  # user-supplied source files (optional)
│   ├── processed/            # cleaned_records.json, graph_triplets.json
│   ├── synthetic/            # generator output (persons/calls/transactions/meetings)
│   ├── exports/              # graph.pkl, graph_data.json, graph_metrics.json,
│   │                         # ghost_predictions.json, evidence_index.json,
│   │                         # findings.json, dossiers/, audit_log.jsonl
│   └── cases/                # case workspaces (JSON)
├── notebooks/
│   ├── exploration.ipynb
│   └── graph_testing.ipynb
├── src/
│   ├── ingestion/            # csv_loader.py, api_loader.py, pdf_loader.py
│   ├── preprocessing/        # cleaner.py, ocr.py, translator.py, standardizer, fir_simulator, ...
│   ├── extraction/           # ner.py, relation_extractor.py, event_extractor.py, pipeline.py
│   ├── resolution/           # entity_matcher.py, clustering.py, guid_generator.py
│   ├── graph/                # graph_builder.py, analytics.py, ghost_nodes.py,
│   │                         # simulation.py, graph_embeddings.py, ontology.py
│   ├── xai/                  # evidence_tracer.py, findings.py,
│   │                         # dossier_generator.py, llm_providers.py, build_evidence.py
│   ├── adapters/             # graph_store.py, postgres_repository.py,
│   │                         # s3_document_store.py, kafka_event_stream.py,
│   │                         # neo4j_graph_store.py, airflow_dags/
│   ├── api/                  # main.py, routes.py, schemas.py, services.py,
│   │                         # audit.py, paths.py, data_access.py, jobs.py,
│   │                         # pipeline_steps.py, routers/
│   └── main.py               # preprocessing CLI entrypoint
├── tests/                    # pytest suite (145 tests)
├── frontend/                 # React/Vite investigator UI (Cytoscape explorer)
├── requirements.txt
├── docker-compose.yml
├── pytest.ini
├── run_stage.py              # stage runner (generate|preprocess|extract|graph|ghosts|evidence|findings)
├── run_demo.py               # one-click demo + guided scenario
├── conftest.py
├── .env.example
└── docs/                     # ARCHITECTURE.md, API.md, DEMO_GUIDE.md,
                              # VALIDATION_REPORT.md, LIMITATIONS.md, ...
```

---

## 3. Install

Python 3.12 recommended.

```bash
cd sentinelgraph-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# spaCy model used by the extraction stage:
python -m spacy download en_core_web_sm
```

Optional extras (never required for the demo):

```bash
pip install pypdf                # PDF ingestion
pip install neo4j psycopg[binary] boto3 confluent-kafka   # production adapters
```

---

## 4. Run the demo (one click)

```bash
python run_demo.py            # full deterministic chain, ~3 minutes
python run_demo.py --scenario # guided walkthrough with real ids
```

Start the services:

```bash
# terminal 1 - API
uvicorn src.api.main:app --port 8000
# terminal 2 - UI
cd frontend && npm install && npm run dev
# open http://localhost:5173
```

Interactive API docs: <http://localhost:8000/docs>

Demo flow in the UI: **Network explorer** → search an entity → inspect
relationships + evidence → **Ghost candidates** → open a hypothesis
(confidence breakdown, supporting/counter evidence) → **Counterfactual
sandbox** → simulate node removal (~30 s, cached afterwards) → **Findings
(XAI)** → inspect observed/inferred/unknown → **Dossiers** → generate and
review a draft dossier.

Run stages individually:

```bash
python run_stage.py generate     # synthetic dataset (seed=42)
python run_stage.py preprocess   # cleaning + FIRs + OCR sample
python run_stage.py extract      # NLP extraction -> graph_triplets.json
python run_stage.py graph        # resolution + graph + analytics
python run_stage.py ghosts       # hidden-intermediary inference
python run_stage.py evidence     # evidence provenance index (~25 s)
python run_stage.py findings     # XAI findings from ghosts
```

Run the test suite:

```bash
python -m pytest tests/ -q                 # full suite incl. one slow test
python -m pytest tests/ -q -m "not slow"   # fast subset
```

Frontend build check:

```bash
cd frontend && npm run build
```

---

## 5. Operating modes

### Demo / local mode (default)

Everything runs locally: CSV artifacts, NetworkX, JSON evidence index,
offline mock LLM. **No cloud credentials, no API keys.**

### Production-adapter mode (optional)

Clean interfaces live in `src/adapters/`. Each adapter imports its client
lazily and raises a descriptive `AdapterNotConfigured` when unconfigured —
they are never auto-enabled. Configure via `.env` (see `.env.example`):

| Adapter | Env vars | Interface |
|---|---|---|
| PostgreSQL | `SENTINELGRAPH_PG_DSN` | `SourceRepository` |
| S3 / object storage | `SENTINELGRAPH_S3_BUCKET` | `DocumentStore` (local FS impl included) |
| Kafka | `SENTINELGRAPH_KAFKA_BOOTSTRAP` | `EventStream` (in-memory impl included) |
| Neo4j | `SENTINELGRAPH_NEO4J_URI` / `_PASSWORD` | `GraphStore` (NetworkX impl is default) |
| LLM | `SENTINELGRAPH_LLM_API_KEY` / `SENTINELGRAPH_LLM_API_KEY_FALLBACK` | `LLMProvider` (mock is default; Google fallback is used only on quota/rate-limit responses) |

Airflow: copy `src/adapters/airflow_dags/sentinelgraph_pipeline.py` into a
DAGs folder.

---

## 6. Safety & human oversight

* Every finding/dossier separates **OBSERVED**, **INFERRED**, **UNKNOWN** and
  **CONTRADICTED** claims.
* Every factual claim maps to an evidence id validated against the store;
  fabricated ids are rejected by `validate_finding` / `validate_dossier`.
* Counter-evidence is searched and preserved; missing information is listed.
* Simulation payloads carry `method`, `warnings` and the disclaimer
  **"NETWORK EFFECT SCORE — NOT AN ENFORCEMENT RECOMMENDATION"**.
* Investigator actions (searches, expansions, evidence views, simulations,
  dossier generation) are written to an append-only audit log
  (`data/exports/audit_log.jsonl`) without raw personal payloads.

---

## 7. Documentation

* `docs/ARCHITECTURE.md` — pipeline, data flow, what is implemented vs adapter vs simulated
* `docs/API.md` — endpoint reference
* `docs/DEMO_GUIDE.md` — full click-path demo
* `docs/VALIDATION_REPORT.md` — benchmark numbers (precision/recall/F1, timings)
* `docs/LIMITATIONS.md` — explicit limitations and non-goals
* `IMPLEMENTATION_BASELINE.md` — pre-implementation audit record
* `FINAL_IMPLEMENTATION_REPORT.md` — phase-by-phase completion report
* `GHOST_NODE_REPORT.md` — original ghost-detector design report

---

## 8. Known limitations (summary)

Full list in `docs/LIMITATIONS.md`. Highlights:

* Ghost recall on the planted-coordinator benchmark is ~0.25–0.27 at
  precision 1.0 — the detector misses most planted coordinators (documented,
  by design of the benchmark's masking).
* The evidence index reflects the *observed* subset (what preprocessing
  captured), not the simulator's full ground truth.
* Counterfactual simulation on the full 13k-node graph takes ~12–30 s per
  request (sampled metrics, cached baseline context).
* The mock LLM is deterministic and template-based; a real provider is
  optional and its output is strictly schema-validated with a deterministic
  fallback.
* All data is synthetic; nothing here is trained-model grade or court-ready.

---

## 9. Deployment architecture

```
Browser
  ↓
GitHub Pages (React frontend — static)
  ↓ HTTPS API requests
Render.com (FastAPI backend + pre-generated data files)
```

The React app is built by GitHub Actions, deployed to GitHub Pages as static
files, and makes all API calls directly to the Render backend. The backend
serves the pre-built graph data, runs the pipeline, and executes XAI inference
on demand. No VS Code, Python, Node.js, or model files are needed on the demo
computer — only a browser with internet access.

---

## 10. Local development

### Frontend

```bash
cd frontend
npm install
npm run dev        # starts Vite on http://localhost:5173, proxies /api → backend
```

### Backend

```bash
# from the repo root
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # optional — falls back to rules-only NER

uvicorn src.api.main:app --reload --port 8000
```

### Run both at once

```bash
# In one terminal:
uvicorn src.api.main:app --reload --port 8000

# In another:
cd frontend && npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` to the
backend automatically.

### Environment

Copy `.env.example` to `.env` (optional — the backend works without it):

```bash
cp .env.example .env
```

All backend environment variables are documented in `.env.example`. The
frontend reads `VITE_API_URL` and `BASE_PATH` at build time.

---

## 11. Frontend deployment (GitHub Pages)

GitHub Actions automatically builds and deploys the React frontend whenever
code is pushed to `main`.

### One-time GitHub setup

1. Push this repository to GitHub
2. Go to **Settings → Pages** and set **Source** to **GitHub Actions**
3. Set **Settings → Secrets and variables → Actions → Variables**:
   - `VITE_API_URL` = `https://YOUR_RENDER_SERVICE_URL.onrender.com`

### What happens on push

The workflow at `.github/workflows/deploy.yml`:

1. Checks out the code
2. Installs Node 20 and runs `npm ci && npm run build` in `frontend/`
3. Uploads the `dist/` folder as a GitHub Pages artifact
4. Deploys it to GitHub Pages

**Required variable** (set once in GitHub repo Settings):

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://sentinelgraph-ai.onrender.com` (your Render URL) |

**Expected URL:** `https://Hemachandru-BCA.github.io/Thupparivu-SIH26189/`

---

## 12. Backend deployment (Render.com)

### One-time setup

1. Go to [render.com](https://render.com) and sign in
2. Click **New → Web Service**
3. Connect your GitHub repository
4. Fill in:
   - **Name:** `sentinelgraph-api`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt && python -m spacy download en_core_web_sm || true`
   - **Start Command:** `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables (see below)
6. Click **Create Web Service**

Alternatively, use the `render.yaml` blueprint in this repository:
```bash
# install the Render CLI, then:
render deploy
```

### Render environment variables

| Variable | Value |
|---|---|
| `CORS_ORIGINS` | `https://YOUR_USERNAME.github.io` |
| `SENTINELGRAPH_LOG_LEVEL` | `INFO` |

### Health check

The backend exposes `GET /api/health` which returns:
```json
{"status": "ok", "service": "sentinelgraph-ai", "version": "2.0.0"}
```

Render uses this endpoint to check if the service is healthy.

### Cold start considerations

Render free-tier services sleep after ~15 minutes of inactivity. On first
request after sleep, there is a cold start of approximately 30–60 seconds
while the service boots. The React frontend will show a retry button if the
API is not yet responding. Click **Retry request** and the page will load
normally once the backend is awake.

The backend loads data lazily (on first API request, not at boot), so the
initial startup is fast — just `uvicorn` + Python imports (~5–10 s).

---

## 13. Model requirements

| Component | Model | Size | CPU/GPU | Loaded at |
|---|---|---|---|---|
| NER | spaCy `en_core_web_sm` | ~12 MB | CPU only | Lazy (first extract call) |
| Graph embeddings | Node2Vec-style (gensim Word2Vec) | ~50 MB | CPU only | Optional, lazy |
| GraphSAGE-style embeddings | numpy projection weights | ~0 KB | CPU only | Optional, lazy |
| Dossier LLM | `MockLLMProvider` (offline, deterministic) | ~0 KB | CPU only | Lazy (first dossier call) |

**No large model files are stored in the repository.** The spaCy model is
downloaded during the Render build step. Everything else is either optional
or deterministic and does not require a real trained model.

The application runs entirely on CPU — no GPU is required or expected.

---

## 14. Demo instructions

The demo computer needs only:

1. **Internet access**
2. **A modern web browser** (Chrome, Firefox, Safari, or Edge)

To use the demo:

1. Open `https://Hemachandru-BCA.github.io/Thupparivu-SIH26189/` in a browser
2. The dashboard loads immediately (static files from GitHub Pages)
3. API calls go to the Render backend automatically
4. If the backend is sleeping, click **Retry request** on any section — it
   will wake up within ~30–60 seconds
5. Browse the network explorer, ghost candidates, findings, evidence,
   analytics, pipeline, and other sections

The demo computer does **NOT** need:

- VS Code or any IDE
- Python, Node.js, or npm
- FastAPI or any backend framework
- Model files or spaCy
- Any local environment variables
- Any software installation

---

## 15. Git commands to push

This repo is already initialized with the correct remote. To push:

```bash
cd sentinelgraph-ai

# Authenticate once (Personal Access Token or `gh auth login`), then:
git push -u origin main
```

If you are starting a fresh clone, the full setup is:

```bash
cd sentinelgraph-ai

git init
git add .
git commit -m "Prepare for GitHub Pages + Render deployment"
git branch -M main
git remote add origin https://github.com/Hemachandru-BCA/Thupparivu-SIH26189.git
git push -u origin main
```

force start cloudflare push 2

**Important:** Make sure to set up the GitHub Pages and Render variables
described in sections 11 and 12 before pushing, or immediately after.
