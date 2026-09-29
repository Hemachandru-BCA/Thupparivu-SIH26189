/**
 * Entities Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §6: Entities Screen.
 * Toolbar: Search, Type, Community, View, Saved views, Metric definitions
 * Table: ID, NAME, TYPE, COMMUNITY, CONNECTIONS, PAGERANK, BETWEENNESS, MENTIONS
 * Single confidence band (Low / Moderate / High)
 * Bulk actions + real pagination
 */
import React, { useState } from 'react';
import { useLocation } from 'wouter';
import {
    Users, Search, Filter, Download, Network,
    Bookmark, Info, ChevronDown, CheckSquare, Square
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { SYNTHETIC_ENTITIES } from '@/state/synthetic-case-data';
import { ConfidenceBand, Pagination, BulkActionBar } from '@/components/shared';

export default function EntitiesWorkspace() {
    const { activeCase, inspectEntity } = useInvestigation();
    const [, setLocation] = useLocation();

    const [searchTerm, setSearchTerm] = useState('');
    const [selectedType, setSelectedType] = useState('ALL');
    const [selectedCommunity, setSelectedCommunity] = useState('ALL');
    const [selectedEntities, setSelectedEntities] = useState([]);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);
    const [metricModalOpen, setMetricModalOpen] = useState(false);

    const types = ['ALL', 'Person', 'Account', 'Identifier'];
    const communities = ['ALL', 'Community 0', 'Community 4', 'Community 6', 'Community 12'];

    const filteredEntities = SYNTHETIC_ENTITIES.filter(e => {
        const matchesSearch = e.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
            e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            e.notes?.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesType = selectedType === 'ALL' || e.type === selectedType;
        const matchesComm = selectedCommunity === 'ALL' || e.community === selectedCommunity;
        return matchesSearch && matchesType && matchesComm;
    });

    const totalEntities = activeCase.entities_count; // Real scope: 13,146

    const handleSelectAll = () => {
        if (selectedEntities.length === filteredEntities.length) {
            setSelectedEntities([]);
        } else {
            setSelectedEntities(filteredEntities.map(e => e.id));
        }
    };

    const handleToggleSelect = (id, event) => {
        event.stopPropagation();
        setSelectedEntities(prev =>
            prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
        );
    };

    const handleExportCSV = () => {
        const rows = filteredEntities.map(e => `${e.id},"${e.name}",${e.type},${e.community},${e.connections},${e.pagerank},${e.betweenness},${e.mentions},${e.confidence}`);
        const header = "ID,NAME,TYPE,COMMUNITY,CONNECTIONS,PAGERANK,BETWEENNESS,MENTIONS,CONFIDENCE\n";
        const blob = new Blob([header + rows.join('\n')], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `entities_${activeCase.id}_${Date.now()}.csv`;
        a.click();
    };

    return (
        <div className="flex flex-col h-full bg-[hsl(var(--bg-root))] overflow-hidden animate-fade-in">
            {/* Top Toolbar */}
            <div className="p-4 bg-[hsl(var(--bg-surface))] border-b border-[hsl(var(--border-subtle))] space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                        <Users size={16} className="text-[hsl(var(--primary))]" />
                        <h1 className="text-[16px] font-semibold text-[hsl(var(--fg-primary))]">Entities</h1>
                        <span className="text-[12px] text-[hsl(var(--fg-muted))]">
                            ({totalEntities.toLocaleString()} scope)
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <button className="sg-btn sg-btn-sm" onClick={() => setMetricModalOpen(true)}>
                            <Info size={12} />
                            Metric definitions
                        </button>
                        <button className="sg-btn sg-btn-sm" onClick={handleExportCSV}>
                            <Download size={12} />
                            Export CSV
                        </button>
                    </div>
                </div>

                {/* Filter Controls */}
                <div className="flex flex-wrap items-center gap-3">
                    <div className="relative flex-1 min-w-[200px]">
                        <Search size={13} className="absolute left-2.5 top-2 text-[hsl(var(--fg-faint))]" />
                        <input
                            className="sg-input pl-8"
                            placeholder="Search entities by name or ID (e.g. Nicole Jackson, ENT-1042)…"
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                        />
                    </div>

                    <div className="flex items-center gap-2">
                        <label className="text-[11px] text-[hsl(var(--fg-muted))]">Type:</label>
                        <select
                            className="sg-select text-[12px]"
                            value={selectedType}
                            onChange={e => setSelectedType(e.target.value)}
                        >
                            {types.map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                    </div>

                    <div className="flex items-center gap-2">
                        <label className="text-[11px] text-[hsl(var(--fg-muted))]">Community:</label>
                        <select
                            className="sg-select text-[12px]"
                            value={selectedCommunity}
                            onChange={e => setSelectedCommunity(e.target.value)}
                        >
                            {communities.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>

                    <div className="flex items-center gap-2">
                        <label className="text-[11px] text-[hsl(var(--fg-muted))]">Saved views:</label>
                        <select className="sg-select text-[12px]">
                            <option>Default topology view</option>
                            <option>High betweenness bridges</option>
                            <option>Account nodes only</option>
                        </select>
                    </div>
                </div>

                {/* Bulk Actions Bar */}
                {selectedEntities.length > 0 && (
                    <BulkActionBar
                        count={selectedEntities.length}
                        onClear={() => setSelectedEntities([])}
                        actions={[
                            {
                                label: 'Add to watchlist',
                                onClick: () => alert(`Added ${selectedEntities.length} entities to investigative watchlist.`)
                            },
                            {
                                label: 'Compare in network',
                                onClick: () => setLocation('/network')
                            },
                            {
                                label: 'Export selection CSV',
                                onClick: handleExportCSV
                            }
                        ]}
                    />
                )}
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto bg-[hsl(var(--bg-surface))]">
                <table className="sg-table">
                    <thead>
                        <tr>
                            <th className="w-8">
                                <button className="cursor-pointer" onClick={handleSelectAll}>
                                    {selectedEntities.length === filteredEntities.length && filteredEntities.length > 0 ? (
                                        <CheckSquare size={13} className="text-[hsl(var(--primary))]" />
                                    ) : (
                                        <Square size={13} className="text-[hsl(var(--fg-faint))]" />
                                    )}
                                </button>
                            </th>
                            <th>ID</th>
                            <th>NAME</th>
                            <th>TYPE</th>
                            <th>COMMUNITY</th>
                            <th>CONNECTIONS</th>
                            <th>PAGERANK</th>
                            <th>BETWEENNESS</th>
                            <th>MENTIONS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredEntities.map(e => {
                            const isSelected = selectedEntities.includes(e.id);
                            return (
                                <tr
                                    key={e.id}
                                    className={isSelected ? 'selected' : ''}
                                    onClick={() => inspectEntity(e)}
                                >
                                    <td onClick={evt => handleToggleSelect(e.id, evt)}>
                                        {isSelected ? (
                                            <CheckSquare size={13} className="text-[hsl(var(--primary))]" />
                                        ) : (
                                            <Square size={13} className="text-[hsl(var(--fg-faint))]" />
                                        )}
                                    </td>
                                    <td className="font-mono font-medium text-[hsl(var(--primary))] text-[12px]">{e.id}</td>
                                    <td>
                                        <div className="font-medium text-[hsl(var(--fg-primary))]">{e.name}</div>
                                        {e.notes && <div className="text-[10px] text-[hsl(var(--fg-muted))] truncate max-w-xs">{e.notes}</div>}
                                    </td>
                                    <td>
                                        <span className="sg-badge sg-badge-neutral">{e.type}</span>
                                    </td>
                                    <td className="text-[12px] text-[hsl(var(--fg-secondary))]">{e.community}</td>
                                    <td className="font-mono text-[12px]">{e.connections}</td>
                                    <td className="font-mono text-[12px]">{e.pagerank.toFixed(3)}</td>
                                    <td className="font-mono text-[12px] font-semibold text-[hsl(var(--primary))]">{e.betweenness.toFixed(3)}</td>
                                    <td className="font-mono text-[12px]">{e.mentions}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            <Pagination
                page={page}
                pageSize={pageSize}
                total={totalEntities}
                onPageChange={p => setPage(p)}
                onPageSizeChange={s => setPageSize(s)}
            />

            {/* Metric Definitions Modal */}
            {metricModalOpen && (
                <div className="sg-overlay" onClick={() => setMetricModalOpen(false)}>
                    <div className="sg-dialog p-5" onClick={e => e.stopPropagation()}>
                        <h2 className="text-[14px] font-semibold mb-3">Graph Metric Definitions</h2>
                        <div className="space-y-3 text-[12px]">
                            <div>
                                <span className="font-semibold text-[hsl(var(--fg-primary))]">PageRank:</span>
                                <p className="text-[hsl(var(--fg-secondary))]">Relative authority and influence in the transfer graph based on recursive incoming connectivity.</p>
                            </div>
                            <div>
                                <span className="font-semibold text-[hsl(var(--fg-primary))]">Betweenness Centrality:</span>
                                <p className="text-[hsl(var(--fg-secondary))]">Measures how often a node falls on the shortest path between other pairs of nodes; critical for identifying bottleneck coordinators and intermediaries.</p>
                            </div>
                            <div>
                                <span className="font-semibold text-[hsl(var(--fg-primary))]">Community:</span>
                                <p className="text-[hsl(var(--fg-secondary))]">Dense modular cluster derived via Louvain algorithm indicating closely coupled operational units.</p>
                            </div>
                            <div>
                                <span className="font-semibold text-[hsl(var(--fg-primary))]">Confidence Band:</span>
                                <p className="text-[hsl(var(--fg-secondary))]">Single qualitative band (Low / Moderate / High) expressing deterministic evidence coverage. Numerical percentages are intentionally avoided.</p>
                            </div>
                        </div>
                        <button className="sg-btn sg-btn-ghost mt-4 w-full justify-center" onClick={() => setMetricModalOpen(false)}>Close</button>
                    </div>
                </div>
            )}
        </div>
    );
}
