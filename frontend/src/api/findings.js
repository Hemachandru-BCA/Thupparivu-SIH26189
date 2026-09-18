// src/api/findings.js — findings hooks (split from xai.js)
import { useQuery } from '@tanstack/react-query';
import { request, requestJson } from './client';

async function send(method, path, body) {
    return requestJson(path, { method, body });
}

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
