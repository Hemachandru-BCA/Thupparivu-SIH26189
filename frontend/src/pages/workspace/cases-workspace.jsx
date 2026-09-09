import { useState, useEffect } from 'react';
import { useRoute } from 'wouter';
import { useCases, useCaseDetail } from '@/api/xai';
import { FolderOpen, Plus, ChevronRight, Clock, Users, FileText } from 'lucide-react';
import { formatTimestamp } from '@/components/app-shell';

export default function CasesWorkspace() {
    const [, params] = useRoute('/cases/:id');
    const { data: casesData, isLoading } = useCases();
    const cases = casesData?.results || casesData?.items || casesData || [];
    const [selectedId, setSelectedId] = useState(params?.id || null);

    useEffect(() => {
        if (params?.id) setSelectedId(params.id);
    }, [params?.id]);

    const { data: detailData } = useCaseDetail(selectedId);
    const detail = detailData?.result || detailData;

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex overflow-hidden animate-fade-in">
            {/* Left: Case list */}
            <div className="w-80 border-r border-border-subtle flex flex-col shrink-0">
                <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                    <FolderOpen size={13} className="text-primary" />
                    <span className="text-[11px] font-semibold text-fg-primary">CASES</span>
                    <span className="tp-badge tp-badge-neutral">{cases.length}</span>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {cases.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center p-4">
                            <FolderOpen size={20} className="text-fg-faint mb-2" />
                            <span className="text-[10px] font-mono text-fg-faint uppercase">NO CASES</span>
                        </div>
                    ) : cases.map(c => (
                        <div key={c.id} onClick={() => setSelectedId(c.id)}
                            className={`px-3 py-2.5 border-b border-border-subtle cursor-pointer transition-colors
                                ${selectedId === c.id ? 'bg-blue-bg' : 'hover:bg-bg-hover'}`}>
                            <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                    <div className="text-[11px] text-fg-primary font-medium truncate">{c.title || c.id}</div>
                                    <div className="text-[9px] text-fg-faint font-mono">{c.id}</div>
                                </div>
                                <span className={`tp-badge shrink-0 ${
                                    c.status === 'active' ? 'tp-badge-green' :
                                    c.status === 'closed' ? 'tp-badge-neutral' :
                                    'tp-badge-blue'
                                }`}>{(c.status || 'OPEN').toUpperCase()}</span>
                            </div>
                            {c.description && (
                                <div className="text-[9px] text-fg-faint mt-1 line-clamp-2">{c.description}</div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Right: Case detail */}
            <div className="flex-1 overflow-y-auto">
                {!detail ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <FolderOpen size={24} className="text-fg-faint mb-3" />
                        <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">SELECT A CASE</span>
                    </div>
                ) : (
                    <div className="max-w-3xl mx-auto p-6 space-y-4">
                        <div className="border-b border-border-subtle pb-4">
                            <div className="font-mono text-[10px] text-fg-faint mb-1">{detail.id}</div>
                            <h2 className="text-[16px] font-semibold text-fg-primary mb-2">{detail.title || 'Investigation Case'}</h2>
                            <span className={`tp-badge ${detail.status === 'active' ? 'tp-badge-green' : 'tp-badge-blue'}`}>
                                {(detail.status || 'OPEN').toUpperCase()}
                            </span>
                        </div>
                        {detail.description && (
                            <div>
                                <div className="tp-section-label mb-2">DESCRIPTION</div>
                                <div className="text-[12px] text-fg-secondary leading-relaxed">{detail.description}</div>
                            </div>
                        )}
                        <div className="grid grid-cols-2 gap-3 text-[11px]">
                            <div className="tp-panel p-3">
                                <div className="text-[10px] font-mono text-fg-faint">INVESTIGATOR</div>
                                <div className="text-fg-secondary mt-0.5">{detail.investigator || '—'}</div>
                            </div>
                            <div className="tp-panel p-3">
                                <div className="text-[10px] font-mono text-fg-faint">ITEMS</div>
                                <div className="text-fg-secondary mt-0.5">{detail.items_count || detail.items?.length || 0}</div>
                            </div>
                            <div className="tp-panel p-3">
                                <div className="text-[10px] font-mono text-fg-faint">CREATED</div>
                                <div className="text-fg-secondary mt-0.5 font-mono">{formatTimestamp(detail.created_at)}</div>
                            </div>
                            <div className="tp-panel p-3">
                                <div className="text-[10px] font-mono text-fg-faint">UPDATED</div>
                                <div className="text-fg-secondary mt-0.5 font-mono">{formatTimestamp(detail.updated_at)}</div>
                            </div>
                        </div>
                        {detail.disclaimer && (
                            <div className="tp-panel p-3 border-amber/20 bg-amber-bg text-[10px] text-amber">
                                {detail.disclaimer}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
