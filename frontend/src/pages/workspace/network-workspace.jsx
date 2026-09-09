import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useGetGraphOverview, useGetGraphNetwork, useSearchGraph, useFindGraphPath, useGetCentrality, useGetCommunities } from '@/api/graph';
import { useEvidenceForNode } from '@/api/xai';
import {
    Network as NetworkIcon, Search, Maximize2, Minimize2, ZoomIn, ZoomOut,
    RefreshCw, ChevronDown, ChevronRight, Eye, EyeOff, Filter, Download,
    Layers, Users, MapPin, Database, BarChart3, Clock, FileText, X
} from 'lucide-react';
import { getEntityTypeColor, formatNumber, ENTITY_COLORS } from '@/components/app-shell';

/* ── Graph filters panel ── */
function GraphFilters({ filters, onFilterChange, graphData }) {
    const entityTypes = useMemo(() => {
        if (!graphData?.nodes) return [];
        const types = new Map();
        graphData.nodes.forEach(n => {
            const t = n.type || n.label || 'unknown';
            types.set(t, (types.get(t) || 0) + 1);
        });
        return Array.from(types.entries()).sort((a, b) => b[1] - a[1]);
    }, [graphData]);

    const edgeTypes = useMemo(() => {
        if (!graphData?.edges) return [];
        const types = new Map();
        graphData.edges.forEach(e => {
            const t = e.type || e.label || 'unknown';
            types.set(t, (types.get(t) || 0) + 1);
        });
        return Array.from(types.entries()).sort((a, b) => b[1] - a[1]);
    }, [graphData]);

    return (
        <div className="space-y-3">
            {/* Entity filters */}
            <div>
                <div className="tp-section-label mb-2">ENTITY TYPES</div>
                <div className="space-y-1">
                    <label className="flex items-center gap-2 text-[11px] text-fg-secondary cursor-pointer">
                        <input type="checkbox" checked={filters.showAll}
                            onChange={e => onFilterChange({ ...filters, showAll: e.target.checked, excludedTypes: [] })}
                            className="accent-primary" />
                        All
                    </label>
                    {entityTypes.map(([type, count]) => (
                        <label key={type} className="flex items-center gap-2 text-[11px] text-fg-secondary cursor-pointer">
                            <input type="checkbox"
                                checked={!filters.excludedTypes.includes(type)}
                                onChange={e => {
                                    const excluded = e.target.checked
                                        ? filters.excludedTypes.filter(t => t !== type)
                                        : [...filters.excludedTypes, type];
                                    onFilterChange({ ...filters, showAll: false, excludedTypes: excluded });
                                }}
                                className="accent-primary" />
                            <span className="w-2 h-2 rounded-full" style={{ background: getEntityTypeColor(type) }} />
                            <span className="flex-1">{type}</span>
                            <span className="font-mono text-[9px] text-fg-faint">{count}</span>
                        </label>
                    ))}
                </div>
            </div>

            {/* Edge type filters */}
            <div>
                <div className="tp-section-label mb-2">RELATIONSHIP TYPES</div>
                <div className="space-y-1">
                    {edgeTypes.map(([type, count]) => (
                        <label key={type} className="flex items-center gap-2 text-[11px] text-fg-secondary cursor-pointer">
                            <input type="checkbox"
                                checked={!filters.excludedEdgeTypes.includes(type)}
                                onChange={e => {
                                    const excluded = e.target.checked
                                        ? filters.excludedEdgeTypes.filter(t => t !== type)
                                        : [...filters.excludedEdgeTypes, type];
                                    onFilterChange({ ...filters, excludedEdgeTypes: excluded });
                                }}
                                className="accent-primary" />
                            <span className="flex-1">{type}</span>
                            <span className="font-mono text-[9px] text-fg-faint">{count}</span>
                        </label>
                    ))}
                </div>
            </div>

            {/* Confidence threshold */}
            <div>
                <div className="tp-section-label mb-2">CONFIDENCE THRESHOLD</div>
                <input type="range" min="0" max="100" value={filters.confidenceThreshold * 100}
                    onChange={e => onFilterChange({ ...filters, confidenceThreshold: e.target.value / 100 })}
                    className="w-full accent-primary" />
                <div className="flex justify-between text-[9px] font-mono text-fg-faint mt-0.5">
                    <span>0%</span>
                    <span>{(filters.confidenceThreshold * 100).toFixed(0)}%</span>
                    <span>100%</span>
                </div>
            </div>

            {/* Inferred/Observed toggle */}
            <div>
                <div className="tp-section-label mb-2">EPISTEMIC STATE</div>
                <div className="space-y-1">
                    {[
                        { key: 'observed', label: 'Observed', color: 'var(--fg-primary)' },
                        { key: 'inferred', label: 'Inferred', color: 'var(--purple)' },
                        { key: 'predicted', label: 'Predicted', color: 'var(--amber)' },
                    ].map(s => (
                        <label key={s.key} className="flex items-center gap-2 text-[11px] text-fg-secondary cursor-pointer">
                            <input type="checkbox" checked={filters.epistemic.includes(s.key)}
                                onChange={e => {
                                    const epistemic = e.target.checked
                                        ? [...filters.epistemic, s.key]
                                        : filters.epistemic.filter(k => k !== s.key);
                                    onFilterChange({ ...filters, epistemic });
                                }}
                                className="accent-primary" />
                            <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />
                            {s.label}
                        </label>
                    ))}
                </div>
            </div>
        </div>
    );
}

