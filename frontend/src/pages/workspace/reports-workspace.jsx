import { useState, useMemo, useEffect } from 'react';
import { useRoute } from 'wouter';
import { useDossiers, useDossierDetail, generateDossier } from '@/api/xai';
import { BookOpen, ChevronRight, Plus, FileText, AlertTriangle, Download, FileArchive, CheckCircle2 } from 'lucide-react';
import { formatTimestamp } from '@/components/app-shell';
import { requestJson } from '@/api/client';

export default function ReportsWorkspace() {
    const [, params] = useRoute('/dossiers/:id');
    const { data: dossiersData, isLoading } = useDossiers();
    const dossiers = dossiersData?.results || dossiersData?.items || dossiersData || [];
    const [selectedId, setSelectedId] = useState(params?.id || null);

    useEffect(() => {
        if (params?.id) setSelectedId(params.id);
    }, [params?.id]);

    const [generateTarget, setGenerateTarget] = useState('');
    const [generating, setGenerating] = useState(false);
    const [exporting, setExporting] = useState(false);
    const [exportSuccess, setExportSuccess] = useState(false);

    const { data: detailData } = useDossierDetail(selectedId);
    const detail = detailData?.result || detailData;

    const handleGenerate = async () => {
        if (!generateTarget.trim()) return;
        setGenerating(true);
        try {
            await generateDossier({ subject_id: generateTarget.trim() });
            setGenerateTarget('');
        } catch (e) {
            console.error('Dossier generation failed:', e);
        } finally {
            setGenerating(false);
        }
    };

    const handleExportPack = async () => {
        setExporting(true);
        try {
            const pack = await requestJson('/api/dossiers/export/investigation-pack?case_id=CASE-0421', { method: 'GET' });
            // Download as JSON file
            const blob = new Blob([JSON.stringify(pack, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sentinelgraph_investigation_pack_${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            setExportSuccess(true);
            setTimeout(() => setExportSuccess(false), 3000);
        } catch (e) {
            console.error('Export failed:', e);
            alert('Export failed. See console for details.');
        } finally {
            setExporting(false);
        }
    };

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex overflow-hidden animate-fade-in">
            {/* Left: Dossier list */}
            <div className="w-80 border-r border-border-subtle flex flex-col shrink-0">
                <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                    <BookOpen size={13} className="text-primary" />
                    <span className="text-[11px] font-semibold text-fg-primary">REPORTS</span>
                    <span className="tp-badge tp-badge-neutral">{dossiers.length}</span>
                </div>

                {/* Generate & Export */}
                <div className="px-3 py-2 border-b border-border-subtle space-y-2">
                    <button 
                        onClick={handleExportPack} 
                        disabled={exporting}
                        className={`w-full tp-btn h-8 text-[10px] gap-2 ${exportSuccess ? 'tp-btn-green' : 'tp-btn-ghost hover:bg-bg-hover'}`}
                    >
                        {exportSuccess ? <CheckCircle2 size={12} /> : <FileArchive size={12} />}
                        {exportSuccess ? 'EXPORT COMPLETE' : 'EXPORT FULL INVESTIGATION PACK'}
                    </button>
                    <div className="flex gap-2 pt-1 border-t border-border-subtle">
                        <input value={generateTarget} onChange={e => setGenerateTarget(e.target.value)}
                            placeholder="Subject ID..."
                            className="tp-input h-7 text-[10px] flex-1" />
                        <button onClick={handleGenerate} disabled={generating || !generateTarget.trim()}
                            className="tp-btn tp-btn-primary text-[9px] h-7">
                            <Plus size={10} /> Generate
                        </button>
                    </div>
                </div>

                {/* List */}
                <div className="flex-1 overflow-y-auto">
                    {dossiers.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center p-4">
                            <BookOpen size={20} className="text-fg-faint mb-2" />
                            <span className="text-[10px] font-mono text-fg-faint uppercase">NO REPORTS</span>
                            <span className="text-[9px] text-fg-faint mt-1">Generate a dossier to begin</span>
                        </div>
                    ) : dossiers.map(d => (
                        <div key={d.id} onClick={() => setSelectedId(d.id)}
                            className={`px-3 py-2.5 border-b border-border-subtle cursor-pointer transition-colors
                                ${selectedId === d.id ? 'bg-blue-bg' : 'hover:bg-bg-hover'}`}>
                            <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                    <div className="text-[11px] text-fg-primary font-medium truncate">{d.title || d.id}</div>
                                    <div className="text-[9px] text-fg-faint font-mono">{d.id}</div>
                                </div>
                                <span className={`tp-badge shrink-0 ${
                                    d.status === 'reviewed' ? 'tp-badge-green' :
                                    d.status === 'draft' ? 'tp-badge-neutral' :
                                    'tp-badge-blue'
                                }`}>
                                    {d.status || 'DRAFT'}
                                </span>
                            </div>
                            {d.confidence != null && (
                                <div className="mt-1 text-[9px] font-mono text-fg-faint">
                                    CONFIDENCE: {(d.confidence * 100).toFixed(0)}%
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Right: Dossier detail */}
            <div className="flex-1 overflow-y-auto">
                {!detail ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <FileText size={24} className="text-fg-faint mb-3" />
                        <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">SELECT A REPORT</span>
                    </div>
                ) : (
                    <div className="max-w-3xl mx-auto p-6 space-y-6">
                        {/* Header */}
                        <div className="border-b border-border-subtle pb-4">
                            <div className="font-mono text-[10px] text-fg-faint mb-1">{detail.id}</div>
                            <h2 className="text-[16px] font-semibold text-fg-primary mb-2">{detail.title || 'Intelligence Dossier'}</h2>
                            <div className="flex items-center gap-3">
                                <span className={`tp-badge ${detail.status === 'reviewed' ? 'tp-badge-green' : 'tp-badge-blue'}`}>
                                    {(detail.status || 'DRAFT').toUpperCase()}
                                </span>
                                {detail.confidence != null && (
                                    <span className="text-[10px] font-mono text-fg-faint">
                                        CONFIDENCE: {(detail.confidence * 100).toFixed(0)}%
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* Executive summary */}
                        {detail.executive_summary && (
                            <div>
                                <div className="tp-section-label mb-2">EXECUTIVE SUMMARY</div>
                                <div className="text-[12px] text-fg-secondary leading-relaxed border-l-2 border-primary pl-3">
                                    {detail.executive_summary}
                                </div>
                            </div>
                        )}

                        {/* Sections */}
                        {detail.sections?.map((section, i) => (
                            <div key={i}>
                                <div className="tp-section-label mb-2">{section.title?.toUpperCase()}</div>
                                <div className="space-y-2">
                                    {section.items?.map((item, j) => (
                                        <div key={j} className="tp-panel p-3">
                                            <div className="text-[11px] text-fg-primary font-medium mb-1">{item.label}</div>
                                            <div className="text-[11px] text-fg-secondary">{item.text}</div>
                                            {item.evidence_ids?.length > 0 && (
                                                <div className="flex gap-1 mt-1.5">
                                                    {item.evidence_ids.map(eid => (
                                                        <span key={eid} className="tp-badge tp-badge-neutral" style={{fontSize: '8px'}}>{eid}</span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}

                        {/* Limitations */}
                        {detail.limitations?.length > 0 && (
                            <div>
                                <div className="tp-section-label mb-2">LIMITATIONS</div>
                                <div className="space-y-1">
                                    {detail.limitations.map((lim, i) => (
                                        <div key={i} className="flex items-start gap-2 text-[11px] text-amber">
                                            <AlertTriangle size={10} className="shrink-0 mt-0.5" />
                                            <span>{lim}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Human review */}
                        {detail.human_review && (
                            <div className="tp-panel p-3 border-amber/20 bg-amber-bg">
                                <div className="tp-section-label mb-1">HUMAN REVIEW</div>
                                <div className="text-[10px] text-fg-secondary">
                                    Required: {detail.human_review.required ? 'Yes' : 'No'}
                                    {detail.human_review.decision && ` · Decision: ${detail.human_review.decision}`}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
