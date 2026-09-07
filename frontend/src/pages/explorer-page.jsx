// src/pages/explorer-page.jsx
// Redesigned SentinelGraph Network Explorer Workspace
import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'wouter';
import {
    Activity,
    ChevronDown,
    ChevronUp,
    Crosshair,
    Database,
    Expand,
    ExternalLink,
    FileSearch,
    FileText,
    Ghost,
    Layers,
    Network,
    Route,
    ScanSearch,
    ShieldAlert,
    Sparkles,
    X,
    Zap,
} from 'lucide-react';
import { EmptyState, ErrorState, LoadingRows, Pill } from '@/components/graph-shell';
import { CytoscapeGraph } from '@/components/cytoscape-graph';
import { useSubgraph, usePaths } from '@/api/xai';
import { useGetGraphOverview, useGetGhosts } from '@/api/graph';
import {
    getSubgraphQueryKey,
    runNodeRemovalSimulation,
    useEvidenceForNode,
    useEvidenceTimeline,
    useGlobalSearch,
    useFindings,
} from '@/api/xai';
import { useQueryClient } from '@tanstack/react-query';

const ENTITY_TYPES = ['ALL', 'PERSON', 'ORGANIZATION', 'LOCATION', 'ACCOUNT', 'PHONE', 'VEHICLE'];

function fmt(n) {
    if (n === null || n === undefined) return '—';
    const num = Number(n);
    if (Number.isNaN(num)) return String(n);
    return num.toFixed(3);
}

