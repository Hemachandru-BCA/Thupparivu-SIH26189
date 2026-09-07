# Ghost Node Detection — Final Assessment

## 1. Current assessment

| Area | Rating | Assessment |
|---|---:|---|
| Architecture | 7/10 | The existing four-stage design is coherent and reusable, but the original implementation let infrastructure nodes distort structural/community analysis and treated an inferred intermediary too literally as an observed node. |
| Data quality | 6/10 | The generated dataset contains useful calls, transfers, accounts and timestamps, but extraction is still synthetic/fallback NLP and the current artifacts contain many sparse/infrastructure entities. |
| Algorithm quality | 6.5/10 | Burt constraint/effective size/betweenness + Louvain + shared-surface evidence is reasonable heuristic link analysis. It is not research-grade probabilistic inference, and its community quality is limited by sparse synthetic topology. |
| Explainability | 8.5/10 | Predictions expose confidence components, supporting anchors, communities, predicted edges and rationale. |
| End-to-end functionality | 8/10 | Existing artifacts now flow through graph build -> masked ghost inference -> JSON -> FastAPI -> React ghost view. |
| Validation/testing | 6/10 | Unit tests are clean and the detector has a positive/negative miniature harness plus real-dataset planted-account validation, but recall is only partial and no independent labeled corpus exists. |

## 2. Root causes of the original failure

1. The relation ontology was inconsistent between extractor and ghost detector (`LOCATED_AT` vs `LOCATED_IN`, `TRANSFERRED_TO` vs `TRANSFERRED_FUNDS`). A canonical normalization layer was already the right fix and is now used by graph construction.
2. The original ghost run was not using the project's synthetic hidden-coordinator semantics: known coordinator nodes could remain in the graph, so the detector could score observed truth instead of inferring an unobserved intermediary.
3. The graph was dominated by infrastructure nodes (accounts/locations). Running Louvain and structural-hole metrics over those hubs fragmented the person network and made the resulting communities unsuitable for coordinator inference.
4. Structural-hole metrics returned NaNs for disconnected/small components, which propagated into JSON as `null` confidence values.
5. Timestamp evidence was recomputed by scanning the whole graph for every candidate pair, making the pair stage unnecessarily expensive.
6. The existing frontend had no dedicated surface for ghost evidence even though the API already exposed the prediction document.

## 3. Changes made

### `graph/ontology.py`
- Centralized the relation aliases and canonicalized legacy `LOCATED_AT` / `TRANSFERRED_FUNDS` labels.

### `preprocessing/pipeline.py`
- Preserved generator-owned call/transaction/meeting observations in the cleaned pipeline artifact.
- Made optional event fields tolerant of small test fixtures missing `currency`/`channel`.

### `graph/ghost_nodes.py`
- Made communities and structural-hole analysis person-centric by excluding `LOCATION` and `ACCOUNT` nodes from the topology projection while keeping them as evidence anchors.
- Made Louvain insertion order deterministic.
- Made min-max normalization ignore NaNs instead of propagating them into confidence.
- Added one-time timestamp indexing for all community pairs.
- Added an explicit shared-anchor requirement to the proposal gate.
- Kept rare shared accounts as strong money-route evidence after masking hidden coordinators.
- Made the standalone CLI mirror API behavior by masking synthetic hidden coordinators when `persons.csv` is available.
- Updated output metadata/method descriptions to reflect the actual heuristic.

### `api/pipeline_steps.py`
- Runs ghost detection on a graph with the generator-marked hidden coordinators masked.
- Writes the full `ghost_predictions.json` artifact and reports summary counts.

### `api/routers/graph.py`
- Exposes `GET /api/graph/ghosts`.
- Exposes `GET /api/graph/ghosts/{id}/evidence`.

### React frontend
- Added a minimal `/ghosts` page.
- Added a sidebar entry under the investigation workspace.
- Displays candidate confidence, community pair, structured evidence and account anchors.

### `tests/validate_ghost_pipeline.py`
- Added real-dataset validation using the existing synthetic artifacts.
- Added a planted two-account positive case.
- Added a common-location-only negative case.

## 4. Algorithm improvements

The detector now separates topology from infrastructure evidence. People/organizations define communities and structural holes; accounts/locations remain shared surfaces that can explain why two communities might have an unobserved intermediary.

The shared-surface score remains rarity-weighted and union-normalized, but proposals require an actual shared anchor. Common-location-only evidence therefore does not pass the proposal gate in the validation harness.

Temporal evidence is retained and indexed once instead of rescanning the graph for every pair. On the current synthetic data the timestamps available for the surviving shared anchors did not materially raise the final candidates, so the temporal component remains a weak/zero contribution in the current result rather than being overstated.

Confidence is still a heuristic blend. Node2Vec was not enabled for the validated run, and GraphSAGE is explicitly disabled rather than being presented as a learned model.

## 5. Validation results

### Extracted/graph signal

Current `graph_triplets.json` contains 23,982 triplets with this relation distribution:

