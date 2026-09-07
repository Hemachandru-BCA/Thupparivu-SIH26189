import { useQuery, useQueryClient } from '@tanstack/react-query';

let baseUrl = '';

export function setBaseUrl(url) {
    baseUrl = (url || '').replace(/\/+$/, '');
}

function buildUrl(path, params) {
    const search = new URLSearchParams();
    if (params) {
        for (const [key, value] of Object.entries(params)) {
            if (value !== undefined && value !== null && value !== '') {
                search.set(key, String(value));
            }
        }
    }
    const qs = search.toString();
    return `${baseUrl}${path}${qs ? `?${qs}` : ''}`;
}

export async function requestJson(path, options = {}) {
    const { method = 'GET', params, body } = options;
    const url = buildUrl(path, params);
    let res;
    try {
        res = await fetch(url, {
            method,
            headers: {
                Accept: 'application/json',
                ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
            },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
    } catch (cause) {
        throw new Error(`API unreachable at ${url} (${cause.message})`);
    }
    if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try {
            const body = await res.json();
            // FastAPI errors are {"detail": "..."} — old code read body.error
            if (typeof body?.detail === 'string') detail = body.detail;
        } catch { /* not JSON */ }
        throw new Error(`API request failed (${url}): ${detail}`);
    }
    return res.json();
}

export async function request(path, params) {
    return requestJson(path, { params });
}

// ---------------------------------------------------------------------------
// Shared graph payload: /api/graph/data fetched once, reused by the
// client-side computations below (per your backend's intended design).
// ---------------------------------------------------------------------------

const GRAPH_DATA_KEY = ['/api/graph/data'];

function useGraphData() {
    const qc = useQueryClient();
    return () => qc.ensureQueryData({
        queryKey: GRAPH_DATA_KEY,
        queryFn: () => request('/api/graph/data'),
        staleTime: 5 * 60 * 1000, // only stale when the pipeline reruns
    });
}

// node-link helpers — graph_data.json uses links[] with source/target
function buildAdjacency(data) {
    const adj = new Map();
    const ensure = (v) => {
        const k = String(v);
        if (!adj.has(k)) adj.set(k, []);
        return k;
    };
    for (const n of data.nodes ?? []) ensure(n.id ?? n.label);
    for (const l of data.links ?? []) {
        const s = ensure(l.source);
        const t = ensure(l.target);
        adj.get(s).push(t);
        adj.get(t).push(s);
    }
    return adj;
}

function withEdgesAlias(data) {
    return { ...data, edges: data.links ?? [] };
}

function egoSlice(data, center, depth) {
    if (!center) return withEdgesAlias(data);
    const adj = buildAdjacency(data);
    const key = String(center);
    if (!adj.has(key)) throw new Error(`Unknown node: ${center}`);
    const seen = new Set([key]);
    let frontier = [key];
    for (let d = 0; d < depth; d++) {
        const next = [];
        for (const n of frontier) {
            for (const m of adj.get(n)) {
                if (!seen.has(m)) { seen.add(m); next.push(m); }
            }
        }
        frontier = next;
    }
    const keep = seen;
    const links = (data.links ?? []).filter(
        (l) => keep.has(String(l.source)) && keep.has(String(l.target)),
    );
    return {
        ...data,
        nodes: (data.nodes ?? []).filter((n) => keep.has(String(n.id ?? n.label))),
        links,
        edges: links,
    };
}

// ---------------------------------------------------------------------------
// Hooks (names unchanged — components don't change)
// ---------------------------------------------------------------------------

export const getHealthCheckQueryKey = () => ['/api/health'];
export function useHealthCheck(options) {
    return useQuery({
        queryKey: getHealthCheckQueryKey(),
        queryFn: () => request('/api/health'),
        ...(options?.query ?? {}),
    });
}

// was /api/graph/overview — the backend's equivalent is /api/graph/info
export const getGetGraphOverviewQueryKey = () => ['/api/graph/info'];
export function useGetGraphOverview(options) {
    return useQuery({
        queryKey: getGetGraphOverviewQueryKey(),
        queryFn: () => request('/api/graph/info'),
        ...(options?.query ?? {}),
    });
}

export const getGetGraphNetworkQueryKey = (params) =>
    params ? ['/api/graph/network', params] : ['/api/graph/network'];

export function useGetGraphNetwork(params, options) {
    const getGraph = useGraphData();
    return useQuery({
        queryKey: getGetGraphNetworkQueryKey(params),
        queryFn: async () => {
            const data = await getGraph();
            return egoSlice(data, params?.center, Math.max(params?.depth ?? 1, 1));
        },
        ...(options?.query ?? {}),
    });
}

export const getSearchGraphQueryKey = (params) =>
    params ? ['/api/graph/search', params] : ['/api/graph/search'];

export function useSearchGraph(params, options) {
    const getGraph = useGraphData();
    const q = (params?.q ?? '').trim().toLowerCase();
    return useQuery({
        queryKey: getSearchGraphQueryKey(params),
        queryFn: async () => {
            if (!q) return { results: [], total: 0 };
            const data = await getGraph();
            const results = (data.nodes ?? [])
                .filter((n) => String(n.id ?? n.label).toLowerCase().includes(q))
                .map((n) => ({
                    ...n,
                    id: String(n.id ?? n.label),
                    label: String(n.label ?? n.id),
                }));
            return { results, total: results.length };
        },
        ...(options?.query ?? {}),
    });
}

export const getFindGraphPathQueryKey = (params) =>
    params ? ['/api/graph/path', params] : ['/api/graph/path'];

export function useFindGraphPath(params, options) {
    const getGraph = useGraphData();
    return useQuery({
        queryKey: getFindGraphPathQueryKey(params),
        queryFn: async () => {
            const s = params?.from;
            const t = params?.to;
            if (!s || !t) throw new Error('Both "from" and "to" are required');
            const data = await getGraph();
            const adj = buildAdjacency(data);
            if (!adj.has(String(s))) throw new Error(`Unknown node: ${s}`);
            if (!adj.has(String(t))) throw new Error(`Unknown node: ${t}`);

            // BFS
            const prev = new Map([[String(s), null]]);
            const queue = [String(s)];
            while (queue.length) {
                const cur = queue.shift();
                if (cur === String(t)) break;
                for (const nb of adj.get(cur)) {
                    if (!prev.has(nb)) { prev.set(nb, cur); queue.push(nb); }
                }
            }
            if (!prev.has(String(t))) throw new Error(`No path between "${s}" and "${t}"`);

            const chain = [];
            for (let v = String(t); v !== null; v = prev.get(v)) chain.push(v);
            chain.reverse();

            const nodeById = new Map(
                (data.nodes ?? []).map((n) => [String(n.id ?? n.label), n]),
            );
            const linkKey = (a, b) => [a, b].sort().join('\u0000');
            const linkIndex = new Map(
                (data.links ?? []).map((l) => [linkKey(String(l.source), String(l.target)), l]),
            );
            const links = [];
            for (let i = 0; i < chain.length - 1; i++) {
                const l = linkIndex.get(linkKey(chain[i], chain[i + 1]));
                if (l) links.push(l);
            }
            return {
                nodes: chain.map((id) => nodeById.get(id) ?? { id }),
                links,
                edges: links,
                length: chain.length - 1,
            };
        },
        enabled: Boolean(params?.from && params?.to),
        ...(options?.query ?? {}),
    });
}

export const getGetCentralityQueryKey = () => ['/api/graph/centrality'];

export function useGetCentrality(options) {
    const getGraph = useGraphData();
    return useQuery({
        queryKey: getGetCentralityQueryKey(),
        queryFn: async () => {
            const data = await getGraph();
            const counts = new Map();
            for (const l of data.links ?? []) {
                for (const v of [String(l.source), String(l.target)]) {
                    counts.set(v, (counts.get(v) ?? 0) + 1);
                }
            }
            const n = (data.nodes ?? []).length;
            const results = (data.nodes ?? [])
                .map((nd) => {
                    const id = String(nd.id ?? nd.label);
                    const degree = counts.get(id) ?? 0;
                    return {
                        ...nd,
                        id,
                        label: String(nd.label ?? nd.id),
                        degree,
                        centrality: n > 1 ? degree / (n - 1) : 0,
                    };
                })
                .sort((a, b) => b.degree - a.degree);
            return { results };
        },
        // If graph_metrics.json turns out to already contain per-node scores,
        // swap queryFn for: () => request('/api/graph/metrics')
        ...(options?.query ?? {}),
    });
}

export const getGetCommunitiesQueryKey = () => ['/api/graph/communities'];

export function useGetCommunities(options) {
    const getGraph = useGraphData();
    return useQuery({
        queryKey: getGetCommunitiesQueryKey(),
        queryFn: async () => {
            const data = await getGraph();
            const adj = buildAdjacency(data);
            const ids = (data.nodes ?? []).map((n) => String(n.id ?? n.label));
            // simple label propagation — good enough for visualization
            const labels = new Map(ids.map((id) => [id, id]));
            for (let iter = 0; iter < 12; iter++) {
                for (const id of ids) {
                    const counts = new Map();
                    for (const nb of adj.get(id) ?? []) {
                        const lb = labels.get(nb);
                        counts.set(lb, (counts.get(lb) ?? 0) + 1);
                    }
                    if (counts.size) {
                        labels.set(
                            id,
                            [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0],
                        );
                    }
                }
            }
            const groups = new Map();
            for (const [id, lb] of labels) {
                if (!groups.has(lb)) groups.set(lb, []);
                groups.get(lb).push(id);
            }
            const results = [...groups.values()].map((members, i) => ({
                id: i,
                size: members.length,
                members,
            }));
            return { results };
        },
        ...(options?.query ?? {}),
    });
}

export const getGetGraphTimelineQueryKey = (params) =>
    params ? ['/api/graph/timeline', params] : ['/api/graph/timeline'];

export function useGetGraphTimeline(params, options) {
    return useQuery({
        queryKey: getGetGraphTimelineQueryKey(params),
        queryFn: () =>
            request('/api/graph/events', {
                entity_id: params?.entityId,
                from: params?.from,
                to: params?.to,
            }),
        ...(options?.query ?? {}),
    });
}

export const getGetCallsQueryKey = (params) => ['/api/data/calls', params ?? null];
export function useGetCalls(params, options) {
    return useQuery({
        queryKey: getGetCallsQueryKey(params),
        queryFn: () => request('/api/data/calls', params),
        ...(options?.query ?? {}),
    });
}

export const getGetMeetingsQueryKey = (params) => ['/api/data/meetings', params ?? null];
export function useGetMeetings(params, options) {
    return useQuery({
        queryKey: getGetMeetingsQueryKey(params),
        queryFn: () => request('/api/data/meetings', params),
        ...(options?.query ?? {}),
    });
}

export const getGetTransactionsQueryKey = (params) => ['/api/data/transactions', params ?? null];
export function useGetTransactions(params, options) {
    return useQuery({
        queryKey: getGetTransactionsQueryKey(params),
        queryFn: () => request('/api/data/transactions', params),
        ...(options?.query ?? {}),
    });
}

// ---------------------------------------------------------------------------
// Passthrough hooks for backend endpoints you'll build UI against later.
// All list endpoints return the backend envelope untouched:
//   { items, total, page, page_size }
// Copy this 6-line pattern for /api/data/* and /api/pipeline/* too.
// ---------------------------------------------------------------------------

export const getGetEntitiesQueryKey = (params) => ['/api/graph/entities', params ?? null];
export function useGetEntities(params, options) {
    return useQuery({
        queryKey: getGetEntitiesQueryKey(params),
        queryFn: () => request('/api/graph/entities', params),
        ...(options?.query ?? {}),
    });
}

export const getGetPersonsQueryKey = (params) => ['/api/data/persons', params ?? null];
export function useGetPersons(params, options) {
    return useQuery({
        queryKey: getGetPersonsQueryKey(params),
        queryFn: () => request('/api/data/persons', params),
        ...(options?.query ?? {}),
    });
}

export function useNodeNeighbors(nodeLabel, options) {
    return useQuery({
        queryKey: ['/api/graph/neighbors', nodeLabel],
        queryFn: () => request(`/api/graph/neighbors/${encodeURIComponent(nodeLabel)}`),
        enabled: Boolean(nodeLabel),
        ...(options?.query ?? {}),
    });
}

export function useGhostEvidence(ghostId, options) {
    return useQuery({
        queryKey: ['/api/graph/ghosts', ghostId, 'evidence'],
        queryFn: () => request(`/api/graph/ghosts/${encodeURIComponent(ghostId)}/evidence`),
        enabled: Boolean(ghostId),
        ...(options?.query ?? {}),
    });
}

// ---------------------------------------------------------------------------
// Pipeline hooks — backed by /api/pipeline/* endpoints
// ---------------------------------------------------------------------------

export const getJobsQueryKey = () => ['/api/pipeline/jobs'];

export function useListJobs(options) {
    return useQuery({
        queryKey: getJobsQueryKey(),
        queryFn: () => request('/api/pipeline/jobs'),
        refetchInterval: (query) => {
            const jobs = query.state.data ?? [];
            const hasActive = jobs.some((j) => j.status === 'pending' || j.status === 'running');
            return hasActive ? 2000 : false;
        },
        ...(options?.query ?? {}),
    });
}

export function useTriggerPipeline() {
    const qc = useQueryClient();
    return {
        trigger: async (stage) => {
            const res = await requestJson(`/api/pipeline/${stage}`, { method: 'POST', body: {} });
            qc.invalidateQueries({ queryKey: getJobsQueryKey() });
            return res;
        },
    };
}
