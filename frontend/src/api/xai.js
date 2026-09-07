// src/api/xai.js — hooks for the evidence / findings / simulation / dossier /
// case / global-search route groups. All list endpoints return the backend
// envelope untouched: { items, total, page, page_size }.
import { useQuery } from '@tanstack/react-query';
import { request, requestJson } from './client';

// NOTE: request() throws on !res.ok with the backend's detail — good.
// For POST/PATCH we need a small JSON poster; client.js only does GETs.
async function send(method, path, body) {
    return requestJson(path, { method, body });
}

// ---------------------------------------------------------------- evidence --
export const getEvidenceForNodeQueryKey = (nodeId) => ['/api/evidence/for-node', nodeId];
export function useEvidenceForNode(nodeId, options) {
    return useQuery({
        queryKey: getEvidenceForNodeQueryKey(nodeId),
        queryFn: () => request(`/api/evidence/for-node/${encodeURIComponent(nodeId)}`),
        enabled: Boolean(nodeId),
        ...(options?.query ?? {}),
    });
}

export const getEvidenceSearchQueryKey = (params) => ['/api/evidence/search', params ?? null];
export function useEvidenceSearch(params, options) {
    return useQuery({
        queryKey: getEvidenceSearchQueryKey(params),
        queryFn: () => request('/api/evidence/search', params),
        enabled: Boolean(params?.q && params.q.length >= 2),
        ...(options?.query ?? {}),
    });
}

export const getEvidenceTimelineQueryKey = (subjectId) => ['/api/evidence/timeline', subjectId];
export function useEvidenceTimeline(subjectId, options) {
    return useQuery({
        queryKey: getEvidenceTimelineQueryKey(subjectId),
        queryFn: () => request(`/api/evidence/timeline/${encodeURIComponent(subjectId)}`),
        enabled: Boolean(subjectId),
        ...(options?.query ?? {}),
    });
}

export function useEvidenceDetail(evidenceId, options) {
    return useQuery({
        queryKey: ['/api/evidence/item', evidenceId],
        queryFn: () => request(`/api/evidence/${encodeURIComponent(evidenceId)}`),
        enabled: Boolean(evidenceId),
        ...(options?.query ?? {}),
    });
}

// ---------------------------------------------------------------- findings --
export const getFindingsQueryKey = (params) => ['/api/findings', params ?? null];
export function useFindings(params, options) {
    return useQuery({
        queryKey: getFindingsQueryKey(params),
        queryFn: () => request('/api/findings', params),
        ...(options?.query ?? {}),
    });
}

export function useFindingDetail(findingId, options) {
    return useQuery({
        queryKey: ['/api/findings/item', findingId],
        queryFn: () => request(`/api/findings/${encodeURIComponent(findingId)}`),
        enabled: Boolean(findingId),
        ...(options?.query ?? {}),
    });
}

export async function generateFindings() {
    return send('POST', '/api/findings/generate');
}

// -------------------------------------------------------------- simulation --
export async function runNodeRemovalSimulation(payload) {
    return send('POST', '/api/simulation/node-removal', payload);
}

export async function runScenarioComparison(nodeIds) {
    return send('POST', '/api/simulation/compare', { node_ids: nodeIds });
}

// ---------------------------------------------------------------- dossiers --
export const getDossiersQueryKey = () => ['/api/dossiers'];
export function useDossiers(options) {
    return useQuery({
        queryKey: getDossiersQueryKey(),
        queryFn: () => request('/api/dossiers'),
        ...(options?.query ?? {}),
    });
}

export function useDossierDetail(dossierId, options) {
    return useQuery({
        queryKey: ['/api/dossiers/item', dossierId],
        queryFn: () => request(`/api/dossiers/${encodeURIComponent(dossierId)}`),
        enabled: Boolean(dossierId),
        ...(options?.query ?? {}),
    });
}

export async function generateDossier(payload) {
    return send('POST', '/api/dossiers/generate', payload);
}

export async function reviewDossier(dossierId, payload) {
    return send('POST', `/api/dossiers/${encodeURIComponent(dossierId)}/review`, payload);
}

// ------------------------------------------------------------------- cases --
export const getCasesQueryKey = () => ['/api/cases'];
export function useCases(options) {
    return useQuery({
        queryKey: getCasesQueryKey(),
        queryFn: () => request('/api/cases'),
        ...(options?.query ?? {}),
    });
}

export function useCaseDetail(caseId, options) {
    return useQuery({
        queryKey: ['/api/cases/item', caseId],
        queryFn: () => request(`/api/cases/${encodeURIComponent(caseId)}`),
        enabled: Boolean(caseId),
        ...(options?.query ?? {}),
    });
}

export async function createCase(payload) {
    return send('POST', '/api/cases', payload);
}

export async function updateCase(caseId, payload) {
    return send('PATCH', `/api/cases/${encodeURIComponent(caseId)}`, payload);
}

// ----------------------------------------------------------- global search --
export const getGlobalSearchQueryKey = (params) => ['/api/search', params ?? null];
export function useGlobalSearch(params, options) {
    return useQuery({
        queryKey: getGlobalSearchQueryKey(params),
        queryFn: () => request('/api/search', params),
        enabled: Boolean(params?.q && params.q.length >= 2),
        ...(options?.query ?? {}),
    });
}

// ------------------------------------------------------------ server graph --
export const getSubgraphQueryKey = (params) => ['/api/graph/subgraph', params ?? null];
export function useSubgraph(params, options) {
    return useQuery({
        queryKey: getSubgraphQueryKey(params),
        queryFn: () => request('/api/graph/subgraph', params),
        enabled: Boolean(params?.node_id),
        ...(options?.query ?? {}),
    });
}

export const getPathsQueryKey = (params) => ['/api/graph/paths', params ?? null];
export function usePaths(params, options) {
    return useQuery({
        queryKey: getPathsQueryKey(params),
        queryFn: () =>
            request(
                `/api/graph/paths/${encodeURIComponent(params?.source)}/${encodeURIComponent(params?.target)}`,
                { k: params?.k },
            ),
        enabled: Boolean(params?.source && params?.target),
        ...(options?.query ?? {}),
    });
}
