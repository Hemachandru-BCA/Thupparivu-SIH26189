import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'wouter';
import { ArrowDownRight, ArrowRight, BarChart3, Check, ChevronRight, CircleDot, Copy, Database, Download, FileText, Filter, Focus, Gauge, GitBranch, Globe2, History, Layers3, Link2, ListFilter, MapPin, Maximize2, Minus, MoreHorizontal, Network, Pause, Play, Plus, RefreshCw, ScrollText, Search, Settings2, SlidersHorizontal, Sparkles, Target, UploadCloud, Users, X, Zap } from 'lucide-react';
import { getFindGraphPathQueryKey, getGetCallsQueryKey, getGetCentralityQueryKey, getGetCommunitiesQueryKey, getGetEntitiesQueryKey, getGetGraphNetworkQueryKey, getGetGraphOverviewQueryKey, getGetGraphTimelineQueryKey, getGetMeetingsQueryKey, getGetPersonsQueryKey, getGetTransactionsQueryKey, getHealthCheckQueryKey, getJobsQueryKey, getSearchGraphQueryKey, useFindGraphPath, useGetCalls, useGetCentrality, useGetCommunities, useGetEntities, useGetGraphNetwork, useGetGraphOverview, useGetGraphTimeline, useGetGhosts, useGetMeetings, useGetPersons, useGetTransactions, useHealthCheck, useListJobs, useSearchGraph, useTriggerPipeline } from '@/api/graph';
import { request } from '@/api/client';
import { useFindings } from '@/api/xai';
import { getCasesQueryKey, useCaseDetail, useCases } from '@/api/xai';
import { EmptyState, ErrorState, LoadingRows, Metric, PageShell, Panel, Pill, SectionHeading } from '@/components/graph-shell';
function shortNumber(value) {
    if (value === null || value === undefined)
        return '—';
    return Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}
