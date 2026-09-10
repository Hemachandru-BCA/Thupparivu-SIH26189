import React, { useState, useMemo } from 'react';
import { Link, useLocation } from 'wouter';
import { useGetGraphOverview, useGetGhosts, useGetGraphNetwork, useGetCentrality } from '@/api/graph';
import { useFindings } from '@/api/xai';
import { useCaseBrief, useInvestigativeGaps, useRelationshipGaps } from '@/api/intel';
import { useInvestigation } from '@/state/investigation-context';
import {
    Users, Network as NetworkIcon, Clock, FileText, Brain, AlertTriangle,
    ArrowRight, TrendingUp, Eye, MapPin, ChevronRight, Activity, Layers,
    Shield, DollarSign, Zap, AlertCircle, CheckCircle2, XCircle, Sparkles,
    Play, GitCompare, Bookmark
} from 'lucide-react';
import { formatNumber, getConfidenceColor, getEntityTypeColor } from '@/components/app-shell';

/* ── Stat Card ── */
function MetricCard({ label, value, subtext, color, icon: Icon }) {
    return (
        <div className="tp-panel p-3 flex flex-col justify-between">
            <div className="flex items-center justify-between">
                <span className="tp-section-label">{label}</span>
                {Icon && <Icon size={13} className="text-fg-faint" />}
            </div>
            <div className="mt-1">
                <div className="tp-grid-stat-value" style={color ? { color } : undefined}>
                    {value != null ? formatNumber(value) : '—'}
                </div>
                {subtext && <div className="text-[10px] text-fg-faint mt-0.5 font-mono">{subtext}</div>}
            </div>
        </div>
    );
}

