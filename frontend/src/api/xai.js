// src/api/xai.js — barrel re-export (backwards compat, deprecate later)
// Domain logic has been split into dedicated files.
export * from './findings';
export * from './cases';
export * from './search';

// --- Evidence, Simulation, Dossiers, Subgraph (remaining domain logic) ---
import { useQuery } from '@tanstack/react-query';
import { request, requestJson } from './client';

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

export function useEvidenceChainForEntity(entityId, options) {
    return useQuery({
        queryKey: ['/api/evidence/chain/entity', entityId],
        queryFn: () => request(`/api/evidence/chain/entity/${encodeURIComponent(entityId)}`),
        enabled: Boolean(entityId),
        ...(options?.query ?? {}),
    });
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
