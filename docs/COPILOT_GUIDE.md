# Investigation Copilot — User Guide

The Investigation Copilot is an investigative assistant that lets you
ask questions about the network in plain English. Every response
includes a **tool-call trace** — showing exactly which analytical tools
were called and what they returned before the final answer.

---

## 1. Accessing the Copilot

Open **/copilot** from the left sidebar (✦ COPILOT under INTELLIGENCE)
or press **Ctrl+K** and search "copilot".

---

## 2. Available tools

The copilot has access to 16 backend tools. Each tool maps to a
specific analysis capability:

| Category | Tool | Description | Example query |
|---|---|---|---|
| **Search** | `search_entities` | Find entities by name or attribute | "Find all persons named Singh" |
| **Search** | `search_evidence` | Full-text evidence search | "Show evidence about phone calls on Jan 15" |
| **Search** | `search_ghosts` | Find ghost candidates | "Which ghost nodes are most suspicious?" |
| **Graph** | `find_paths` | Find paths between two entities | "Find shortest path from Person-001 to Person-042" |
| **Graph** | `centrality` | Compute centrality metrics | "Who has the highest betweenness centrality?" |
| **Graph** | `community` | Community detection | "What communities exist in the network?" |
| **Graph** | `ego_network` | Ego network of an entity | "Show the ego network of Person-001" |
| **Evidence** | `find_evidence` | Get evidence for an entity | "What evidence links Person-001 to Person-042?" |
| **Evidence** | `trace_provenance` | Follow evidence chain | "Trace the provenance of evidence EV-abc123" |
| **Evidence** | `build_dossier` | Generate dossier for subject | "Build a dossier for Person-001" |
| **Financial** | `analyze_financial_flow` | Trace financial flows | "Show all financial flows from Person-001" |
| **Financial** | `detect_cycles` | Find circular flows | "Are there any round-trip transactions?" |
| **Financial** | `anomaly_patterns` | Temporal anomaly detection | "Any communication bursts recently?" |
| **Simulation** | `simulate_removal` | Counterfactual node removal | "What happens if we remove Person-001?" |
| **Simulation** | `compare_scenarios` | Compare two simulations | "Compare removing Person-001 vs Person-042" |
| **Analytics** | `graph_summary` | Overall graph statistics | "Give me a summary of the network" |

---

## 3. How it works

### Step 1: You ask a question

Type a natural-language question in the input field and press
**Ctrl+Enter** (or click **Send**).

### Step 2: Tools are called

The copilot breaks your question into one or more tool calls. Each
tool call is shown in a **tool-call trace** panel (collapsed by default).

### Step 3: Answer is composed

The copilot reads the tool results and composes a plain-English answer.
Entity mentions in the answer are rendered as clickable **entity chips**
that navigate to the Network Canvas with the node highlighted.

### Step 4: Transparency

Below the answer you see:
- **Confidence badge** — how certain the copilot is (green ≥ 70%, blue ≥ 40%, amber < 40%)
- **Warnings** — any caveats about the answer
- **Tool-call trace** — expandable to show the full JSON of each tool's output

---

## 4. Demo queries

When you first open the Copilot, four demo query cards are shown.
Click any card to auto-fill and send the query.

Suggested queries:

1. **"Find all entities connected to Person-001"** — Explores direct connections
2. **"What financial flows exist?"** — Traces money movement across accounts
3. **"Show communication patterns"** — Analyses call/transaction activity
4. **"Identify ghost nodes"** — Surfaces structural hypothesis candidates

---

## 5. Entity chips and graph navigation

When the copilot answer mentions an entity (e.g. `E-5ef4789c...`), it
is rendered as a clickable chip `[E-5ef4789c... ↗]`.

Clicking the chip:
1. Navigates to the **Network Canvas** (`/network`)
2. Passes the entity as a URL query param: `?highlight=E-5ef4789c...`
3. The graph auto-selects and centers on that node

---

## 6. Session management

Each copilot page load generates a new session UUID. All tool calls
within a session are passed to the backend, allowing the copilot to
maintain context across follow-up questions within the same page visit.

---

## 7. Limitations

- The copilot uses a mock LLM (deterministic, template-based) by default.
  A real LLM provider (OpenAI-compatible) can be configured via the
  `LLM_PROVIDER` environment variable.
- Tool results are limited to prevent context overflow.
- Financial analysis uses synthetic transaction amounts.
- The copilot does not have access to external data sources.
- All answers are labelled as hypotheses, not conclusions.
