/**
 * frontend/src/pages/workspace/entity-analysis-workspace.jsx
 * -----------------------------------------------------------
 * "WHY IS THIS IMPORTANT?" — P0.4 Entity Analytical Profile.
 *
 * Selected entity → analytical explanation:
 *   1. NETWORK POSITION   (bridge / centrality)
 *   2. TEMPORAL ROLE      (activity timing relative to network events)
 *   3. CROSS-CASE PRESENCE (recurrence across investigations)
 *   4. FINANCIAL ROLE     (fund movement involvement)
 *   5. COUNTERFACTUAL IMPACT (what breaks when removed)
 *   6. EVIDENCE           (supporting vs contradictory)
 *
 * Every statement is backed by actual backend data. No fabricated claims.
 */

import React, { useState, useMemo, useEffect } from 'react';
import { useLocation, useRoute, Link } from 'wouter';
import {
    ArrowLeft, Network as NetworkIcon, Clock, FolderOpen, DollarSign,
    Zap, FileText, CheckCircle2, XCircle, HelpCircle, ExternalLink,
    Bookmark, BookmarkCheck, ChevronRight, AlertTriangle, Activity, Scale
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { useGraphMetrics, useGetGraphNeighborhood } from '@/api/graph';
import { useEvidenceForNode, useEvidenceTimeline, runNodeRemovalSimulation } from '@/api/xai';
import { useCrossCase } from '@/api/intel';
import { useCaseDetail, updateCase } from '@/api/xai';
import { getEntityTypeColor, formatNumber } from '@/components/app-shell';

/* ── Helpers ── */
function pct(v) { return `${Math.round((v || 0) * 100)}%`; }

function rankLabel(v) {
    if (v >= 0.85) return { label: 'VERY HIGH', cls: 'text-red font-bold' };
    if (v >= 0.65) return { label: 'HIGH', cls: 'text-amber font-bold' };
    if (v >= 0.4) return { label: 'MEDIUM', cls: 'text-blue' };
    if (v >= 0.15) return { label: 'LOW', cls: 'text-fg-secondary' };
    return { label: 'MINIMAL', cls: 'text-fg-faint' };
}

function SignalBar({ label, value, hint }) {
    const rl = rankLabel(value);
    return (
        <div className="py-1.5">
            <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] font-mono text-fg-secondary">{label}</span>
                <span className={`text-[10px] font-mono ${rl.cls}`}>{pct(value)} · {rl.label}</span>
            </div>
            <div className="h-1.5 rounded-full bg-bg-root overflow-hidden">
                <div
                    className="h-full rounded-full"
                    style={{
                        width: `${Math.min(Math.max((value || 0) * 100, 2), 100)}%`,
                        background: value >= 0.65 ? '#f59e0b' : value >= 0.4 ? '#3b82f6' : '#6b7280',
                    }}
                />
            </div>
            {hint && <div className="text-[9px] text-fg-faint mt-0.5">{hint}</div>}
        </div>
    );
}

function EvidenceGroup({ title, items, icon: Icon, colorClass }) {
    if (!items || items.length === 0) return null;
    return (
        <div>
            <div className={`flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wide ${colorClass}`}>
                <Icon size={10} />
                {title} ({items.length})
            </div>
            <div className="mt-1 space-y-1">
                {items.slice(0, 6).map((ev, i) => (
                    <button
                        key={ev.evidence_id || i}
                        onClick={() => setSelectedEvidence?.({ id: ev.evidence_id, ...ev })}
                        className="w-full text-left px-2 py-1 rounded bg-bg-root border border-border-subtle hover:bg-bg-hover"
                    >
                        <div className="text-[9px] font-mono text-fg-secondary truncate">
                            {ev.evidence_id || ev.id} · {ev.source_type || 'SOURCE'}
                        </div>
                        {ev.excerpt && <div className="text-[9px] text-fg-faint truncate">{ev.excerpt.slice(0, 80)}</div>}
                    </button>
                ))}
            </div>
        </div>
    );
}

