// src/api/cases.js — case hooks (split from xai.js)
import { useQuery } from '@tanstack/react-query';
import { request, requestJson } from './client';

async function send(method, path, body) {
    return requestJson(path, { method, body });
}

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