/* ── Graph toolbar ── */
function GraphToolbar({ onSearch, onFit, onLayout, layout, setLayout }) {
    return (
        <div className="flex items-center gap-1 px-3 py-1.5 border-b border-border-subtle bg-bg-surface">
            <button onClick={onSearch} className="tp-btn tp-btn-ghost text-[10px] h-6 px-2">
                <Search size={11} /> Search
            </button>
            <button onClick={onFit} className="tp-btn tp-btn-ghost text-[10px] h-6 px-2">
                <Maximize2 size={11} /> Fit
            </button>
            <div className="w-px h-4 bg-border-default mx-1" />
            <select value={layout} onChange={e => setLayout(e.target.value)}
                className="tp-select h-6 text-[10px] px-2 w-auto">
                <option value="cose">Force</option>
                <option value="grid">Grid</option>
                <option value="circle">Circle</option>
                <option value="breadthfirst">Hierarchical</option>
            </select>
            <div className="flex-1" />
            <span className="text-[9px] font-mono text-fg-faint">
                Click to select · Double-click to expand · Right-click for menu
            </span>
        </div>
    );
}

/* ── Entity inspector panel (inline, for network context) ── */
function EntityInspector({ entity, evidence, onClose }) {
    if (!entity) return null;

    return (
        <div className="h-full flex flex-col bg-inspector-bg border-l border-border-subtle" style={{width: 280}}>
            <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle">
                <span className="tp-section-label">ENTITY INSPECTOR</span>
                <button onClick={onClose} className="tp-btn tp-btn-ghost p-0.5"><X size={11} /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-4">
                {/* Header */}
                <div>
                    <div className="text-[14px] font-semibold text-fg-primary mb-1">
                        {entity.name || entity.id}
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className="tp-badge tp-badge-blue">{entity.type || entity.label}</span>
                        {entity.community_id != null && (
                            <span className="tp-badge tp-badge-neutral">C{entity.community_id}</span>
                        )}
                    </div>
                </div>

                {/* Identity */}
                <div>
                    <div className="tp-section-label mb-2">IDENTITY</div>
                    <div className="space-y-1.5 text-[11px]">
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Canonical ID</span>
                            <span className="font-mono text-fg-secondary">{entity.id}</span>
                        </div>
                    </div>
                </div>

                {/* Network Metrics */}
                <div>
                    <div className="tp-section-label mb-2">NETWORK ROLE</div>
                    <div className="space-y-2">
                        {[
                            { label: 'Betweenness', value: entity.metrics?.betweenness_centrality },
                            { label: 'PageRank', value: entity.metrics?.pagerank },
                            { label: 'Degree', value: entity.degree },
                        ].map(m => m.value != null && (
                            <div key={m.label}>
                                <div className="flex justify-between text-[10px] mb-0.5">
                                    <span className="text-fg-faint">{m.label}</span>
                                    <span className="font-mono text-fg-secondary">
                                        {typeof m.value === 'number' ? m.value.toFixed(3) : m.value}
                                    </span>
                                </div>
                                {typeof m.value === 'number' && m.value <= 1 && (
                                    <div className="tp-confidence-bar">
                                        <div className="tp-confidence-fill" style={{
                                            width: `${m.value * 100}%`,
                                            background: 'hsl(var(--primary))'
                                        }} />
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Evidence */}
                {evidence && evidence.length > 0 && (
                    <div>
                        <div className="tp-section-label mb-2">EVIDENCE ({evidence.length})</div>
                        <div className="space-y-1.5">
                            {evidence.slice(0, 5).map((ev, i) => (
                                <div key={i} className="tp-panel p-2 text-[10px]">
                                    <div className="font-mono text-fg-faint mb-0.5">{ev.evidence_id || ev.id}</div>
                                    <div className="text-fg-secondary line-clamp-2">{ev.text_excerpt || ev.text || 'Evidence item'}</div>
                                    {ev.timestamp && (
                                        <div className="text-fg-faint font-mono mt-1">{ev.timestamp}</div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────
   NETWORK WORKSPACE
   ────────────────────────────────────────────────────────────── */

export default function NetworkWorkspace() {
    const [selectedNode, setSelectedNode] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [showSearch, setShowSearch] = useState(false);
    const [layout, setLayout] = useState('cose');
    const [showFilters, setShowFilters] = useState(true);
    const [filters, setFilters] = useState({
        showAll: true,
        excludedTypes: [],
        excludedEdgeTypes: [],
        confidenceThreshold: 0,
        epistemic: ['observed', 'inferred', 'predicted'],
    });
    const [depth, setDepth] = useState(2);
    const [centerNode, setCenterNode] = useState(null);

    const graphRef = useRef(null);
    const cyRef = useRef(null);

    const { data: overview } = useGetGraphOverview();
    const { data: graphData, isLoading } = useGetGraphNetwork({ center: centerNode, depth, limit: 1000 });
    const { data: evidence } = useEvidenceForNode(selectedNode?.id);

    // Filter graph data
    const filteredData = useMemo(() => {
        if (!graphData) return { nodes: [], edges: [] };
        const nodes = (graphData.nodes || []).filter(n => {
            if (!filters.showAll && filters.excludedTypes.includes(n.type || n.label)) return false;
            return true;
        });
        const nodeIds = new Set(nodes.map(n => n.id));
        const edges = (graphData.edges || []).filter(e => {
            if (!nodeIds.has(e.source) && !nodeIds.has(e.target)) return false;
            if (filters.excludedEdgeTypes.includes(e.type || e.label)) return false;
            return true;
        });
        return { nodes, edges };
    }, [graphData, filters]);

    // Handle search
    const handleSearch = useCallback(async (q) => {
        if (!q.trim()) { setSearchResults([]); return; }
        // Use local filter
        const results = (graphData?.nodes || []).filter(n => {
            const name = (n.name || n.id || '').toLowerCase();
            return name.includes(q.toLowerCase());
        }).slice(0, 20);
        setSearchResults(results);
    }, [graphData]);

    useEffect(() => {
        if (showSearch) handleSearch(searchQuery);
    }, [searchQuery, showSearch, handleSearch]);

    // Cytoscape initialization
    useEffect(() => {
        if (!graphRef.current || filteredData.nodes.length === 0) return;

        let cancelled = false;

        import('cytoscape').then(cytoscape => {
            if (cancelled || !graphRef.current) return;

            // Clean existing
            if (cyRef.current) {
                cyRef.current.destroy();
            }

            const cy = cytoscape.default({
                container: graphRef.current,
                elements: [
                    ...filteredData.nodes.map(n => ({
                        data: {
                            id: n.id,
                            label: n.name || n.id,
                            type: n.type || n.label || 'unknown',
                            pagerank: n.metrics?.pagerank || 0.1,
                            betweenness: n.metrics?.betweenness_centrality || 0,
                            community: n.community_id,
                            degree: n.degree || 0,
                        },
                    })),
                    ...filteredData.edges.map((e, i) => ({
                        data: {
                            id: `e${i}`,
                            source: e.source,
                            target: e.target,
                            label: e.type || e.label || '',
                            inferred: e.inferred,
                        },
                    })),
                ],
                style: [
                    {
                        selector: 'node',
                        style: {
                            'background-color': (ele) => {
                                const type = ele.data('type');
                                return ENTITY_COLORS[type] || '#666';
                            },
                            'width': (ele) => Math.max(8, (ele.data('pagerank') || 0.1) * 40),
                            'height': (ele) => Math.max(8, (ele.data('pagerank') || 0.1) * 40),
                            'label': 'data(label)',
                            'font-size': '9px',
                            'font-family': 'Inter, sans-serif',
                            'color': 'hsl(220 14% 92%)',
                            'text-valign': 'bottom',
                            'text-margin-y': 4,
                            'border-width': 1.5,
                            'border-color': 'hsl(220 16% 6%)',
                            'border-opacity': 0.8,
                        },
                    },
                    {
                        selector: 'node:selected',
                        style: {
                            'border-width': 2.5,
                            'border-color': 'hsl(214 80% 56%)',
                            'background-color': (ele) => {
                                const type = ele.data('type');
                                return ENTITY_COLORS[type] || '#666';
                            },
                        },
                    },
                    {
                        selector: 'node.highlighted',
                        style: {
                            'border-width': 2,
                            'border-color': 'hsl(36 82% 55%)',
                        },
                    },
                    {
                        selector: 'edge',
                        style: {
                            'line-color': (ele) => ele.data('inferred')
                                ? 'hsl(270 55% 58% / 0.4)'
                                : 'hsl(220 10% 35%)',
                            'width': 1,
                            'curve-style': 'bezier',
                            'target-arrow-shape': 'none',
                            'line-style': (ele) => ele.data('inferred') ? 'dashed' : 'solid',
                            'label': '',
                            'font-size': '7px',
                            'color': 'hsl(220 8% 50%)',
                            'text-rotation': 'autorotate',
                        },
                    },
                    {
                        selector: 'edge:selected',
                        style: {
                            'line-color': 'hsl(214 80% 56%)',
                            'width': 2,
                            'label': 'data(label)',
                        },
                    },
                ],
                layout: {
                    name: layout,
                    animate: true,
                    animationDuration: 400,
                    padding: 40,
                    nodeDimensionsIncludeLabels: true,
                    ...(layout === 'cose' ? {
                        idealEdgeLength: 100,
                        nodeRepulsion: 4500,
                        edgeElasticity: 100,
                        gravity: 0.25,
                        numIter: 250,
                    } : {}),
                },
                minZoom: 0.1,
                maxZoom: 5,
                wheelSensitivity: 0.2,
                boxSelectionEnabled: false,
            });

            // Event handlers
            cy.on('tap', 'node', (evt) => {
                const node = evt.target;
                const data = node.data();
                setSelectedNode({
                    id: data.id,
                    name: data.label,
                    type: data.type,
                    community_id: data.community,
                    metrics: {
                        pagerank: data.pagerank,
                        betweenness_centrality: data.betweenness,
                    },
                    degree: data.degree,
                });
                // Also expose to shell inspector
                window.__thupparivu?.setInspectorEntity({
                    id: data.id,
                    name: data.label,
                    type: data.type,
                    community_id: data.community,
                    metrics: {
                        pagerank: data.pagerank,
                        betweenness_centrality: data.betweenness,
                    },
                    degree: data.degree,
                });
            });

            cy.on('tap', (evt) => {
                if (evt.target === cy) {
                    setSelectedNode(null);
                    window.__thupparivu?.clearInspector();
                }
            });

            cyRef.current = cy;
        });

        return () => { cancelled = true; };
    }, [filteredData, layout]);

    // Handle fit
    const handleFit = useCallback(() => {
        cyRef.current?.fit(undefined, 40);
    }, []);

    // Focus on node from search
    const focusNode = useCallback((nodeId) => {
        if (!cyRef.current) return;
        const node = cyRef.current.getElementById(nodeId);
        if (node.length) {
            cyRef.current.animate({ center: { eles: node }, zoom: 2 }, { duration: 300 });
            node.addClass('highlighted');
            setTimeout(() => node.removeClass('highlighted'), 2000);
        }
        setShowSearch(false);
    }, []);

    return (
        <div className="flex h-full overflow-hidden">
            {/* Left: Filters */}
            {showFilters && (
                <div className="w-52 border-r border-border-subtle bg-bg-surface overflow-y-auto shrink-0">
                    <div className="px-3 py-2 border-b border-border-subtle flex items-center justify-between">
                        <span className="tp-section-label">FILTERS</span>
                        <button onClick={() => setShowFilters(false)} className="tp-btn tp-btn-ghost p-0.5">
                            <EyeOff size={10} />
                        </button>
                    </div>
                    <div className="p-3">
                        <GraphFilters filters={filters} onFilterChange={setFilters} graphData={graphData} />
                    </div>

                    {/* Depth control */}
                    <div className="px-3 pb-3 border-t border-border-subtle pt-3">
                        <div className="tp-section-label mb-2">EXPANSION DEPTH</div>
                        <input type="range" min="1" max="5" value={depth}
                            onChange={e => setDepth(Number(e.target.value))}
                            className="w-full accent-primary" />
                        <div className="flex justify-between text-[9px] font-mono text-fg-faint mt-0.5">
                            <span>1 hop</span>
                            <span>{depth} hops</span>
                            <span>5</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Center: Graph canvas */}
            <div className="flex-1 flex flex-col min-w-0">
                {!showFilters && (
                    <button onClick={() => setShowFilters(true)}
                        className="absolute left-2 top-12 z-10 tp-btn tp-btn-ghost h-6 px-1.5 text-[9px]">
                        <Eye size={10} /> Filters
                    </button>
                )}
                <GraphToolbar
                    onSearch={() => setShowSearch(true)}
                    onFit={handleFit}
                    layout={layout}
                    setLayout={setLayout}
                />
                <div ref={graphRef} className="flex-1 graph-canvas-bg" />

                {/* Inline search overlay */}
                {showSearch && (
                    <div className="absolute top-14 left-1/2 -translate-x-1/2 z-20 w-96 bg-bg-panel border border-border-default rounded shadow-xl">
                        <div className="flex items-center gap-2 px-3 h-9 border-b border-border-subtle">
                            <Search size={12} className="text-fg-faint" />
                            <input autoFocus value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                                placeholder="Search nodes..."
                                className="flex-1 bg-transparent text-[12px] text-fg-primary outline-none placeholder:text-fg-faint" />
                            <button onClick={() => setShowSearch(false)} className="tp-btn tp-btn-ghost p-0.5">
                                <X size={10} />
                            </button>
                        </div>
                        <div className="max-h-60 overflow-y-auto">
                            {searchResults.length === 0 && searchQuery && (
                                <div className="px-3 py-2 text-[10px] text-fg-faint">No results found</div>
                            )}
                            {searchResults.map(node => (
                                <button key={node.id} onClick={() => focusNode(node.id)}
                                    className="w-full px-3 py-2 flex items-center gap-2 hover:bg-bg-hover text-left transition-colors">
                                    <span className="w-2 h-2 rounded-full" style={{ background: getEntityTypeColor(node.type || node.label) }} />
                                    <span className="text-[11px] text-fg-primary flex-1">{node.name || node.id}</span>
                                    <span className="tp-badge tp-badge-blue" style={{fontSize: '8px'}}>{node.type || node.label}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Graph stats overlay */}
                <div className="absolute bottom-14 left-2 z-10 flex items-center gap-3 text-[9px] font-mono text-fg-faint bg-bg-panel/80 px-2 py-1 rounded border border-border-subtle">
                    <span>{formatNumber(filteredData.nodes.length)} nodes</span>
                    <span>·</span>
                    <span>{formatNumber(filteredData.edges.length)} edges</span>
                    {selectedNode && (
                        <>
                            <span>·</span>
                            <span className="text-primary">Selected: {selectedNode.name || selectedNode.id}</span>
                        </>
                    )}
                </div>

                {/* Legend */}
                <div className="absolute bottom-14 right-2 z-10 bg-bg-panel/80 border border-border-subtle rounded p-2 text-[8px] space-y-1">
                    <div className="tp-section-label mb-1">LEGEND</div>
                    {Object.entries(ENTITY_COLORS).slice(0, 6).map(([type, color]) => (
                        <div key={type} className="flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                            <span className="text-fg-faint uppercase">{type}</span>
                        </div>
                    ))}
                    <div className="border-t border-border-subtle pt-1 mt-1">
                        <div className="flex items-center gap-1.5">
                            <span className="w-4 h-px bg-fg-secondary" />
                            <span className="text-fg-faint">Observed</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className="w-4 h-px bg-purple" style={{borderTop: '1px dashed hsl(var(--purple))'}} />
                            <span className="text-fg-faint">Inferred</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Right: Entity Inspector */}
            {selectedNode && (
                <EntityInspector
                    entity={selectedNode}
                    evidence={evidence?.results || evidence?.items || evidence}
                    onClose={() => {
                        setSelectedNode(null);
                        window.__thupparivu?.clearInspector();
                    }}
                />
            )}
        </div>
    );
}