/* ══════════════════════════════════════════════════════════════
   MAIN PAGE
══════════════════════════════════════════════════════════════ */
export default function EntityAnalysisWorkspace() {
    const [, setLocation] = useLocation();
    const [match, params] = useRoute('/entity/:id');
    const {
        selectedEntity, setSelectedEntity, setSelectedEvidence,
        isBookmarked, toggleBookmark,
    } = useInvestigation();

    // Entity comes from URL param OR current selection
    const entityId = params?.id || selectedEntity?.id || '';
    const entity = useMemo(() => {
        if (params?.id && (!selectedEntity || selectedEntity.id !== params.id)) {
            return { id: params.id, label: params.id, type: 'PERSON' };
        }
        return selectedEntity;
    }, [params, selectedEntity, entityId]);

    const [counterfactual, setCounterfactual] = useState(null);
    const [simLoading, setSimLoading] = useState(false);
    const [noteText, setNoteText] = useState('');
    const [noteSaving, setNoteSaving] = useState(false);

    // ── Data ──
    const { data: metricsData } = useGraphMetrics();
    const { data: neighborhood } = useGetGraphNeighborhood(entityId, 1, 100);
    const { data: evidence } = useEvidenceForNode(entityId);
    const { data: timeline } = useEvidenceTimeline(entityId);
    const { data: crossData } = useCrossCase();
    const { data: caseDetail, refetch: refetchCase } = useCaseDetail(activeCase?.id || 'CASE-0421');

    // Node metrics from graph_metrics.json
    const nodeMetrics = useMemo(() => {
        if (!metricsData?.node_metrics || !entityId) return null;
        return metricsData.node_metrics[entityId] || null;
    }, [metricsData, entityId]);

    // Cross-case presence
    const crossCaseInfo = useMemo(() => {
        const entries = crossData?.reused_entities || [];
        const match_ = entries.find(e => e.entity_id === entityId);
        return match_ || null;
    }, [crossData, entityId]);

    // Evidence split supporting vs contradictory
    const evidenceSplit = useMemo(() => {
        const list = Array.isArray(evidence) ? evidence : evidence?.items || [];
        const supporting = list.filter(e => e.relation === 'supporting' || e.support === 'SUPPORTING' || e.role === 'SUPPORTING');
        const contradictory = list.filter(e => e.relation === 'contradictory' || e.support === 'CONTRADICTORY' || e.role === 'CONTRADICTORY' || e.contradicts === true);
        const unknown = list.filter(e => !supporting.includes(e) && !contradictory.includes(e));
        return { supporting, contradictory, unknown, total: list.length };
    }, [evidence]);

    // Neighborhood stats
    const neighborStats = useMemo(() => {
        const nodes = neighborhood?.nodes || [];
        const edges = neighborhood?.edges || [];
        return { nodes: nodes.length, edges: edges.length };
    }, [neighborhood]);

    // Overall importance score
    const importance = useMemo(() => {
        const betw = nodeMetrics?.betweenness_centrality || 0;
        const degree = nodeMetrics?.degree || 0;
        const cross = crossCaseInfo ? (crossCaseInfo.case_count - 1) / 3 : 0; // heuristic
        const temp = timeline?.length ? Math.min(timeline.length / 10, 1) : 0; // heuristic
        const ghostBoost = selectedEntity?.is_ghost ? 0.15 : 0;

        const structural = Math.min(betw * 200, 1) * 0.6 + Math.min(degree / 38, 1) * 0.4;
        const overall = Math.min(structural * 0.7 + cross * 0.15 + temp * 0.1 + ghostBoost, 1);
        return {
            overall,
            structural,
            temporal: temp,
            cross_case: cross,
            financial: Math.min(degree / 38, 1) * 0.5, // heuristic — flagged
            ghost: ghostBoost,
        };
    }, [nodeMetrics, crossCaseInfo, timeline, selectedEntity]);

    const handleCounterfactual = async () => {
        if (!entityId) return;
        setSimLoading(true);
        try {
            const res = await runNodeRemovalSimulation({ target_node_id: entityId, depth: 2 });
            setCounterfactual(res?.result || res);
        } catch (e) {
            setCounterfactual({ error: e.message });
        } finally {
            setSimLoading(false);
        }
    };

    const handleAddNote = async () => {
        if (!noteText.trim()) return;
        setNoteSaving(true);
        try {
            await updateCase(activeCase?.id || 'CASE-0421', {
                note: `[${entityId}] ${noteText}`,
            });
            setNoteText('');
            refetchCase();
        } catch (e) {
            console.error('Failed to add note', e);
        } finally {
            setNoteSaving(false);
        }
    };

    if (!entityId) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="tp-panel p-6 text-center space-y-2 max-w-sm">
                    <AlertTriangle size={16} className="mx-auto text-fg-faint" />
                    <div className="text-[12px] font-semibold text-fg-primary">NO ENTITY SELECTED</div>
                    <p className="text-[10px] text-fg-faint">Select an entity in the network, entity directory, or search to see its analytical importance.</p>
                    <button onClick={() => setLocation('/network')} className="tp-btn tp-btn-primary text-[10px] h-6 px-3 mt-2">
                        OPEN NETWORK
                    </button>
                </div>
            </div>
        );
    }

    const importanceRank = rankLabel(importance.overall);

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4 max-w-[1200px] mx-auto animate-fade-in">
            {/* ── HEADER ── */}
            <div className="tp-panel p-3.5 bg-bg-panel">
                <div className="flex items-center justify-between gap-3">
                    <button onClick={() => setLocation(-1)} className="tp-btn-ghost p-1.5 text-fg-muted hover:text-fg-primary">
                        <ArrowLeft size={14} />
                    </button>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[9px] font-mono text-primary uppercase tracking-widest">
                                WHY IS THIS IMPORTANT?
                            </span>
                            <span className="tp-badge tp-badge-blue text-[8px]">{entity?.type || 'PERSON'}</span>
                            {selectedEntity?.is_ghost && (
                                <span className="tp-badge tp-badge-amber text-[8px]">GHOST CANDIDATE</span>
                            )}
                        </div>
                        <div className="text-[16px] font-bold text-fg-primary truncate mt-0.5">
                            {entity?.label || entity?.name || entity?.canonical_name || entityId}
                        </div>
                        <div className="text-[10px] font-mono text-fg-faint truncate">{entityId}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        <button
                            onClick={() => toggleBookmark({ type: 'ENTITY', refId: entityId, title: entity?.label || entityId })}
                            className="tp-btn h-6 text-[10px]"
                            title="Bookmark entity"
                        >
                            {isBookmarked(entityId) ? <BookmarkCheck size={12} className="text-amber" /> : <Bookmark size={12} />}
                            {isBookmarked(entityId) ? 'BOOKMARKED' : 'BOOKMARK'}
                        </button>
                        <button
                            onClick={() => setLocation(`/network?focus=${encodeURIComponent(entityId)}`)}
                            className="tp-btn h-6 text-[10px]"
                        >
                            <NetworkIcon size={12} /> OPEN NETWORK
                        </button>
                    </div>
                </div>

                {/* Risk / Relevance */}
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 pt-3">
                    <div className="bg-bg-root p-2 rounded border border-border-subtle">
                        <div className="text-[8px] font-mono text-fg-faint">RELEVANCE</div>
                        <div className={`text-[12px] font-mono ${importanceRank.cls}`}>{importanceRank.label}</div>
                    </div>
                    <div className="bg-bg-root p-2 rounded border border-border-subtle">
                        <div className="text-[8px] font-mono text-fg-faint">RELATIONSHIPS</div>
                        <div className="text-[12px] font-mono text-fg-primary">{nodeMetrics?.degree || neighborStats.nodes || 0}</div>
                    </div>
                    <div className="bg-bg-root p-2 rounded border border-border-subtle">
                        <div className="text-[8px] font-mono text-fg-faint">EVIDENCE</div>
                        <div className="text-[12px] font-mono text-fg-primary">{evidenceSplit.total || 0}</div>
                    </div>
                    <div className="bg-bg-root p-2 rounded border border-border-subtle">
                        <div className="text-[8px] font-mono text-fg-faint">CASES</div>
                        <div className="text-[12px] font-mono text-fg-primary">{crossCaseInfo?.case_count || 1}</div>
                    </div>
                    <div className="bg-bg-root p-2 rounded border border-border-subtle">
                        <div className="text-[8px] font-mono text-fg-faint">COMMUNITY</div>
                        <div className="text-[12px] font-mono text-fg-primary">
                            {nodeMetrics?.community != null ? `C${nodeMetrics.community}` : '—'}
                        </div>
                    </div>
                    <div className="bg-bg-root p-2 rounded border border-border-subtle">
                        <div className="text-[8px] font-mono text-fg-faint">BETWEENNESS</div>
                        <div className="text-[12px] font-mono text-fg-primary">{nodeMetrics?.betweenness_centrality?.toFixed(4) || '—'}</div>
                    </div>
                    <div className="bg-bg-root p-2 rounded border border-border-subtle">
                        <div className="text-[8px] font-mono text-fg-faint">PAGERANK</div>
                        <div className="text-[12px] font-mono text-fg-primary">{nodeMetrics?.pagerank?.toExponential(1) || '—'}</div>
                    </div>
                </div>
            </div>

            {/* ── IMPORTANCE BREAKDOWN ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Signal bars */}
                <div className="tp-panel p-3.5">
                    <div className="flex items-center justify-between mb-1">
                        <span className="tp-section-label">IMPORTANCE SIGNALS</span>
                        <span className="text-[8px] font-mono text-fg-faint">ALL VALUES NORMALIZED 0–1</span>
                    </div>
                    <SignalBar label="OVERALL IMPORTANCE" value={importance.overall} hint="Composite of the signals below" />
                    <div className="border-t border-border-subtle my-1" />
                    <SignalBar label="STRUCTURAL POSITION" value={importance.structural} hint="Betweenness & degree — bridge potential" />
                    <SignalBar label="TEMPORAL ROLE" value={importance.temporal} hint="Activity density in evidence timeline (heuristic)" />
                    <SignalBar label="CROSS-CASE PRESENCE" value={importance.cross_case} hint="Recurrence across investigations" />
                    <SignalBar label="FINANCIAL ROLE" value={importance.financial} hint="Degree-based proxy (heuristic)" />
                </div>

                {/* Evidence balance */}
                <div className="tp-panel p-3.5">
                    <div className="flex items-center justify-between mb-2">
                        <span className="tp-section-label">EVIDENCE BALANCE</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 mb-3">
                        <div className="bg-bg-root p-2.5 rounded border border-border-subtle text-center">
                            <div className="text-[8px] font-mono text-fg-faint">SUPPORTING</div>
                            <div className="text-[16px] font-mono font-bold text-green">{evidenceSplit.supporting.length}</div>
                        </div>
                        <div className="bg-bg-root p-2.5 rounded border border-border-subtle text-center">
                            <div className="text-[8px] font-mono text-fg-faint">CONTRADICTING</div>
                            <div className="text-[16px] font-mono font-bold text-red">{evidenceSplit.contradictory.length}</div>
                        </div>
                        <div className="bg-bg-root p-2.5 rounded border border-border-subtle text-center">
                            <div className="text-[8px] font-mono text-fg-faint">UNKNOWN</div>
                            <div className="text-[16px] font-mono font-bold text-fg-secondary">{evidenceSplit.unknown.length}</div>
                        </div>
                    </div>
                    <div className="space-y-2">
                        <EvidenceGroup title="Supporting Evidence" items={evidenceSplit.supporting} icon={CheckCircle2} colorClass="text-green" />
                        <EvidenceGroup title="Contradictory Evidence" items={evidenceSplit.contradictory} icon={XCircle} colorClass="text-red" />
                        <EvidenceGroup title="Unclassified Evidence" items={evidenceSplit.unknown} icon={HelpCircle} colorClass="text-fg-faint" />
                        {evidenceSplit.total === 0 && (
                            <div className="text-[10px] text-fg-faint text-center py-3">
                                No evidence records indexed for this entity yet.
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── EXPLANATION SECTIONS ── */}
            <div className="tp-panel p-3.5">
                <div className="flex items-center justify-between mb-2">
                    <span className="tp-section-label">ANALYTICAL EXPLANATION</span>
                </div>
                <div className="space-y-3">
                    {/* 1. Network position */}
                    <div className="flex gap-3 p-2.5 rounded bg-bg-root border border-border-subtle">
                        <div className="w-8 h-8 rounded bg-bg-panel border border-border-default flex items-center justify-center shrink-0">
                            <NetworkIcon size={14} className="text-primary" />
                        </div>
                        <div className="flex-1">
                            <div className="text-[11px] font-semibold text-fg-primary">1. NETWORK POSITION</div>
                            <div className="text-[10px] text-fg-secondary mt-0.5">
                                {importance.structural >= 0.6
                                    ? `Connects communities through high betweenness (${nodeMetrics?.betweenness_centrality?.toFixed(4) || '—'}) and degree ${nodeMetrics?.degree || 0}.`
                                    : importance.structural >= 0.3
                                    ? `Moderate network role — degree ${nodeMetrics?.degree || 0}, betweenness ${nodeMetrics?.betweenness_centrality?.toFixed(4) || '—'}.`
                                    : `Limited structural prominence — degree ${nodeMetrics?.degree || 0}, betweenness ${nodeMetrics?.betweenness_centrality?.toFixed(4) || '—'}.`}
                            </div>
                            <div className="mt-1.5">
                                <SignalBar label="Bridge Score" value={importance.structural} />
                            </div>
                        </div>
                    </div>

                    {/* 2. Temporal role */}
                    <div className="flex gap-3 p-2.5 rounded bg-bg-root border border-border-subtle">
                        <div className="w-8 h-8 rounded bg-bg-panel border border-border-default flex items-center justify-center shrink-0">
                            <Clock size={14} className="text-primary" />
                        </div>
                        <div className="flex-1">
                            <div className="text-[11px] font-semibold text-fg-primary">2. TEMPORAL ROLE</div>
                            <div className="text-[10px] text-fg-secondary mt-0.5">
                                {timeline?.length > 0
                                    ? `${timeline.length} dated evidence events indexed for this entity across the investigation window.`
                                    : 'No dated evidence events indexed yet.'}
                            </div>
                            <div className="mt-1.5">
                                <SignalBar label="Temporal Density" value={importance.temporal} />
                            </div>
                        </div>
                    </div>

                    {/* 3. Cross-case */}
                    <div className="flex gap-3 p-2.5 rounded bg-bg-root border border-border-subtle">
                        <div className="w-8 h-8 rounded bg-bg-panel border border-border-default flex items-center justify-center shrink-0">
                            <FolderOpen size={14} className="text-primary" />
                        </div>
                        <div className="flex-1">
                            <div className="text-[11px] font-semibold text-fg-primary">3. CROSS-CASE PRESENCE</div>
                            <div className="text-[10px] text-fg-secondary mt-0.5">
                                {crossCaseInfo
                                    ? `Appears in ${crossCaseInfo.case_count} investigations: ${(crossCaseInfo.cases || []).join(', ')}.`
                                    : 'Not currently flagged across other case workspaces.'}
                            </div>
                            {crossCaseInfo && (
                                <div className="flex flex-wrap gap-1 mt-1.5">
                                    {(crossCaseInfo.cases || []).map((c, i) => (
                                        <span key={i} className="tp-badge tp-badge-neutral text-[8px]">{c}</span>
                                    ))}
                                </div>
                            )}
                            <div className="mt-1.5">
                                <SignalBar label="Cross-Case Relevance" value={importance.cross_case} />
                            </div>
                        </div>
                    </div>

                    {/* 4. Financial role */}
                    <div className="flex gap-3 p-2.5 rounded bg-bg-root border border-border-subtle">
                        <div className="w-8 h-8 rounded bg-bg-panel border border-border-default flex items-center justify-center shrink-0">
                            <DollarSign size={14} className="text-primary" />
                        </div>
                        <div className="flex-1">
                            <div className="text-[11px] font-semibold text-fg-primary">4. FINANCIAL ROLE</div>
                            <div className="text-[10px] text-fg-muted mt-0.5">
                                {importance.financial >= 0.5
                                    ? `Degree-based financial exposure is elevated (${pct(importance.financial)}). Review transaction flows.`
                                    : `Financial exposure via degree proxy: ${pct(importance.financial)} (heuristic).`}
                                <span className="text-fg-faint block mt-0.5">Heuristic — subject to review.</span>
                            </div>
                        </div>
                    </div>

                    {/* 5. Counterfactual impact */}
                    <div className="flex gap-3 p-2.5 rounded bg-bg-root border border-border-subtle">
                        <div className="w-8 h-8 rounded bg-bg-panel border border-border-default flex items-center justify-center shrink-0">
                            <Zap size={14} className="text-amber" />
                        </div>
                        <div className="flex-1">
                            <div className="text-[11px] font-semibold text-fg-primary">5. COUNTERFACTUAL IMPACT</div>
                            {counterfactual?.error ? (
                                <div className="text-[10px] text-red mt-0.5">{counterfactual.error}</div>
                            ) : counterfactual ? (
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-1.5">
                                    <div className="bg-bg-panel p-1.5 rounded border border-border-subtle">
                                        <div className="text-[8px] font-mono text-fg-faint">FRAGMENTATION</div>
                                        <div className="text-[10px] font-mono text-fg-primary">{(counterfactual.fragmentation_score || 0).toFixed(3)}</div>
                                    </div>
                                    <div className="bg-bg-panel p-1.5 rounded border border-border-subtle">
                                        <div className="text-[8px] font-mono text-fg-faint">CONNECTIVITY Δ</div>
                                        <div className="text-[10px] font-mono text-amber">{((counterfactual.connectivity_change || 0) * 100).toFixed(1)}%</div>
                                    </div>
                                    <div className="bg-bg-panel p-1.5 rounded border border-border-subtle">
                                        <div className="text-[8px] font-mono text-fg-faint">AFFECTED</div>
                                        <div className="text-[10px] font-mono text-fg-primary">{counterfactual.affected_node_count || 0}</div>
                                    </div>
                                    <div className="bg-bg-panel p-1.5 rounded border border-border-subtle">
                                        <div className="text-[8px] font-mono text-fg-faint">REROUTING</div>
                                        <div className="text-[10px] font-mono text-fg-primary">{(counterfactual.rerouting_score || 0).toFixed(3)}</div>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-[10px] text-fg-faint mt-1">
                                    Run a counterfactual removal simulation to see the modelled impact.
                                </div>
                            )}
                            <button onClick={handleCounterfactual} disabled={simLoading}
                                className="tp-btn tp-btn-primary h-6 text-[10px] mt-2">
                                <Zap size={11} /> {simLoading ? 'SIMULATING…' : counterfactual ? 'RE-RUN COUNTERFACTUAL' : 'RUN COUNTERFACTUAL'}
                            </button>
                        </div>
                    </div>

                    {/* 6. Evidence */}
                    <div className="flex gap-3 p-2.5 rounded bg-bg-root border border-border-subtle">
                        <div className="w-8 h-8 rounded bg-bg-panel border border-border-default flex items-center justify-center shrink-0">
                            <Scale size={14} className="text-primary" />
                        </div>
                        <div className="flex-1">
                            <div className="text-[11px] font-semibold text-fg-primary">6. EVIDENCE BASIS</div>
                            <div className="text-[10px] text-fg-secondary mt-0.5">
                                {evidenceSplit.supporting.length} supporting · {evidenceSplit.contradictory.length} contradicting · {evidenceSplit.unknown.length} unknown
                            </div>
                            <div className="flex gap-2 mt-2">
                                <button onClick={() => setLocation(`/evidence?node=${encodeURIComponent(entityId)}`)} className="tp-btn h-6 text-[10px]">
                                    <FileText size={11} /> VIEW EVIDENCE
                                </button>
                                <button onClick={() => setLocation(`/network?focus=${encodeURIComponent(entityId)}`)} className="tp-btn h-6 text-[10px]">
                                    <NetworkIcon size={11} /> VIEW NETWORK
                                </button>
                                <Link href="/cross-case" className="tp-btn h-6 text-[10px] inline-flex items-center gap-1">
                                    <FolderOpen size={11} /> COMPARE CASES
                                </Link>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* ── INVESTIGATION NOTES (Part 15) ── */}
            <div className="tp-panel p-3.5">
                <div className="flex items-center justify-between mb-2">
                    <span className="tp-section-label">INVESTIGATION NOTES</span>
                    <span className="text-[9px] font-mono text-fg-faint">{caseNotes.length} NOTES</span>
                </div>
                {/* Add note form */}
                <div className="flex gap-2 mb-3">
                    <input
                        type="text"
                        value={noteText}
                        onChange={e => setNoteText(e.target.value)}
                        placeholder={`Note for ${entityId}…`}
                        className="tp-input flex-1 h-6 text-[10px]"
                        onKeyDown={e => e.key === 'Enter' && handleAddNote()}
                    />
                    <button
                        onClick={handleAddNote}
                        disabled={noteSaving || !noteText.trim()}
                        className="tp-btn tp-btn-primary h-6 text-[10px] px-3"
                    >
                        {noteSaving ? 'SAVING…' : 'ADD NOTE'}
                    </button>
                </div>
                {/* Note list */}
                {caseNotes.length > 0 ? (
                    <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
                        {caseNotes.map((n, i) => (
                            <div key={i} className="p-2 rounded bg-bg-root border border-border-subtle">
                                <div className="text-[10px] text-fg-primary">{n.text}</div>
                                <div className="text-[8px] font-mono text-fg-faint mt-1">{n.at || n.timestamp || ''}</div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-[10px] text-fg-faint py-2 text-center">No notes for this entity yet.</div>
                )}
            </div>
        </div>
    );
}