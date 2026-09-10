/**
 * frontend/src/api/intel.js
 * -------------------------
 * React Query hooks for the Thupparivu intelligence route groups:
 *
 *  - /api/temporal/*       (snapshots, timeline replay, graph diff, evolution, layers)
 *  - /api/hypotheses/*     (hypothesis generation, detail with contradiction, disposition)
 *  - /api/investigation/*  (relationship gaps, network resilience, counterfactuals)
 *  - /api/models/*         (model registry, benchmark metrics, benchmark run)
 *  - /api/communities/*    (profiles, member roles, before/after compare)
 *  - /api/financial/*      (account transfer network, fund-flow tracing)
 *  - /api/intel/*          (case brief, investigative gaps, cross-case entity reuse)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { request, requestJson } from './client';

async function send(method, path, body) {
    return requestJson(path, { method, body });
}

// ─────────────────────────────────────────────────────────────
// TEMPORAL INTELLIGENCE
// ─────────────────────────────────────────────────────────────

export function useTemporalInfo(options) {
    return useQuery({
        queryKey: ['/api/temporal/info'],
        queryFn: () => request('/api/temporal/info'),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useTemporalSnapshot(asOf, options) {
    return useQuery({
        queryKey: ['/api/temporal/snapshot', asOf],
        queryFn: () => request('/api/temporal/snapshot', { as_of: asOf }),
        enabled: Boolean(asOf),
        ...(options?.query ?? {}),
    });
}

export function useTemporalTimeline(nBuckets = 12, options) {
    return useQuery({
        queryKey: ['/api/temporal/timeline', nBuckets],
        queryFn: () => request('/api/temporal/timeline', { n_buckets: nBuckets }),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useTemporalDiff(start, end, options) {
    return useQuery({
        queryKey: ['/api/temporal/diff', start, end],
        queryFn: () => request('/api/temporal/diff', { start, end }),
        enabled: Boolean(start && end),
        ...(options?.query ?? {}),
    });
}

export function useTemporalEvolution(nBuckets = 8, options) {
    return useQuery({
        queryKey: ['/api/temporal/communities/evolution', nBuckets],
        queryFn: () => request('/api/temporal/communities/evolution', { n_buckets: nBuckets }),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useTemporalLayers(options) {
    return useQuery({
        queryKey: ['/api/temporal/layers'],
        queryFn: () => request('/api/temporal/layers'),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useTemporalLayer(layerName, options) {
    return useQuery({
        queryKey: ['/api/temporal/layer', layerName],
        queryFn: () => request(`/api/temporal/layer/${encodeURIComponent(layerName)}`),
        enabled: Boolean(layerName),
        ...(options?.query ?? {}),
    });
}

export function useNodeTemporalFeatures(nodeId, options) {
    return useQuery({
        queryKey: ['/api/temporal/nodes/features', nodeId],
        queryFn: () => request(`/api/temporal/nodes/${encodeURIComponent(nodeId)}/features`),
        enabled: Boolean(nodeId),
        ...(options?.query ?? {}),
    });
}

// ─────────────────────────────────────────────────────────────
// HYPOTHESES & DISPOSITION
// ─────────────────────────────────────────────────────────────

export function useHypotheses(params, options) {
    return useQuery({
        queryKey: ['/api/hypotheses', params ?? null],
        queryFn: () => request('/api/hypotheses', params),
        ...(options?.query ?? {}),
    });
}

export function useHypothesisDetail(hypothesisId, options) {
    return useQuery({
        queryKey: ['/api/hypotheses/item', hypothesisId],
        queryFn: () => request(`/api/hypotheses/${encodeURIComponent(hypothesisId)}`),
        enabled: Boolean(hypothesisId),
        ...(options?.query ?? {}),
    });
}

export async function generateHypotheses() {
    return send('POST', '/api/hypotheses/generate');
}

export async function recordHypothesisDisposition(hypothesisId, payload) {
    return send('POST', `/api/hypotheses/${encodeURIComponent(hypothesisId)}/disposition`, payload);
}

// ─────────────────────────────────────────────────────────────
// DEEP INVESTIGATION & COUNTERFACTUAL
// ─────────────────────────────────────────────────────────────

export function useRelationshipGaps(params, options) {
    return useQuery({
        queryKey: ['/api/investigation/relationship-gaps', params ?? null],
        queryFn: () => request('/api/investigation/relationship-gaps', params),
        ...(options?.query ?? {}),
    });
}

export async function runResilienceAnalysis(payload) {
    return send('POST', '/api/investigation/resilience', payload);
}

export function useCounterfactualOperations(options) {
    return useQuery({
        queryKey: ['/api/investigation/counterfactual/operations'],
        queryFn: () => request('/api/investigation/counterfactual/operations'),
        staleTime: 5 * 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export async function runDeepCounterfactual(payload) {
    return send('POST', '/api/investigation/counterfactual', payload);
}

// ─────────────────────────────────────────────────────────────
// MODEL REGISTRY & BENCHMARKS
// ─────────────────────────────────────────────────────────────

export function useModels(options) {
    return useQuery({
        queryKey: ['/api/models'],
        queryFn: () => request('/api/models'),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useModelDetail(modelName, options) {
    return useQuery({
        queryKey: ['/api/models/item', modelName],
        queryFn: () => request(`/api/models/${encodeURIComponent(modelName)}`),
        enabled: Boolean(modelName),
        ...(options?.query ?? {}),
    });
}

export function useModelRuns(params, options) {
    return useQuery({
        queryKey: ['/api/models/runs', params ?? null],
        queryFn: () => request('/api/models/runs', params),
        ...(options?.query ?? {}),
    });
}

export function useBenchmarkMetrics(options) {
    return useQuery({
        queryKey: ['/api/models/benchmark/metrics'],
        queryFn: () => request('/api/models/benchmark/metrics'),
        ...(options?.query ?? {}),
    });
}

export async function runBenchmark() {
    return send('POST', '/api/models/benchmark/run');
}

// ─────────────────────────────────────────────────────────────
// COMMUNITIES
// ─────────────────────────────────────────────────────────────

export function useCommunities(params, options) {
    return useQuery({
        queryKey: ['/api/communities', params ?? null],
        queryFn: () => request('/api/communities', params),
        ...(options?.query ?? {}),
    });
}

export function useCommunityDetail(communityId, options) {
    return useQuery({
        queryKey: ['/api/communities/item', communityId],
        queryFn: () => request(`/api/communities/${encodeURIComponent(communityId)}`),
        enabled: Boolean(communityId),
        ...(options?.query ?? {}),
    });
}

export function useCommunityRoles(communityId, options) {
    return useQuery({
        queryKey: ['/api/communities/roles', communityId],
        queryFn: () => request(`/api/communities/${encodeURIComponent(communityId)}/roles`),
        enabled: Boolean(communityId),
        ...(options?.query ?? {}),
    });
}

export async function compareCommunities(payload) {
    return send('POST', '/api/communities/compare', payload);
}

// ─────────────────────────────────────────────────────────────
// FINANCIAL FLOWS
// ─────────────────────────────────────────────────────────────

export function useFinancialAccounts(params, options) {
    return useQuery({
        queryKey: ['/api/financial/accounts', params ?? null],
        queryFn: () => request('/api/financial/accounts', params),
        ...(options?.query ?? {}),
    });
}

export async function traceFunds(payload) {
    return send('POST', '/api/financial/trace', payload);
}

// ─────────────────────────────────────────────────────────────
// P1 ANALYTICAL INTELLIGENCE
// ─────────────────────────────────────────────────────────────

export function useReplayBuckets(nBuckets = 12, options) {
    return useQuery({
        queryKey: ['/api/replay/buckets', nBuckets],
        queryFn: () => request('/api/replay/buckets', { n_buckets: nBuckets }),
        staleTime: 5 * 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useReplaySnapshot(timestamp, mode = 'cumulative', options) {
    return useQuery({
        queryKey: ['/api/replay/snapshot', timestamp, mode],
        queryFn: () => request('/api/replay/snapshot', { timestamp, mode }),
        enabled: Boolean(timestamp),
        ...(options?.query ?? {}),
    });
}

export function useReplayDiff(from, to, options) {
    return useQuery({
        queryKey: ['/api/replay/diff', from, to],
        queryFn: () => request('/api/replay/diff', { from, to }),
        enabled: Boolean(from && to),
        ...(options?.query ?? {}),
    });
}

export function useReplayEvents(options) {
    return useQuery({
        queryKey: ['/api/replay/events'],
        queryFn: () => request('/api/replay/events'),
        staleTime: 5 * 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useMotifs(params, options) {
    return useQuery({
        queryKey: ['/api/motifs', params ?? null],
        queryFn: () => request('/api/motifs/', params),
        staleTime: 5 * 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useDataQuality(entityIds, options) {
    return useQuery({
        queryKey: ['/api/data-quality', entityIds ?? null],
        queryFn: () => request('/api/data-quality/', entityIds ? { entity_ids: entityIds.join(',') } : undefined),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useEntityDataQuality(entityId, options) {
    return useQuery({
        queryKey: ['/api/data-quality/entity', entityId],
        queryFn: () => request(`/api/data-quality/entity/${encodeURIComponent(entityId)}`),
        enabled: Boolean(entityId),
        ...(options?.query ?? {}),
    });
}

export function useMethodAgreement(entityIds, options) {
    return useQuery({
        queryKey: ['/api/method-agreement', entityIds ?? null],
        queryFn: () => request('/api/method-agreement/', entityIds ? { entity_ids: entityIds.join(',') } : undefined),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useEntityMethodAgreement(entityId, options) {
    return useQuery({
        queryKey: ['/api/method-agreement/entity', entityId],
        queryFn: () => request(`/api/method-agreement/entity/${encodeURIComponent(entityId)}`),
        enabled: Boolean(entityId),
        ...(options?.query ?? {}),
    });
}

export function useFinancialSignals(options) {
    return useQuery({
        queryKey: ['/api/financial-enhanced/signals'],
        queryFn: () => request('/api/financial-enhanced/signals'),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useFinancialAggregated(params, options) {
    return useQuery({
        queryKey: ['/api/financial-enhanced/aggregated', params ?? null],
        queryFn: () => request('/api/financial-enhanced/aggregated', params),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useCounterEvidence(findingId, options) {
    return useQuery({
        queryKey: ['/api/counter-evidence/finding', findingId],
        queryFn: () => request(`/api/counter-evidence/finding/${encodeURIComponent(findingId)}`),
        enabled: Boolean(findingId),
        ...(options?.query ?? {}),
    });
}

// ─────────────────────────────────────────────────────────────
// INTEL & GAPS & CROSS-CASE
// ─────────────────────────────────────────────────────────────

export function useCaseBrief(caseId, options) {
    return useQuery({
        queryKey: ['/api/intel/case-brief', caseId],
        queryFn: () => request(`/api/intel/cases/${encodeURIComponent(caseId)}/brief`),
        enabled: Boolean(caseId),
        ...(options?.query ?? {}),
    });
}

export function useInvestigativeGaps(params, options) {
    return useQuery({
        queryKey: ['/api/intel/gaps', params ?? null],
        queryFn: () => request('/api/intel/gaps', params),
        ...(options?.query ?? {}),
    });
}

export function useCrossCase(params, options) {
    return useQuery({
        queryKey: ['/api/intel/cross-case', params ?? null],
        queryFn: () => request('/api/intel/cross-case', params),
        ...(options?.query ?? {}),
    });
}

// ─────────────────────────────────────────────────────────────
// P2 — CASE DNA / SIMILARITY
// ─────────────────────────────────────────────────────────────

export function useCaseFingerprint(caseId = 'CASE-0421', options) {
    return useQuery({
        queryKey: ['/api/case-dna/fingerprint', caseId],
        queryFn: () => request('/api/case-dna/fingerprint', { case_id: caseId }),
        staleTime: 5 * 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useCaseSimilarity(caseId = 'CASE-0421', weights, options) {
    return useQuery({
        queryKey: ['/api/case-dna/similarity', caseId, weights],
        queryFn: () => request('/api/case-dna/similarity', { case_id: caseId, ...weights }),
        staleTime: 5 * 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useCaseCompare(caseA, caseB, options) {
    return useQuery({
        queryKey: ['/api/case-dna/compare', caseA, caseB],
        queryFn: () => request('/api/case-dna/compare', { case_a: caseA, case_b: caseB }),
        enabled: Boolean(caseA && caseB),
        ...(options?.query ?? {}),
    });
}

// ─────────────────────────────────────────────────────────────
// P2 — GEOSPATIAL INTELLIGENCE
// ─────────────────────────────────────────────────────────────

export function useGeoObservations(params, options) {
    return useQuery({
        queryKey: ['/api/geo/observations', params ?? null],
        queryFn: () => request('/api/geo/observations', params),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useGeoClusters(gridSizeKm = 5, options) {
    return useQuery({
        queryKey: ['/api/geo/clusters', gridSizeKm],
        queryFn: () => request('/api/geo/clusters', { grid_size_km: gridSizeKm }),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export function useGeoProximity(maxDistanceKm = 5, options) {
    return useQuery({
        queryKey: ['/api/geo/proximity', maxDistanceKm],
        queryFn: () => request('/api/geo/proximity', { max_distance_km: maxDistanceKm }),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

// ─────────────────────────────────────────────────────────────
// P2 — NATURAL LANGUAGE QUERY
// ─────────────────────────────────────────────────────────────

export function useDemoQueries(options) {
    return useQuery({
        queryKey: ['/api/nl-query/demo-queries'],
        queryFn: () => request('/api/nl-query/demo-queries'),
        staleTime: 10 * 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export async function askAnalystQuery(query) {
    return requestJson('/api/nl-query/ask', { method: 'POST', body: { query } });
}

// ─────────────────────────────────────────────────────────────
// P2 — NEXT-BEST ACTION
// ─────────────────────────────────────────────────────────────

export function useRecommendations(params, options) {
    return useQuery({
        queryKey: ['/api/recommendations', params ?? null],
        queryFn: () => request('/api/recommendations/', params),
        staleTime: 60 * 1000,
        ...(options?.query ?? {}),
    });
}

export async function submitRecommendationFeedback(recommendationId, action) {
    return requestJson('/api/recommendations/feedback', {
        method: 'POST',
        body: { recommendation_id: recommendationId, action },
    });
}
