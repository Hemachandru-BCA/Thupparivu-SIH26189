import { useState, useMemo } from 'react';
import { useEvidenceSearch, useEvidenceDetail, useEvidenceForNode } from '@/api/xai';
import { FileText, Search, Filter, ChevronRight, ExternalLink, Hash } from 'lucide-react';
import { formatTimestamp } from '@/components/app-shell';

export default function EvidenceWorkspace() {
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedId, setSelectedId] = useState(null);
    const [searchMode, setSearchMode] = useState('search'); // 'search' | 'node' | 'detail'
    const [nodeId, setNodeId] = useState('');

    const { data: searchResults } = useEvidenceSearch(searchQuery.length > 1 ? searchQuery : null);
    const { data: detailData } = useEvidenceDetail(selectedId);
    const { data: nodeEvidence } = useEvidenceForNode(nodeId || null);

    const results = searchResults?.results || searchResults?.items || searchResults || [];
    const detail = detailData?.result || detailData;
    const nodeEv = nodeEvidence?.results || nodeEvidence?.items || nodeEvidence || [];

    return (
        <div className="h-full flex overflow-hidden animate-fade-in">
            {/* Left: Evidence list */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Toolbar */}
                <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                    <FileText size={13} className="text-primary" />
                    <span className="text-[11px] font-semibold text-fg-primary">EVIDENCE</span>
                    <div className="w-px h-4 bg-border-default" />
                    <div className="flex gap-1">
                        {['search', 'node', 'detail'].map(mode => (
                            <button key={mode} onClick={() => setSearchMode(mode)}
                                className={`tp-btn text-[9px] h-5 px-2 ${searchMode === mode ? 'tp-btn-primary' : 'tp-btn-ghost'}`}>
                                {mode.toUpperCase()}
                            </button>
                        ))}
                    </div>
                    <div className="flex-1" />
                    {searchMode === 'search' && (
                        <div className="relative max-w-sm">
                            <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint" />
                            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                                placeholder="Search evidence..."
                                className="tp-input pl-7 h-7 text-[11px]" />
                        </div>
                    )}
                    {searchMode === 'node' && (
                        <div className="flex items-center gap-2">
                            <input value={nodeId} onChange={e => setNodeId(e.target.value)}
                                placeholder="Node ID (e.g. P-0172)"
                                className="tp-input h-7 text-[11px] w-48" />
                        </div>
                    )}
                    {searchMode === 'detail' && (
                        <div className="flex items-center gap-2">
                            <input value={selectedId || ''} onChange={e => setSelectedId(e.target.value)}
                                placeholder="Evidence ID (e.g. EV-0182)"
                                className="tp-input h-7 text-[11px] w-48" />
                        </div>
                    )}
                </div>

                {/* Results */}
                <div className="flex-1 overflow-y-auto">
                    {searchMode === 'search' && (
                        results.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-center">
                                <FileText size={24} className="text-fg-faint mb-3" />
                                <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">
                                    {searchQuery.length > 1 ? 'NO EVIDENCE MATCHES' : 'ENTER A SEARCH QUERY'}
                                </span>
                            </div>
                        ) : (
                            <table className="tp-table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>TYPE</th>
                                        <th>SOURCE</th>
                                        <th>TEXT</th>
                                        <th>TIMESTAMP</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {results.map((ev, i) => (
                                        <tr key={ev.evidence_id || i} className="cursor-pointer"
                                            onClick={() => { setSelectedId(ev.evidence_id || ev.id); setSearchMode('detail'); }}>
                                            <td className="font-mono text-fg-faint">{ev.evidence_id || ev.id}</td>
                                            <td>
                                                <span className="tp-badge tp-badge-blue">{ev.source_type || 'RECORD'}</span>
                                            </td>
                                            <td className="font-mono text-fg-secondary text-[10px]">{ev.source_record_id || '—'}</td>
                                            <td className="text-fg-secondary max-w-xs truncate">{ev.text_excerpt || '—'}</td>
                                            <td className="font-mono text-fg-faint text-[10px]">{formatTimestamp(ev.timestamp)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )
                    )}

                    {searchMode === 'node' && (
                        nodeEv.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-center">
                                <FileText size={24} className="text-fg-faint mb-3" />
                                <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">
                                    {nodeId ? 'NO EVIDENCE FOR THIS NODE' : 'ENTER A NODE ID'}
                                </span>
                            </div>
                        ) : (
                            <div className="p-3 space-y-2">
                                {nodeEv.map((ev, i) => (
                                    <div key={ev.evidence_id || i} className="tp-panel p-3 cursor-pointer hover:border-border-default"
                                        onClick={() => { setSelectedId(ev.evidence_id || ev.id); setSearchMode('detail'); }}>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="tp-badge tp-badge-blue" style={{fontSize: '8px'}}>{ev.source_type}</span>
                                            <span className="font-mono text-[9px] text-fg-faint">{ev.evidence_id}</span>
                                        </div>
                                        <div className="text-[11px] text-fg-secondary">{ev.text_excerpt}</div>
                                        <div className="text-[9px] font-mono text-fg-faint mt-1">{formatTimestamp(ev.timestamp)}</div>
                                    </div>
                                ))}
                            </div>
                        )
                    )}

                    {searchMode === 'detail' && detail && (
                        <div className="p-4 space-y-4">
                            <div>
                                <div className="tp-section-label mb-1">EVIDENCE ID</div>
                                <div className="font-mono text-[13px] text-fg-primary">{detail.evidence_id || detail.id}</div>
                            </div>
                            <div>
                                <div className="tp-section-label mb-1">SOURCE</div>
                                <div className="flex items-center gap-2">
                                    <span className="tp-badge tp-badge-blue">{detail.source_type}</span>
                                    <span className="font-mono text-[11px] text-fg-secondary">{detail.source_record_id}</span>
                                </div>
                            </div>
                            <div>
                                <div className="tp-section-label mb-1">TIMESTAMP</div>
                                <div className="font-mono text-[11px] text-fg-secondary">{formatTimestamp(detail.timestamp)}</div>
                            </div>
                            <div>
                                <div className="tp-section-label mb-1">TEXT EXCERPT</div>
                                <div className="text-[12px] text-fg-secondary leading-relaxed border-l-2 border-border-default pl-3">
                                    {detail.text_excerpt}
                                </div>
                            </div>
                            {detail.provenance && (
                                <div>
                                    <div className="tp-section-label mb-1">PROVENANCE</div>
                                    <div className="text-[11px] font-mono text-fg-secondary">{detail.provenance}</div>
                                </div>
                            )}
                            {detail.hash && (
                                <div>
                                    <div className="tp-section-label mb-1">HASH</div>
                                    <div className="text-[10px] font-mono text-fg-faint break-all">{detail.hash}</div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