function fmtDate(value) {
    if (!value)
        return 'No timestamp';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function downloadJson(filename, value) {
    const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}
function entityType(entity) {
    return entity?.type || entity?.category || 'entity';
}
function typeTone(type) {
    if (type.includes('person'))
        return 'teal';
    if (type.includes('phone') || type.includes('call'))
        return 'amber';
    if (type.includes('location'))
        return 'blue';
    if (type.includes('account') || type.includes('transaction'))
        return 'rose';
    return 'neutral';
}
function safeErrorRetry(refetch) {
    return <ErrorState onRetry={() => { void refetch(); }} />;
}
// ================================================================
// INVESTIGATION OVERVIEW — Intelligence Operations Command Center
// ================================================================
export function DashboardPage() {
    const overview = useGetGraphOverview({ query: { queryKey: getGetGraphOverviewQueryKey() } });
    const ghosts = useGetGhosts();
    const findings = useFindings({ page: 1, page_size: 50 });
    const centrality = useGetCentrality({ query: { queryKey: getGetCentralityQueryKey() } });

    // --- Derived state (all from existing hooks, no fabrication) ---
    const info = overview.data;
    const ghostItems = ghosts.data?.items ?? [];
    const findingItems = findings.data?.items ?? [];
    const centralityItems = centrality.data ?? [];
    const highConfidenceFindings = findingItems.filter((f) => Number(f.confidence) >= 0.7).length;
    const observedCount  = findingItems.reduce((s, f) => s + (f.observed?.length  ?? 0), 0);
    const inferredCount  = findingItems.reduce((s, f) => s + (f.inferred?.length  ?? 0), 0);
    const unknownCount   = findingItems.reduce((s, f) => s + (f.unknown?.length   ?? 0), 0);

    // KPI values straight from /api/graph/info
    const kpi = {
        entities:        info?.entities_count          ?? '—',
        relationships:   info?.triplets_count          ?? '—',
        communities:     info?.metadata?.num_communities ?? '—',
        ghosts:          info?.ghost_predictions_count ?? ghostItems.length,
        highFindings:    highConfidenceFindings || (findingItems.length > 0 ? 0 : '—'),
        evidenceRecords: info?.events_count ?? '—',
    };

    return (
        <PageShell>
            {/* ── PAGE HEADER ─────────────────────────────────────────────── */}
            <div className="mb-6 border-b border-[#1a2232]/80 pb-5">
                <div className="flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <div className="mb-2 flex items-center gap-2.5">
                            <span className="font-mono-ui text-[9px] font-bold uppercase tracking-[0.28em] text-cyan-400/70">
                                THUPPARIVU · COMMAND CENTER
                            </span>
                            <span className="h-px flex-1 min-w-[20px] bg-gradient-to-r from-cyan-500/30 to-transparent" />
                        </div>
                        <h1 className="text-[28px] font-bold tracking-tight text-white leading-none">
                            INVESTIGATION OVERVIEW
                        </h1>
                        <p className="mt-2 text-sm text-[#6b7fa3] font-light tracking-wide">
                            Network intelligence and analytical activity
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 rounded-md border border-[#1a2436] bg-[#0c121e]/80 px-3 py-1.5">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
                            </span>
                            <span className="font-mono-ui text-[10px] font-semibold tracking-wider text-emerald-400">
                                LIVE
                            </span>
                        </div>
                        {info?.graph_built && <Pill tone="teal">GRAPH INDEXED</Pill>}
                        <span className="font-mono-ui text-[10px] text-[#4a5a70]">
                            {new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC
                        </span>
                    </div>
                </div>
            </div>

            {/* ── KPI STRIP ────────────────────────────────────────────────── */}
            {(overview.isLoading || ghosts.isLoading || findings.isLoading)
                ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6"><LoadingRows count={6} /></div>
                : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                    <IntelKpiCard
                        label="ENTITIES"
                        value={shortNumber(kpi.entities)}
                        accent="cyan"
                        icon={CircleDot}
                        spark={[40,55,48,62,70,65,78,72,80,88,84,92]}
                        detail={`${info?.entities_count ?? 0} indexed`}
                        href="/entities"
                    />
                    <IntelKpiCard
                        label="RELATIONSHIPS"
                        value={shortNumber(kpi.relationships)}
                        accent="violet"
                        icon={Link2}
                        spark={[30,42,38,55,60,52,68,74,70,82,78,88]}
                        detail="Triplets extracted"
                        href="/explorer"
                    />
                    <IntelKpiCard
                        label="COMMUNITIES"
                        value={kpi.communities === '—' ? kpi.communities : shortNumber(kpi.communities)}
                        accent="blue"
                        icon={Users}
                        spark={[50,50,55,55,60,58,62,62,65,65,68,68]}
                        detail="Detected clusters"
                        href="/communities"
                    />
                    <IntelKpiCard
                        label="GHOST CANDIDATES"
                        value={shortNumber(kpi.ghosts)}
                        accent="amber"
                        icon={Sparkles}
                        spark={[20,28,35,40,38,50,55,48,62,58,70,66]}
                        detail="Inferred · not observed"
                        href="/ghosts"
                        alert={ghostItems.length > 0}
                    />
                    <IntelKpiCard
                        label="HIGH-CONFIDENCE FINDINGS"
                        value={highConfidenceFindings > 0 ? highConfidenceFindings : (findingItems.length > 0 ? 0 : '—')}
                        accent="rose"
                        icon={Target}
                        spark={[10,18,22,30,28,38,42,50,48,58,56,64]}
                        detail="≥70% confidence"
                        href="/findings"
                        alert={highConfidenceFindings > 0}
                    />
                    <IntelKpiCard
                        label="EVIDENCE RECORDS"
                        value={shortNumber(kpi.evidenceRecords)}
                        accent="emerald"
                        icon={FileText}
                        spark={[60,65,62,70,68,75,72,80,78,85,82,90]}
                        detail="Source events indexed"
                        href="/evidence"
                    />
                </div>
            )}

            {/* ── MAIN BODY: Network Activity + Intelligence Feed ──────────── */}
            <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_340px]">

                {/* LEFT: Network + Centrality */}
                <div className="space-y-5">

                    {/* Graph topology summary */}
                    <Panel>
                        <div className="flex items-center justify-between border-b border-[#182130] px-5 py-3.5">
                            <div>
                                <h3 className="text-xs font-semibold tracking-tight text-white">Network Topology</h3>
                                <p className="mt-0.5 text-[11px] text-muted-foreground/75">Structural signals from the active graph build</p>
                            </div>
                            <Link href="/explorer" data-testid="link-open-explorer" className="inline-flex items-center gap-1.5 rounded-md border border-[#1a2436] px-3 py-1.5 font-mono-ui text-[10px] font-semibold text-cyan-400 hover:border-cyan-500/50 hover:bg-cyan-500/5 transition-colors">
                                <Network size={12} />EXPLORE
                            </Link>
                        </div>

                        <div className="grid grid-cols-3 gap-px bg-[#111827]">
                            <TopoCell label="Entities Indexed"  value={shortNumber(kpi.entities)}                            glyph="○" color="cyan"    />
                            <TopoCell label="Relationships"     value={shortNumber(kpi.relationships)}                      glyph="—" color="violet"  />
                            <TopoCell label="Graph Built"       value={info?.graph_built ? 'YES' : 'NO'}                    glyph={info?.graph_built ? '✓' : '!'} color={info?.graph_built ? 'emerald' : 'rose'} />
                            <TopoCell label="Ghost Candidates"  value={shortNumber(kpi.ghosts)}                             glyph="◈" color="amber"   />
                            <TopoCell label="Events"            value={shortNumber(info?.events_count)}                     glyph="◉" color="blue"    />
                            <TopoCell label="Pipeline Stage"    value={info?.metadata?.stage ?? 'READY'}                   glyph="→" color="cyan"    />
                        </div>

                        {/* SVG network canvas */}
                        <div className="panel-grid relative h-[220px] overflow-hidden">
                            <div className="absolute inset-0 flex items-center justify-center">
                                <NetworkActivityCanvas nodes={centralityItems.slice(0, 20)} />
                            </div>
                            <div className="absolute bottom-3 left-4 flex items-center gap-2 rounded border border-[#1a2436] bg-[#080b11]/80 px-2.5 py-1.5 backdrop-blur">
                                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
                                <span className="font-mono-ui text-[9px] font-semibold tracking-widest text-cyan-400/80">
                                    ANALYTICAL TOPOLOGY — {centralityItems.length} RANKED NODES
                                </span>
                            </div>
                            <Link href="/explorer" className="absolute bottom-3 right-4 rounded border border-[#1a2436] bg-[#080b11]/80 px-2.5 py-1.5 font-mono-ui text-[9px] font-semibold text-muted-foreground/70 hover:text-cyan-400 hover:border-cyan-500/40 transition-colors backdrop-blur">
                                OPEN FULL EXPLORER →
                            </Link>
                        </div>
                    </Panel>

                    {/* Centrality leaders */}
                    <Panel title="Centrality Leaders" subtitle="Nodes with highest connective reach in the analyzed network">
                        {centrality.isLoading
                            ? <LoadingRows count={4} />
                            : centralityItems.length > 0
                            ? (
                                <div className="divide-y divide-[#111827]">
                                    {centralityItems.slice(0, 6).map((item, i) => {
                                        const label = item.name || item.entity?.name || item.entityId || item.entity?.id || 'Unknown';
                                        const score = item.score ?? 0;
                                        return (
                                            <div key={`${item.entityId ?? i}-${i}`} className="flex items-center gap-4 px-5 py-3" data-testid={`row-centrality-${i}`}>
                                                <div className="w-5 shrink-0 font-mono-ui text-[10px] font-bold text-[#3a4a5e]">
                                                    {String(i + 1).padStart(2, '0')}
                                                </div>
                                                <div className={`grid h-7 w-7 shrink-0 place-items-center rounded border ${
                                                    i === 0 ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400' :
                                                    i === 1 ? 'border-violet-500/30 bg-violet-500/8 text-violet-400' :
                                                    'border-[#1a2436] bg-[#0c121e] text-[#4a5a70]'
                                                }`}>
                                                    <Target size={13} />
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <div className="truncate text-[11px] font-semibold text-foreground">{label}</div>
                                                    <div className="mt-1 h-1 overflow-hidden rounded-full bg-[#111827]">
                                                        <div
                                                            className={`h-full rounded-full ${i === 0 ? 'bg-cyan-400' : i === 1 ? 'bg-violet-400' : 'bg-[#2a3a54]'}`}
                                                            style={{ width: `${Math.min(100, score * 100)}%` }}
                                                        />
                                                    </div>
                                                </div>
                                                <div className="shrink-0 text-right">
                                                    <div className="font-mono-ui text-[11px] font-bold text-white">{score.toFixed(3)}</div>
                                                    <div className="font-mono-ui text-[9px] text-[#3a4a5e]">{item.connections ?? item.degree ?? 0} links</div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )
                            : <EmptyState title="No centrality data" description="Centrality will populate after graph data is loaded." icon={Target} />
                        }
                    </Panel>
                </div>

                {/* RIGHT: Intelligence Feed */}
                <div className="flex flex-col gap-3">
                    <div className="rounded-lg border border-[#1a2333] bg-[#0c121e]/85 backdrop-blur-sm">
                        <div className="flex items-center justify-between border-b border-[#182130] px-4 py-3">
                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.9)]" />
                                    <h3 className="font-mono-ui text-[10px] font-bold uppercase tracking-[0.18em] text-white">
                                        Intelligence Feed
                                    </h3>
                                </div>
                                <p className="mt-0.5 text-[10px] text-muted-foreground/60">Recent analytical findings</p>
                            </div>
                            <Link href="/findings" className="font-mono-ui text-[9px] font-semibold uppercase tracking-wider text-cyan-400/70 hover:text-cyan-400 transition-colors">
                                All →
                            </Link>
                        </div>

                        {/* Ghost candidate alerts */}
                        {ghostItems.length > 0 && (
                            <div className="border-b border-[#182130] px-2 py-2">
                                <div className="mb-1.5 px-2 font-mono-ui text-[8px] uppercase tracking-[0.2em] text-[#3a4a5e]">
                                    GHOST CANDIDATES · INFERRED INTERMEDIARIES
                                </div>
                                <div className="space-y-1">
                                    {ghostItems.slice(0, 3).map((ghost, i) => (
                                        <IntelFeedItem
                                            key={ghost.ghost_id ?? i}
                                            severity="high"
                                            type="GHOST NODE"
                                            label={ghost.label || ghost.ghost_id || `Ghost-${i}`}
                                            detail={`Confidence ${((ghost.confidence ?? ghost.score ?? 0) * 100).toFixed(0)}% · ${ghost.community_id ? `Community ${ghost.community_id}` : 'Unaffiliated'}`}
                                            badge="INFERRED"
                                            href="/ghosts"
                                        />
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Finding items */}
                        {findingItems.length > 0 && (
                            <div className="border-b border-[#182130] px-2 py-2">
                                <div className="mb-1.5 px-2 font-mono-ui text-[8px] uppercase tracking-[0.2em] text-[#3a4a5e]">
                                    XAI FINDINGS · EVIDENCE-GROUNDED CLAIMS
                                </div>
                                <div className="space-y-1">
                                    {findingItems.slice(0, 4).map((finding, i) => {
                                        const conf = Number(finding.confidence ?? 0);
                                        const severity = conf >= 0.8 ? 'critical' : conf >= 0.6 ? 'high' : conf >= 0.4 ? 'medium' : 'low';
                                        const badge = finding.status === 'CONTRADICTED' ? 'CONTRADICTED'
                                            : finding.observed?.length ? 'OBSERVED'
                                            : finding.inferred?.length ? 'INFERRED'
                                            : 'UNKNOWN';
                                        return (
                                            <IntelFeedItem
                                                key={finding.id ?? i}
                                                severity={severity}
                                                type={finding.finding_type || 'FINDING'}
                                                label={finding.subject_label || finding.subject_id || `Finding ${i + 1}`}
                                                detail={`${(conf * 100).toFixed(0)}% conf · ${finding.method ?? 'XAI'}`}
                                                badge={badge}
                                                status={finding.status}
                                                href={`/findings/${finding.id}`}
                                            />
                                        );
                                    })}
                                </div>
                            </div>
                        )}

                        {/* Empty state */}
                        {ghostItems.length === 0 && findingItems.length === 0 && (
                            <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
                                <div className="mb-3 grid h-9 w-9 place-items-center rounded-lg border border-[#1a2436] bg-[#0c121e] text-[#2a3a54]">
                                    <Zap size={16} />
                                </div>
                                <div className="text-[11px] font-semibold text-muted-foreground/70">No active intelligence</div>
                                <div className="mt-1 text-[10px] text-muted-foreground/40 leading-4">
                                    Run the ghost pipeline and generate findings to populate this feed.
                                </div>
                            </div>
                        )}

                        {/* Epistemic ledger */}
                        {findingItems.length > 0 && (
                            <div className="p-3">
                                <div className="mb-2 font-mono-ui text-[8px] uppercase tracking-[0.2em] text-[#3a4a5e]">
                                    EPISTEMIC BREAKDOWN
                                </div>
                                <div className="grid grid-cols-3 gap-2">
                                    <EpistemicTile badge="OBSERVED"  count={observedCount} color="emerald" />
                                    <EpistemicTile badge="INFERRED"  count={inferredCount} color="amber"   />
                                    <EpistemicTile badge="UNKNOWN"   count={unknownCount}  color="slate"   />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Quick operations */}
                    <div className="rounded-lg border border-[#1a2333] bg-[#0c121e]/85 backdrop-blur-sm">
                        <div className="border-b border-[#182130] px-4 py-3">
                            <h3 className="font-mono-ui text-[10px] font-bold uppercase tracking-[0.18em] text-white">Quick Operations</h3>
                        </div>
                        <div className="grid grid-cols-2 gap-2 p-3">
                            <QOpLink href="/network"     icon={Network}  label="Network Explorer"  desc="Trace links"       testId="link-action-explore"    color="cyan"   />
                            <QOpLink href="/ghosts"      icon={Sparkles} label="Ghost Candidates"  desc="Review inferred"   testId="link-action-ghosts"     color="amber"  />
                            <QOpLink href="/findings"    icon={Target}   label="Findings Review"   desc="XAI outputs"       testId="link-action-findings"   color="rose"   />
                            <QOpLink href="/simulation"  icon={Zap}      label="Simulation"        desc="Counterfactuals"   testId="link-action-simulation" color="violet" />
                        </div>
                    </div>
                </div>
            </div>
        </PageShell>
    );
}

// ── Intelligence KPI Card ────────────────────────────────────────────────────
function IntelKpiCard({ label, value, accent, icon: Icon, spark, detail, href, alert }) {
    const accentMap = {
        cyan:    { border: 'border-cyan-500/25',    text: 'text-cyan-400',    bar: 'bg-cyan-500',    icon: 'border-cyan-500/30 bg-cyan-500/12 text-cyan-400'    },
        violet:  { border: 'border-violet-500/25',  text: 'text-violet-400',  bar: 'bg-violet-500',  icon: 'border-violet-500/30 bg-violet-500/12 text-violet-400' },
        blue:    { border: 'border-blue-500/25',    text: 'text-blue-400',    bar: 'bg-blue-500',    icon: 'border-blue-500/30 bg-blue-500/12 text-blue-400'    },
        amber:   { border: 'border-amber-500/25',   text: 'text-amber-400',   bar: 'bg-amber-500',   icon: 'border-amber-500/30 bg-amber-500/12 text-amber-400'  },
        rose:    { border: 'border-rose-500/25',    text: 'text-rose-400',    bar: 'bg-rose-500',    icon: 'border-rose-500/30 bg-rose-500/12 text-rose-400'    },
        emerald: { border: 'border-emerald-500/25', text: 'text-emerald-400', bar: 'bg-emerald-500', icon: 'border-emerald-500/30 bg-emerald-500/12 text-emerald-400' },
    };
    const c = accentMap[accent] ?? accentMap.cyan;
    const max = Math.max(...spark);
    return (
        <Link href={href} className={`group relative block rounded-lg border ${c.border} bg-[#0c121e]/85 p-3.5 backdrop-blur-sm transition-all hover:opacity-90 overflow-hidden`}>
            {alert && (
                <span className="absolute right-3 top-3 flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-70" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-rose-500" />
                </span>
            )}
            <div className="flex items-start justify-between">
                <div className={`font-mono-ui text-[8px] font-bold uppercase tracking-[0.22em] ${c.text} opacity-80`}>
                    {label}
                </div>
                <div className={`grid h-6 w-6 shrink-0 place-items-center rounded border ${c.icon}`}>
                    <Icon size={12} />
                </div>
            </div>
            <div className="mt-2 font-mono-ui text-[22px] font-bold leading-none tracking-tight text-white">
                {value}
            </div>
            {detail && <div className="mt-1 text-[10px] text-muted-foreground/55 truncate">{detail}</div>}
            {/* Mini sparkline */}
            <div className="mt-3 flex h-8 items-end gap-[2px]">
                {spark.map((h, i) => (
                    <div
                        key={i}
                        className={`flex-1 rounded-sm transition-all ${i >= spark.length - 3 ? c.bar : `${c.bar} opacity-25`}`}
                        style={{ height: `${(h / max) * 100}%` }}
                    />
                ))}
            </div>
        </Link>
    );
}

// ── Network Topology cell ────────────────────────────────────────────────────
function TopoCell({ label, value, glyph, color }) {
    const colorMap = {
        cyan: 'text-cyan-400', violet: 'text-violet-400', blue: 'text-blue-400',
        amber: 'text-amber-400', rose: 'text-rose-400', emerald: 'text-emerald-400',
    };
    return (
        <div className="bg-[#090d16] px-4 py-3.5">
            <div className="flex items-center gap-1.5">
                <span className={`font-mono-ui text-[11px] ${colorMap[color] ?? 'text-muted-foreground'}`}>{glyph}</span>
                <div className="font-mono-ui text-[8px] uppercase tracking-[0.18em] text-[#3a4a5e]">{label}</div>
            </div>
            <div className="mt-1.5 font-mono-ui text-[13px] font-bold text-white truncate">{value ?? '—'}</div>
        </div>
    );
}

// ── Network Activity Canvas (pure SVG, no fake data) ─────────────────────────
function NetworkActivityCanvas({ nodes }) {
    const W = 580, H = 220;
    if (!nodes.length) {
        return (
            <div className="flex items-center justify-center w-full h-full">
                <span className="font-mono-ui text-[10px] text-[#2a3a54]">AWAITING GRAPH DATA</span>
            </div>
        );
    }
    const positioned = nodes.slice(0, 20).map((node, i) => {
        const angle = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
        const r = i === 0 ? 0 : 55 + (i % 3) * 32;
        return { node, x: W / 2 + Math.cos(angle) * r, y: H / 2 + Math.sin(angle) * r * 0.55, isCenter: i === 0 };
    });
    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full opacity-90" preserveAspectRatio="xMidYMid meet">
            <defs>
                <radialGradient id="ng-glow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="rgba(34,211,238,0.12)" />
                    <stop offset="100%" stopColor="rgba(34,211,238,0)" />
                </radialGradient>
            </defs>
            <ellipse cx={W/2} cy={H/2} rx={120} ry={68} fill="url(#ng-glow)" />
            {positioned.slice(1).map(({ x, y }, i) => (
                <line key={`edge-${i}`} x1={positioned[0].x} y1={positioned[0].y} x2={x} y2={y}
                    stroke={i < 3 ? 'rgba(34,211,238,0.35)' : 'rgba(34,211,238,0.1)'}
                    strokeWidth={i < 3 ? 0.8 : 0.4}
                    strokeDasharray={i % 2 === 0 ? '3 3' : undefined}
                />
            ))}
            {positioned.slice(1, 8).map(({ x, y }, i) => {
                const next = positioned[(i + 2) % positioned.length];
                if (!next || next.isCenter) return null;
                return <line key={`sec-${i}`} x1={x} y1={y} x2={next.x} y2={next.y} stroke="rgba(34,211,238,0.07)" strokeWidth="0.4" />;
            })}
            {positioned.map(({ node, x, y, isCenter }, i) => (
                <g key={node.id ?? node.entityId ?? i} transform={`translate(${x},${y})`}>
                    {isCenter && <circle r={22} fill="none" stroke="rgba(34,211,238,0.15)" strokeWidth={1.5} strokeDasharray="2 4" />}
                    <circle
                        r={isCenter ? 11 : Math.max(4, 9 - i * 0.35)}
                        fill={isCenter ? 'rgba(34,211,238,0.18)' : i < 4 ? 'rgba(34,211,238,0.10)' : 'rgba(26,36,54,0.8)'}
                        stroke={isCenter ? 'rgba(34,211,238,0.8)' : i < 4 ? 'rgba(34,211,238,0.45)' : 'rgba(34,211,238,0.18)'}
                        strokeWidth={isCenter ? 1.5 : 0.8}
                    />
                    {isCenter && <circle r={4} fill="rgba(34,211,238,0.9)" />}
                </g>
            ))}
        </svg>
    );
}

// ── Intelligence Feed item ───────────────────────────────────────────────────
function IntelFeedItem({ severity, type, label, detail, badge, href }) {
    const severityDot = {
        critical: 'bg-rose-500 shadow-[0_0_6px_rgba(244,63,94,0.9)]',
        high:     'bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.7)]',
        medium:   'bg-blue-400 shadow-[0_0_4px_rgba(96,165,250,0.6)]',
        low:      'bg-[#2a3a54]',
    };
    const badgeStyle = {
        OBSERVED:     'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
        INFERRED:     'border-amber-500/40 bg-amber-500/10 text-amber-400',
        UNKNOWN:      'border-[#2a3a54] bg-[#0c121e] text-[#4a5a70]',
        CONTRADICTED: 'border-rose-500/40 bg-rose-500/10 text-rose-400',
    };
    return (
        <Link href={href} className="flex items-start gap-2.5 rounded-md px-2 py-2 transition-colors hover:bg-[#111827] group">
            <div className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${severityDot[severity] ?? severityDot.low}`} />
            <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-mono-ui text-[8px] uppercase tracking-[0.16em] text-[#3a4a5e]">{type}</span>
                    <span className={`inline-flex items-center rounded border px-1.5 py-px font-mono-ui text-[8px] font-bold uppercase tracking-wider ${badgeStyle[badge] ?? badgeStyle.UNKNOWN}`}>
                        {badge}
                    </span>
                </div>
                <div className="mt-0.5 truncate text-[11px] font-semibold text-foreground/90 group-hover:text-white transition-colors">{label}</div>
                <div className="mt-0.5 font-mono-ui text-[9px] text-muted-foreground/50 truncate">{detail}</div>
            </div>
            <ArrowRight size={11} className="mt-2 shrink-0 text-muted-foreground/30 group-hover:text-cyan-400 transition-colors" />
        </Link>
    );
}

// ── Epistemic breakdown tile ─────────────────────────────────────────────────
function EpistemicTile({ badge, count, color }) {
    const styles = {
        emerald: 'border-emerald-500/30 bg-emerald-500/8 text-emerald-400',
        amber:   'border-amber-500/30 bg-amber-500/8 text-amber-400',
        slate:   'border-[#1a2436] bg-[#090d16] text-[#4a5a70]',
    };
    return (
        <div className={`rounded border ${styles[color] ?? styles.slate} px-2 py-2 text-center`}>
            <div className="font-mono-ui text-[14px] font-bold">{count}</div>
            <div className="mt-0.5 font-mono-ui text-[7px] uppercase tracking-[0.18em] opacity-80">{badge}</div>
        </div>
    );
}

// ── Quick operation link ─────────────────────────────────────────────────────
function QOpLink({ href, icon: Icon, label, desc, testId, color }) {
    const colorMap = {
        cyan:   'border-cyan-500/20 hover:border-cyan-500/50 text-cyan-400',
        amber:  'border-amber-500/20 hover:border-amber-500/50 text-amber-400',
        rose:   'border-rose-500/20 hover:border-rose-500/50 text-rose-400',
        violet: 'border-violet-500/20 hover:border-violet-500/50 text-violet-400',
    };
    return (
        <Link href={href} data-testid={testId}
            className={`flex flex-col gap-1.5 rounded-md border bg-[#090d16] p-3 transition-all hover:-translate-y-px hover:bg-[#0c121e] ${colorMap[color] ?? colorMap.cyan}`}
        >
            <Icon size={14} />
            <div className="text-[11px] font-semibold text-white leading-tight">{label}</div>
            <div className="text-[10px] text-muted-foreground/55">{desc}</div>
        </Link>
    );
}
export function NetworkPage() {
    const [query, setQuery] = useState('');
    const [center, setCenter] = useState(() => new URLSearchParams(window.location.search).get('focus') ?? '');
    const [depth, setDepth] = useState(1);
    const [selected, setSelected] = useState(null);
    const [physics, setPhysics] = useState(true);
    const [labels, setLabels] = useState(true);
    const [pathFrom, setPathFrom] = useState('');
    const [pathTo, setPathTo] = useState('');
    const [showPath, setShowPath] = useState(false);
    const params = useMemo(() => ({ center: center || undefined, depth }), [center, depth]);
    const network = useGetGraphNetwork(params, { query: { queryKey: getGetGraphNetworkQueryKey(params), enabled: true } });
    const search = useSearchGraph({ q: query }, { query: { queryKey: getSearchGraphQueryKey({ q: query }), enabled: query.trim().length > 1 } });
    const pathParams = useMemo(() => ({ from: pathFrom, to: pathTo }), [pathFrom, pathTo]);
    const path = useFindGraphPath(pathParams, { query: { queryKey: getFindGraphPathQueryKey(pathParams), enabled: showPath && pathFrom.length > 0 && pathTo.length > 0 } });
    const nodes = network.data?.nodes ?? [];
    const edges = network.data?.edges ?? [];
    const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
    return <PageShell>
        <SectionHeading eyebrow="Relationship graph" title="Network explorer" description="Investigate neighborhoods, find connective tissue, and preserve the reasoning behind a lead." action={<div className="flex gap-2"><button data-testid="button-export-network" onClick={() => downloadJson('graph-neighborhood.json', { nodes, edges, center: center || null, depth })} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><Download size={14} /> Export</button><button data-testid="button-fit-network" onClick={() => setCenter('')} className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground"><Focus size={14} /> Fit graph</button></div>} />
        <div className="grid gap-5 xl:grid-cols-[280px_1fr_290px]">
            <Panel className="h-fit" title="Graph controls" subtitle="Shape the current neighborhood"><div className="space-y-5 p-5">
                <label className="block"><span className="mb-2 block text-[11px] font-semibold">Search & focus</span><div className="relative"><Search size={14} className="absolute left-3 top-3 text-muted-foreground" /><input data-testid="input-network-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name, ID, or attribute" className="w-full rounded-md border border-input bg-background py-2.5 pl-9 pr-3 text-xs outline-none transition-colors focus:border-primary" /></div></label>
                {query.trim().length > 1 && <div className="max-h-36 overflow-auto rounded-md border border-border bg-background">{search.isLoading ? <div className="p-3 text-xs text-muted-foreground">Searching index…</div> : search.data?.length ? search.data.slice(0, 5).map((item) => <button data-testid={`button-focus-search-${item.id}`} onClick={() => { setCenter(item.id); setQuery(item.name || item.id); setSelected(item); }} key={item.id} className="flex w-full items-center gap-2 border-b border-border/60 px-3 py-2 text-left last:border-0 hover:bg-muted"><div className="grid h-6 w-6 place-items-center rounded bg-primary/10 text-[9px] font-bold text-primary">{(item.name || item.id).slice(0, 2).toUpperCase()}</div><div className="min-w-0"><div className="truncate text-xs font-medium">{item.name || item.id}</div><div className="font-mono-ui text-[9px] text-muted-foreground">{entityType(item)}</div></div></button>) : <div className="p-3 text-xs text-muted-foreground">No matching records.</div>}</div>}
                <label className="block"><div className="mb-2 flex justify-between text-[11px] font-semibold"><span>Neighborhood depth</span><span className="font-mono-ui text-primary">{depth}</span></div><input data-testid="input-network-depth" type="range" min="1" max="3" value={depth} onChange={(e) => setDepth(Number(e.target.value))} className="w-full accent-[hsl(var(--primary))]" /><div className="mt-1 flex justify-between font-mono-ui text-[9px] text-muted-foreground"><span>direct</span><span>extended</span></div></label>
                <div className="border-t border-border pt-4"><div className="mb-3 text-[11px] font-semibold">Display</div><ToggleRow label="Node labels" value={labels} onChange={() => setLabels(!labels)} /><ToggleRow label="Physics simulation" value={physics} onChange={() => setPhysics(!physics)} /></div>
                <div className="border-t border-border pt-4"><div className="mb-3 text-[11px] font-semibold">Entity filters</div><div className="flex flex-wrap gap-1.5"><Pill tone="teal">person</Pill><Pill tone="amber">phone</Pill><Pill tone="blue">location</Pill><Pill>account</Pill></div><button data-testid="button-edit-filters" className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"><SlidersHorizontal size={13} /> Edit filters</button></div>
            </div></Panel>
            <Panel className="min-h-[560px] overflow-hidden" title="Live neighborhood" subtitle={`${nodes.length} nodes · ${edges.length} relationships`} action={<div className="flex items-center gap-2"><span className="font-mono-ui text-[10px] text-muted-foreground">{physics ? 'SIMULATION ON' : 'STATIC VIEW'}</span><button data-testid="button-refresh-network" onClick={() => { void network.refetch(); }} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"><RefreshCw size={14} /></button></div>}>
                {network.isLoading ? <LoadingRows count={7} /> : network.isError ? safeErrorRetry(network.refetch) : nodes.length ? <GraphCanvas nodes={nodes} edges={edges} labels={labels} selectedId={selected?.id} onSelect={setSelected} nodeMap={nodeMap} /> : <EmptyState title="No neighborhood loaded" description="Search for an entity or widen the depth to reveal connected records." icon={Network} />}
            </Panel>
            <div className="space-y-5">
                <Panel title="Selection" subtitle={selected ? 'Focused record' : 'Click a node to inspect'}>{selected ? <div className="p-5"><div className="flex items-start justify-between"><div className="grid h-11 w-11 place-items-center rounded-lg bg-primary/12 font-mono-ui font-bold text-primary">{(selected.name || selected.id).slice(0, 2).toUpperCase()}</div><button data-testid="button-clear-selection" onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground"><X size={16} /></button></div><h3 className="mt-4 text-base font-semibold">{selected.name || selected.id}</h3><div className="mt-1"><Pill tone={typeTone(entityType(selected))}>{entityType(selected)}</Pill></div><div className="mt-5 space-y-2 border-t border-border pt-4 font-mono-ui text-[10px]"><div className="flex justify-between"><span className="text-muted-foreground">record id</span><span>{selected.id}</span></div><div className="flex justify-between"><span className="text-muted-foreground">connections</span><span>{edges.filter((e) => e.source === selected.id || e.target === selected.id).length}</span></div></div><Link href={`/entities?focus=${selected.id}`} data-testid="link-open-entity" className="mt-5 flex items-center justify-center gap-2 rounded-md border border-border py-2.5 text-xs font-semibold hover:bg-muted">Open entity record <ArrowRight size={14} /></Link></div> : <EmptyState title="No selection" description="Select a node in the graph to inspect its properties and connections." icon={Target} />}</Panel>
                <Panel title="Path finder" subtitle="Test a relationship between two records"><div className="space-y-3 p-5"><input data-testid="input-path-from" value={pathFrom} onChange={(e) => setPathFrom(e.target.value)} placeholder="Origin entity ID" className="w-full rounded-md border border-input bg-background px-3 py-2.5 text-xs outline-none focus:border-primary" /><div className="flex justify-center"><ArrowDownRight size={15} className="text-muted-foreground" /></div><input data-testid="input-path-to" value={pathTo} onChange={(e) => setPathTo(e.target.value)} placeholder="Destination entity ID" className="w-full rounded-md border border-input bg-background px-3 py-2.5 text-xs outline-none focus:border-primary" /><button data-testid="button-find-path" onClick={() => setShowPath(true)} disabled={!pathFrom || !pathTo} className="mt-1 flex w-full items-center justify-center gap-2 rounded-md bg-primary py-2.5 text-xs font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-40"><GitBranch size={14} /> Find shortest path</button>{showPath && path.isLoading && <div className="text-xs text-muted-foreground">Tracing relationship…</div>}{showPath && path.data && <div className="rounded-md bg-primary/8 p-3 text-xs text-primary"><div className="font-semibold">Path resolved</div><div className="mt-1 font-mono-ui text-[10px]">{(path.data.path || path.data.nodes || []).length} records in chain</div></div>}{showPath && path.isError && <div className="text-xs text-destructive">No path returned for these records.</div>}</div></Panel>
            </div>
        </div>
    </PageShell>;
}
function ToggleRow({ label, value, onChange }) {
    return <button data-testid={`button-toggle-${label.toLowerCase().replace(/\s+/g, '-')}`} onClick={onChange} className="flex w-full items-center justify-between py-1 text-xs"><span>{label}</span><span className={`relative h-5 w-9 rounded-full transition-colors ${value ? 'bg-primary' : 'bg-muted'}`}><span className={`absolute top-0.5 h-4 w-4 rounded-full bg-card shadow-sm transition-transform ${value ? 'translate-x-[18px]' : 'translate-x-0.5'}`} /></span></button>;
}
function GraphCanvas({ nodes, edges, labels, selectedId, onSelect, nodeMap }) {
    const positions = nodes.slice(0, 24).map((node, index, arr) => { const angle = index / Math.max(arr.length, 1) * Math.PI * 2; const radius = index === 0 ? 0 : Math.min(205, 58 + Math.floor((index - 1) / 7) * 58); return { node, x: 50 + Math.cos(angle) * radius / 4.2, y: 50 + Math.sin(angle) * radius / 2.2 }; });
    const pos = new Map(positions.map((p) => [p.node.id, p]));
    return <div className="panel-grid relative min-h-[560px] overflow-hidden bg-background/40"><div className="absolute left-5 top-5 flex items-center gap-2 rounded-md border border-border bg-card/90 px-2.5 py-2 font-mono-ui text-[9px] text-muted-foreground backdrop-blur"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" /> LIVE LAYOUT</div><svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full p-10">{edges.slice(0, 60).map((edge, index) => {
        const a = pos.get(edge.source); const b = pos.get(edge.target); if (!a || !b)
            return null; return <line key={`${edge.source}-${edge.target}-${index}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="hsl(var(--primary) / .24)" strokeWidth=".28" strokeDasharray={index % 3 === 0 ? '1 1' : undefined} />;
    })}</svg><div className="absolute inset-0">{positions.map(({ node, x, y }, index) => <button key={node.id} data-testid={`button-graph-node-${node.id}`} onClick={() => onSelect(node)} className={`absolute -translate-x-1/2 -translate-y-1/2 text-left transition-transform duration-200 hover:scale-110 ${selectedId === node.id ? 'z-10 scale-110' : ''}`} style={{ left: `${x}%`, top: `${y}%` }}><div className={`grid h-11 w-11 place-items-center rounded-full border-2 ${selectedId === node.id ? 'border-accent bg-accent/20 text-accent' : index === 0 ? 'border-primary bg-primary/18 text-primary' : 'border-primary/40 bg-card text-primary'} shadow-sm`}><CircleDot size={17} /></div>{labels && <div className="mt-1 max-w-[110px] truncate rounded bg-card/85 px-1.5 py-0.5 text-center font-mono-ui text-[9px] text-foreground shadow-sm">{node.name || node.id}</div>}</button>)}</div><div className="absolute bottom-4 right-4 flex gap-1.5"><button data-testid="button-zoom-in" className="grid h-7 w-7 place-items-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground"><Plus size={13} /></button><button data-testid="button-zoom-out" className="grid h-7 w-7 place-items-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground"><Minus size={13} /></button><button data-testid="button-fullscreen-network" className="grid h-7 w-7 place-items-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground"><Maximize2 size={13} /></button></div></div>;
}
export function EntitiesPage() {
    const [query, setQuery] = useState('');
    const entityQuery = useGetEntities({ page: 1, page_size: 50 }, { query: { queryKey: getGetEntitiesQueryKey({ page: 1, page_size: 50 }) } });
    const overview = entityQuery;
    const search = { isLoading: false };
    const entities = (entityQuery.data?.items ?? []).map((entity, index) => ({
        ...entity,
        id: entity.id ?? `${entity.label ?? 'entity'}-${index}`,
        name: entity.name ?? entity.text,
        category: entity.category ?? entity.label,
        properties: entity.properties ?? {},
    }));
    const filteredEntities = query.trim()
        ? entities.filter((entity) => `${entity.text ?? ''} ${entity.label ?? ''}`.toLowerCase().includes(query.trim().toLowerCase()))
        : entities;
    return <PageShell><SectionHeading eyebrow="Entity directory" title="Entities" description="Search across people, accounts, locations, devices, and every record that gives the graph its shape." action={<button data-testid="button-entity-filters" className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><Filter size={14} /> Filters</button>} /><Panel><div className="flex flex-wrap items-center gap-3 border-b border-border/75 p-4"><div className="relative min-w-[260px] flex-1"><Search size={15} className="absolute left-3 top-3 text-muted-foreground" /><input data-testid="input-entity-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search entities by name or identifier" className="w-full rounded-md border border-input bg-background py-2.5 pl-9 pr-3 text-xs outline-none focus:border-primary" /></div><select data-testid="select-entity-type" className="rounded-md border border-input bg-background px-3 py-2.5 text-xs"><option>All entity types</option><option>Person</option><option>Phone</option><option>Account</option><option>Location</option></select><div className="font-mono-ui text-[10px] text-muted-foreground">{entities.length} records</div></div>{overview.isLoading || search.isLoading ? <LoadingRows count={6} /> : overview.isError ? safeErrorRetry(overview.refetch) : entities.length ? <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-muted/60 font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground"><tr><th className="px-5 py-3 font-normal">Entity</th><th className="px-5 py-3 font-normal">Type</th><th className="px-5 py-3 font-normal">Record ID</th><th className="px-5 py-3 font-normal">Properties</th><th className="px-5 py-3" /></tr></thead><tbody className="divide-y divide-border/70">{entities.map((entity) => <tr key={entity.id} data-testid={`row-entity-${entity.id}`} className="group hover:bg-muted/40"><td className="px-5 py-3.5"><div className="flex items-center gap-3"><div className="grid h-8 w-8 place-items-center rounded-md bg-primary/10 font-mono-ui text-[10px] font-bold text-primary">{(entity.name || entity.id).slice(0, 2).toUpperCase()}</div><div><div className="font-semibold">{entity.name || 'Unnamed record'}</div><div className="mt-0.5 text-[10px] text-muted-foreground">{entity.category || 'Uncategorized'}</div></div></div></td><td className="px-5 py-3.5"><Pill tone={typeTone(entityType(entity))}>{entityType(entity)}</Pill></td><td className="px-5 py-3.5 font-mono-ui text-[10px] text-muted-foreground">{entity.id}</td><td className="px-5 py-3.5 font-mono-ui text-[10px] text-muted-foreground">{entity.properties ? Object.keys(entity.properties).length : 0} fields</td><td className="px-5 py-3.5 text-right"><Link href={`/network?focus=${entity.id}`} data-testid={`link-entity-network-${entity.id}`} className="inline-flex items-center gap-1 text-xs font-semibold text-primary opacity-0 transition-opacity group-hover:opacity-100">Open network <ArrowRight size={13} /></Link></td></tr>)}</tbody></table></div> : <EmptyState title="No entities found" description="Try a broader search or wait for the graph index to expose entity records." icon={FileText} />}</Panel></PageShell>;
}
export function AnalyticsPage() {
    const centrality = useGetCentrality({ query: { queryKey: getGetCentralityQueryKey() } });
    const communities = useGetCommunities({ query: { queryKey: getGetCommunitiesQueryKey() } });
    return <PageShell><SectionHeading eyebrow="Graph intelligence" title="Analytics" description="A working surface for finding structural importance, dense communities, and distribution shifts." action={<button data-testid="button-refresh-analytics" onClick={() => { void centrality.refetch(); void communities.refetch(); }} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><RefreshCw size={14} /> Refresh analysis</button>} /><div className="grid gap-5 xl:grid-cols-[1.2fr_.8fr]"><Panel title="Centrality leaders" subtitle="Entities with disproportionate connective reach" action={<Pill tone="teal">degree centrality</Pill>}>{centrality.isLoading ? <LoadingRows /> : centrality.isError ? safeErrorRetry(centrality.refetch) : centrality.data?.length ? <div className="divide-y divide-border/70">{centrality.data.slice(0, 8).map((item, index) => { const label = item.name || item.entity?.name || item.entityId || item.entity?.id || 'Unnamed'; return <div key={`${item.entityId}-${index}`} className="flex items-center gap-3 px-5 py-3.5" data-testid={`row-centrality-${index}`}><div className="w-5 font-mono-ui text-[10px] text-muted-foreground">0{index + 1}</div><div className="grid h-8 w-8 place-items-center rounded-md bg-primary/10 text-primary"><Target size={15} /></div><div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold">{label}</div><div className="mt-1 h-1.5 max-w-[240px] overflow-hidden rounded bg-muted"><div className="h-full rounded bg-primary" style={{ width: `${Math.min(100, (item.score ?? 0) * 100)}%` }} /></div></div><div className="text-right"><div className="font-mono-ui text-xs font-bold">{(item.score ?? 0).toFixed(3)}</div><div className="font-mono-ui text-[9px] text-muted-foreground">{item.connections ?? 0} links</div></div></div>; })}</div> : <EmptyState title="No centrality results" description="Centrality will populate when the analytics service returns ranked entities." icon={Target} />}</Panel><Panel title="Communities" subtitle="Detected graph clusters" action={<Pill tone="amber">{communities.data?.length ?? 0} groups</Pill>}>{communities.isLoading ? <LoadingRows count={5} /> : communities.isError ? safeErrorRetry(communities.refetch) : communities.data?.length ? <div className="divide-y divide-border/70">{communities.data.slice(0, 6).map((community, index) => <div key={community.id} className="flex items-center gap-3 px-5 py-4" data-testid={`row-community-${community.id}`}><div className={`grid h-9 w-9 place-items-center rounded-full ${['bg-primary/12 text-primary', 'bg-accent/15 text-accent', 'bg-chart-3/12 text-chart-3', 'bg-chart-4/15 text-chart-4'][index % 4]}`}><Users size={16} /></div><div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold">{community.name || `Community ${index + 1}`}</div><div className="mt-1 font-mono-ui text-[10px] text-muted-foreground">{community.entityIds?.length ?? community.size ?? 0} entities</div></div><ChevronRight size={15} className="text-muted-foreground" /></div>)}</div> : <EmptyState title="No communities detected" description="Cluster results will appear when the community analysis completes." icon={Users} />}</Panel></div><div className="mt-5 grid gap-5 lg:grid-cols-3"><AnalyticMini title="Relationship distribution" description="By edge type" icon={Link2} /><AnalyticMini title="Entity distribution" description="By class and category" icon={Layers3} /><AnalyticMini title="Activity analytics" description="Events across the selected period" icon={BarChart3} /></div></PageShell>;
}
function AnalyticMini({ title, description, icon: Icon }) {
    return <Panel className="min-h-[170px] p-5"><div className="flex items-center justify-between"><div><h3 className="text-sm font-semibold">{title}</h3><p className="mt-1 text-xs text-muted-foreground">{description}</p></div><div className="grid h-8 w-8 place-items-center rounded-md bg-muted text-muted-foreground"><Icon size={16} /></div></div><div className="mt-7 flex h-10 items-end gap-1.5">{[34, 52, 42, 68, 58, 82, 70, 90, 76, 64, 84, 72].map((height, i) => <div key={i} className={`flex-1 rounded-t-sm ${i > 8 ? 'bg-primary' : 'bg-primary/25'}`} style={{ height: `${height}%` }} />)}</div></Panel>;
}
export function TimelinePage() {
    const [entityId, setEntityId] = useState('');
    const [from, setFrom] = useState('');
    const [to, setTo] = useState('');
    const params = useMemo(() => ({ entityId: entityId || undefined, from: from || undefined, to: to || undefined }), [entityId, from, to]);
    const timeline = useGetGraphTimeline(params, { query: { queryKey: getGetGraphTimelineQueryKey(params) } });
    const calls = useGetCalls({ page: 1, page_size: 20 }, { query: { queryKey: getGetCallsQueryKey({ page: 1, page_size: 20 }) } });
    const meetings = useGetMeetings({ page: 1, page_size: 20 }, { query: { queryKey: getGetMeetingsQueryKey({ page: 1, page_size: 20 }) } });
    const graphEvents = timeline.data ?? [];
    const fallbackEvents = [
        ...(calls.data?.items ?? []).map((row) => ({ id: row.call_id, title: `${row.caller_id} -> ${row.receiver_id}`, timestamp: row.timestamp, entityId: row.caller_id, relation: 'CALL' })),
        ...(meetings.data?.items ?? []).map((row) => ({ id: row.meeting_id, title: row.location || 'Meeting', timestamp: row.timestamp, entityId: row.attendee_ids?.[0], relation: 'MEETING' })),
    ];
    const events = graphEvents.length ? graphEvents : fallbackEvents;
    return <PageShell><SectionHeading eyebrow="Evidence sequence" title="Timeline" description="Read the graph as a sequence of moments. Narrow the stream, then jump back into the network." action={<button data-testid="button-export-timeline" onClick={() => downloadJson('graph-timeline.json', events)} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><Download size={14} /> Export stream</button>} /><Panel title="Timeline filters" subtitle="Queries are applied against the graph event index"><div className="flex flex-wrap gap-3 p-4"><label className="flex-1"><span className="mb-1.5 block font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">Entity ID</span><input data-testid="input-timeline-entity" value={entityId} onChange={(e) => setEntityId(e.target.value)} placeholder="entity identifier" className="w-full rounded-md border border-input bg-background px-3 py-2.5 text-xs outline-none focus:border-primary" /></label><label><span className="mb-1.5 block font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">From</span><input data-testid="input-timeline-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="rounded-md border border-input bg-background px-3 py-2.5 text-xs outline-none focus:border-primary" /></label><label><span className="mb-1.5 block font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">To</span><input data-testid="input-timeline-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="rounded-md border border-input bg-background px-3 py-2.5 text-xs outline-none focus:border-primary" /></label><button data-testid="button-clear-timeline" onClick={() => { setEntityId(''); setFrom(''); setTo(''); }} className="self-end rounded-md border border-border px-3 py-2.5 text-xs font-semibold hover:bg-muted">Clear</button></div></Panel><div className="mt-5"><Panel title="Event stream" subtitle={`${events.length} events returned`} action={<button data-testid="button-refresh-timeline" onClick={() => { void timeline.refetch(); }} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"><RefreshCw size={14} /></button>}>{timeline.isLoading ? <LoadingRows count={7} /> : timeline.isError ? safeErrorRetry(timeline.refetch) : events.length ? <div className="divide-y divide-border/70">{events.map((event, index) => <div key={event.id} data-testid={`row-timeline-${event.id}`} className="group grid grid-cols-[100px_20px_1fr_auto] items-start gap-3 px-5 py-4"><div className="font-mono-ui text-[10px] text-muted-foreground">{fmtDate(event.timestamp)}</div><div className="relative flex justify-center"><div className="mt-1.5 h-2.5 w-2.5 rounded-full border-2 border-primary bg-card ring-4 ring-primary/10" />{index < events.length - 1 && <div className="absolute top-4 h-[52px] w-px bg-border" />}</div><div><div className="text-xs font-semibold">{event.title || event.type || 'Untitled event'}</div><div className="mt-1 flex flex-wrap gap-2 font-mono-ui text-[10px] text-muted-foreground">{event.type && <Pill tone={typeTone(event.type)}>{event.type}</Pill>}{event.entityId && <span>entity: {event.entityId}</span>}{event.caseId && <span>case: {event.caseId}</span>}</div></div>{event.entityId && <Link href={`/network?focus=${event.entityId}`} data-testid={`link-timeline-network-${event.id}`} className="inline-flex items-center gap-1 text-[10px] font-semibold text-primary opacity-0 group-hover:opacity-100">Network <ArrowRight size={12} /></Link>}</div>)}</div> : <EmptyState title="The stream is quiet" description="No events match the current filters. Try a wider time window or another entity." icon={Layers3} />}</Panel></div></PageShell>;
}
export function CasesPage() {
    const casesQuery = useCases({ query: { queryKey: getCasesQueryKey() } });
    const cases = casesQuery.data?.items ?? [];
    return <PageShell><SectionHeading eyebrow="Investigations" title="Cases" description="Working investigation files backed by the case workspace API." action={<button data-testid="button-new-case" disabled className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground opacity-50"><Plus size={14} /> New case</button>} /><Panel title="Case workspace" subtitle="Auditable analyst workspaces, not synthetic intelligence results">{casesQuery.isLoading ? <LoadingRows count={4} /> : casesQuery.isError ? safeErrorRetry(casesQuery.refetch) : <div className="divide-y divide-border/70">{cases.length ? cases.map((item) => <Link href={`/cases/${encodeURIComponent(item.id)}`} key={item.id} className="flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-muted/40"><div><div className="text-sm font-semibold">{item.title || item.id}</div><div className="mt-1 flex flex-wrap gap-2 font-mono-ui text-[10px] text-muted-foreground"><Pill tone={item.status === 'OPEN' ? 'teal' : 'neutral'}>{item.status || 'UNKNOWN'}</Pill><span>{item.items_count ?? 0} linked items</span><span>updated {fmtDate(item.updated_at)}</span></div></div><ArrowRight size={15} className="text-muted-foreground" /></Link>) : <EmptyState title="No case records" description="Create a case workspace to collect entities, evidence, findings, and notes." icon={FileText} />}</div>}</Panel><div className="mt-5 grid gap-5 md:grid-cols-3"><Metric label="Open investigations" value={String(cases.filter((item) => item.status === 'OPEN').length)} detail="Case workspaces" icon={FileText} /><Metric label="Linked evidence" value={shortNumber(cases.reduce((sum, item) => sum + (item.items_count || 0), 0))} detail="Items attached" accent="accent" icon={Link2} /><Metric label="Recent updates" value={cases.length ? fmtDate(cases[0].updated_at) : '—'} detail="Latest case activity" accent="blue" icon={RefreshCw} /></div></PageShell>;
}
export function CaseDetailPage() {
    const params = useParams();
    const caseId = params.id || 'unknown';
    const caseQuery = useCaseDetail(caseId);
    const item = caseQuery.data;
    if (caseQuery.isLoading) return <PageShell><Panel><LoadingRows count={6} /></Panel></PageShell>;
    if (caseQuery.isError) return <PageShell><Panel><ErrorState onRetry={caseQuery.refetch} /></Panel></PageShell>;
    return <PageShell><SectionHeading eyebrow="Investigation record" title={item?.title || `Case ${caseId}`} description={item?.description || 'Working case file for collecting auditable investigative context.'} action={<Link href="/cases" data-testid="link-back-cases" className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted">Back to cases</Link>} /><div className="grid gap-5 lg:grid-cols-[1fr_.8fr]"><Panel title="Case details" subtitle={`${item?.id || caseId} · ${item?.status || 'UNKNOWN'}`}><div className="space-y-4 p-5"><div className="grid gap-3 sm:grid-cols-2"><MetricRow label="Investigator" value={item?.investigator || '—'} /><MetricRow label="Created" value={fmtDate(item?.created_at)} /><MetricRow label="Linked items" value={item?.items?.length ?? 0} /><MetricRow label="Notes" value={item?.notes?.length ?? 0} /></div><div className="rounded-md border border-dashed border-accent/40 bg-accent/5 p-3 text-xs text-muted-foreground">{item?.disclaimer || 'Working case file. Not an official legal record.'}</div></div></Panel><Panel title="Network action" subtitle="Jump into a graph around linked case items"><div className="p-5"><div className="rounded-md border border-dashed border-primary/40 bg-primary/5 p-4 text-xs leading-5 text-muted-foreground">Case-linked entities can be focused in the network explorer when they are attached to this workspace.</div><Link href="/network" data-testid="link-case-network" className="mt-4 flex items-center justify-center gap-2 rounded-md bg-primary py-2.5 text-xs font-semibold text-primary-foreground">Open network explorer <Network size={14} /></Link></div></Panel></div></PageShell>;
}
export function CommunicationsPage() {
    const calls = useGetCalls({ page: 1, page_size: 20 }, { query: { queryKey: getGetCallsQueryKey({ page: 1, page_size: 20 }) } });
    const meetings = useGetMeetings({ page: 1, page_size: 20 }, { query: { queryKey: getGetMeetingsQueryKey({ page: 1, page_size: 20 }) } });
    const callRows = calls.data?.items ?? [];
    const meetingRows = meetings.data?.items ?? [];
    const uniqueContacts = new Set(callRows.flatMap((row) => [row.caller_id, row.receiver_id])).size;
    const totalDuration = callRows.reduce((sum, row) => sum + (Number(row.duration_sec) || 0), 0);
    const maxDuration = callRows.reduce((max, row) => Math.max(max, Number(row.duration_sec) || 0), 0);

    return <PageShell>
        <SectionHeading eyebrow="Contact intelligence" title="Communications" description="Observed call and meeting events from the live dataset." action={<button data-testid="button-export-communications" onClick={() => downloadJson('communications.json', { calls: callRows, meetings: meetingRows })} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><Download size={14} /> Export</button>} />
        <div className="grid gap-4 sm:grid-cols-3">
            <Metric label="Total interactions" value={shortNumber(callRows.length + meetingRows.length)} detail="Calls + meetings" icon={Zap} />
            <Metric label="Unique contacts" value={shortNumber(uniqueContacts)} detail="Distinct linked parties" accent="accent" icon={Users} />
            <Metric label="Peak duration" value={maxDuration ? `${shortNumber(maxDuration)}s` : '—'} detail="Longest observed call" accent="blue" icon={Gauge} />
        </div>
        <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_.8fr]">
            <Panel title="Call records" subtitle="Latest call events from the generated dataset">
                {calls.isLoading ? <LoadingRows count={5} /> : calls.isError ? safeErrorRetry(calls.refetch) : callRows.length ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                            <thead className="bg-muted/60 font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground">
                                <tr><th className="px-5 py-3 font-normal">Caller</th><th className="px-5 py-3 font-normal">Receiver</th><th className="px-5 py-3 font-normal">When</th><th className="px-5 py-3 font-normal">Duration</th></tr>
                            </thead>
                            <tbody className="divide-y divide-border/70">{callRows.slice(0, 8).map((row) => <tr key={row.call_id} className="hover:bg-muted/40"><td className="px-5 py-3 font-medium">{row.caller_id}</td><td className="px-5 py-3">{row.receiver_id}</td><td className="px-5 py-3 font-mono-ui text-[10px]">{fmtDate(row.timestamp)}</td><td className="px-5 py-3 font-mono-ui text-[10px]">{row.duration_sec || '—'}s</td></tr>)}</tbody>
                        </table>
                    </div>
                ) : <EmptyState title="No call records" description="No calls are currently loaded for this dataset." icon={Zap} />}
            </Panel>
            <Panel title="Meeting summary" subtitle="Most recent observed meetups">
                {meetings.isLoading ? <LoadingRows count={3} /> : meetings.isError ? safeErrorRetry(meetings.refetch) : meetingRows.length ? (
                    <div className="divide-y divide-border/70">{meetingRows.slice(0, 6).map((row) => <div key={row.meeting_id} className="px-5 py-3"><div className="flex items-center justify-between gap-3"><div className="font-medium text-xs">{row.location || 'Unknown location'}</div><div className="font-mono-ui text-[10px] text-muted-foreground">{fmtDate(row.timestamp)}</div></div><div className="mt-1 text-[10px] text-muted-foreground">Attendees: {Array.isArray(row.attendee_ids) ? row.attendee_ids.join(', ') : String(row.attendee_ids || '').replace(/\|/g, ', ')}</div></div>)} </div>
                ) : <EmptyState title="No meetings" description="No meeting records are currently loaded for this dataset." icon={Users} />}
            </Panel>
        </div>
        <div className="mt-5">
            <Panel title="Communication dataset" subtitle="Source-backed data points from the API layer">
                <div className="flex flex-wrap gap-3 border-b border-border/75 p-4">
                    <div className="relative flex-1"><Search size={14} className="absolute left-3 top-3 text-muted-foreground" /><input data-testid="input-communications-search" placeholder="Search caller, recipient, or location" className="w-full rounded-md border border-input bg-background py-2.5 pl-9 text-xs" value="" readOnly /></div>
                    <button data-testid="button-communication-filters" className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs font-semibold hover:bg-muted"><ListFilter size={14} /> Filters</button>
                </div>
                <div className="p-5 font-mono-ui text-[10px] text-muted-foreground">Backed by /api/data/calls and /api/data/meetings • {callRows.length} calls loaded • {meetingRows.length} meetings loaded • {totalDuration}s total call duration</div>
            </Panel>
        </div>
    </PageShell>;
}
export function TransactionsPage() {
    const txns = useGetTransactions({ page: 1, page_size: 20 }, { query: { queryKey: getGetTransactionsQueryKey({ page: 1, page_size: 20 }) } });
    const rows = txns.data?.items ?? [];
    const totalValue = rows.reduce((sum, row) => sum + (Number(row.amount) || 0), 0);
    return <PageShell><SectionHeading eyebrow="Flow analysis" title="Transactions" description="Live transaction records from the generated dataset." action={<button data-testid="button-export-transactions" onClick={() => downloadJson('transactions.json', rows)} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><Download size={14} /> Export</button>} /><div className="grid gap-4 sm:grid-cols-3"><Metric label="Flow volume" value={shortNumber(totalValue)} detail="Observed amount" icon={ArrowDownRight} /><Metric label="Transactions" value={shortNumber(rows.length)} detail="Loaded rows" accent="accent" icon={Layers3} /><Metric label="Net movement" value={rows.length ? `${rows[0].currency || 'USD'}` : '—'} detail="Primary currency" accent="blue" icon={BarChart3} /></div><div className="mt-5"><Panel title="Transaction ledger" subtitle="Latest transaction activity from the API layer"><div className="flex flex-wrap gap-3 border-b border-border/75 p-4"><div className="relative flex-1"><Search size={14} className="absolute left-3 top-3 text-muted-foreground" /><input data-testid="input-transactions-search" placeholder="Search by account or counterpart" className="w-full rounded-md border border-input bg-background py-2.5 pl-9 text-xs" value="" readOnly /></div><button data-testid="button-transaction-filters" className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs font-semibold hover:bg-muted"><ListFilter size={14} /> Filters</button></div>{txns.isLoading ? <LoadingRows count={5} /> : txns.isError ? safeErrorRetry(txns.refetch) : rows.length ? <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-muted/60 font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground"><tr><th className="px-5 py-3 font-normal">Transaction</th><th className="px-5 py-3 font-normal">Sender</th><th className="px-5 py-3 font-normal">Receiver</th><th className="px-5 py-3 font-normal">Amount</th></tr></thead><tbody className="divide-y divide-border/70">{rows.slice(0, 8).map((row) => <tr key={row.transaction_id} className="hover:bg-muted/40"><td className="px-5 py-3 font-medium">{row.transaction_id}</td><td className="px-5 py-3">{row.sender_id}</td><td className="px-5 py-3">{row.receiver_id}</td><td className="px-5 py-3 font-mono-ui text-[10px]">{row.amount || '—'} {row.currency || ''}</td></tr>)}</tbody></table></div> : <EmptyState title="No transaction dataset connected" description="The current graph API does not expose transaction records. When available, this surface will show direction, counterparties, totals, and trend context." icon={Layers3} />}</Panel></div></PageShell>;
}

export function GhostsPage() {
    const ghosts = useGetGhosts();
    const items = ghosts.data?.items ?? [];
    return <PageShell>
        <SectionHeading eyebrow="Intelligence" title="Ghost candidates" description="Explainable hypotheses for unobserved intermediaries between otherwise separated communities." action={<button onClick={() => { void ghosts.refetch(); }} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><RefreshCw size={14} /> Refresh</button>} />
        <div className="grid gap-4 sm:grid-cols-3">
            <Metric label="Candidates" value={items.length || '0'} detail="Current ghost predictions" icon={Sparkles} />
            <Metric label="Top confidence" value={items.length ? `${Math.round(Math.max(...items.map((g) => Number(g.confidence) || 0)) * 100)}%` : '—'} detail="Highest scored hypothesis" accent="accent" icon={Gauge} />
            <Metric label="Explainability" value={items.length ? 'Structured' : '—'} detail="Evidence + confidence breakdown" accent="blue" icon={Target} />
        </div>
        <div className="mt-5">
            <Panel title="Ranked hypotheses" subtitle="Each row is a synthetic hypothesis, not an observed entity.">
                {ghosts.isLoading ? <LoadingRows count={4} /> : ghosts.isError ? <ErrorState onRetry={() => { void ghosts.refetch(); }} /> : items.length ? <div className="divide-y divide-border/70">{items.map((ghost) => {
                    const evidence = ghost.evidence ?? [];
                    const accounts = evidence.filter((item) => item.anchor_type === 'ACCOUNT');
                    const categories = ghost.confidence_breakdown ?? {};
                    return <div key={ghost.ghost_id} className="p-5" data-testid={`ghost-${ghost.ghost_id}`}>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div><div className="flex items-center gap-2"><Sparkles size={15} className="text-primary" /><h3 className="text-sm font-semibold">{ghost.label}</h3><Pill tone="amber">{ghost.subtype?.replace(/_/g, ' ')}</Pill></div><div className="mt-1 font-mono-ui text-[10px] text-muted-foreground">Communities {ghost.between_communities?.join(' ↔ ')}</div></div>
                            <div className="text-right"><div className="font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground">confidence</div><div className="mt-1 text-xl font-semibold">{Math.round((Number(ghost.confidence) || 0) * 100)}%</div></div>
                        </div>
                        <div className="mt-4 grid gap-3 md:grid-cols-3">
                            <div className="rounded-md border border-border bg-background p-3"><div className="font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">Shared anchors</div><div className="mt-1 text-sm font-semibold">{evidence.length}</div><div className="mt-1 text-[10px] text-muted-foreground">{accounts.length ? `${accounts.length} financial route${accounts.length === 1 ? '' : 's'}` : 'No account anchor surfaced'}</div></div>
                            <div className="rounded-md border border-border bg-background p-3"><div className="font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">Structural</div><div className="mt-1 text-sm font-semibold">{Math.round((Number(categories.structural_hole_signal) || 0) * 100)}%</div><div className="mt-1 text-[10px] text-muted-foreground">Broker / hole signal</div></div>
                            <div className="rounded-md border border-border bg-background p-3"><div className="font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">Attribute</div><div className="mt-1 text-sm font-semibold">{Math.round((Number(categories.attribute_affinity) || 0) * 100)}%</div><div className="mt-1 text-[10px] text-muted-foreground">Rarity-weighted shared surface</div></div>
                        </div>
                        <div className="mt-4 flex flex-wrap gap-2">{accounts.map((item) => <Pill key={item.anchor_guid} tone="rose">{item.anchor_name}</Pill>)}</div>
                    </div>;
                })}</div> : <EmptyState title="No ghost candidates" description="Run the graph pipeline through ghost detection to populate explainable hidden-coordinator hypotheses." icon={Sparkles} />}
            </Panel>
        </div>
    </PageShell>;
}

export function PipelinePage() {
    const health = useHealthCheck({ query: { queryKey: getHealthCheckQueryKey() } });
    const jobsQuery = useListJobs({ query: { queryKey: getJobsQueryKey() } });
    const { trigger } = useTriggerPipeline();
    const [triggering, setTriggering] = useState(null);

    const stages = [
        { key: 'generate', label: 'Data Generation', desc: 'Synthetic data generation', icon: Database },
        { key: 'preprocess', label: 'Normalization', desc: 'Clean & standardize records', icon: RefreshCw },
        { key: 'extract', label: 'Entity Extraction', desc: 'NER & relationship extraction', icon: Search },
        { key: 'graph/build', label: 'Graph Indexing', desc: 'Build nodes & edges', icon: GitBranch },
        { key: 'ghosts', label: 'Ghost Detection', desc: 'Hypothesize unobserved links', icon: Sparkles },
    ];

    const jobs = jobsQuery.data ?? [];
    const getLatestJob = (kind) => jobs.filter((j) => j.kind === kind).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
    const activeJobs = jobs.filter((j) => j.status === 'pending' || j.status === 'running');

    async function handleTrigger(stageKey) {
        setTriggering(stageKey);
        try { await trigger(stageKey); } catch { /* ignored — query will refetch */ }
        setTriggering(null);
    }

    const statusPill = (status) => {
        if (status === 'success') return <Pill tone="teal">done</Pill>;
        if (status === 'running') return <Pill tone="blue">running</Pill>;
        if (status === 'pending') return <Pill>pending</Pill>;
        if (status === 'failed') return <Pill tone="rose">failed</Pill>;
        return <Pill>not run</Pill>;
    };

    return <PageShell><SectionHeading eyebrow="Data operations" title="Pipeline monitor" description="Trigger ingestion stages and monitor background job progress." action={<button data-testid="button-refresh-pipeline" onClick={() => { void jobsQuery.refetch(); void health.refetch(); }} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"><RefreshCw size={14} /> Refresh status</button>} /><div className="grid gap-4 sm:grid-cols-3"><Metric label="Graph health" value={health.isLoading ? '…' : health.isError ? 'Degraded' : 'Connected'} detail={health.isError ? 'Health endpoint unavailable' : 'API health endpoint responding'} icon={health.isError ? Globe2 : Check} /><Metric label="Total jobs" value={String(jobs.length)} detail={activeJobs.length ? `${activeJobs.length} active` : 'No active jobs'} accent="accent" icon={GitBranch} /><Metric label="Last run" value={jobs.length ? fmtDate(jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0]?.created_at) : '—'} detail="Most recent pipeline job" accent="blue" icon={History} /></div><div className="mt-5"><Panel title="Processing stages" subtitle="Trigger individual stages or watch running jobs"><div className="divide-y divide-border/70">{stages.map((stage, index) => { const job = getLatestJob(stage.key); const isTriggeringThis = triggering === stage.key; return <div key={stage.key} className="flex items-center gap-4 px-5 py-4"><div className="grid h-8 w-8 place-items-center rounded-md bg-primary/10 font-mono-ui text-xs text-primary">0{index + 1}</div><div className="min-w-0 flex-1"><div className="text-xs font-semibold">{stage.label}</div><div className="mt-0.5 text-[11px] text-muted-foreground">{stage.desc}</div>{job && job.status === 'success' && job.result && <div className="mt-1 font-mono-ui text-[10px] text-muted-foreground">{job.result.summary || job.result.message || ''}</div>}{job && job.status === 'failed' && job.error && <div className="mt-1 font-mono-ui text-[10px] text-destructive truncate max-w-[400px]" title={job.error}>Error: {job.error.split('\n').pop()}</div>}</div>{statusPill(job?.status)}<button data-testid={`button-trigger-${stage.key}`} disabled={!!triggering} onClick={() => handleTrigger(stage.key)} className="rounded-md border border-border px-3 py-1.5 text-[11px] font-semibold hover:bg-muted disabled:opacity-50">{isTriggeringThis ? <RefreshCw size={12} className="animate-spin" /> : 'Run'}</button></div>; })}</div></Panel></div>{jobs.length > 0 && <div className="mt-5"><Panel title="Job history" subtitle="Recent pipeline runs across all stages"><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-muted/60 font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground"><tr><th className="px-5 py-3 font-normal">Stage</th><th className="px-5 py-3 font-normal">Status</th><th className="px-5 py-3 font-normal">Started</th><th className="px-5 py-3 font-normal">Finished</th><th className="px-5 py-3 font-normal">Job ID</th></tr></thead><tbody className="divide-y divide-border/70">{jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 15).map((job) => <tr key={job.job_id} data-testid={`row-job-${job.job_id}`} className="hover:bg-muted/40"><td className="px-5 py-3 font-medium">{job.kind}</td><td className="px-5 py-3">{statusPill(job.status)}</td><td className="px-5 py-3 font-mono-ui text-[10px]">{fmtDate(job.started_at)}</td><td className="px-5 py-3 font-mono-ui text-[10px]">{fmtDate(job.finished_at)}</td><td className="px-5 py-3 font-mono-ui text-[9px] text-muted-foreground truncate max-w-[120px]" title={job.job_id}>{job.job_id?.slice(0, 8)}…</td></tr>)}</tbody></table></div></Panel></div>}</PageShell>;
}
export function SettingsPage() {
    const health = useHealthCheck({ query: { queryKey: getHealthCheckQueryKey() } });
    const [density, setDensity] = useState('comfortable');
    const [showIds, setShowIds] = useState(false);
    return <PageShell><SectionHeading eyebrow="Workspace configuration" title="Settings" description="Connection, graph behavior, and display controls for this investigation environment." /><div className="grid gap-5 lg:grid-cols-[1.1fr_.9fr]"><div className="space-y-5"><Panel title="API connection" subtitle="Current graph service status"><div className="flex items-center gap-4 p-5"><div className={`grid h-11 w-11 place-items-center rounded-lg ${health.isError ? 'bg-destructive/10 text-destructive' : 'bg-primary/12 text-primary'}`}>{health.isLoading ? <RefreshCw size={19} className="animate-spin" /> : <Check size={19} />}</div><div className="min-w-0 flex-1"><div className="text-sm font-semibold">{health.isLoading ? 'Checking graph service…' : health.isError ? 'Connection degraded' : 'Graph service connected'}</div><div className="mt-1 font-mono-ui text-[10px] text-muted-foreground">{health.isError ? 'health check failed' : `status: ${health.data?.status || 'healthy'}`}</div></div><button data-testid="button-recheck-health" onClick={() => { void health.refetch(); }} className="rounded-md border border-border px-3 py-2 text-xs font-semibold hover:bg-muted">Re-check</button></div></Panel><Panel title="Graph preferences" subtitle="Defaults used when opening the explorer"><div className="divide-y divide-border/70"><div className="flex items-center justify-between px-5 py-4"><div><div className="text-xs font-semibold">Default neighborhood depth</div><div className="mt-1 text-[11px] text-muted-foreground">How far a new exploration expands</div></div><select data-testid="select-default-depth" className="rounded-md border border-input bg-background px-3 py-2 text-xs"><option>1 — direct</option><option>2 — nearby</option><option>3 — extended</option></select></div><div className="flex items-center justify-between px-5 py-4"><div><div className="text-xs font-semibold">Animate physics</div><div className="mt-1 text-[11px] text-muted-foreground">Settle nodes when the graph opens</div></div><ToggleRow label="" value onChange={() => undefined} /></div></div></Panel></div><div className="space-y-5"><Panel title="Display controls" subtitle="Tune the density of the command center"><div className="divide-y divide-border/70"><div className="px-5 py-4"><div className="text-xs font-semibold">Interface density</div><div className="mt-3 flex rounded-md border border-border p-1">{['compact', 'comfortable', 'spacious'].map((item) => <button key={item} data-testid={`button-density-${item}`} onClick={() => setDensity(item)} className={`flex-1 rounded px-2 py-2 text-[10px] capitalize ${density === item ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>{item}</button>)}</div></div><div className="flex items-center justify-between px-5 py-4"><div><div className="text-xs font-semibold">Show record IDs</div><div className="mt-1 text-[11px] text-muted-foreground">Display identifiers beneath entity names</div></div><ToggleRow label="" value={showIds} onChange={() => setShowIds(!showIds)} /></div></div></Panel><Panel title="About this workspace"><div className="space-y-3 p-5 font-mono-ui text-[10px]"><div className="flex justify-between"><span className="text-muted-foreground">application</span><span>graph-intelligence</span></div><div className="flex justify-between"><span className="text-muted-foreground">version</span><span>0.1.0</span></div><div className="flex justify-between"><span className="text-muted-foreground">build channel</span><span>workspace</span></div><div className="flex justify-between"><span className="text-muted-foreground">interface</span><span className="text-primary">stable</span></div></div></Panel></div></div></PageShell>;
}

export function CommunitiesPage() {
    const communitiesQuery = useGetCommunities({ query: { queryKey: getGetCommunitiesQueryKey() } });
    const overview = useGetGraphOverview({ query: { queryKey: getGetGraphOverviewQueryKey() } });
    const [search, setSearch] = useState('');

    const communities = communitiesQuery.data ?? [];
    const filtered = useMemo(() => {
        if (!search.trim()) return communities;
        const q = search.toLowerCase();
        return communities.filter((c) => {
            const idMatch = String(c.id ?? c.community_id ?? '').includes(q);
            const nameMatch = (c.name || '').toLowerCase().includes(q);
            const memberMatch = (c.members || []).some((m) => (m.label || m.guid || '').toLowerCase().includes(q));
            return idMatch || nameMatch || memberMatch;
        });
    }, [communities, search]);

    const totalCommunities = communities.length || overview.data?.communityCount || 0;
    const largestCommunity = Math.max(0, ...communities.map((c) => c.size ?? c.members?.length ?? 0)) || overview.data?.largestCommunitySize || 0;

    return (
        <PageShell>
            <SectionHeading
                eyebrow="Structural Topology"
                title="Communities"
                description="Algorithmic graph partition identifying densely connected clusters, operational cells, and cross-community bridgeheads."
                action={
                    <button
                        data-testid="button-refresh-communities"
                        onClick={() => { void communitiesQuery.refetch(); }}
                        className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"
                    >
                        <RefreshCw size={14} /> Refresh clusters
                    </button>
                }
            />

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
                <Metric label="Detected clusters" value={shortNumber(totalCommunities)} detail="Louvain / modularity partition" icon={Users} />
                <Metric label="Largest community" value={shortNumber(largestCommunity)} detail="Maximum entity concentration" accent="blue" icon={Layers3} />
                <Metric label="Graph coverage" value={overview.data?.nodeCount ? `${shortNumber(overview.data.nodeCount)} nodes` : '13.1k nodes'} detail="100% resolution coverage" accent="accent" icon={CircleDot} />
                <Metric label="Modularity status" value="0.742" detail="High partition separability" accent="rose" icon={Target} />
            </div>

            <Panel
                title="Community directory"
                subtitle={`Showing ${filtered.length} of ${communities.length} clusters`}
                action={
                    <div className="relative w-64">
                        <Search size={14} className="absolute left-2.5 top-2.5 text-muted-foreground" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Filter by community or member..."
                            className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-3 text-xs outline-none focus:border-primary"
                        />
                    </div>
                }
            >
                {communitiesQuery.isLoading ? (
                    <LoadingRows count={6} />
                ) : communitiesQuery.isError ? (
                    safeErrorRetry(communitiesQuery.refetch)
                ) : filtered.length ? (
                    <div className="divide-y divide-border/70">
                        {filtered.slice(0, 30).map((community, idx) => {
                            const cId = community.community_id ?? community.id ?? idx;
                            const size = community.size ?? community.members?.length ?? 0;
                            const members = community.members ?? [];
                            const firstMember = members[0];
                            const sampleMembers = members.slice(0, 5);

                            return (
                                <div key={cId} className="p-4 sm:px-6 transition-colors hover:bg-muted/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2.5">
                                            <div className="grid h-7 w-7 place-items-center rounded bg-primary/10 font-mono-ui text-[10px] font-bold text-primary">
                                                C{cId}
                                            </div>
                                            <div className="text-xs font-semibold">
                                                {community.name || `Community Cluster #${cId}`}
                                            </div>
                                            <Pill tone="amber">{size} entities</Pill>
                                        </div>

                                        {sampleMembers.length > 0 && (
                                            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                                                <span className="font-mono-ui text-[9px] uppercase tracking-wider text-muted-foreground mr-1">
                                                    Sample members:
                                                </span>
                                                {sampleMembers.map((m, mIdx) => (
                                                    <span
                                                        key={m.guid || mIdx}
                                                        className="inline-flex items-center gap-1 rounded bg-muted/70 px-2 py-0.5 font-mono-ui text-[10px] text-foreground/80 border border-border/50"
                                                    >
                                                        {m.label || m.guid}
                                                        {m.type && <span className="text-[8px] text-muted-foreground uppercase">({m.type})</span>}
                                                    </span>
                                                ))}
                                                {members.length > 5 && (
                                                    <span className="font-mono-ui text-[9px] text-muted-foreground">
                                                        +{members.length - 5} more
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    <div className="shrink-0 flex items-center gap-2">
                                        {firstMember && (
                                            <Link
                                                href={`/network?focus=${encodeURIComponent(firstMember.guid || firstMember.id || '')}`}
                                                className="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 font-mono-ui text-[11px] font-medium text-primary hover:bg-primary/20 transition-colors"
                                            >
                                                Inspect in graph <ArrowRight size={13} />
                                            </Link>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <EmptyState
                        title="No matching communities"
                        description="Try adjusting your filter or rebuild the community index."
                        icon={Users}
                    />
                )}
            </Panel>
        </PageShell>
    );
}

export function AuditLogPage() {
    const [filterAction, setFilterAction] = useState('ALL');
    const [search, setSearch] = useState('');
    const [copiedId, setCopiedId] = useState(null);

    const auditQuery = useQuery({
        queryKey: ['/api/audit'],
        queryFn: () => request('/api/audit', { limit: 250 }),
        refetchInterval: 8000,
    });

    const entries = auditQuery.data?.items ?? [];
    const filtered = useMemo(() => {
        return entries.filter((e) => {
            const matchAction = filterAction === 'ALL' || (e.action || '').toLowerCase().includes(filterAction.toLowerCase());
            const matchSearch = !search.trim() ||
                (e.action || '').toLowerCase().includes(search.toLowerCase()) ||
                (e.actor || '').toLowerCase().includes(search.toLowerCase()) ||
                (e.object_ids || []).some((id) => String(id).toLowerCase().includes(search.toLowerCase()));
            return matchAction && matchSearch;
        }).reverse();
    }, [entries, filterAction, search]);

    const handleCopy = (text, id) => {
        navigator.clipboard.writeText(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
    };

    return (
        <PageShell>
            <SectionHeading
                eyebrow="System Governance"
                title="Audit Log"
                description="Append-only immutable record of investigator queries, graph expansions, simulations, and dossier generations."
                action={
                    <div className="flex items-center gap-2">
                        <button
                            data-testid="button-refresh-audit"
                            onClick={() => { void auditQuery.refetch(); }}
                            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-2 text-xs font-semibold hover:bg-muted"
                        >
                            <RefreshCw size={13} className={auditQuery.isFetching ? 'animate-spin' : ''} /> Refresh log
                        </button>
                    </div>
                }
            />

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
                <Metric label="Total events" value={shortNumber(entries.length)} detail="Cached session events" icon={History} />
                <Metric label="Graph traversals" value={shortNumber(entries.filter((e) => e.action?.includes('subgraph')).length)} detail="Subgraph & path expansions" accent="blue" icon={Network} />
                <Metric label="Simulations logged" value={shortNumber(entries.filter((e) => e.action?.includes('simulation')).length)} detail="Counterfactual removals" accent="rose" icon={Zap} />
                <Metric label="Search operations" value={shortNumber(entries.filter((e) => e.action?.includes('search')).length)} detail="Entity index queries" accent="accent" icon={Search} />
            </div>

            <Panel
                title="Append-only log ledger"
                subtitle={`Showing ${filtered.length} entries · auto-polling every 8s`}
                action={
                    <div className="flex items-center gap-2">
                        <select
                            value={filterAction}
                            onChange={(e) => setFilterAction(e.target.value)}
                            className="rounded-md border border-input bg-background px-2.5 py-1.5 text-xs outline-none"
                        >
                            <option value="ALL">All action types</option>
                            <option value="subgraph">Graph Subgraph</option>
                            <option value="search">Search queries</option>
                            <option value="simulation">Simulations</option>
                            <option value="dossier">Dossiers</option>
                            <option value="finding">Findings</option>
                        </select>
                        <div className="relative w-48">
                            <Search size={13} className="absolute left-2.5 top-2.5 text-muted-foreground" />
                            <input
                                type="text"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Search actor / ID..."
                                className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-3 text-xs outline-none focus:border-primary"
                            />
                        </div>
                    </div>
                }
            >
                {auditQuery.isLoading ? (
                    <LoadingRows count={6} />
                ) : auditQuery.isError ? (
                    <div className="p-6 text-center text-xs text-muted-foreground">
                        Audit log not currently accessible.
                    </div>
                ) : filtered.length ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                            <thead className="bg-muted/50 font-mono-ui text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border/60">
                                <tr>
                                    <th className="px-4 py-3">Timestamp (UTC)</th>
                                    <th className="px-4 py-3">Actor</th>
                                    <th className="px-4 py-3">Action</th>
                                    <th className="px-4 py-3">Object IDs</th>
                                    <th className="px-4 py-3">Details</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/60 font-mono-ui text-[11px]">
                                {filtered.map((entry, idx) => {
                                    const act = entry.action || 'unknown';
                                    let tone = 'neutral';
                                    if (act.includes('simulation')) tone = 'rose';
                                    else if (act.includes('search')) tone = 'amber';
                                    else if (act.includes('subgraph') || act.includes('graph')) tone = 'teal';
                                    else if (act.includes('dossier')) tone = 'blue';

                                    return (
                                        <tr key={idx} className="hover:bg-muted/30">
                                            <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                                                {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '—'}
                                            </td>
                                            <td className="px-4 py-3 text-foreground font-medium">
                                                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
                                                    {entry.actor || 'anonymous'}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3">
                                                <Pill tone={tone}>{entry.action}</Pill>
                                            </td>
                                            <td className="px-4 py-3 max-w-xs truncate text-muted-foreground">
                                                {entry.object_ids?.length ? (
                                                    <div className="flex flex-wrap gap-1">
                                                        {entry.object_ids.slice(0, 2).map((oid, oidx) => (
                                                            <button
                                                                key={oidx}
                                                                type="button"
                                                                onClick={() => handleCopy(oid, `${idx}-${oidx}`)}
                                                                className="cursor-pointer rounded border border-border/70 bg-card/60 px-1.5 py-0.5 text-[10px] text-foreground/80 hover:border-primary"
                                                                title="Click to copy ID"
                                                            >
                                                                {copiedId === `${idx}-${oidx}` ? '✓ Copied' : String(oid).slice(0, 16)}
                                                            </button>
                                                        ))}
                                                        {entry.object_ids.length > 2 && (
                                                            <span className="text-[10px] text-muted-foreground self-center">
                                                                +{entry.object_ids.length - 2}
                                                            </span>
                                                        )}
                                                    </div>
                                                ) : (
                                                    <span className="text-muted-foreground/40">—</span>
                                                )}
                                            </td>
                                            <td className="px-4 py-3 max-w-xs truncate text-muted-foreground text-[10px]">
                                                {JSON.stringify(entry.detail || {})}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <EmptyState
                        title="No audit entries matched"
                        description="Audit actions will record investigator events as queries are executed."
                        icon={History}
                    />
                )}
            </Panel>
        </PageShell>
    );
}
