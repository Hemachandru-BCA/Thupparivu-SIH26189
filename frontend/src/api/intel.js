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
