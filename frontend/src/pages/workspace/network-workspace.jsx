import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useGetGraphSummary, useGetGraphCommunity, useGetGraphNeighborhood } from '@/api/graph';
import { useEvidenceForNode } from '@/api/xai';
import {
    Network as NetworkIcon, Search, Maximize2, Minimize2, ZoomIn, ZoomOut,
    RefreshCw, Eye, EyeOff, Filter, Layers, Users, MapPin, Database,
    BarChart3, Clock, FileText, X, Pin, PinOff, Expand, Focus, Crosshair
} from 'lucide-react';
import { getEntityTypeColor, formatNumber } from '@/components/app-shell';
import { MassiveGraphCanvas } from '@/components/massive-graph-canvas';

/* ---------------------------------------------------------------------------
   VIEW MODES — NETWORK | FINANCIAL | COMMUNITIES | TEMPORAL | CROSS-CASE
--------------------------------------------------------------------------- */
const VIEW_MODES = [
    { id: 'network', label: 'NETWORK', icon: NetworkIcon },
    { id: 'communities', label: 'COMMUNITIES', icon: Users },
    { id: 'temporal', label: 'TEMPORAL', icon: Clock },
    { id: 'crosscase', label: 'CROSS-CASE', icon: Focus },
];

function PerfPanel({ stats, visible }) {
    if (!visible) return null;
    return (
        <div className="absolute bottom-14 right-36 z-20 bg-bg-panel/90 border border-border-subtle rounded p-2 text-[9px] font-mono text-fg-faint space-y-0.5">
            <div className="tp-section-label mb-1">GRAPH PERFORMANCE</div>
            {Object.entries(stats).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4">
                    <span>{k.replace(/_/g, ' ')}</span>
                    <span className="text-fg-secondary">{v}</span>
                </div>
            ))}
        </div>
    );
}

function CommunityCard({ community, onClick, selected }) {
    return (
        <button onClick={onClick}
            className={`tp-panel p-2.5 text-left w-full transition-colors ${selected ? 'ring-1 ring-primary' : 'hover:bg-bg-hover'}`}>
            <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold text-fg-primary">Community {community.id}</span>
                <span className="tp-badge tp-badge-neutral text-[8px]">{community.size}</span>
            </div>
            <div className="flex flex-wrap gap-1">
                {(community.members || []).slice(0, 5).map((m, i) => (
                    <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-bg-surface text-fg-secondary border border-border-subtle font-mono">
                        {typeof m === 'string' ? m : (m.label || m.id || String(m))}
                    </span>
                ))}
                {community.size > 5 && (
                    <span className="text-[9px] px-1 py-0.5 rounded bg-bg-surface text-fg-faint font-mono">+{community.size - 5}</span>
                )}
            </div>
        </button>
    );
}

function LoadingState() {
    return (
        <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col gap-2 text-fg-secondary">
                <div className="text-[11px] font-semibold tracking-wide text-fg-primary">BUILDING INVESTIGATION CONTEXT</div>
                <div className="text-[10px] text-fg-faint">Resolving entities…</div>
            </div>
        </div>
    );
}

function ErrorState({ message, onRetry }) {
    return (
        <div className="flex-1 flex items-center justify-center">
            <div className="tp-panel p-4 max-w-sm text-center space-y-3">
                <div className="text-[12px] font-semibold text-amber-400">NETWORK EXPANSION FAILED</div>
                <div className="text-[10px] text-fg-faint">{message}</div>
                <button onClick={onRetry} className="tp-btn tp-btn-primary text-[10px] h-6 px-3">RETRY</button>
            </div>
        </div>
    );
}

