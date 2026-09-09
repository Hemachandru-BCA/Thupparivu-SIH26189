import { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { useGetGraphOverview, useGetGhosts, useGetGraphNetwork, useGetCentrality, useGetCommunities } from '@/api/graph';
import { useFindings } from '@/api/xai';
import {
    Users, Network as NetworkIcon, Clock, FileText, Brain, AlertTriangle,
    ArrowRight, TrendingUp, Eye, MapPin, ChevronRight, Activity, Layers
} from 'lucide-react';
import { formatNumber, getConfidenceColor, getEntityTypeColor } from '@/components/app-shell';

/* ── Stat card ── */
function StatCard({ label, value, color }) {
    return (
        <div className="tp-panel p-3 flex flex-col gap-1">
            <div className="tp-grid-stat-label">{label}</div>
            <div className="tp-grid-stat-value" style={color ? { color } : undefined}>
                {value != null ? formatNumber(value) : '—'}
            </div>
        </div>
    );
}

/* ── Priority finding card ── */
function FindingCard({ finding }) {
    const conf = finding.confidence || 0;
    const confColor = getConfidenceColor(conf);
    return (
        <Link href={`/findings/${finding.finding_id || finding.id}`}>
            <div className="tp-panel p-3 cursor-pointer hover:border-border-default transition-colors">
                <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="font-mono text-[10px] text-fg-faint">{finding.finding_id || finding.id}</span>
                    <span className="font-mono text-[11px] font-semibold" style={{color: confColor}}>
                        {(conf * 100).toFixed(0)}%
                    </span>
                </div>
                <div className="text-[11px] text-fg-primary font-medium mb-1 leading-tight">
                    {finding.subject_label || finding.subject_id || 'Unknown subject'}
                </div>
                <div className="text-[10px] text-fg-faint leading-snug line-clamp-2">
                    {finding.finding_type || finding.method || 'Analysis finding'}
                </div>
                <div className="mt-2">
                    <div className="tp-confidence-bar">
                        <div className="tp-confidence-fill" style={{ width: `${conf * 100}%`, background: confColor }} />
                    </div>
                </div>
            </div>
        </Link>
    );
}

/* ── Ghost candidate card ── */
function GhostCard({ ghost }) {
    const conf = ghost.confidence || 0;
    const confColor = getConfidenceColor(conf);
    return (
        <div className="tp-panel p-3">
            <div className="flex items-start justify-between gap-2 mb-1">
                <span className="font-mono text-[10px] text-fg-faint">{ghost.ghost_id}</span>
                <span className="font-mono text-[11px] font-semibold" style={{color: confColor}}>
                    {(conf * 100).toFixed(0)}%
                </span>
            </div>
            <div className="text-[11px] text-fg-primary font-medium mb-0.5">
                {ghost.label || 'Unknown candidate'}
            </div>
            <div className="text-[10px] text-fg-faint">
                {ghost.subtype || 'Structural anomaly'}
            </div>
            {ghost.between_communities?.length > 0 && (
                <div className="flex gap-1 mt-1.5">
                    {ghost.between_communities.slice(0, 3).map(c => (
                        <span key={c} className="tp-badge tp-badge-neutral" style={{fontSize: '8px', padding: '0 4px'}}>
                            C{c}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── Network mini visualization (SVG) ── */
function NetworkMiniViz({ nodes, edges }) {
    if (!nodes?.length) return <div className="h-full flex items-center justify-center text-[10px] text-fg-faint">No network data</div>;

    const width = 500;
    const height = 280;
    const padding = 30;

    // Use simple force-directed layout approximation
    const positioned = useMemo(() => {
        const map = new Map();
        const n = Math.min(nodes.length, 60);
        for (let i = 0; i < n; i++) {
            const node = nodes[i];
            const angle = (i / n) * Math.PI * 2;
            const radius = 80 + (node.metrics?.pagerank || 0.1) * 120;
            map.set(node.id, {
                ...node,
                x: width / 2 + Math.cos(angle) * radius + (Math.sin(i * 7) * 20),
                y: height / 2 + Math.sin(angle) * radius + (Math.cos(i * 5) * 20),
            });
        }
        return map;
    }, [nodes]);

    const visibleEdges = useMemo(() => {
        if (!edges) return [];
        return edges.filter(e => positioned.has(e.source) && positioned.has(e.target)).slice(0, 100);
    }, [edges, positioned]);

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
            {visibleEdges.map((e, i) => {
                const s = positioned.get(e.source);
                const t = positioned.get(e.target);
                if (!s || !t) return null;
                return (
                    <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                        stroke={e.inferred ? 'hsl(270 55% 58% / 0.3)' : 'hsl(220 10% 30%)'}
                        strokeWidth={0.5}
                        strokeDasharray={e.inferred ? '4 2' : undefined} />
                );
            })}
            {Array.from(positioned.values()).map(node => {
                const size = 3 + (node.metrics?.pagerank || 0.1) * 12;
                return (
                    <circle key={node.id} cx={node.x} cy={node.y} r={size}
                        fill={getEntityTypeColor(node.type || node.label)}
                        opacity={0.85} stroke="hsl(220 16% 6%)" strokeWidth={0.5} />
                );
            })}
        </svg>
    );
}

/* ──────────────────────────────────────────────────────────────
   INVESTIGATION DESK
   ────────────────────────────────────────────────────────────── */

export default function InvestigationDesk() {
    const { data: overview, isLoading: overviewLoading } = useGetGraphOverview();
    const { data: ghosts } = useGetGhosts();
    const { data: findings } = useFindings();
    const { data: graphData } = useGetGraphNetwork({ center: null, depth: 0, limit: 500 });
    const { data: centralityData } = useGetCentrality();

    const ghostList = ghosts?.results || ghosts?.items || ghosts || [];
    const findingsList = findings?.results || findings?.items || findings || [];
    const nodes = graphData?.nodes || [];
    const edges = graphData?.edges || [];
    const centralityList = centralityData?.results || centralityData?.items || centralityData || [];

    const stats = {
        entity_count: overview?.entities_count,
        triplet_count: overview?.triplets_count,
        community_count: overview?.metadata?.num_communities,
        ghost_count: overview?.ghost_predictions_count ?? ghostList.length,
        event_count: overview?.events_count,
    };

    // Sort findings by confidence
    const topFindings = useMemo(() => {
        return [...findingsList]
            .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
            .slice(0, 5);
    }, [findingsList]);

    // Top ghosts by confidence
    const topGhosts = useMemo(() => {
        return [...ghostList]
            .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
            .slice(0, 4);
    }, [ghostList]);

    // Top centrality — use centrality API results if available, else fall back to nodes
    const topCentral = useMemo(() => {
        const source = centralityList.length > 0 ? centralityList : nodes;
        return [...source]
            .sort((a, b) => (b.degree || b.metrics?.betweenness_centrality || 0) - (a.degree || a.metrics?.betweenness_centrality || 0))
            .slice(0, 6);
    }, [centralityList, nodes]);

    if (overviewLoading) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
                <span className="text-[10px] font-mono text-fg-faint uppercase tracking-wider">Loading investigation...</span>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto">
            <div className="max-w-[1600px] mx-auto p-4 space-y-4 animate-fade-in">

                {/* ── Case metadata header ── */}
                <div className="tp-panel">
                    <div className="px-4 py-3 flex items-center gap-6 border-b border-border-subtle">
                        <div>
                            <div className="tp-section-label mb-0.5">CASE</div>
                            <div className="text-[13px] font-semibold text-fg-primary">SIH-26189 / CASE-00421</div>
                        </div>
                        <div className="w-px h-8 bg-border-default" />
                        <div>
                            <div className="tp-section-label mb-0.5">INVESTIGATION</div>
                            <div className="text-[12px] text-fg-secondary">Criminal Network Analysis</div>
                        </div>
                        <div className="w-px h-8 bg-border-default" />
                        <div>
                            <div className="tp-section-label mb-0.5">DATASET</div>
                            <div className="text-[12px] text-fg-secondary">Synthetic Investigation 07</div>
                        </div>
                        <div className="w-px h-8 bg-border-default" />
                        <div>
                            <div className="tp-section-label mb-0.5">MODEL RUN</div>
                            <div className="font-mono text-[12px] text-fg-secondary">MR-0247</div>
                        </div>
                        <div className="w-px h-8 bg-border-default" />
                        <div>
                            <div className="tp-section-label mb-0.5">STATUS</div>
                            <div className="flex items-center gap-1.5">
                                <div className="tp-status-dot bg-green" />
                                <span className="text-[12px] text-green font-medium">Analysis current</span>
                            </div>
                        </div>
                    </div>

                    {/* ── Quantitative summary ── */}
                    <div className="grid grid-cols-6 divide-x divide-border-subtle">
                        <div className="p-3 text-center">
                            <div className="tp-grid-stat-label">ENTITIES</div>
                            <div className="tp-grid-stat-value">{formatNumber(stats.entity_count)}</div>
                        </div>
                        <div className="p-3 text-center">
                            <div className="tp-grid-stat-label">RELATIONSHIPS</div>
                            <div className="tp-grid-stat-value">{formatNumber(stats.triplet_count)}</div>
                        </div>
                        <div className="p-3 text-center">
                            <div className="tp-grid-stat-label">EVENTS</div>
                            <div className="tp-grid-stat-value">{formatNumber(stats.event_count || 0)}</div>
                        </div>
                        <div className="p-3 text-center">
                            <div className="tp-grid-stat-label">COMMUNITIES</div>
                            <div className="tp-grid-stat-value">{formatNumber(stats.community_count)}</div>
                        </div>
                        <div className="p-3 text-center">
                            <div className="tp-grid-stat-label">ANOMALIES</div>
                            <div className="tp-grid-stat-value text-amber">{formatNumber(stats.ghost_count)}</div>
                        </div>
                        <div className="p-3 text-center">
                            <div className="tp-grid-stat-label">FINDINGS</div>
                            <div className="tp-grid-stat-value text-purple">{formatNumber(findingsList.length)}</div>
                        </div>
                    </div>
                </div>

                {/* ── Main workspace: Network + Findings ── */}
                <div className="grid grid-cols-12 gap-4" style={{minHeight: '420px'}}>

                    {/* LEFT: Network visualization (7 columns) */}
                    <div className="col-span-7 tp-panel flex flex-col">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <NetworkIcon size={12} className="text-primary" />
                                <span className="text-[11px] font-semibold text-fg-primary">NETWORK</span>
                                <span className="text-[10px] text-fg-faint font-mono">
                                    {formatNumber(nodes.length)} nodes · {formatNumber(edges.length)} edges
                                </span>
                            </div>
                            <Link href="/network">
                                <button className="tp-btn tp-btn-ghost text-[10px] h-5">
                                    Open workspace <ChevronRight size={10} />
                                </button>
                            </Link>
                        </div>
                        <div className="flex-1 graph-canvas-bg overflow-hidden" style={{minHeight: 300}}>
                            <NetworkMiniViz nodes={nodes} edges={edges} />
                        </div>
                    </div>

                    {/* RIGHT: Priority findings + Anomalies (5 columns) */}
                    <div className="col-span-5 flex flex-col gap-4">

                        {/* Priority Findings */}
                        <div className="tp-panel flex-1 flex flex-col">
                            <div className="tp-panel-header">
                                <div className="flex items-center gap-2">
                                    <Brain size={12} className="text-purple" />
                                    <span className="text-[11px] font-semibold text-fg-primary">PRIORITY FINDINGS</span>
                                    <span className="tp-badge tp-badge-purple">{findingsList.length}</span>
                                </div>
                                <Link href="/findings">
                                    <button className="tp-btn tp-btn-ghost text-[10px] h-5">
                                        View all <ChevronRight size={10} />
                                    </button>
                                </Link>
                            </div>
                            <div className="flex-1 overflow-y-auto p-2 space-y-2">
                                {topFindings.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-center py-6">
                                        <Brain size={16} className="text-fg-faint mb-2" />
                                        <span className="text-[10px] text-fg-faint font-mono uppercase">NO HYPOTHESES DETECTED</span>
                                        <span className="text-[10px] text-fg-faint mt-1">Run analysis to generate findings</span>
                                    </div>
                                ) : topFindings.map(f => (
                                    <FindingCard key={f.finding_id || f.id} finding={f} />
                                ))}
                            </div>
                        </div>

                        {/* Anomalies */}
                        <div className="tp-panel flex-1 flex flex-col">
                            <div className="tp-panel-header">
                                <div className="flex items-center gap-2">
                                    <AlertTriangle size={12} className="text-amber" />
                                    <span className="text-[11px] font-semibold text-fg-primary">ANOMALIES</span>
                                    <span className="tp-badge tp-badge-amber">{ghostList.length}</span>
                                </div>
                                <Link href="/ghosts">
                                    <button className="tp-btn tp-btn-ghost text-[10px] h-5">
                                        View all <ChevronRight size={10} />
                                    </button>
                                </Link>
                            </div>
                            <div className="flex-1 overflow-y-auto p-2 space-y-2">
                                {topGhosts.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-center py-6">
                                        <AlertTriangle size={16} className="text-fg-faint mb-2" />
                                        <span className="text-[10px] text-fg-faint font-mono uppercase">NO ANOMALIES DETECTED</span>
                                        <span className="text-[10px] text-fg-faint mt-1">No structural anomalies found in current dataset</span>
                                    </div>
                                ) : topGhosts.map(g => (
                                    <GhostCard key={g.ghost_id} ghost={g} />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* ── Bottom row: Centrality + Network changes ── */}
                <div className="grid grid-cols-12 gap-4">

                    {/* Centrality Leaders */}
                    <div className="col-span-5 tp-panel">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <TrendingUp size={12} className="text-primary" />
                                <span className="text-[11px] font-semibold text-fg-primary">CENTRALITY LEADERS</span>
                            </div>
                            <Link href="/analytics">
                                <button className="tp-btn tp-btn-ghost text-[10px] h-5">Full analysis <ChevronRight size={10} /></button>
                            </Link>
                        </div>
                        <div className="overflow-y-auto" style={{maxHeight: 220}}>
                            <table className="tp-table">
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        <th>Entity</th>
                                        <th>Type</th>
                                        <th>Betweenness</th>
                                        <th>Degree</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {topCentral.map((node, i) => (
                                        <tr key={node.id}>
                                            <td className="font-mono text-fg-faint">{i + 1}</td>
                                            <td className="text-fg-primary font-medium">{node.name || node.id}</td>
                                            <td>
                                                <span className="tp-badge tp-badge-blue">{node.type || node.label}</span>
                                            </td>
                                            <td className="font-mono text-fg-secondary">
                                                {(node.metrics?.betweenness_centrality || 0).toFixed(3)}
                                            </td>
                                            <td className="font-mono text-fg-secondary">{node.degree || 0}</td>
                                        </tr>
                                    ))}
                                    {topCentral.length === 0 && (
                                        <tr><td colSpan={5} className="text-center text-fg-faint py-4">No centrality data available</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Network Changes / Community Summary */}
                    <div className="col-span-7 tp-panel">
                        <div className="tp-panel-header">
                            <div className="flex items-center gap-2">
                                <Layers size={12} className="text-cyan" />
                                <span className="text-[11px] font-semibold text-fg-primary">COMMUNITY STRUCTURE</span>
                            </div>
                            <Link href="/communities">
                                <button className="tp-btn tp-btn-ghost text-[10px] h-5">Details <ChevronRight size={10} /></button>
                            </Link>
                        </div>
                        <div className="p-4">
                            <CommunitySummary nodes={nodes} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ── Community summary ── */
function CommunitySummary({ nodes }) {
    const communities = useMemo(() => {
        const map = new Map();
        nodes.forEach(n => {
            const cid = n.community_id ?? 'unknown';
            if (!map.has(cid)) map.set(cid, { id: cid, count: 0, types: new Map() });
            const c = map.get(cid);
            c.count++;
            const t = n.type || n.label || 'unknown';
            c.types.set(t, (c.types.get(t) || 0) + 1);
        });
        return Array.from(map.values()).sort((a, b) => b.count - a.count).slice(0, 12);
    }, [nodes]);

    if (communities.length === 0) {
        return <span className="text-[10px] text-fg-faint">No community data available</span>;
    }

    const maxCount = Math.max(...communities.map(c => c.count), 1);

    return (
        <div className="grid grid-cols-4 gap-3">
            {communities.map(c => (
                <div key={c.id} className="tp-panel p-2.5">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono text-[10px] text-fg-muted">C{c.id}</span>
                        <span className="font-mono text-[11px] text-fg-primary font-semibold">{c.count}</span>
                    </div>
                    {/* Bar */}
                    <div className="tp-confidence-bar mb-1.5">
                        <div className="tp-confidence-fill" style={{
                            width: `${(c.count / maxCount) * 100}%`,
                            background: 'hsl(var(--primary))'
                        }} />
                    </div>
                    {/* Type breakdown */}
                    <div className="flex flex-wrap gap-1">
                        {Array.from(c.types.entries()).slice(0, 3).map(([type, count]) => (
                            <span key={type} className="text-[8px] font-mono text-fg-faint">
                                {type}:{count}
                            </span>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}
