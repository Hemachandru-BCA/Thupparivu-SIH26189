# SentinelGraph AI — Demo Guide

This guide walks the exact end-to-end reviewer journey defined in the
implementation prompt (Section 36). Everything runs locally with no API
keys.

---

## 0. One-time setup

```bash
cd sentinelgraph-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

cd frontend && npm install && cd ..
```

## 1. Build the demo data (one command)

```bash
python run_demo.py
```

This runs the deterministic chain (seed 42):

```text
Generate Dataset → Run Pipeline → Build Graph → Run Analytics
→ Detect Ghosts → Prepare Evidence → Generate Findings
```

Typical timings on a laptop: generate 2s · preprocess 3s · extract ~50s ·
graph ~31s · ghosts ~40s · evidence ~25s · findings ~2s.

If you already have artifacts and only want the XAI layers:

```bash
python run_demo.py --skip-generate
```

Guided scenario (real ids from your current artifacts):

```bash
python run_demo.py --scenario
```

It prints the highest-confidence ghost candidate, a suggested simulation
target, the top finding id, the dossier subject, and — for benchmarking
only — the planted hidden coordinators.

## 2. Start the services

```bash
# terminal 1
uvicorn src.api.main:app --port 8000
# terminal 2
cd frontend && npm run dev
# open http://localhost:5173
```

## 3. The reviewer journey (click path)

| Step | Where | What you see |
|---|---|---|
| 1 | Open `http://localhost:5173` | Command center dashboard |
| 2 | Sidebar → **Network explorer** | Cytoscape graph (server-side subgraph, ≤ your node cap) |
| 3 | Search box → type a person/location name | Global results (nodes, ghosts, evidence) |
| 4 | Click a result → graph focuses | Community colors, PageRank-sized nodes, evidence-teal edges |
| 5 | Select a node | Inspector: PageRank, betweenness, degree, community, mentions |
| 6 | Bottom panel | Evidence timeline for the node (chronological, clickable ids) |
| 7 | Sidebar → **Ghost candidates** | List of hypotheses with confidence |
| 8 | Open a ghost | Between-communities bridge, shared anchors, predicted edges |
| 9 | Sidebar → **Findings (XAI)** | Findings with component confidence bars |
| 10 | Open a finding | OBSERVED (evidence-cited) vs INFERRED vs UNKNOWN; counter-evidence; limitations |
| 11 | Sidebar → **Counterfactual sandbox** | Node-removal simulation form |
| 12 | Paste a node guid (or use the explorer's **Counterfactual** button) → Run | ~30 s loading state, then metrics |
| 13 | Back in the explorer with overlay | Red removed node, amber affected, cyan new brokers, dimmed rest |
| 14 | Simulation panel | Fragmentation, connectivity change, community changes, new brokers, alternate paths, rerouting score — labelled **NETWORK EFFECT SCORE, NOT AN ENFORCEMENT RECOMMENDATION** |
| 15 | Scenario comparison (2nd panel) | Side-by-side counterfactuals ranked by network effect |
| 16 | Sidebar → **Dossiers** → paste subject guid → Generate | Executive summary, labelled sections, timeline |
| 17 | Open the dossier | Evidence links, counter-evidence, methodology, limitations, **DRAFT — HUMAN REVIEW REQUIRED** |
| 18 | Click **Record human review** | Reviewer + decision recorded (still marked not court-ready) |
| 19 | Sidebar → **Evidence register** | Search all evidence; open any id from findings/dossiers |
| 20 | Sidebar → **Cases** → create a case | Add entities/evidence/findings/simulations + notes (working file, not a legal record) |

### Demo scenario suggestion

Run `python run_demo.py --scenario` first; then in the UI open the ghost it
names (highest confidence), generate the dossier for its finding's subject,
and simulate removal of its suggested target — this reproduces the full
"hidden coordinator" story in ~10 clicks.

## 4. API-only walkthrough

```bash
# findings + dossier + simulation in three calls
curl -s -X POST localhost:8000/api/findings/generate | jq '.generated'
SID=$(curl -s localhost:8000/api/findings | jq -r '.items[0].subject_id')
curl -s -X POST localhost:8000/api/dossiers/generate \
     -H 'content-type: application/json' -d "{\"subject_id\": \"$SID\"}" | jq '.dossier.id'
curl -s -X POST localhost:8000/api/simulation/node-removal \
     -H 'content-type: application/json' -d "{\"node_id\": \"$SID\", \"depth\": 2}" \
     | jq '{frag: .fragmentation_score, conn: .connectivity_change, reroute: .rerouting_score}'
```

## 5. Regenerating from scratch

Artifacts are rebuildable at any time; `run_stage.py all` (or the pipeline
UI page) reproduces the dataset deterministically. Delete `data/exports/*`
first if you want a byte-fresh XAI chain.