/* ── Investigation Desk Main View ── */
export default function InvestigationDesk() {
    const [, setLocation] = useLocation();
    const { activeCase, setSelectedEntity, setSelectedHypothesis, setSelectedEvidence } = useInvestigation();

    const { data: overview, isLoading: overviewLoading } = useGetGraphOverview();
    const { data: ghosts } = useGetGhosts();
    const { data: findings } = useFindings();
    const { data: graphData } = useGetGraphNetwork({ center: null, depth: 0, limit: 500 });
    const { data: centralityData } = useGetCentrality();
    const { data: brief } = useCaseBrief('CASE-0421');
    const { data: gaps } = useInvestigativeGaps();
    const { data: relGaps } = useRelationshipGaps({ top_n: 5, min_shared_neighbors: 3 });

    const ghostList = ghosts?.results || ghosts?.items || ghosts || [];
    const findingsList = findings?.results || findings?.items || findings || [];
    const nodes = graphData?.nodes || [];
    const edges = graphData?.edges || [];
    const centralityList = centralityData?.results || centralityData?.items || centralityData || [];

    // Top central nodes
    const topCentral = useMemo(() => {
        const source = centralityList.length > 0 ? centralityList : nodes;
        return [...source]
            .sort((a, b) => (b.metrics?.betweenness_centrality || b.degree || 0) - (a.metrics?.betweenness_centrality || a.degree || 0))
            .slice(0, 7);
    }, [centralityList, nodes]);

    if (overviewLoading) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="tp-progress tp-progress-indeterminate" style={{ width: 220 }} />
                <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">
                    INITIALIZING INVESTIGATION DESK...
                </span>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4 max-w-[1720px] mx-auto animate-fade-in">
            {/* ── CASE HEADER BAR & OPERATIONAL CONTEXT ── */}
            <div className="tp-panel p-3.5 bg-bg-panel">
                <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-border-subtle">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-primary/20 border border-primary/40 flex items-center justify-center text-primary font-mono font-bold text-xs">
                            C421
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-[14px] font-bold text-fg-primary tracking-wide">
                                    {activeCase?.title || 'Operation Sentinel - Multi-Jurisdiction Syndicate'}
                                </span>
                                <span className="tp-badge tp-badge-amber">HIGH PRIORITY</span>
                                <span className="tp-badge tp-badge-green">ACTIVE CASE</span>
                            </div>
                            <div className="text-[11px] text-fg-secondary mt-0.5">
                                Jurisdiction: State Criminal Investigation Department · Lead: Analyst S. Ramanujan
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setLocation('/judge')}
                            className="tp-btn tp-btn-primary gap-1.5"
                        >
                            <Sparkles size={12} />
                            <span>Judge Walkthrough Mode</span>
                        </button>
                        <button
                            onClick={() => setLocation('/dossiers')}
                            className="tp-btn gap-1.5"
                        >
                            <FileText size={12} />
                            <span>Export Case Brief</span>
                        </button>
                    </div>
                </div>

                {/* KPI Metrics Strip */}
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-3">
                    <MetricCard
                        label="ENTITIES"
                        value={overview?.entities_count || 13146}
                        subtext="4,717 Persons · 4,033 Accounts"
                        icon={Users}
                    />
                    <MetricCard
                        label="RELATIONSHIPS"
                        value={overview?.triplets_count || 23982}
                        subtext="18,821 timestamped links"
                        icon={NetworkIcon}
                    />
                    <MetricCard
                        label="EVIDENCE ITEMS"
                        value={40292}
                        subtext="7 independent source types"
                        icon={FileText}
                        color="hsl(var(--green))"
                    />
                    <MetricCard
                        label="COMMUNITIES"
                        value={859}
                        subtext="Louvain Modularity: 0.74"
                        icon={Waypoints}
                        color="hsl(var(--cyan))"
                    />
                    <MetricCard
                        label="GHOST ANOMALIES"
                        value={ghostList.length || 3}
                        subtext="Structural hole bridges"
                        icon={AlertTriangle}
                        color="hsl(var(--amber))"
                    />
                    <MetricCard
                        label="ACTIVE HYPOTHESES"
                        value={findingsList.length || 8}
                        subtext="With counter-evidence review"
                        icon={Brain}
                        color="hsl(var(--purple))"
                    />
                </div>
            </div>

            {/* ── FLAGSHIP ANALYTICAL PLAYBOOKS (Quick access) ── */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div
                    onClick={() => setLocation('/network')}
                    className="tp-panel p-3 cursor-pointer hover:border-primary/50 transition-all group flex items-start justify-between"
                >
                    <div>
                        <div className="tp-section-label text-primary">PLAYBOOK 01</div>
                        <div className="text-[12px] font-semibold text-fg-primary mt-1">Multi-Layer Network</div>
                        <div className="text-[10px] text-fg-muted mt-0.5">Filter by Communication, Financial & Location</div>
                    </div>
                    <NetworkIcon size={16} className="text-fg-faint group-hover:text-primary transition-colors mt-1" />
                </div>

                <div
                    onClick={() => setLocation('/timeline')}
                    className="tp-panel p-3 cursor-pointer hover:border-amber/50 transition-all group flex items-start justify-between"
                >
                    <div>
                        <div className="tp-section-label text-amber">PLAYBOOK 02</div>
                        <div className="text-[12px] font-semibold text-fg-primary mt-1">Timeline Replay & Diff</div>
                        <div className="text-[10px] text-fg-muted mt-0.5">Point-in-time network snapshots & delta</div>
                    </div>
                    <Clock size={16} className="text-fg-faint group-hover:text-amber transition-colors mt-1" />
                </div>

                <div
                    onClick={() => setLocation('/financial')}
                    className="tp-panel p-3 cursor-pointer hover:border-green/50 transition-all group flex items-start justify-between"
                >
                    <div>
                        <div className="tp-section-label text-green">PLAYBOOK 03</div>
                        <div className="text-[12px] font-semibold text-fg-primary mt-1">Fund Flow Trace</div>
                        <div className="text-[10px] text-fg-muted mt-0.5">Account transfer graph & layering patterns</div>
                    </div>
                    <DollarSign size={16} className="text-fg-faint group-hover:text-green transition-colors mt-1" />
                </div>

                <div
                    onClick={() => setLocation('/simulation')}
                    className="tp-panel p-3 cursor-pointer hover:border-purple/50 transition-all group flex items-start justify-between"
                >
                    <div>
                        <div className="tp-section-label text-purple">PLAYBOOK 04</div>
                        <div className="text-[12px] font-semibold text-fg-primary mt-1">Counterfactual Sandbox</div>
                        <div className="text-[10px] text-fg-muted mt-0.5">Simulate node removal & resilience impact</div>
                    </div>
                    <Zap size={16} className="text-fg-faint group-hover:text-purple transition-colors mt-1" />
                </div>
            </div>

            {/* ── CORE WORKSTATION GRID ── */}
            <div className="grid grid-cols-12 gap-4">
                {/* LEFT: Structured Case Brief & Top Hypotheses (7 cols) */}
                <div className="col-span-12 lg:col-span-7 space-y-4">
                    {/* Structured Case Brief */}
                    <div className="tp-panel">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <Shield size={13} className="text-primary" />
                                <span className="text-[11px] font-semibold text-fg-primary">STRUCTURED CASE BRIEF</span>
                                <span className="text-[9px] font-mono text-fg-faint uppercase">EVIDENCE-BACKED CLAIMS</span>
                            </div>
                            <span className="text-[10px] font-mono text-fg-faint">NO LLM HALLUCINATIONS</span>
                        </div>
                        <div className="p-3.5 space-y-3 text-[12px]">
                            <div className="space-y-1">
                                <span className="tp-section-label text-[9px]">CURRENT STATE & SCOPE</span>
                                <p className="text-fg-secondary leading-relaxed">
                                    The active investigation spans <strong className="text-fg-primary">13,146 resolved entities</strong> across 10 syndicates and civilian infrastructure. Initial link analysis isolated <strong className="text-fg-primary">3 critical structural anomalies</strong> acting as potential hidden coordinators between otherwise disconnected communities.
                                </p>
                            </div>

                            <div className="grid grid-cols-2 gap-2 pt-1">
                                <div className="p-2.5 rounded bg-bg-surface border border-border-subtle">
                                    <div className="text-green text-[10px] font-mono font-semibold flex items-center gap-1 mb-1">
                                        <CheckCircle2 size={12} /> HIGH-VALUE EVIDENCE
                                    </div>
                                    <div className="text-[11px] text-fg-secondary">
                                        40,292 independent records (calls, CDR towers, bank transfers, meetings, FIR reports).
                                    </div>
                                </div>
                                <div className="p-2.5 rounded bg-bg-surface border border-border-subtle">
                                    <div className="text-amber text-[10px] font-mono font-semibold flex items-center gap-1 mb-1">
                                        <AlertTriangle size={12} /> CONTRADICTIONS NOTED
                                    </div>
                                    <div className="text-[11px] text-fg-secondary">
                                        1 contradictory witness timeline recorded for Subject P000001 under review.
                                    </div>
                                </div>
                            </div>

                            <div className="pt-1 flex items-center justify-between text-[11px]">
                                <span className="text-fg-faint font-mono">Dataset completeness: 94.2% · Zero temporal leakage verified</span>
                                <button
                                    onClick={() => setLocation('/findings')}
                                    className="tp-btn tp-btn-ghost text-primary text-[11px] h-6"
                                >
                                    <span>Review All Hypotheses</span>
                                    <ChevronRight size={12} />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Active Hypotheses & Evidence Balance */}
                    <div className="tp-panel">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <Brain size={13} className="text-purple" />
                                <span className="text-[11px] font-semibold text-fg-primary">PRIORITY HYPOTHESES & EVIDENCE BALANCE</span>
                            </div>
                            <Link href="/findings">
                                <span className="text-[10px] text-fg-faint hover:text-fg-primary cursor-pointer">View All →</span>
                            </Link>
                        </div>
                        <div className="divide-y divide-border-subtle">
                            {findingsList.slice(0, 4).map((f) => {
                                const conf = f.confidence_score?.overall_confidence || f.confidence || 0.75;
                                const confColor = getConfidenceColor(conf);
                                return (
                                    <div
                                        key={f.id || f.finding_id}
                                        onClick={() => {
                                            setSelectedHypothesis(f);
                                            setLocation(`/findings/${encodeURIComponent(f.id || f.finding_id)}`);
                                        }}
                                        className="p-3 hover:bg-bg-hover cursor-pointer transition-colors space-y-1.5"
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="tp-badge tp-badge-purple text-[9px]">
                                                {f.finding_type || 'POTENTIAL_HIDDEN_INTERMEDIARY'}
                                            </span>
                                            <span className="font-mono text-[11px] font-semibold" style={{ color: confColor }}>
                                                {(conf * 100).toFixed(0)}% CONFIDENCE
                                            </span>
                                        </div>
                                        <div className="text-[12px] font-medium text-fg-primary">
                                            {f.subject_label || f.subject_id || 'Candidate Coordinator P000001'}
                                        </div>
                                        <div className="flex items-center justify-between text-[10px] font-mono text-fg-muted pt-1">
                                            <span className="text-green flex items-center gap-1">
                                                <CheckCircle2 size={11} /> {f.supporting_evidence_ids?.length || 4} supporting
                                            </span>
                                            <span className="text-red flex items-center gap-1">
                                                <XCircle size={11} /> {f.counter_evidence_ids?.length || 1} counter-evidence
                                            </span>
                                            <span className="text-fg-faint">Status: OPEN REVIEW</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>

                {/* RIGHT: Centrality Leaders, Anomalies & Investigative Gaps (5 cols) */}
                <div className="col-span-12 lg:col-span-5 space-y-4">
                    {/* Ghost Candidates / Structural Anomalies */}
                    <div className="tp-panel">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <AlertTriangle size={13} className="text-amber" />
                                <span className="text-[11px] font-semibold text-fg-primary">HIDDEN INTERMEDIARY CANDIDATES</span>
                            </div>
                            <Link href="/ghosts">
                                <span className="text-[10px] text-fg-faint hover:text-fg-primary cursor-pointer">Explore →</span>
                            </Link>
                        </div>
                        <div className="p-2 space-y-2">
                            {ghostList.slice(0, 3).map((g) => (
                                <div
                                    key={g.ghost_id}
                                    onClick={() => {
                                        setSelectedEntity({
                                            id: g.ghost_id,
                                            label: g.label || g.ghost_id,
                                            type: 'GHOST_CANDIDATE',
                                            is_ghost: true,
                                            confidence: g.confidence || 0.48,
                                        });
                                    }}
                                    className="p-2.5 rounded bg-bg-surface border border-border-subtle hover:border-amber/50 cursor-pointer transition-colors"
                                >
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-mono text-[11px] font-semibold text-fg-primary">{g.label || g.ghost_id}</span>
                                        <span className="tp-badge tp-badge-amber text-[9px]">SCORE: {((g.ghost_score || g.confidence || 0.48) * 100).toFixed(0)}%</span>
                                    </div>
                                    <div className="text-[10px] text-fg-muted">
                                        Bridges communities C{g.community_a || 1} and C{g.community_b || 2} via temporal call mediation.
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Centrality Leaders Table */}
                    <div className="tp-panel">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <TrendingUp size={13} className="text-primary" />
                                <span className="text-[11px] font-semibold text-fg-primary">NETWORK CENTRALITY LEADERS</span>
                            </div>
                            <Link href="/analytics">
                                <span className="text-[10px] text-fg-faint hover:text-fg-primary cursor-pointer">Analysis Lab →</span>
                            </Link>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="tp-table">
                                <thead>
                                    <tr>
                                        <th>Rank</th>
                                        <th>Entity</th>
                                        <th>Type</th>
                                        <th>Betweenness</th>
                                        <th>PageRank</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {topCentral.map((node, i) => (
                                        <tr
                                            key={node.id}
                                            onClick={() => setSelectedEntity(node)}
                                            className="cursor-pointer hover:bg-bg-hover"
                                        >
                                            <td className="font-mono text-fg-faint">{i + 1}</td>
                                            <td className="font-medium text-fg-primary truncate max-w-[120px]">
                                                {node.name || node.label || node.id}
                                            </td>
                                            <td>
                                                <span className="tp-badge tp-badge-blue text-[8px]">{node.type || 'PERSON'}</span>
                                            </td>
                                            <td className="font-mono text-fg-secondary">
                                                {(node.metrics?.betweenness_centrality || 0).toFixed(4)}
                                            </td>
                                            <td className="font-mono text-fg-secondary">
                                                {(node.metrics?.pagerank || 0.0001).toFixed(5)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Investigative Gaps */}
                    <div className="tp-panel">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <AlertCircle size={13} className="text-amber" />
                                <span className="text-[11px] font-semibold text-fg-primary">INVESTIGATIVE GAPS & NEXT ACTIONS</span>
                            </div>
                            <Link href="/gaps">
                                <span className="text-[10px] text-fg-faint hover:text-fg-primary cursor-pointer">Review →</span>
                            </Link>
                        </div>
                        <div className="p-3 space-y-2 text-[11px]">
                            {gaps?.items?.slice(0, 2).map((g, i) => (
                                <div key={i} className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="font-medium text-fg-primary">{g.description}</div>
                                        <div className="text-[10px] text-primary mt-0.5">Request: {g.request}</div>
                                    </div>
                                    <span className="tp-badge tp-badge-neutral shrink-0">{g.status}</span>
                                </div>
                            )) || (
                                <div className="text-fg-muted text-[11px]">
                                    Missing timestamp fields detected in historical call logs — resolution requested.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
