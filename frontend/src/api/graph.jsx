import { useQuery } from '@tanstack/react-query';
import { request } from './client';
import { getFindGraphPathQueryKey, getGetCallsQueryKey, getGetCentralityQueryKey, getGetCommunitiesQueryKey, getGetEntitiesQueryKey, getGetGraphNetworkQueryKey, getGetGraphOverviewQueryKey, getGetGraphTimelineQueryKey, getGetMeetingsQueryKey, getGetPersonsQueryKey, getGetTransactionsQueryKey, getHealthCheckQueryKey, getSearchGraphQueryKey, useFindGraphPath as useGeneratedFindGraphPath, useGetCalls as useGeneratedGetCalls, useGetCentrality as useGeneratedGetCentrality, useGetCommunities as useGeneratedGetCommunities, useGetEntities as useGeneratedGetEntities, useGetGraphNetwork as useGeneratedGetGraphNetwork, useGetGraphOverview as useGeneratedGetGraphOverview, useGetGraphTimeline as useGeneratedGetGraphTimeline, useGetMeetings as useGeneratedGetMeetings, useGetPersons as useGeneratedGetPersons, useGetTransactions as useGeneratedGetTransactions, useHealthCheck as useGeneratedHealthCheck, useSearchGraph as useGeneratedSearchGraph, } from './client';
export { getFindGraphPathQueryKey, getGetCallsQueryKey, getGetCentralityQueryKey, getGetCommunitiesQueryKey, getGetEntitiesQueryKey, getGetGraphNetworkQueryKey, getGetGraphOverviewQueryKey, getGetGraphTimelineQueryKey, getGetMeetingsQueryKey, getGetPersonsQueryKey, getGetTransactionsQueryKey, getHealthCheckQueryKey, getSearchGraphQueryKey, };
export function useGetGraphOverview(...args) {
    const result = useGeneratedGetGraphOverview(...args);
    const raw = result.data;
    const data = raw
        ? {
            ...raw,
            entityCounts: raw.entityCounts ?? {},
            topEntities: raw.topEntities ?? [],
            recentActivity: raw.recentActivity ?? [],
        }
        : raw;
    return { ...result, data };
}
export function useGetGraphNetwork(...args) {
    const result = useGeneratedGetGraphNetwork(...args);
    const raw = result.data;
    return {
        ...result,
        data: raw
            ? {
                ...raw,
                nodes: raw.nodes ?? [],
                edges: raw.edges ?? [],
            }
            : raw,
    };
}
export function useSearchGraph(...args) {
    const result = useGeneratedSearchGraph(...args);
    return { ...result, data: result.data?.results ?? result.data ?? [] };
}
export function useFindGraphPath(...args) {
    const result = useGeneratedFindGraphPath(...args);
    const raw = result.data;
    return {
        ...result,
        data: raw
            ? {
                ...raw,
                nodes: raw.nodes ?? [],
                edges: raw.edges ?? [],
                path: raw.path ?? [],
            }
            : raw,
    };
}
export function useGetCentrality(...args) {
    const result = useGeneratedGetCentrality(...args);
    return { ...result, data: result.data?.results ?? result.data ?? [] };
}
export function useGetCommunities(...args) {
    const result = useGeneratedGetCommunities(...args);
    return { ...result, data: result.data?.results ?? result.data ?? [] };
}
export function useGetGraphTimeline(...args) {
    const result = useGeneratedGetGraphTimeline(...args);
    return { ...result, data: result.data?.items ?? result.data ?? [] };
}
export function useGetCalls(...args) {
    const result = useGeneratedGetCalls(...args);
    return { ...result, data: result.data ?? { items: [], total: 0 } };
}
export function useGetMeetings(...args) {
    const result = useGeneratedGetMeetings(...args);
    return { ...result, data: result.data ?? { items: [], total: 0 } };
}
export function useGetTransactions(...args) {
    const result = useGeneratedGetTransactions(...args);
    return { ...result, data: result.data ?? { items: [], total: 0 } };
}
export function useGetEntities(...args) {
    const result = useGeneratedGetEntities(...args);
    return { ...result, data: result.data ?? { items: [], total: 0 } };
}
export function useGetPersons(...args) {
    const result = useGeneratedGetPersons(...args);
    return { ...result, data: result.data ?? { items: [], total: 0 } };
}
export function useHealthCheck(...args) {
    const result = useGeneratedHealthCheck(...args);
    return { ...result, data: result.data };
}

export const getGetGhostsQueryKey = () => ['/api/graph/ghosts'];

export function useGetGhosts() {
    return useQuery({
        queryKey: getGetGhostsQueryKey(),
        queryFn: () => request('/api/graph/ghosts', { page: 1, page_size: 50 }),
    });
}

// Pipeline
export { getJobsQueryKey, useListJobs, useTriggerPipeline } from './client';
