// src/api/search.js — global/entity search hooks (split from xai.js)
import { useQuery } from '@tanstack/react-query';
import { request } from './client';

export const getGlobalSearchQueryKey = (params) => ['/api/search', params ?? null];
export function useGlobalSearch(params, options) {
    return useQuery({
        queryKey: getGlobalSearchQueryKey(params),
        queryFn: () => request('/api/search', params),
        enabled: Boolean(params?.q && params.q.length >= 2),
        ...(options?.query ?? {}),
    });
}

export const getEntitySearchQueryKey = (params) => ['/api/entity/search', params ?? null];
export function useEntitySearch(params, options) {
    return useQuery({
        queryKey: getEntitySearchQueryKey(params),
        queryFn: () => request('/api/entity/search', params),
        enabled: Boolean(params?.q && params.q.length >= 2),
        ...(options?.query ?? {}),
    });
}