function TopConnections({ connections, onFocus }) {
    if (!connections || connections.length === 0) return null;
    return (
        <div className="absolute left-1/2 -translate-x-1/2 top-14 z-20 w-80 bg-bg-panel/95 border border-border-default rounded shadow-xl max-h-64 overflow-y-auto">
            <div className="px-3 py-1.5 border-b border-border-subtle text-[9px] font-semibold text-fg-faint">TOP CONNECTIONS</div>
            {connections.map((c, i) => (
                <button key={c.id} onClick={() => onFocus(c.id)}
                    className="w-full px-3 py-1.5 flex items-center gap-2 hover:bg-bg-hover text-left">
                    <span className="font-mono text-[9px] text-fg-faint">{i + 1}.</span>
                    <span className="w-2 h-2 rounded-full" style={{ background: getEntityTypeColor(c.type) }} />
                    <span className="text-[11px] text-fg-primary flex-1">{c.label}</span>
                    <span className="tp-badge tp-badge-blue text-[8px]">{c.type || '—'}</span>
                </button>
            ))}
        </div>
    );
}

/* ============================================================================
   NETWORK WORKSPACE — investigator-first, progressive, 100k-ready
============================================================================ */
export default function NetworkWorkspace() {
    const [selectedNode, setSelectedNode] = useState(null);
    const [pinnedNodes, setPinnedNodes] = useState([]);
    const [showFilters, setShowFilters] = useState(true);
    const [viewMode, setViewMode] = useState('network');
    const [layout, setLayout] = useState('force');
    const [depth, setDepth] = useState(1);
    const [expandedIds, setExpandedIds] = useState(new Set());
    const [expandedCommunities, setExpandedCommunities] = useState(new Set());
    const [showPerf, setShowPerf] = useState(false);
    const [stats, setStats] = useState({ nodes: 0, edges: 0, last_expansion_ms: 0 });

    const graphHostRef = useRef(null);
    const graphRef = useRef(null);

    // Level 0: graph summary (aggregates only — never the whole graph)
    const { data: summary, isLoading, error, refetch } = useGetGraphSummary();

    // Level 1: currently active community
    const [activeCommunity, setActiveCommunity] = useState(null);
    const communityQuery = useGetGraphCommunity(activeCommunity, 300);

    // Level 2: neighborhood expansion of the focus node
    const [focusNode, setFocusNode] = useState(null);
    const neighborhoodQuery = useGetGraphNeighborhood(focusNode, depth, 200);

    // selected entity evidence
    const { data: evidence } = useEvidenceForNode(selectedNode?.id);

    // ── build visible graph layer ──
    const visibleNodes = useMemo(() => {
        const nodeMap = new Map();

        // seed with top entities from summary (Level 0)
        (summary?.top_entities || []).forEach((e) => {
            nodeMap.set(String(e.id), {
                id: String(e.id),
                label: e.label || e.id,
                type: e.type,
                community: null,
                size: 6 + Math.sqrt(e.pagerank || 0) * 18,
                pagerank: e.pagerank || 0,
                priority: 2,
            });
        });

        // community members (Level 1)
        if (communityQuery.data) {
            (communityQuery.data.members || []).forEach((m) => {
                const key = String(m.id);
                nodeMap.set(key, {
                    id: key,
                    label: m.label || m.id,
                    type: m.type,
                    community: activeCommunity,
                    size: 4 + Math.sqrt(m.metrics?.pagerank || 0) * 14,
                    pagerank: m.metrics?.pagerank || 0,
                    priority: 1,
                });
            });
        }

        // neighborhoods (Level 2/3)
        if (neighborhoodQuery.data) {
            (neighborhoodQuery.data.nodes || []).forEach((n) => {
                const key = String(n.id);
                if (nodeMap.has(key)) return;
                nodeMap.set(key, {
                    id: key,
                    label: n.label || n.id,
                    type: n.type,
                    community: n.community_id ?? n.community,
                    size: 4 + Math.sqrt(n.metrics?.pagerank || 0) * 14,
                    pagerank: n.metrics?.pagerank || 0,
                    priority: 0,
                });
            });
        }

        return Array.from(nodeMap.values());
    }, [summary, communityQuery.data, neighborhoodQuery.data, activeCommunity]);

    const visibleEdges = useMemo(() => {
        const edgeKey = new Set();
        const edges = [];

        const addEdge = (source, target, type, extra = {}) => {
            const key = source < target ? `${source}|${target}` : `${target}|${source}`;
            if (edgeKey.has(key)) return;
            edgeKey.add(key);
            edges.push({ source: String(source), target: String(target), type, ...extra });
        };

        (communityQuery.data?.edges || []).forEach((e) => {
            addEdge(e.source, e.target, e.type, { color: '#38bdf8' });
        });

        (neighborhoodQuery.data?.edges || []).forEach((e) => {
            addEdge(e.source, e.target, e.type, {
                color: e.inferred ? '#a855f7' : '#64748b',
                dashed: Boolean(e.inferred),
            });
        });

        return edges;
    }, [communityQuery.data, neighborhoodQuery.data]);

    const graphNodeCount = visibleNodes.length;
    const graphEdgeCount = visibleEdges.length;

    // ── actions ──
    const handleExpand = useCallback((nodeId) => {
        const t0 = performance.now();
        setFocusNode(nodeId);
        setExpandedIds((prev) => new Set(prev).add(nodeId));
        setTimeout(() => {
            setStats((s) => ({ ...s, last_expansion_ms: (performance.now() - t0).toFixed(0) }));
        }, 100);
    }, []);

    const handleSelect = useCallback((id, node) => {
        setSelectedNode(node);
    }, []);

    const handleTogglePin = useCallback((nodeId) => {
        setPinnedNodes((prev) => {
            const has = prev.includes(nodeId);
            const next = has ? prev.filter((p) => p !== nodeId) : [...prev, nodeId];
            if (graphRef.current) graphRef.current.setPinnedList(next);
            return next;
        });
    }, []);

    const handleViewChange = useCallback((view) => {
        setStats((s) => ({ ...s, zoom: Number(view.zoom.toFixed(2)) }));
    }, []);

    const openEntity = useCallback((entityId) => {
        graphRef.current?.zoomTo(entityId, 4);
        handleExpand(entityId);
    }, [handleExpand]);

    const openCommunity = useCallback((communityId) => {
        setActiveCommunity(String(communityId));
        setExpandedCommunities((prev) => new Set(prev).add(String(communityId)));
    }, []);

    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Escape') setSelectedNode(null);
        if (e.key === ' ' && selectedNode?.id) {
            e.preventDefault();
            handleExpand(selectedNode.id);
        }
    }, [selectedNode, handleExpand]);

    useEffect(() => {
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [handleKeyDown]);

    const overlayRatio = useMemo(() => {
        if (!graphNodeCount) return 0;
        const total = summary?.node_count || graphNodeCount;
        return Math.min(1, graphNodeCount / (total || 1));
    }, [graphNodeCount, summary]);

    return (
        <div className="flex h-full overflow-hidden">
            {/* Left: filters */}
            {showFilters && (
                <div className="w-56 border-r border-border-subtle bg-bg-surface overflow-y-auto shrink-0">
                    <div className="px-3 py-2 border-b border-border-subtle">
                        <div className="tp-section-label mb-2">VIEW MODE</div>
                        <div className="space-y-1">
                            {VIEW_MODES.map((m) => (
                                <button key={m.id} onClick={() => setViewMode(m.id)}
                                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-[10px] transition-colors ${viewMode === m.id ? 'bg-bg-hover text-fg-primary' : 'text-fg-secondary hover:bg-bg-hover/60'}`}>
                                    <m.icon size={11} /> {m.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="px-3 py-2 border-b border-border-subtle">
                        <div className="tp-section-label mb-2">EXPANSION DEPTH</div>
                        <input type="range" min="1" max="3" value={depth}
                            onChange={e => setDepth(Number(e.target.value))}
                            className="w-full accent-primary" />
                        <div className="flex justify-between text-[9px] font-mono text-fg-faint mt-0.5">
                            <span>1 hop</span><span>{depth} hops</span><span>3</span>
                        </div>
                    </div>

                    <div className="px-3 py-2 border-b border-border-subtle">
                        <div className="tp-section-label mb-2">PINNED</div>
                        {pinnedNodes.length === 0 ? (
                            <div className="text-[9px] text-fg-faint">Select a node, then pin it.</div>
                        ) : (
                            <div className="space-y-1">
                                {pinnedNodes.map((id) => (
                                    <div key={id} className="flex items-center gap-1.5 text-[10px] font-mono text-fg-secondary">
                                        <Pin size={9} className="text-amber-400" />
                                        <span className="flex-1 truncate">{id}</span>
                                        <button onClick={() => handleTogglePin(id)} className="tp-btn tp-btn-ghost p-0"><X size={9} /></button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="px-3 py-2 border-b border-border-subtle">
                        <div className="tp-section-label mb-2">LOADED NEIGHBORHOODS</div>
                        {expandedIds.size === 0 ? (
                            <div className="text-[9px] text-fg-faint">No expansions yet.</div>
                        ) : (
                            <div className="space-y-1">
                                {Array.from(expandedIds).map((id) => (
                                    <button key={id} onClick={() => graphRef.current?.zoomTo(id, 4)}
                                        className="w-full flex items-center gap-1.5 text-[10px] font-mono text-fg-secondary hover:bg-bg-hover rounded px-1 py-0.5">
                                        <Crosshair size={9} className="text-primary" />
                                        <span className="flex-1 truncate">{id}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="px-3 py-2">
                        <button onClick={() => setShowPerf(v => !v)} className="tp-btn tp-btn-ghost text-[9px] h-5 px-2">
                            <BarChart3 size={9} /> {showPerf ? 'HIDE PERF' : 'SHOW PERF'}
                        </button>
                    </div>
                </div>
            )}

            {/* Center: graph canvas */}
            <div className="flex-1 flex flex-col min-w-0 relative">
                <div className="flex items-center gap-1 px-3 py-1.5 border-b border-border-subtle bg-bg-surface">
                    <button onClick={() => setShowFilters(v => !v)} className="tp-btn tp-btn-ghost text-[10px] h-6 px-2">
                        <Filter size={11} /> Filters
                    </button>
                    <button onClick={() => graphRef.current?.fit()} className="tp-btn tp-btn-ghost text-[10px] h-6 px-2">
                        <Maximize2 size={11} /> Fit
                    </button>
                    <div className="w-px h-4 bg-border-default mx-1" />
                    <span className="text-[9px] font-mono text-fg-faint">
                        {formatNumber(graphNodeCount)} loaded · {formatNumber(graphEdgeCount)} edges · space = EXPAND
                    </span>
                    <div className="flex-1" />
                    {summary && (
                        <span className="text-[9px] font-mono text-fg-faint">
                            TOTAL: {formatNumber(summary.node_count)} entities · {formatNumber(summary.community_count)} communities
                        </span>
                    )}
                </div>

                <div className="flex-1 relative graph-canvas-bg">
                    {isLoading ? (
                        <LoadingState />
                    ) : error ? (
                        <ErrorState message={error.message} onRetry={() => refetch()} />
                    ) : (
                        <>
                            <MassiveGraphCanvas
                                ref={graphRef}
                                nodes={visibleNodes}
                                edges={visibleEdges}
                                onSelect={handleSelect}
                                onViewChange={handleViewChange}
                                debug={showPerf}
                            />

                            {!activeCommunity && (summary?.top_communities?.length > 0) && (
                                <div className="absolute left-3 top-3 z-10 w-56 space-y-1.5 max-h-[70%] overflow-y-auto">
                                    <div className="tp-section-label text-[9px] mb-1">COMMUNITIES — CLICK TO EXPAND</div>
                                    {summary.top_communities.slice(0, 12).map((c) => (
                                        <CommunityCard key={c.id} community={c} onClick={() => openCommunity(c.id)} />
                                    ))}
                                </div>
                            )}

                            {activeCommunity && communityQuery.data && (
                                <div className="absolute left-3 top-3 z-10 tp-panel p-2.5 w-56 space-y-1.5">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-semibold text-fg-primary">COMMUNITY {activeCommunity}</span>
                                        <button onClick={() => setActiveCommunity(null)} className="tp-btn tp-btn-ghost p-0.5"><X size={10} /></button>
                                    </div>
                                    <div className="text-[9px] font-mono text-fg-faint">
                                        {formatNumber(communityQuery.data.member_count)} entities · {formatNumber(communityQuery.data.edge_count)} relationships
                                        {communityQuery.data.truncated ? ' · truncated' : ''}
                                    </div>
                                    <button onClick={() => { setActiveCommunity(null); graphRef.current?.fit(); }}
                                        className="tp-btn tp-btn-ghost text-[9px] h-5 px-2 w-full">
                                        <Minimize2 size={9} /> BACK TO OVERVIEW
                                    </button>
                                </div>
                            )}

                            {neighborhoodQuery.data && focusNode && (
                                <TopConnections
                                    connections={(neighborhoodQuery.data.nodes || [])
                                        .filter(n => String(n.id) !== String(focusNode))
                                        .slice(0, 10)}
                                    onFocus={(id) => graphRef.current?.zoomTo(id, 5)}
                                />
                            )}

                            <div className="absolute bottom-3 left-3 z-10 text-[9px] font-mono text-fg-faint bg-bg-panel/80 px-2 py-1 rounded border border-border-subtle">
                                <span>{formatNumber(graphNodeCount)} loaded</span>
                                <span className="mx-1">·</span>
                                <span>{formatNumber(summary?.node_count || 0)} total (progressive)</span>
                            </div>

                            {pinnedNodes.length > 0 && (
                                <div className="absolute bottom-3 right-3 z-10 text-[9px] font-mono bg-bg-panel/80 border border-border-subtle rounded p-1.5 space-y-0.5">
                                    <div className="tp-section-label text-[8px]">PINNED</div>
                                    {pinnedNodes.map((id) => (
                                        <div key={id} className="flex items-center gap-1 text-fg-secondary">
                                            <Pin size={8} className="text-amber-400" /> <span>{id}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <PerfPanel
                                visible={showPerf}
                                stats={{
                                    nodes_loaded: formatNumber(graphNodeCount),
                                    edges_loaded: formatNumber(graphEdgeCount),
                                    ...stats,
                                    layout: 'CACHED',
                                    overlay_ratio: overlayRatio.toFixed(3),
                                }}
                            />
                        </>
                    )}
                </div>

                {selectedNode && (
                    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 tp-panel px-3 py-2 flex items-center gap-3 max-w-xl w-5/6">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ background: getEntityTypeColor(selectedNode.type) }} />
                        <div className="min-w-0">
                            <div className="text-[11px] font-semibold text-fg-primary truncate">{selectedNode.label}</div>
                            <div className="text-[9px] font-mono text-fg-faint">{selectedNode.id} · {selectedNode.type || 'UNKNOWN'}</div>
                        </div>
                        <div className="flex-1" />
                        <div className="text-[9px] font-mono text-fg-secondary shrink-0">
                            {(evidence?.results || evidence?.items || evidence || []).length} evidence
                        </div>
                        <button onClick={() => handleExpand(selectedNode.id)} className="tp-btn tp-btn-primary text-[9px] h-6 px-2 shrink-0">
                            <Expand size={9} /> EXPAND
                        </button>
                        <button onClick={() => handleTogglePin(selectedNode.id)} className="tp-btn tp-btn-ghost text-[9px] h-6 px-2 shrink-0">
                            <Pin size={9} /> {pinnedNodes.includes(selectedNode.id) ? 'UNPIN' : 'PIN'}
                        </button>
                        <button onClick={() => setSelectedNode(null)} className="tp-btn tp-btn-ghost p-1 shrink-0">
                            <X size={11} />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
