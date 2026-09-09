import { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { useFindings, useFindingDetail } from '@/api/xai';
import { Brain, ChevronRight, AlertTriangle, Clock, Target, FileText } from 'lucide-react';
import { getConfidenceColor, formatNumber } from '@/components/app-shell';

function ConfidenceBar({ value, height = 3 }) {
    const color = getConfidenceColor(value);
    return (
        <div className="tp-confidence-bar" style={{ height }}>
            <div className="tp-confidence-fill" style={{ width: `${value * 100}%`, background: color }} />
        </div>
    );
}

function FindingRow({ finding }) {
    const conf = finding.confidence || 0;
    const confColor = getConfidenceColor(conf);
    return (
        <Link href={`/findings/${finding.finding_id || finding.id}`}>
            <div className="flex items-center gap-4 px-4 py-2.5 border-b border-border-subtle hover:bg-bg-hover cursor-pointer transition-colors">
                {/* ID */}
                <span className="font-mono text-[10px] text-fg-faint w-20 shrink-0">
                    {finding.finding_id || finding.id}
                </span>

                {/* Type */}
                <span className="tp-badge tp-badge-purple shrink-0" style={{maxWidth: 100}}>
                    {finding.finding_type || 'FINDING'}
                </span>

                {/* Subject */}
                <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-fg-primary font-medium truncate">
                        {finding.subject_label || finding.subject_id || 'Unknown'}
                    </div>
                    <div className="text-[10px] text-fg-faint truncate">
                        {finding.method || 'Analysis finding'}
                    </div>
                </div>

                {/* Evidence counts */}
                <div className="flex items-center gap-3 shrink-0">
                    {finding.observed?.length > 0 && (
                        <span className="text-[9px] font-mono text-green">
                            {finding.observed.length} observed
                        </span>
                    )}
                    {finding.counter_evidence_ids?.length > 0 && (
                        <span className="text-[9px] font-mono text-red">
                            {finding.counter_evidence_ids.length} counter
                        </span>
                    )}
                </div>

                {/* Confidence */}
                <div className="w-24 shrink-0">
                    <div className="flex items-center justify-between mb-0.5">
                        <span className="font-mono text-[10px] font-semibold" style={{color: confColor}}>
                            {(conf * 100).toFixed(0)}%
                        </span>
                    </div>
                    <ConfidenceBar value={conf} />
                </div>

                {/* Status */}
                <span className={`tp-badge shrink-0 ${
                    finding.status === 'open' ? 'tp-badge-blue' :
                    finding.status === 'review' ? 'tp-badge-amber' :
                    'tp-badge-neutral'
                }`}>
                    {finding.status || 'OPEN'}
                </span>

                <ChevronRight size={12} className="text-fg-faint shrink-0" />
            </div>
        </Link>
    );
}

export default function HypothesesWorkspace() {
    const { data: findingsData, isLoading } = useFindings();
    const findings = findingsData?.results || findingsData?.items || findingsData || [];
    const [filterStatus, setFilterStatus] = useState('ALL');

    const stats = useMemo(() => {
        const total = findings.length;
        const open = findings.filter(f => f.status === 'open' || !f.status).length;
        const highConf = findings.filter(f => (f.confidence || 0) >= 0.75).length;
        const review = findings.filter(f => f.status === 'review').length;
        return { total, open, highConf, review };
    }, [findings]);

    const filtered = useMemo(() => {
        if (filterStatus === 'ALL') return findings;
        if (filterStatus === 'HIGH') return findings.filter(f => (f.confidence || 0) >= 0.75);
        return findings.filter(f => f.status === filterStatus.toLowerCase());
    }, [findings, filterStatus]);

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            {/* Header stats */}
            <div className="flex items-center gap-4 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <div className="flex items-center gap-2">
                    <Brain size={13} className="text-purple" />
                    <span className="text-[11px] font-semibold text-fg-primary">HYPOTHESES</span>
                </div>
                <div className="w-px h-4 bg-border-default" />
                <div className="flex items-center gap-4 text-[10px] font-mono">
                    <span className="text-fg-faint">{stats.total} TOTAL</span>
                    <span className="text-blue">{stats.open} OPEN</span>
                    <span className="text-amber">{stats.highConf} HIGH CONFIDENCE</span>
                    {stats.review > 0 && <span className="text-amber">{stats.review} REVIEW</span>}
                </div>
                <div className="flex-1" />
                <div className="flex items-center gap-1">
                    {['ALL', 'HIGH', 'OPEN', 'REVIEW'].map(s => (
                        <button key={s} onClick={() => setFilterStatus(s)}
                            className={`tp-btn text-[9px] h-5 px-2 ${filterStatus === s ? 'tp-btn-primary' : 'tp-btn-ghost'}`}>
                            {s}
                        </button>
                    ))}
                </div>
            </div>

            {/* Findings table */}
            <div className="flex-1 overflow-y-auto">
                {filtered.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <Brain size={24} className="text-fg-faint mb-3" />
                        <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">NO HYPOTHESES DETECTED</span>
                        <span className="text-[10px] text-fg-faint mt-1">The current evidence does not support a strong inference</span>
                    </div>
                ) : (
                    <>
                        {/* Table header */}
                        <div className="flex items-center gap-4 px-4 py-1.5 border-b border-border-default bg-bg-panel sticky top-0 z-1">
                            <span className="font-mono text-[9px] text-fg-faint w-20 shrink-0">ID</span>
                            <span className="font-mono text-[9px] text-fg-faint shrink-0" style={{width: 100}}>TYPE</span>
                            <span className="font-mono text-[9px] text-fg-faint flex-1">SUBJECT</span>
                            <span className="font-mono text-[9px] text-fg-faint shrink-0">EVIDENCE</span>
                            <span className="font-mono text-[9px] text-fg-faint w-24 shrink-0">CONFIDENCE</span>
                            <span className="font-mono text-[9px] text-fg-faint shrink-0">STATUS</span>
                            <span className="w-3" />
                        </div>
                        {filtered.map((f, i) => (
                            <FindingRow key={f.finding_id || f.id || i} finding={f} />
                        ))}
                    </>
                )}
            </div>
        </div>
    );
}
