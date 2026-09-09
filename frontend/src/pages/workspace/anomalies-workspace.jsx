import { useState, useMemo } from 'react';
import { useGetGhosts } from '@/api/graph';
import { AlertTriangle, ChevronRight, Search, Filter, ExternalLink } from 'lucide-react';
import { getConfidenceColor, formatNumber } from '@/components/app-shell';

export default function AnomaliesWorkspace() {
    const { data: ghostsData, isLoading } = useGetGhosts();
    const ghosts = ghostsData?.results || ghostsData?.items || ghostsData || [];
    const [search, setSearch] = useState('');
    const [selected, setSelected] = useState(null);

    const filtered = useMemo(() => {
        if (!search) return ghosts;
        const q = search.toLowerCase();
        return ghosts.filter(g =>
            (g.ghost_id || '').toLowerCase().includes(q) ||
            (g.label || '').toLowerCase().includes(q) ||
            (g.subtype || '').toLowerCase().includes(q)
        );
    }, [ghosts, search]);

    const stats = useMemo(() => ({
        total: ghosts.length,
        highPriority: ghosts.filter(g => (g.confidence || 0) >= 0.75).length,
        avgConf: ghosts.length > 0
            ? ghosts.reduce((s, g) => s + (g.confidence || 0), 0) / ghosts.length
            : 0,
    }), [ghosts]);

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex overflow-hidden animate-fade-in">
            {/* Left: List */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Header */}
                <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                    <AlertTriangle size={13} className="text-amber" />
                    <span className="text-[11px] font-semibold text-fg-primary">ANOMALIES</span>
                    <span className="tp-badge tp-badge-amber">{stats.total}</span>
                    <div className="w-px h-4 bg-border-default" />
                    <span className="text-[10px] font-mono text-fg-faint">{stats.highPriority} HIGH PRIORITY</span>
                    <div className="flex-1" />
                    <div className="relative max-w-xs">
                        <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint" />
                        <input value={search} onChange={e => setSearch(e.target.value)}
                            placeholder="Filter anomalies..."
                            className="tp-input pl-7 h-7 text-[11px]" />
                    </div>
                </div>

                {/* List */}
                <div className="flex-1 overflow-y-auto">
                    {filtered.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center">
                            <AlertTriangle size={24} className="text-fg-faint mb-3" />
                            <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">NO ANOMALIES DETECTED</span>
                            <span className="text-[10px] text-fg-faint mt-1">No structural anomalies found in the current dataset</span>
                        </div>
                    ) : (
                        <table className="tp-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>LABEL</th>
                                    <th>SUBTYPE</th>
                                    <th>COMMUNITIES</th>
                                    <th>CONFIDENCE</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(ghost => {
                                    const conf = ghost.confidence || 0;
                                    const confColor = getConfidenceColor(conf);
                                    const isSelected = selected?.ghost_id === ghost.ghost_id;
                                    return (
                                        <tr key={ghost.ghost_id}
                                            className={`cursor-pointer ${isSelected ? 'bg-blue-bg' : ''}`}
                                            onClick={() => setSelected(ghost)}>
                                            <td className="font-mono text-fg-faint">{ghost.ghost_id}</td>
                                            <td className="text-fg-primary font-medium">{ghost.label || 'Unknown'}</td>
                                            <td>
                                                <span className="tp-badge tp-badge-amber">{ghost.subtype || 'STRUCTURAL'}</span>
                                            </td>
                                            <td>
                                                <div className="flex gap-1">
                                                    {ghost.between_communities?.slice(0, 3).map(c => (
                                                        <span key={c} className="tp-badge tp-badge-neutral" style={{fontSize: '8px'}}>C{c}</span>
                                                    ))}
                                                </div>
                                            </td>
                                            <td>
                                                <div className="flex items-center gap-2">
                                                    <span className="font-mono text-[10px] font-semibold" style={{color: confColor}}>
                                                        {(conf * 100).toFixed(0)}%
                                                    </span>
                                                    <div className="tp-confidence-bar w-16">
                                                        <div className="tp-confidence-fill" style={{width: `${conf * 100}%`, background: confColor}} />
                                                    </div>
                                                </div>
                                            </td>
                                            <td><ChevronRight size={10} className="text-fg-faint" /></td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>

            {/* Right: Detail panel */}
            {selected && (
                <div className="w-80 border-l border-border-subtle bg-inspector-bg overflow-y-auto">
                    <div className="px-3 py-2 border-b border-border-subtle flex items-center justify-between">
                        <span className="tp-section-label">ANOMALY DETAIL</span>
                        <button onClick={() => setSelected(null)} className="tp-btn tp-btn-ghost p-0.5 text-[10px]">Close</button>
                    </div>
                    <div className="p-3 space-y-4">
                        <div>
                            <div className="font-mono text-[10px] text-fg-faint mb-1">{selected.ghost_id}</div>
                            <div className="text-[13px] font-semibold text-fg-primary mb-1">{selected.label || 'Unknown candidate'}</div>
                            <span className="tp-badge tp-badge-amber">{selected.subtype || 'STRUCTURAL ANOMALY'}</span>
                        </div>

                        {/* Confidence breakdown */}
                        <div>
                            <div className="tp-section-label mb-2">CONFIDENCE</div>
                            <div className="text-[18px] font-mono font-bold mb-2" style={{color: getConfidenceColor(selected.confidence || 0)}}>
                                {((selected.confidence || 0) * 100).toFixed(1)}%
                            </div>
                            {selected.confidence_breakdown && (
                                <div className="space-y-2">
                                    {Object.entries(selected.confidence_breakdown).map(([key, val]) => (
                                        <div key={key}>
                                            <div className="flex justify-between text-[10px] mb-0.5">
                                                <span className="text-fg-faint">{key.replace(/_/g, ' ')}</span>
                                                <span className="font-mono text-fg-secondary">{(val * 100).toFixed(1)}%</span>
                                            </div>
                                            <div className="tp-confidence-bar">
                                                <div className="tp-confidence-fill" style={{width: `${val * 100}%`, background: 'hsl(var(--primary))'}} />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Communities */}
                        {selected.between_communities?.length > 0 && (
                            <div>
                                <div className="tp-section-label mb-2">BETWEEN COMMUNITIES</div>
                                <div className="flex flex-wrap gap-1">
                                    {selected.between_communities.map(c => (
                                        <span key={c} className="tp-badge tp-badge-blue">C{c}</span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Evidence anchors */}
                        {selected.evidence?.length > 0 && (
                            <div>
                                <div className="tp-section-label mb-2">EVIDENCE ANCHORS ({selected.evidence.length})</div>
                                <div className="space-y-1.5">
                                    {selected.evidence.map((ev, i) => (
                                        <div key={i} className="tp-panel p-2 text-[10px]">
                                            <div className="flex items-center gap-2 mb-0.5">
                                                <span className="tp-badge tp-badge-neutral" style={{fontSize: '8px'}}>{ev.anchor_type}</span>
                                                <span className="text-fg-faint font-mono">{ev.anchor_guid}</span>
                                            </div>
                                            <span className="text-fg-secondary">{ev.anchor_name}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Predicted edges */}
                        {selected.predicted_edges?.length > 0 && (
                            <div>
                                <div className="tp-section-label mb-2">PREDICTED EDGES</div>
                                <div className="space-y-1">
                                    {selected.predicted_edges.map((pe, i) => (
                                        <div key={i} className="text-[10px] font-mono text-purple">
                                            {pe.source || pe.from} → {pe.target || pe.to}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
