/**
 * Network Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §7: Network Screen Major Refinement.
 * Light canvas, subtle grid, clean typed nodes, community hulls, visible legend.
 * Inspector for Nicole Jackson (ENT-1042) with complete network metrics.
 * Table Alternative as first-class view.
 */
import React, { useState } from 'react';
import { Network, Table, ZoomIn, ZoomOut, Maximize2, Filter, Layers, Info, Shield, Download } from 'lucide-react';
import { SYNTHETIC_ENTITIES } from '@/state/synthetic-case-data';
import { StatusMark, ConfidenceBand } from '@/components/shared';

export default function NetworkWorkspace() {
    const [viewMode, setViewMode] = useState('graph'); // 'graph' | 'table'
    const [selectedEntity, setSelectedEntity] = useState(SYNTHETIC_ENTITIES[0]); // Default: Nicole Jackson

    return (
        <div className="flex h-full overflow-hidden animate-fade-in bg-[hsl(var(--bg-root))]">
            {/* Main Graph Area */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
                {/* Graph Controls Toolbar */}
                <div className="p-3 bg-[hsl(var(--bg-surface))] border-b border-[hsl(var(--border-subtle))] flex items-center justify-between z-10">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1.5 font-semibold text-[13px] text-[hsl(var(--fg-primary))]">
                            <Network size={15} className="text-[hsl(var(--primary))]" />
                            <span>Network Explorer</span>
                        </div>
                        <span className="text-[11px] text-[hsl(var(--fg-muted))] font-mono">
                            Showing active cluster (10 nodes, 18 links)
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* View Switcher: Graph vs Table Alternative */}
                        <div className="flex border border-[hsl(var(--border-default))] rounded overflow-hidden">
                            <button
                                className={`px-2.5 py-1 text-[11px] font-medium ${viewMode === 'graph' ? 'bg-[hsl(var(--primary))] text-white' : 'bg-[hsl(var(--bg-surface))] text-[hsl(var(--fg-secondary))]'}`}
                                onClick={() => setViewMode('graph')}
                            >
                                Graph View
                            </button>
                            <button
                                className={`px-2.5 py-1 text-[11px] font-medium ${viewMode === 'table' ? 'bg-[hsl(var(--primary))] text-white' : 'bg-[hsl(var(--bg-surface))] text-[hsl(var(--fg-secondary))]'}`}
                                onClick={() => setViewMode('table')}
                            >
                                Table Alternative
                            </button>
                        </div>

                        <button className="sg-btn sg-btn-sm" onClick={() => alert('Graph view exported as high-res PNG.')}>
                            <Download size={12} /> Export
                        </button>
                    </div>
                </div>

                {/* Graph Canvas / Table View Alternative */}
                {viewMode === 'graph' ? (
                    <div className="flex-1 relative bg-[hsl(var(--bg-root))] overflow-hidden flex items-center justify-center">
                        {/* Subtle Grid Background */}
                        <div
                            className="absolute inset-0 opacity-40"
                            style={{
                                backgroundImage: 'radial-gradient(hsl(var(--border-strong)) 1px, transparent 1px)',
                                backgroundSize: '24px 24px'
                            }}
                        />

                        {/* Interactive SVG Diagram matching PDF layout */}
                        <svg className="w-full h-full max-w-4xl max-h-[600px] z-0" viewBox="0 0 800 500">
                            {/* Community Hulls (light backgrounds) */}
                            <ellipse cx="250" cy="250" rx="180" ry="140" fill="hsl(var(--primary-bg))" stroke="hsl(var(--primary-border))" strokeDasharray="4 4" opacity="0.6" />
                            <text x="140" y="140" fill="hsl(var(--primary))" fontSize="11" fontWeight="600">Community 0</text>

                            <ellipse cx="550" cy="250" rx="160" ry="130" fill="hsl(var(--amber-bg))" stroke="hsl(var(--amber-border))" strokeDasharray="4 4" opacity="0.6" />
                            <text x="600" y="140" fill="hsl(var(--amber-fg))" fontSize="11" fontWeight="600">Community 6</text>

                            {/* Edges - Observed (Solid) */}
                            <line x1="220" y1="200" x2="280" y2="280" stroke="hsl(var(--border-strong))" strokeWidth="2" />
                            <line x1="220" y1="200" x2="160" y2="260" stroke="hsl(var(--border-strong))" strokeWidth="1.5" />
                            <line x1="220" y1="200" x2="320" y2="180" stroke="hsl(var(--border-strong))" strokeWidth="1.5" />
                            <line x1="520" y1="220" x2="600" y2="280" stroke="hsl(var(--border-strong))" strokeWidth="2" />
                            <line x1="520" y1="220" x2="560" y2="170" stroke="hsl(var(--border-strong))" strokeWidth="1.5" />

                            {/* Hypothesised Bridge (FND-003) - Dashed with Badge */}
                            <line x1="220" y1="200" x2="520" y2="220" stroke="hsl(var(--amber))" strokeWidth="2" strokeDasharray="6 4" />
                            <rect x="330" y="195" width="140" height="22" rx="4" fill="hsl(var(--amber-bg))" stroke="hsl(var(--amber-border))" />
                            <text x="340" y="210" fill="hsl(var(--amber-fg))" fontSize="10" fontWeight="600">FND-003 · Hypothesised bridge</text>

                            {/* Nodes - Community 0 */}
                            {/* Nicole Jackson (ENT-1042) */}
                            <g className="cursor-pointer" onClick={() => setSelectedEntity(SYNTHETIC_ENTITIES[0])}>
                                <circle cx="220" cy="200" r="22" fill="hsl(var(--primary))" stroke="hsl(var(--bg-surface))" strokeWidth="3" />
                                <text x="220" y="204" fill="white" fontSize="10" fontWeight="bold" textAnchor="middle">NJ</text>
                                <text x="220" y="234" fill="hsl(var(--fg-primary))" fontSize="11" fontWeight="600" textAnchor="middle">Nicole Jackson</text>
                                <text x="220" y="246" fill="hsl(var(--fg-muted))" fontSize="9" textAnchor="middle">ENT-1042</text>
                            </g>

                            {/* Matthew Jones (ENT-1188) */}
                            <g className="cursor-pointer" onClick={() => setSelectedEntity(SYNTHETIC_ENTITIES[1])}>
                                <circle cx="280" cy="280" r="16" fill="hsl(var(--bg-surface))" stroke="hsl(var(--primary))" strokeWidth="2" />
                                <text x="280" y="284" fill="hsl(var(--primary))" fontSize="9" fontWeight="bold" textAnchor="middle">MJ</text>
                                <text x="280" y="306" fill="hsl(var(--fg-primary))" fontSize="10" textAnchor="middle">Matthew Jones</text>
                            </g>

                            {/* Michael Martin (ENT-2214) */}
                            <g className="cursor-pointer" onClick={() => setSelectedEntity(SYNTHETIC_ENTITIES[2])}>
                                <circle cx="160" cy="260" r="16" fill="hsl(var(--bg-surface))" stroke="hsl(var(--primary))" strokeWidth="2" />
                                <text x="160" y="264" fill="hsl(var(--primary))" fontSize="9" fontWeight="bold" textAnchor="middle">MM</text>
                                <text x="160" y="286" fill="hsl(var(--fg-primary))" fontSize="10" textAnchor="middle">Michael Martin</text>
                            </g>

                            {/* Amanda Frank (ENT-3420) */}
                            <g className="cursor-pointer" onClick={() => setSelectedEntity(SYNTHETIC_ENTITIES[3])}>
                                <circle cx="320" cy="180" r="14" fill="hsl(var(--bg-surface))" stroke="hsl(var(--primary))" strokeWidth="2" />
                                <text x="320" y="184" fill="hsl(var(--primary))" fontSize="9" fontWeight="bold" textAnchor="middle">AF</text>
                                <text x="320" y="204" fill="hsl(var(--fg-primary))" fontSize="10" textAnchor="middle">Amanda Frank</text>
                            </g>

                            {/* Nodes - Community 6 */}
                            {/* Carl Khan (ENT-4811) */}
                            <g className="cursor-pointer" onClick={() => setSelectedEntity(SYNTHETIC_ENTITIES[4])}>
                                <circle cx="520" cy="220" r="20" fill="hsl(var(--amber))" stroke="hsl(var(--bg-surface))" strokeWidth="3" />
                                <text x="520" y="224" fill="white" fontSize="10" fontWeight="bold" textAnchor="middle">CK</text>
                                <text x="520" y="252" fill="hsl(var(--fg-primary))" fontSize="11" fontWeight="600" textAnchor="middle">Carl Khan</text>
                                <text x="520" y="264" fill="hsl(var(--fg-muted))" fontSize="9" textAnchor="middle">ENT-4811</text>
                            </g>

                            {/* Account 8814 (ENT-8814) */}
                            <g className="cursor-pointer" onClick={() => setSelectedEntity(SYNTHETIC_ENTITIES[8])}>
                                <rect x="585" y="265" width="30" height="30" rx="4" fill="hsl(var(--bg-surface))" stroke="hsl(var(--amber))" strokeWidth="2" />
                                <text x="600" y="284" fill="hsl(var(--amber-fg))" fontSize="9" fontWeight="bold" textAnchor="middle">ACC</text>
                                <text x="600" y="310" fill="hsl(var(--fg-primary))" fontSize="10" textAnchor="middle">Account 8814</text>
                            </g>

                            {/* Rebecca Mathis (ENT-5920) */}
                            <g className="cursor-pointer" onClick={() => setSelectedEntity(SYNTHETIC_ENTITIES[5])}>
                                <circle cx="560" cy="170" r="14" fill="hsl(var(--bg-surface))" stroke="hsl(var(--amber))" strokeWidth="2" />
                                <text x="560" y="174" fill="hsl(var(--amber-fg))" fontSize="9" fontWeight="bold" textAnchor="middle">RM</text>
                                <text x="560" y="194" fill="hsl(var(--fg-primary))" fontSize="10" textAnchor="middle">Rebecca Mathis</text>
                            </g>
                        </svg>

                        {/* Visible Legend Bar (Bottom Left) */}
                        <div className="absolute bottom-4 left-4 p-3 bg-[hsl(var(--bg-surface))] border border-[hsl(var(--border-default))] rounded-md shadow-sm z-10 space-y-1.5 text-[11px]">
                            <div className="font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider text-[10px]">Graph Legend</div>
                            <div className="flex items-center gap-2">
                                <span className="w-4 h-0.5 bg-[hsl(var(--border-strong))]" />
                                <span>Observed links</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-4 h-0.5 border-b border-dashed border-[hsl(var(--primary))]" />
                                <span>Inferred links</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-4 h-0.5 border-b-2 border-dashed border-[hsl(var(--amber))]" />
                                <span>Hypothesised bridge (FND-003)</span>
                            </div>
                        </div>
                    </div>
                ) : (
                    /* Table Alternative View */
                    <div className="flex-1 overflow-auto bg-[hsl(var(--bg-surface))] p-4">
                        <table className="sg-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>NAME</th>
                                    <th>TYPE</th>
                                    <th>COMMUNITY</th>
                                    <th>CONNECTIONS</th>
                                    <th>PAGERANK</th>
                                    <th>BETWEENNESS</th>
                                </tr>
                            </thead>
                            <tbody>
                                {SYNTHETIC_ENTITIES.map(e => (
                                    <tr key={e.id} onClick={() => setSelectedEntity(e)} className={selectedEntity.id === e.id ? 'selected' : ''}>
                                        <td className="font-mono text-[12px] text-[hsl(var(--primary))] font-medium">{e.id}</td>
                                        <td className="font-medium text-[12px]">{e.name}</td>
                                        <td><span className="sg-badge sg-badge-neutral">{e.type}</span></td>
                                        <td className="text-[12px]">{e.community}</td>
                                        <td className="font-mono text-[12px]">{e.connections}</td>
                                        <td className="font-mono text-[12px]">{e.pagerank.toFixed(3)}</td>
                                        <td className="font-mono text-[12px] font-semibold text-[hsl(var(--primary))]">{e.betweenness.toFixed(3)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Selected Entity Inspector Drawer (Matches PDF Spec §7) */}
            <div className="w-96 bg-[hsl(var(--bg-surface))] flex flex-col shrink-0 overflow-y-auto border-l border-[hsl(var(--border-subtle))] p-5 space-y-5">
                <div className="flex items-center justify-between pb-3 border-b border-[hsl(var(--border-subtle))]">
                    <div>
                        <div className="font-mono text-[14px] font-bold text-[hsl(var(--primary))]">{selectedEntity.id}</div>
                        <h2 className="text-[16px] font-semibold text-[hsl(var(--fg-primary))] mt-0.5">{selectedEntity.name}</h2>
                    </div>
                    <span className="sg-badge sg-badge-neutral">{selectedEntity.type}</span>
                </div>

                {/* Centrality & Graph Metrics */}
                <div className="space-y-3">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Network Metrics</div>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                        <div className="p-2.5 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                            <div className="text-[hsl(var(--fg-muted))]">Connections</div>
                            <div className="font-mono text-[14px] font-bold text-[hsl(var(--fg-primary))]">{selectedEntity.connections} total</div>
                        </div>
                        <div className="p-2.5 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                            <div className="text-[hsl(var(--fg-muted))]">PageRank</div>
                            <div className="font-mono text-[14px] font-bold text-[hsl(var(--fg-primary))]">{selectedEntity.pagerank.toFixed(3)}</div>
                        </div>
                        <div className="p-2.5 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                            <div className="text-[hsl(var(--fg-muted))]">Betweenness</div>
                            <div className="font-mono text-[14px] font-bold text-[hsl(var(--primary))]">{selectedEntity.betweenness.toFixed(3)}</div>
                        </div>
                        <div className="p-2.5 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                            <div className="text-[hsl(var(--fg-muted))]">Global Rank</div>
                            <div className="font-mono text-[14px] font-bold text-[hsl(var(--fg-primary))]">{selectedEntity.rank}</div>
                        </div>
                    </div>
                </div>

                {/* Explicit Observed vs Inferred Links */}
                <div className="space-y-2 pt-3 border-t border-[hsl(var(--border-subtle))]">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Link Breakdown</div>
                    <div className="grid grid-cols-2 gap-2 text-[12px]">
                        <div className="p-2 bg-[hsl(var(--bg-hover))] rounded flex justify-between">
                            <span className="text-[hsl(var(--fg-secondary))]">Observed:</span>
                            <span className="font-mono font-semibold">{selectedEntity.observed_links}</span>
                        </div>
                        <div className="p-2 bg-[hsl(var(--bg-hover))] rounded flex justify-between">
                            <span className="text-[hsl(var(--fg-secondary))]">Inferred:</span>
                            <span className="font-mono font-semibold text-[hsl(var(--primary))]">{selectedEntity.inferred_links}</span>
                        </div>
                    </div>
                </div>

                {/* Evidence & Signal Activity */}
                <div className="space-y-2 pt-3 border-t border-[hsl(var(--border-subtle))] text-[12px]">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1">Case Provenance</div>
                    <div className="flex justify-between py-1 border-b border-[hsl(var(--border-subtle))]">
                        <span className="text-[hsl(var(--fg-muted))]">Evidence records:</span>
                        <span className="font-mono font-medium">{selectedEntity.evidence_records}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-[hsl(var(--border-subtle))]">
                        <span className="text-[hsl(var(--fg-muted))]">Temporal events:</span>
                        <span className="font-mono font-medium">{selectedEntity.events}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-[hsl(var(--border-subtle))]">
                        <span className="text-[hsl(var(--fg-muted))]">Burst signals:</span>
                        <span className="font-mono font-medium text-[hsl(var(--amber-fg))]">{selectedEntity.burst_signals}</span>
                    </div>
                    <div className="flex justify-between py-1">
                        <span className="text-[hsl(var(--fg-muted))]">Linked findings:</span>
                        <span className="font-mono font-medium text-[hsl(var(--primary))]">{selectedEntity.linked_findings} (FND-003)</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
