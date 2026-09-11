import { useFindingDetail, useEvidenceChainForFinding } from '@/api/xai';
import { useRoute, Link } from 'wouter';
import { Brain, ChevronLeft, AlertTriangle, FileText, CheckCircle, HelpCircle, XCircle } from 'lucide-react';
import { getConfidenceColor } from '@/components/app-shell';
import { EvidenceChainWidget } from '@/components/evidence-chain';

export default function FindingDetailPage() {
    const [, params] = useRoute('/findings/:id');
    const findingId = params?.id;
    const { data: findingData, isLoading } = useFindingDetail(findingId);
    const { data: chainData, isLoading: isChainLoading } = useEvidenceChainForFinding(findingId);
    const finding = findingData?.result || findingData;

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    if (!finding) return (
        <div className="flex flex-col items-center justify-center h-full text-center">
            <Brain size={24} className="text-fg-faint mb-3" />
            <span className="text-[11px] font-mono text-fg-faint uppercase">FINDING NOT FOUND</span>
            <Link href="/findings">
                <button className="tp-btn tp-btn-primary text-[10px] mt-3">Back to Hypotheses</button>
            </Link>
        </div>
    );

    const conf = finding.confidence || 0;
    const confColor = getConfidenceColor(conf);

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <Link href="/findings">
                    <button className="tp-btn tp-btn-ghost text-[10px] h-6 px-1.5 gap-1">
                        <ChevronLeft size={12} /> Hypotheses
                    </button>
                </Link>
                <div className="w-px h-4 bg-border-default" />
                <span className="font-mono text-[10px] text-fg-faint">{finding.finding_id || finding.id}</span>
                <span className="tp-badge tp-badge-purple">{finding.finding_type || 'FINDING'}</span>
                <div className="flex-1" />
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-fg-faint">CONFIDENCE:</span>
                    <span className="font-mono text-[13px] font-bold" style={{color: confColor}}>
                        {(conf * 100).toFixed(0)}%
                    </span>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto space-y-6">
                {/* Subject & summary */}
                <div>
                    <h1 className="text-[18px] font-semibold text-fg-primary mb-1">
                        {finding.subject_label || finding.subject_id || 'Investigative Finding'}
                    </h1>
                    <div className="text-[12px] text-fg-secondary leading-relaxed">
                        {finding.finding_text || finding.method || 'Investigative model inference'}
                    </div>
                </div>

                {/* Epistemic claims */}
                <div className="grid grid-cols-3 gap-4">
                    {/* Observed */}
                    <div className="tp-panel p-3">
                        <div className="flex items-center gap-1.5 mb-2">
                            <CheckCircle size={11} className="text-green" />
                            <span className="tp-section-label text-green">OBSERVED FACTS ({finding.observed?.length || 0})</span>
                        </div>
                        <div className="space-y-1.5">
                            {finding.observed?.length > 0 ? finding.observed.map((obs, i) => (
                                <div key={i} className="text-[11px] text-fg-secondary">
                                    {typeof obs === 'string' ? obs : obs.text}
                                    {obs.evidence_ids?.length > 0 && (
                                        <div className="flex gap-1 mt-0.5">
                                            {obs.evidence_ids.map(eid => (
                                                <span key={eid} className="tp-badge tp-badge-neutral" style={{fontSize: '7px'}}>{eid}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )) : (
                                <span className="text-[10px] text-fg-faint">None recorded</span>
                            )}
                        </div>
                    </div>

                    {/* Inferred */}
                    <div className="tp-panel p-3">
                        <div className="flex items-center gap-1.5 mb-2">
                            <Brain size={11} className="text-purple" />
                            <span className="tp-section-label text-purple">MODEL INFERENCES ({finding.inferred?.length || 0})</span>
                        </div>
                        <div className="space-y-1.5">
                            {finding.inferred?.length > 0 ? finding.inferred.map((inf, i) => (
                                <div key={i} className="text-[11px] text-purple italic">
                                    {typeof inf === 'string' ? inf : inf.text}
                                </div>
                            )) : (
                                <span className="text-[10px] text-fg-faint">None recorded</span>
                            )}
                        </div>
                    </div>

                    {/* Unknowns / Unresolved */}
                    <div className="tp-panel p-3">
                        <div className="flex items-center gap-1.5 mb-2">
                            <HelpCircle size={11} className="text-fg-faint" />
                            <span className="tp-section-label text-fg-faint">UNRESOLVED ({finding.unknown?.length || 0})</span>
                        </div>
                        <div className="space-y-1.5">
                            {finding.unknown?.length > 0 ? finding.unknown.map((unk, i) => (
                                <div key={i} className="text-[11px] text-fg-faint">
                                    {typeof unk === 'string' ? unk : unk.text}
                                </div>
                            )) : (
                                <span className="text-[10px] text-fg-faint">None recorded</span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Confidence breakdown components */}
                {finding.confidence_components?.length > 0 && (
                    <div className="tp-panel p-4">
                        <div className="tp-section-label mb-3">ANALYSIS CONTRIBUTION</div>
                        <div className="space-y-2">
                            {finding.confidence_components.map((comp, i) => (
                                <div key={i}>
                                    <div className="flex justify-between text-[11px] mb-0.5">
                                        <span className="text-fg-secondary">{comp.name}</span>
                                        <span className="font-mono text-fg-primary">
                                            {(comp.value > 0 ? '+' : '') + (comp.value?.toFixed(2) || '0.00')}
                                        </span>
                                    </div>
                                    <div className="tp-confidence-bar">
                                        <div className="tp-confidence-fill" style={{
                                            width: `${Math.min(Math.abs(comp.value || 0) * 100, 100)}%`,
                                            background: (comp.value || 0) >= 0 ? 'hsl(var(--primary))' : 'hsl(var(--red))'
                                        }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Supporting evidence */}
                {finding.supporting_evidence_ids?.length > 0 && (
                    <div>
                        <div className="tp-section-label mb-2">SUPPORTING EVIDENCE</div>
                        <div className="flex flex-wrap gap-1.5">
                            {finding.supporting_evidence_ids.map(eid => (
                                <span key={eid} className="tp-badge tp-badge-green font-mono">{eid}</span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Counter evidence */}
                {finding.counter_evidence_ids?.length > 0 && (
                    <div>
                        <div className="tp-section-label mb-2">COUNTER-EVIDENCE</div>
                        <div className="flex flex-wrap gap-1.5">
                            {finding.counter_evidence_ids.map(eid => (
                                <span key={eid} className="tp-badge tp-badge-red font-mono">{eid}</span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Traceable Evidence Chain Widget (5-stage) */}
                <EvidenceChainWidget
                    chainData={chainData}
                    isLoading={isChainLoading}
                    title="End-to-End Provenance & Evidence Chain"
                />

                {/* Limitations */}
                {finding.limitations?.length > 0 && (
                    <div className="tp-panel p-3 border-amber/20 bg-amber-bg">
                        <div className="tp-section-label mb-2 text-amber">LIMITATIONS & CAVEATS</div>
                        <div className="space-y-1">
                            {finding.limitations.map((lim, i) => (
                                <div key={i} className="flex items-start gap-2 text-[11px] text-amber">
                                    <AlertTriangle size={10} className="shrink-0 mt-0.5" />
                                    <span>{lim}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
