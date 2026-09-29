/**
 * Overview Screen — SentinelGraph Investigative Workbench
 * Matches PDF Spec §4: Operation Sentinel CASE-0421
 * Metrics, Review Queue, Recent Evidence, Needs Attention, Pipeline Status.
 */
import React from 'react';
import { Link, useLocation } from 'wouter';
import {
    Network, Users, FileText, Brain, AlertTriangle,
    ArrowRight, Clock, Activity, Shield, Download,
    Layers, ExternalLink, CheckCircle2, ChevronRight
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { SYNTHETIC_FINDINGS, SYNTHETIC_EVIDENCE } from '@/state/synthetic-case-data';
import { StatusMark, ConfidenceBand, ScopeCount } from '@/components/shared';

export default function InvestigationDesk() {
    const { activeCase } = useInvestigation();
    const [, setLocation] = useLocation();

    const handleExportSummary = () => {
        const payload = {
            case: activeCase.id,
            title: activeCase.title,
            lead: activeCase.lead,
            snapshot: activeCase.snapshot,
            metrics: {
                entities: activeCase.entities_count,
                communities: activeCase.communities_count,
                evidence: activeCase.evidence_count,
                relationships: activeCase.relationships_count,
            },
            exported_by: 'A. Rao',
            exported_at: new Date().toISOString(),
            status: 'Draft / Heuristic summary',
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${activeCase.id}_summary_${Date.now()}.json`;
        a.click();
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[hsl(var(--border-default))]">
                <div>
                    <div className="flex items-center gap-2 text-[12px] font-mono text-[hsl(var(--fg-muted))] mb-1">
                        <span className="font-semibold text-[hsl(var(--fg-primary))]">{activeCase.id}</span>
                        <span>·</span>
                        <span>Lead: {activeCase.lead}</span>
                        <span>·</span>
                        <span>{activeCase.scope}</span>
                    </div>
                    <h1 className="text-[20px] font-semibold text-[hsl(var(--fg-primary))]">{activeCase.title}</h1>
                    <div className="text-[12px] text-[hsl(var(--fg-muted))] mt-1">
                        Updated {activeCase.updated}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button className="sg-btn" onClick={handleExportSummary}>
                        <Download size={13} />
                        Export summary
                    </button>
                    <button className="sg-btn sg-btn-primary" onClick={() => setLocation('/network')}>
                        <Network size={13} />
                        Open network
                    </button>
                </div>
            </div>

            {/* Top 4 Metrics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="sg-card p-4">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1">Entities</div>
                    <div className="text-[24px] font-mono font-semibold text-[hsl(var(--fg-primary))]">
                        {activeCase.entities_count.toLocaleString()}
                    </div>
                    <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-1">
                        {activeCase.relationships_count.toLocaleString()} relationships
                    </div>
                </div>
                <div className="sg-card p-4">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1">Communities</div>
                    <div className="text-[24px] font-mono font-semibold text-[hsl(var(--fg-primary))]">
                        {activeCase.communities_count.toLocaleString()}
                    </div>
                    <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-1">
                        Cross-community links available
                    </div>
                </div>
                <div className="sg-card p-4">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1">Evidence Records</div>
                    <div className="text-[24px] font-mono font-semibold text-[hsl(var(--fg-primary))]">
                        {activeCase.evidence_count.toLocaleString()}
                    </div>
                    <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-1">
                        All with indexed provenance
                    </div>
                </div>
                <div className="sg-card p-4">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1">Awaiting Review</div>
                    <div className="text-[24px] font-mono font-semibold text-[hsl(var(--amber-fg))]">
                        {activeCase.open_findings}
                    </div>
                    <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-1">
                        Findings: none dispositioned
                    </div>
                </div>
            </div>

            {/* Two Column Layout: Review Queue (Left) & Side Panels (Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left 2 Cols: Review Queue & Recent Evidence */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Review Queue */}
                    <div className="sg-card">
                        <div className="sg-card-header justify-between">
                            <div className="flex items-center gap-2">
                                <Brain size={15} className="text-[hsl(var(--primary))]" />
                                <span>Review queue</span>
                                <span className="sg-badge sg-badge-neutral">{SYNTHETIC_FINDINGS.length}</span>
                            </div>
                            <Link href="/findings">
                                <span className="text-[11px] text-[hsl(var(--primary))] hover:underline cursor-pointer flex items-center gap-1">
                                    All findings <ChevronRight size={11} />
                                </span>
                            </Link>
                        </div>
                        <div className="divide-y divide-[hsl(var(--border-subtle))]">
                            {SYNTHETIC_FINDINGS.map(f => (
                                <div
                                    key={f.id}
                                    className="p-4 hover:bg-[hsl(var(--bg-hover))] transition-colors cursor-pointer"
                                    onClick={() => setLocation(`/findings`)}
                                >
                                    <div className="flex items-center justify-between mb-1.5">
                                        <div className="flex items-center gap-2">
                                            <span className="font-mono text-[12px] font-semibold text-[hsl(var(--primary))]">{f.id}</span>
                                            <span className="text-[12px] text-[hsl(var(--fg-muted))]">·</span>
                                            <span className="text-[12px] text-[hsl(var(--fg-secondary))]">{f.category}</span>
                                        </div>
                                        <ConfidenceBand level={f.confidence} />
                                    </div>
                                    <div className="text-[13px] font-medium text-[hsl(var(--fg-primary))] mb-1">
                                        {f.title}
                                    </div>
                                    <div className="text-[11px] text-[hsl(var(--fg-muted))] line-clamp-1">
                                        {f.claim}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Recent Evidence */}
                    <div className="sg-card">
                        <div className="sg-card-header justify-between">
                            <div className="flex items-center gap-2">
                                <FileText size={15} className="text-[hsl(var(--primary))]" />
                                <span>Recent evidence</span>
                            </div>
                            <Link href="/evidence">
                                <span className="text-[11px] text-[hsl(var(--primary))] hover:underline cursor-pointer flex items-center gap-1">
                                    Evidence register <ChevronRight size={11} />
                                </span>
                            </Link>
                        </div>
                        <div className="divide-y divide-[hsl(var(--border-subtle))]">
                            {SYNTHETIC_EVIDENCE.slice(0, 3).map(e => (
                                <div
                                    key={e.id}
                                    className="p-3.5 hover:bg-[hsl(var(--bg-hover))] transition-colors cursor-pointer flex items-center justify-between"
                                    onClick={() => setLocation('/evidence')}
                                >
                                    <div className="min-w-0 pr-4">
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <span className="font-mono text-[12px] font-medium text-[hsl(var(--primary))]">{e.id}</span>
                                            <span className="text-[11px] text-[hsl(var(--fg-muted))]">·</span>
                                            <span className="text-[11px] text-[hsl(var(--fg-secondary))]">{e.type}</span>
                                        </div>
                                        <div className="text-[12px] text-[hsl(var(--fg-primary))] truncate">{e.title}</div>
                                    </div>
                                    <div className="text-right shrink-0">
                                        <StatusMark status={e.status} />
                                        <div className="text-[10px] font-mono text-[hsl(var(--fg-faint))] mt-0.5">
                                            {e.timestamp.replace('T', ' ').slice(0, 16)} UTC
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right Column: Needs Attention & Pipeline */}
                <div className="space-y-6">
                    {/* Needs Attention */}
                    <div className="sg-card">
                        <div className="sg-card-header">
                            <AlertTriangle size={15} className="text-[hsl(var(--amber))]" />
                            <span>Needs attention</span>
                        </div>
                        <div className="p-4 space-y-3">
                            <div className="flex items-center justify-between p-2.5 rounded bg-[hsl(var(--bg-hover))]">
                                <div>
                                    <div className="text-[12px] font-medium text-[hsl(var(--fg-primary))]">Burst anomalies</div>
                                    <div className="text-[11px] text-[hsl(var(--fg-muted))]">Unusual transfer velocity</div>
                                </div>
                                <span className="font-mono text-[14px] font-semibold text-[hsl(var(--amber-fg))]">
                                    {activeCase.burst_anomalies}
                                </span>
                            </div>
                            <div className="flex items-center justify-between p-2.5 rounded bg-[hsl(var(--bg-hover))]">
                                <div>
                                    <div className="text-[12px] font-medium text-[hsl(var(--fg-primary))]">Shell-account patterns</div>
                                    <div className="text-[11px] text-[hsl(var(--fg-muted))]">Zero-balance pass-throughs</div>
                                </div>
                                <span className="font-mono text-[14px] font-semibold text-[hsl(var(--amber-fg))]">
                                    {activeCase.shell_accounts}
                                </span>
                            </div>
                            <div className="flex items-center justify-between p-2.5 rounded bg-[hsl(var(--bg-hover))]">
                                <div>
                                    <div className="text-[12px] font-medium text-[hsl(var(--fg-primary))]">Draft dossiers</div>
                                    <div className="text-[11px] text-[hsl(var(--fg-muted))]">Awaiting validation</div>
                                </div>
                                <span className="font-mono text-[14px] font-semibold text-[hsl(var(--primary))]">
                                    {activeCase.draft_dossiers}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Pipeline Status */}
                    <div className="sg-card">
                        <div className="sg-card-header">
                            <Activity size={15} className="text-[hsl(var(--green))]" />
                            <span>Pipeline execution</span>
                        </div>
                        <div className="p-4 space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="font-mono text-[12px] text-[hsl(var(--fg-muted))]">{activeCase.pipeline}</span>
                                <StatusMark status={activeCase.pipeline_state} />
                            </div>
                            <div className="sg-progress">
                                <div className="sg-progress-bar" style={{ width: '90%' }} />
                            </div>
                            <div className="text-[11px] text-[hsl(var(--fg-muted))]">
                                {activeCase.pipeline_stage}
                            </div>
                            <div className="pt-2 border-t border-[hsl(var(--border-subtle))] flex justify-between items-center text-[11px]">
                                <span className="text-[hsl(var(--fg-faint))]">Data times are UTC</span>
                                <Link href="/audit">
                                    <span className="text-[hsl(var(--primary))] hover:underline cursor-pointer">Pipeline details</span>
                                </Link>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