- `USES_ACCOUNT`: 8,087
- `LOCATED_AT`: 5,000
- `MET`: 4,132
- `TRANSFERRED_TO`: 4,049
- `CALLED`: 2,553
- `ASSOCIATED_WITH`: 161

The resolved graph contains 13,146 nodes and 23,982 edges.

### Before / after

```text
Before:
  useful ghost candidates: 0
  relation output dominated by ASSOCIATED_WITH/co-occurrence in the prior failed run
  no usable ghost_predictions artifact

After:
  resolved graph: 13,146 nodes / 23,982 edges
  person-centric communities: 859
  candidate pairs evaluated: 299
  ghost candidates proposed: 3
  mean confidence: ~0.505
```

### Ground-truth-aware synthetic check

Using the existing `persons.csv` hidden-coordinator flags only for evaluation/masking:

```text
Hidden coordinators:                 6
Planted coordinator accounts found:  4 / 6
Coordinator-account recall:          0.667
Ghost candidates without planted
coordinator-account evidence:        0 / 3
Precision under this strict check:   1.000
```

The 3 proposals recover four planted coordinator account surfaces because one prediction can contain more than one supporting account.

### Mini validation harness

```text
Planted two-account money bridge:    1 ghost
Common-location-only bridge:         0 ghosts
```

The full general test suite passes:

```text
92 passed, 3 skipped
```

FastAPI smoke checks pass:

```text
GET /api/graph/ghosts                     -> 200
GET /api/graph/ghosts/{valid}/evidence    -> 200
GET /api/graph/ghosts/invalid/evidence    -> 404
GET /api/graph/info                       -> 200
```

## 6. Remaining weaknesses

- 859 detected communities is still highly fragmented for a 5,000-person synthetic population. The detector therefore has useful evidence, but its community semantics are not strong enough to call the results research-grade.
- The synthetic generator provides ground truth, but the available run does not provide an independent blinded holdout where the detector is evaluated without using generator flags for masking/evaluation.
- Four of six planted coordinator accounts are recovered. Two are missed by the current confidence/structural pairing gates.
- The detector can produce a single ghost supported by multiple planted account surfaces; that is useful evidence, but it means “ghost count” is not equivalent to “number of real hidden coordinators.”
- Location evidence is still synthetic and noisy. It is retained as a secondary signal and should not be interpreted as strong proof by itself.
- Node2Vec and GraphSAGE are not contributing to the validated result. GraphSAGE in this codebase is not a trained model, so it is deliberately not represented as learned evidence.
- A ghost node is a hypothesis about an unobserved intermediary, not an observed person/entity. Predicted edges are inferred links and must remain visually/distinguishably marked as such.

## 7. Copy-paste patches

### File: `graph/ghost_nodes.py`

**Change:** person-centric structural/community topology, deterministic Louvain, NaN-safe normalization, cached temporal evidence, masked CLI.

```python
full_projection = undirected_weighted_projection(graph)
projection = full_projection.subgraph([
    n for n, data in graph.nodes(data=True)
    if str(data.get("entity_type", "")).upper() not in {"LOCATION", "ACCOUNT"}
]).copy()
```

```python
finite = [float(v) for v in values.values() if np.isfinite(v)]
if not finite:
    return {k: 0.0 for k in values}
```

```python
temporal_index = _build_temporal_index(graph, community_of, config)
```

```python
proposed = (
    not connected
    and bool(shared_nodes)
    and attr_affinity >= config.attribute_affinity_threshold
    and confidence >= config.confidence_threshold
)
```

### File: `preprocessing/pipeline.py`

**Change:** tolerate small transaction fixtures that omit optional fields while keeping the generated event observation path intact.

```python
f"{sender} transferred {r.get('amount','')} {r.get('currency','')} "
"to {receiver} via {r.get('channel','')} using account "
"{account} on {r.get('timestamp','')}."
```

### File: `api/pipeline_steps.py`

**Change:** mask generator-marked coordinators before ghost inference.

```python
observed_graph = _mask_nodes(graph, hidden_names) if hidden_names else graph
document = detect_ghost_nodes(observed_graph, config)
```

### File: `frontend/src/api/graph.jsx`

**Change:** query the ghost endpoint with React Query.

```javascript
export const getGetGhostsQueryKey = () => ['/api/graph/ghosts'];

export function useGetGhosts() {
    return useQuery({
        queryKey: getGetGhostsQueryKey(),
        queryFn: async () => {
            const response = await fetch('/api/graph/ghosts?page=1&page_size=50', {
                headers: { Accept: 'application/json' },
            });
            if (!response.ok) throw new Error(`Ghost API request failed (${response.status})`);
            return response.json();
        },
    });
}
```

### File: `frontend/src/App.jsx`

**Change:** add the ghost candidate route.

```jsx
<Route path="/ghosts" component={GhostsPage}/>
```

### File: `tests/validate_ghost_pipeline.py`

**Change:** validate the actual synthetic artifacts plus explicit positive/negative micro-cases.

```python
result = {
    "full_dataset": full_dataset_check(),
    "planted_money_anchor": mini_case("money"),
    "common_location_only": mini_case("location"),
}
```
