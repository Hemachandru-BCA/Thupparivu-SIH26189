# SentinelGraph AI — Limitations

Read this before drawing any conclusion from the system. These limitations
are also surfaced inside the product (finding/dossier `limitations` fields,
simulation `warnings`, UI disclaimers).

## 1. Data

* **All data is synthetic.** The generator produces a simulated world; no
  statement here transfers to real populations, and no model is trained.
* The evidence index contains what the pipeline **observed** (preprocessing
  samples ~10% of calls/transactions and 1,000 of 8,000 meetings), not the
  generator's ground truth. Unobserved events are unknowable by design.
* Generator artifacts (person profiles) are English/Latin-script only in the
  default configuration; translation abstractions exist but are not
  exercised end-to-end by the demo.

## 2. Extraction & resolution

* The NER layer is rule + gazetteer + `en_core_web_sm`; it is not a
  fine-tuned model. Newer spaCy builds miss some PERSON mentions
  (mitigated by the `KNOWN_PERSONS` gazetteer, but the gazetteer is a
  closed list — names outside it rely on the statistical model).
* Relation extraction is pattern-based; relations carry per-triplet
  confidence but there is no learned verifier.
* Entity resolution is name-similarity based; transliteration and shared
  surnames can over- or under-merge. Clustering thresholds are configured
  defaults, not tuned per dataset.

## 3. Ghost inference (hidden intermediaries)

* Ghost candidates are **structural hypotheses**, not identities. The
  output says "a hidden intermediary plausibly connects communities X and
  Y" — it never says who the person is, and predicted edges are plausible
  contact points, not events.
* Confidence is a weighted blend of attribute affinity, temporal affinity,
  embedding affinity and structural-hole signal. It is **not** a probability
  of guilt and **not** calibrated in any statistical sense.
* Benchmark recall is low: pair recall ≈ 0.25–0.27 at precision 1.0 on the
  planted benchmark (F1 ≈ 0.43). The detector prefers precision; most
  planted coordinators are missed. Precision numbers come from a synthetic
  world whose anchors were designed for this detector — real-world precision
  is unknown and likely lower.
* Community detection (Louvain) is stochastic; seeded but not stable to
  minor perturbations, so ghost ids can vary between runs when broker scores
  tie.

## 4. Counterfactual simulation

* Results are **network-statistics what-ifs** — they say what the graph
  would look like if a node disappeared from the *observed graph*. They do
  not predict what a real organization would do, and they are not, in any
  sense, recommendations to remove, arrest, or act against anyone.
* Metrics above the exact-limit (1,500 nodes) are sampled (seeded): global
  efficiency, average shortest path and betweenness are estimates with
  sampling variance.
* Alternate paths are computed on the undirected weighted projection;
  direction and multi-edge semantics are lost in that view by design.
* Rerouting is evaluated on a bounded sample of former-neighbour pairs
  (25 by default) — the score is a fraction over that sample.

## 5. Evidence / XAI / dossiers

* Evidence binding is name/id-based; if a node cannot be matched to a source
  record the claim is demoted to UNKNOWN rather than fabricating a
  reference. This is conservative by design and can leave "observed at
  graph level" facts under-cited.
* The default LLM is a deterministic mock — the dossier's prose is
  template-derived from the bounded context. A real provider (optional)
  writes the summary but is schema-validated, capped by the context, and
  falls back to the deterministic path on any violation. **The LLM is never
  the source of truth.**
* Counter-evidence search is currently aggregate (e.g. direct-edge counts
  between bridged communities); record-level counter-evidence mining is a
  planned enhancement.
* Dossiers are decision-support drafts. They are never court-ready, never
  charges, and carry no evidentiary weight on their own.

## 6. Performance & scale

* The full pipeline (13k nodes / 24k edges) runs in ~2.5 minutes locally,
  but counterfactual simulation takes ~12–30 s per node on that graph —
  fine for demos, not for interactive bulk analysis of much larger graphs.
* The evidence index is an in-memory JSON store (~40k records, ~76 MB on
  disk). It loads in ~2 s but is not a production retrieval system; the
  `EvidenceBackend` interface exists so PostgreSQL/OpenSearch/vector stores
  can replace it.
* No auth/authorization: the demo API is unauthenticated and intended for
  localhost use only.

## 7. Compliance / ethics

* The system intentionally **cannot** output enforcement recommendations;
  arrest/enforcement language is absent by construction (grep-able in
  `src/graph/simulation.py` and the UI).
* The UI distinguishes OBSERVED / INFERRED / UNKNOWN / CONTRADICTED and
  labels hypotheses; it never instructs surveillance or action on an
  unconfirmed ghost identity.
* Audit logging records actions and ids, not payloads; retention is
  unbounded in the demo (configurable in production via the audit module).
* Deploying this class of system against real people requires legal review,
  data-protection compliance (GDPR or equivalents), human-rights impact
  assessment, and human-in-the-loop review workflows that this prototype
  does not provide.