export function ExplorerPage() {
    const [, navigate] = useLocation();
    const qc = useQueryClient();
    const overview = useGetGraphOverview();
    const ghosts = useGetGhosts();

    const [focusId, setFocusId] = useState(() => new URLSearchParams(window.location.search).get('focus'));
    const [depth, setDepth] = useState(2);
    const [maxNodes, setMaxNodes] = useState(400);
    const [typeFilter, setTypeFilter] = useState('ALL');
    const [searchQuery, setSearchQuery] = useState('');
    const [debouncedQuery, setDebouncedQuery] = useState('');
    const [selectedNode, setSelectedNode] = useState(null);
    const [selectedEdge, setSelectedEdge] = useState(null);
    const [simulation, setSimulation] = useState(null);
    const [simLoading, setSimLoading] = useState(false);
    const [simError, setSimError] = useState(null);
    const [bottomDrawerOpen, setBottomDrawerOpen] = useState(false);
    const [activeBottomTab, setActiveBottomTab] = useState('timeline');

    useEffect(() => {
        const t = window.setTimeout(() => setDebouncedQuery(searchQuery), 250);
        return () => window.clearTimeout(t);
    }, [searchQuery]);

    useEffect(() => {
        const requestedFocus = new URLSearchParams(window.location.search).get('focus');
        if (requestedFocus && requestedFocus !== focusId) setFocusId(requestedFocus);
    }, [focusId]);

    const globalSearch = useGlobalSearch(
        { q: debouncedQuery, limit: 8 },
        { query: { enabled: debouncedQuery.trim().length >= 2 } },
    );

    const subgraph = useSubgraph(
        focusId ? { node_id: focusId, depth, max_nodes: maxNodes } : null,
    );

    const allFindings = useFindings({ page: 1, page_size: 50 });

    // Pick default focus if unset
    useEffect(() => {
        if (focusId || !overview.data) return;
        const candidates = ghosts.data?.items ?? [];
        const firstGhost = candidates[0];
        if (firstGhost?.predicted_edges?.length) {
            setFocusId(firstGhost.predicted_edges[0].target);
        }
    }, [overview.data, ghosts.data, focusId]);

    const evidence = useEvidenceForNode(selectedNode?.id, {
        query: { enabled: Boolean(selectedNode?.id) },
    });

    const timeline = useEvidenceTimeline(selectedNode?.id, {
        query: { enabled: Boolean(selectedNode?.id) && bottomDrawerOpen },
    });

    const graphNodes = useMemo(() => subgraph.data?.nodes ?? [], [subgraph.data]);
    const graphEdges = useMemo(() => subgraph.data?.edges ?? [], [subgraph.data]);

    const filteredNodes = useMemo(() => {
        if (typeFilter === 'ALL') return graphNodes;
        return graphNodes.filter((n) => String(n.type).toUpperCase() === typeFilter);
    }, [graphNodes, typeFilter]);

    // Active Node Metrics & Relationships
    const currentNode = useMemo(() => {
        if (!selectedNode?.id) return null;
        return graphNodes.find((n) => n.id === selectedNode.id) || selectedNode;
    }, [graphNodes, selectedNode]);

    const relationshipCount = useMemo(() => {
        if (!selectedNode?.id) return 0;
        return graphEdges.filter(
            (e) => String(e.source) === String(selectedNode.id) || String(e.target) === String(selectedNode.id),
        ).length;
    }, [graphEdges, selectedNode]);

    const relatedFindings = useMemo(() => {
        if (!selectedNode?.id || !allFindings.data?.items) return [];
        const targetId = String(selectedNode.id).toLowerCase();
        return allFindings.data.items.filter((f) => {
            const subj = String(f.subject ?? '').toLowerCase();
            const text = String(f.finding_text ?? '').toLowerCase();
            return subj.includes(targetId) || text.includes(targetId);
        });
    }, [selectedNode, allFindings.data]);

    const handleNodeSelect = (nodeData) => {
        setSelectedEdge(null);
        if (!nodeData) {
            setSelectedNode(null);
            return;
        }
        setSelectedNode({
            id: nodeData.id,
            label: nodeData.label,
            nodeType: nodeData.nodeType,
            isGhost: nodeData.isGhost,
            pagerank: nodeData.pagerank,
            community: nodeData.community,
        });
    };

    const handleExpand = () => {
        if (!focusId && selectedNode?.id) {
            setFocusId(selectedNode.id);
            return;
        }
        setDepth((d) => Math.min(4, d + 1));
    };

    const handleSimulate = async () => {
        const target = selectedNode?.id ?? focusId;
        if (!target) return;
        setSimLoading(true);
        setSimError(null);
        try {
            const result = await runNodeRemovalSimulation({ node_id: target, depth: 2, include_reranking: true });
            setSimulation(result);
            await qc.invalidateQueries({ queryKey: getSubgraphQueryKey({ node_id: focusId, depth, max_nodes: maxNodes }) });
        } catch (cause) {
            setSimError(cause.message);
        } finally {
            setSimLoading(false);
        }
    };

    return (
        <div className="relative flex h-[calc(100dvh-52px)] w-full overflow-hidden bg-[#070b13]">
            {/* ── LEFT: COMPACT NAVIGATION & FILTERS ─────────────────────── */}
            <aside className="z-20 flex w-72 shrink-0 flex-col border-r border-[#1a2333] bg-[#090d16]/95 backdrop-blur-md">
                <div className="border-b border-[#1a2333] px-4 py-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 font-mono-ui text-[11px] font-bold tracking-wider text-cyan-400 uppercase">
                            <Network size={14} /> Explorer Scope
                        </div>
                        <span className="font-mono-ui text-[9px] text-[#64748b]">
                            {overview.data?.entities_count ?? '—'} Entities
                        </span>
                    </div>
                </div>

                <div className="flex-1 space-y-4 overflow-y-auto p-3.5 scrollbar-thin scrollbar-thumb-white/10">
                    <div>
                        <label className="mb-1 block font-mono-ui text-[9px] uppercase tracking-wider text-muted-foreground">
                            Focus Node / Search
                        </label>
                        <div className="relative">
                            <ScanSearch size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                            <input
                                data-testid="input-explorer-search"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Search entity or evidence…"
                                className="w-full rounded border border-[#1f293d] bg-[#0c121e] py-1.5 pl-8 pr-2.5 text-xs text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-cyan-500/60"
                            />
                        </div>
                        {debouncedQuery.length >= 2 && (
                            <div className="mt-1.5 max-h-40 overflow-y-auto rounded border border-[#1f293d] bg-[#0c121e] p-1 shadow-lg">
                                {globalSearch.isLoading && <div className="p-2 text-center text-xs text-muted-foreground">Searching…</div>}
                                {(globalSearch.data?.items ?? []).map((item) => (
                                    <button
                                        key={`${item.result_type}-${item.id}`}
                                        type="button"
                                        onClick={() => {
                                            setFocusId(item.id);
                                            setSelectedNode({ id: item.id, label: item.display_name, nodeType: item.entity_type });
                                            setSearchQuery('');
                                        }}
                                        className="flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-[#182334]"
                                    >
                                        <Pill tone={item.result_type === 'ghost' ? 'amber' : 'teal'}>{item.result_type}</Pill>
                                        <span className="truncate text-xs text-foreground">{item.display_name || item.id}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="space-y-2 rounded-md border border-[#182334] bg-[#0c121e]/60 p-2.5">
                        <div className="flex items-center justify-between font-mono-ui text-[9px] uppercase text-muted-foreground">
                            <span>Hops Depth: {depth}</span>
                            <input
                                type="range"
                                min="1"
                                max="4"
                                value={depth}
                                onChange={(e) => setDepth(Number(e.target.value))}
                                className="w-24 accent-cyan-400"
                            />
                        </div>
                        <div className="flex items-center justify-between font-mono-ui text-[9px] uppercase text-muted-foreground">
                            <span>Node Cap: {maxNodes}</span>
                            <input
                                type="range"
                                min="50"
                                max="1500"
                                step="50"
                                value={maxNodes}
                                onChange={(e) => setMaxNodes(Number(e.target.value))}
                                className="w-24 accent-cyan-400"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="mb-1.5 block font-mono-ui text-[9px] uppercase tracking-wider text-muted-foreground">
                            Entity Filter
                        </label>
                        <div className="flex flex-wrap gap-1">
                            {ENTITY_TYPES.map((t) => (
                                <button
                                    key={t}
                                    type="button"
                                    onClick={() => setTypeFilter(t)}
                                    className={`rounded px-2 py-0.5 font-mono-ui text-[9px] uppercase transition-colors ${
                                        typeFilter === t
                                            ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 font-bold'
                                            : 'bg-[#111827] text-muted-foreground hover:text-foreground border border-transparent'
                                    }`}
                                >
                                    {t}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-1.5 pt-1">
                        <button
                            type="button"
                            onClick={handleExpand}
                            className="flex items-center justify-center gap-1.5 rounded border border-[#1f293d] bg-[#0e1626] px-2 py-1.5 font-mono-ui text-[10px] text-foreground hover:border-cyan-500/50 hover:bg-[#142035]"
                        >
                            <Expand size={12} className="text-cyan-400" /> Expand
                        </button>
                        <button
                            type="button"
                            onClick={() => {
                                const target = selectedNode?.id ?? focusId;
                                if (target) {
                                    setFocusId(target);
                                    setSimulation(null);
                                }
                            }}
                            className="flex items-center justify-center gap-1.5 rounded border border-[#1f293d] bg-[#0e1626] px-2 py-1.5 font-mono-ui text-[10px] text-foreground hover:border-cyan-500/50 hover:bg-[#142035]"
                        >
                            <Crosshair size={12} className="text-cyan-400" /> Focus Center
                        </button>
                    </div>

                    <div className="rounded-md border border-[#1e293b] bg-[#0a0f1d] p-2.5">
                        <div className="mb-2 flex items-center justify-between">
                            <span className="font-mono-ui text-[9px] font-bold uppercase text-amber-400">Sandbox Impact</span>
                            <Zap size={12} className="text-amber-400" />
                        </div>
                        <button
                            type="button"
                            onClick={handleSimulate}
                            disabled={simLoading || !(selectedNode?.id ?? focusId)}
                            className="w-full rounded bg-amber-500/15 py-1.5 font-mono-ui text-[10px] font-bold uppercase text-amber-400 border border-amber-500/30 hover:bg-amber-500/25 disabled:opacity-40 transition-colors"
                        >
                            {simLoading ? 'Simulating…' : 'Simulate Node Removal'}
                        </button>
                        {simulation && (
                            <div className="mt-2 space-y-1 font-mono-ui text-[9px] text-muted-foreground border-t border-[#1e293b] pt-2">
                                <div className="flex justify-between">
                                    <span>Fragmentation:</span>
                                    <span className="text-white font-bold">{fmt(simulation.fragmentation_score)}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Affected Nodes:</span>
                                    <span className="text-white font-bold">{simulation.affected_node_count}</span>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setSimulation(null)}
                                    className="mt-1 w-full text-center text-[8px] uppercase text-cyan-400 hover:underline"
                                >
                                    Clear Simulation
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </aside>

            {/* ── CENTER: LARGE GRAPH CANVAS ─────────────────────────────── */}
            <main className="relative flex-1 h-full w-full overflow-hidden">
                {subgraph.isLoading && (
                    <div className="grid h-full place-items-center bg-[#070b13]">
                        <div className="flex flex-col items-center gap-3">
                            <span className="relative flex h-5 w-5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-60" />
                                <span className="relative inline-flex h-5 w-5 rounded-full bg-cyan-500" />
                            </span>
                            <span className="font-mono-ui text-xs text-muted-foreground uppercase tracking-wider">
                                Resolving Subgraph Topology…
                            </span>
                        </div>
                    </div>
                )}
                {subgraph.isError && (
                    <div className="grid h-full place-items-center bg-[#070b13]">
                        <ErrorState onRetry={() => subgraph.refetch()} />
                    </div>
                )}
                {subgraph.data && (
                    <CytoscapeGraph
                        nodes={filteredNodes}
                        edges={graphEdges}
                        onNodeSelect={handleNodeSelect}
                        onEdgeSelect={(edge) => {
                            setSelectedNode(null);
                            setSelectedEdge(edge);
                        }}
                        focusNodeId={selectedNode?.id ?? focusId}
                        simulation={simulation}
                        selectedNode={selectedNode}
                    />
                )}
                {!subgraph.data && !subgraph.isLoading && (
                    <div className="grid h-full place-items-center bg-[#070b13]">
                        <EmptyState
                            title="No Graph Loaded"
                            description="Select an entity or initiate search to render neighborhood topology."
                            icon={Sparkles}
                        />
                    </div>
                )}
            </main>

            {/* ── RIGHT: CONTEXTUAL ENTITY INSPECTOR ──────────────────────── */}
            {selectedNode && (
                <aside
                    className="z-30 flex w-80 shrink-0 flex-col border-l border-[#1a2333] bg-[#090d16]/95 backdrop-blur-md transition-transform duration-300 animate-in slide-in-from-right"
                    data-testid="panel-entity-inspector"
                >
                    <div className="flex items-center justify-between border-b border-[#1a2333] px-4 py-3">
                        <div className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
                            <h2 className="font-mono-ui text-[11px] font-bold uppercase tracking-wider text-white">
                                Entity Inspector
                            </h2>
                        </div>
                        <button
                            type="button"
                            onClick={() => setSelectedNode(null)}
                            className="rounded p-1 text-muted-foreground hover:bg-[#182334] hover:text-white"
                        >
                            <X size={14} />
                        </button>
                    </div>

                    <div className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-white/10">
                        <div>
                            <div className="flex items-center gap-2">
                                <Pill tone={selectedNode.isGhost ? 'amber' : 'teal'}>
                                    {selectedNode.isGhost ? 'GHOST CANDIDATE' : selectedNode.nodeType || 'ENTITY'}
                                </Pill>
                            </div>
                            <h3 className="mt-2 text-sm font-bold text-white break-words">
                                {selectedNode.label || selectedNode.id}
                            </h3>
                            <div className="mt-0.5 font-mono-ui text-[10px] text-muted-foreground/60 break-all">
                                ID: {selectedNode.id}
                            </div>
                        </div>

                        <div className="rounded-md border border-[#1a2436] bg-[#0c121e] p-3">
                            <div className="mb-2 font-mono-ui text-[9px] font-bold uppercase tracking-wider text-cyan-400">
                                Topological Centrality
                            </div>
                            <div className="space-y-2">
                                <MetricLine label="PageRank" value={fmt(currentNode?.metrics?.pagerank ?? selectedNode?.pagerank)} />
                                <MetricLine label="Betweenness" value={fmt(currentNode?.metrics?.betweenness_centrality)} />
                                <MetricLine label="Degree Centrality" value={fmt(currentNode?.metrics?.degree_centrality)} />
                                <MetricLine label="Community Cluster" value={currentNode?.community_id ?? currentNode?.community ?? selectedNode?.community ?? '—'} />
                                <MetricLine label="Relationship Count" value={relationshipCount} />
                                <MetricLine label="Evidence Count" value={evidence.data?.total ?? 0} />
                            </div>
                        </div>

                        <div className="rounded-md border border-[#1a2436] bg-[#0c121e] p-3">
                            <div className="mb-2 flex items-center justify-between">
                                <span className="font-mono-ui text-[9px] font-bold uppercase tracking-wider text-cyan-400">
                                    Linked Findings ({relatedFindings.length})
                                </span>
                                <ShieldAlert size={12} className="text-cyan-400" />
                            </div>
                            {relatedFindings.length === 0 ? (
                                <div className="text-[11px] text-muted-foreground/60">No specific XAI findings flag this node.</div>
                            ) : (
                                <div className="space-y-2">
                                    {relatedFindings.slice(0, 3).map((f) => (
                                        <div key={f.finding_id} className="rounded border border-[#182334] bg-[#090d16] p-2 text-xs">
                                            <div className="flex items-center justify-between gap-1 mb-1">
                                                <Pill tone={f.status === 'CONTRADICTED' ? 'rose' : 'amber'}>{f.status || 'FINDING'}</Pill>
                                                <span className="font-mono-ui text-[9px] text-cyan-400">
                                                    {((f.confidence ?? 0) * 100).toFixed(0)}% conf
                                                </span>
                                            </div>
                                            <p className="line-clamp-2 text-[11px] text-foreground/85">{f.finding_text}</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-2 pt-2">
                            <button
                                type="button"
                                onClick={() => navigate(`/dossiers?subject=${encodeURIComponent(selectedNode.id)}`)}
                                className="flex items-center justify-center gap-1.5 rounded border border-[#1e293b] bg-[#0d1524] py-2 text-[11px] font-semibold text-white hover:border-cyan-500/50"
                            >
                                <FileText size={12} className="text-cyan-400" /> Open Dossier
                            </button>
                            <button
                                type="button"
                                onClick={() => navigate(`/evidence?focus=${encodeURIComponent(selectedNode.id)}`)}
                                className="flex items-center justify-center gap-1.5 rounded border border-[#1e293b] bg-[#0d1524] py-2 text-[11px] font-semibold text-white hover:border-cyan-500/50"
                            >
                                <FileSearch size={12} className="text-cyan-400" /> Provenance
                            </button>
                        </div>
                    </div>
                </aside>
            )}

            {/* ── BOTTOM: COLLAPSIBLE ANALYTICAL / EVIDENCE DRAWER ───────── */}
            <div
                className={`absolute bottom-0 left-72 right-0 z-20 border-t border-[#1a2333] bg-[#080c14]/95 backdrop-blur-md transition-all duration-300 ${
                    bottomDrawerOpen ? 'h-52' : 'h-8'
                }`}
            >
                <div className="flex h-8 items-center justify-between px-4 border-b border-[#141c2b]">
                    <div className="flex items-center gap-4">
                        <button
                            type="button"
                            onClick={() => setBottomDrawerOpen(!bottomDrawerOpen)}
                            className="flex items-center gap-1.5 font-mono-ui text-[10px] font-bold uppercase tracking-wider text-cyan-400 hover:text-white"
                        >
                            {bottomDrawerOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                            Evidence & Timeline Intelligence
                        </button>
                        {bottomDrawerOpen && (
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    onClick={() => setActiveBottomTab('timeline')}
                                    className={`font-mono-ui text-[9px] uppercase px-2 py-0.5 rounded ${
                                        activeBottomTab === 'timeline' ? 'bg-cyan-500/20 text-cyan-400' : 'text-muted-foreground'
                                    }`}
                                >
                                    Timeline
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setActiveBottomTab('evidence')}
                                    className={`font-mono-ui text-[9px] uppercase px-2 py-0.5 rounded ${
                                        activeBottomTab === 'evidence' ? 'bg-cyan-500/20 text-cyan-400' : 'text-muted-foreground'
                                    }`}
                                >
                                    Evidence Index
                                </button>
                            </div>
                        )}
                    </div>
                    <span className="font-mono-ui text-[9px] text-[#556784]">
                        {selectedNode ? `Context: ${selectedNode.label || selectedNode.id}` : 'Select a node for timeline'}
                    </span>
                </div>

                {bottomDrawerOpen && (
                    <div className="h-[calc(100%-32px)] overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-white/10">
                        {activeBottomTab === 'timeline' ? (
                            timeline.isLoading ? (
                                <LoadingRows count={3} />
                            ) : (timeline.data?.items ?? []).length === 0 ? (
                                <div className="text-center text-xs text-muted-foreground py-4">No timestamped evidence records for current focus.</div>
                            ) : (
                                <div className="space-y-1.5">
                                    {(timeline.data?.items ?? []).map((t) => (
                                        <div key={t.evidence_id} className="flex items-center justify-between rounded border border-[#141e2e] bg-[#0b101a] px-3 py-1.5 text-xs">
                                            <div className="flex items-center gap-3">
                                                <span className="font-mono-ui text-[10px] text-cyan-400">{t.timestamp || 'NO TS'}</span>
                                                <Pill tone="neutral">{t.source_type}</Pill>
                                                <span className="text-foreground/90 truncate max-w-lg">{t.text_excerpt}</span>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => navigate(`/evidence?focus=${encodeURIComponent(t.evidence_id)}`)}
                                                className="font-mono-ui text-[9px] text-cyan-400 hover:underline"
                                            >
                                                TRACE →
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )
                        ) : (
                            <div className="space-y-1.5">
                                {(evidence.data?.items ?? []).map((e) => (
                                    <div key={e.evidence_id} className="flex items-center justify-between rounded border border-[#141e2e] bg-[#0b101a] px-3 py-1.5 text-xs">
                                        <div className="flex items-center gap-3">
                                            <Pill tone="neutral">{e.source_type}</Pill>
                                            <span className="text-foreground/90 truncate max-w-lg">{e.text_excerpt}</span>
                                        </div>
                                        <span className="font-mono-ui text-[9px] text-muted-foreground">{e.source_record_id}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function MetricLine({ label, value }) {
    return (
        <div className="flex items-center justify-between border-b border-[#141f30] pb-1 last:border-0 font-mono-ui text-[10px]">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-semibold text-white">{value}</span>
        </div>
    );
}