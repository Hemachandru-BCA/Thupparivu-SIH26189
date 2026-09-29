/**
 * Findings Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §8: Findings screen & Decision UX.
 * Primary detail state: FND-003 (Potential intermediary bridging communities 0 and 6).
 * Decision Gate with rationale + counter-evidence confirmation.
 */
import React, { useState } from 'react';
import { Brain, Shield, CheckCircle2, XCircle, AlertTriangle, FileText, ChevronRight } from 'lucide-react';
import { SYNTHETIC_FINDINGS } from '@/state/synthetic-case-data';
import { StatusMark, ConfidenceBand, DecisionGate, EvidenceReference } from '@/components/shared';

export default function HypothesesWorkspace() {
    const [selectedFindingId, setSelectedFindingId] = useState('FND-003');
    const [auditLogNotice, setAuditLogNotice] = useState(null);

    const finding = SYNTHETIC_FINDINGS.find(f => f.id === selectedFindingId) || SYNTHETIC_FINDINGS[0];

    const handleDecisionRecorded = (decisionData) => {
        setAuditLogNotice(`Decision recorded for ${finding.id} (${decisionData.decision}) at ${decisionData.timestamp} by ${decisionData.actor}. Rationale logged to immutable audit trail.`);
    };

    return (
        <div className="flex h-full overflow-hidden animate-fade-in bg-[hsl(var(--bg-root))]">
            {/* Left: Findings list */}
            <div className="w-80 bg-[hsl(var(--bg-surface))] border-r border-[hsl(var(--border-subtle))] flex flex-col shrink-0">
                <div className="p-4 border-b border-[hsl(var(--border-subtle))] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Brain size={16} className="text-[hsl(var(--primary))]" />
                        <span className="text-[14px] font-semibold text-[hsl(var(--fg-primary))]">Findings</span>
                    </div>
                    <span className="sg-badge sg-badge-neutral">{SYNTHETIC_FINDINGS.length}</span>
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-[hsl(var(--border-subtle))]">
                    {SYNTHETIC_FINDINGS.map(f => {
                        const isSelected = f.id === finding.id;
                        return (
                            <div
                                key={f.id}
                                className={`p-4 cursor-pointer transition-colors ${isSelected ? 'bg-[hsl(var(--bg-selected))]/60 border-l-2 border-[hsl(var(--primary))]' : 'hover:bg-[hsl(var(--bg-hover))]'}`}
                                onClick={() => setSelectedFindingId(f.id)}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className="font-mono text-[12px] font-semibold text-[hsl(var(--primary))]">{f.id}</span>
                                    <ConfidenceBand level={f.confidence} />
                                </div>
                                <div className="text-[12px] font-medium text-[hsl(var(--fg-primary))] line-clamp-2 mb-2">
                                    {f.title}
                                </div>
                                <div className="flex items-center justify-between">
                                    <StatusMark status={f.status} />
                                    <span className="text-[10px] text-[hsl(var(--fg-faint))] font-mono">{f.type}</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Right: Finding Detail + Decision UX */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {auditLogNotice && (
                    <div className="sg-info-banner">
                        <CheckCircle2 size={16} className="text-[hsl(var(--green))]" />
                        <div>
                            <div className="font-semibold">Successfully written to audit log</div>
                            <div className="text-[11px]">{auditLogNotice}</div>
                        </div>
                    </div>
                )}

                {/* Header card */}
                <div className="sg-card p-5 space-y-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-[14px] font-bold text-[hsl(var(--primary))]">{finding.id}</span>
                            <span className="text-[hsl(var(--fg-faint))]">·</span>
                            <span className="text-[12px] font-semibold uppercase tracking-wider text-[hsl(var(--fg-muted))]">{finding.type}</span>
                        </div>
                        <StatusMark status={finding.status} />
                    </div>
                    <h1 className="text-[18px] font-semibold text-[hsl(var(--fg-primary))]">{finding.title}</h1>
                    <p className="text-[13px] text-[hsl(var(--fg-secondary))] leading-relaxed bg-[hsl(var(--bg-panel))] p-3 rounded border border-[hsl(var(--border-subtle))]">
                        <strong className="text-[hsl(var(--fg-primary))]">Claim:</strong> {finding.claim}
                    </p>
                </div>

                {/* Evidence & Component Breakdown */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="sg-card p-5 space-y-4">
                        <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Supporting & Counter Evidence</div>
                        <div className="space-y-3 text-[12px]">
                            <div>
                                <span className="text-[hsl(var(--fg-muted))] block mb-1">Supporting evidence records:</span>
                                <div className="flex flex-wrap gap-1.5">
                                    {finding.supporting_evidence.map(id => (
                                        <EvidenceReference key={id} id={id} />
                                    ))}
                                </div>
                            </div>
                            <div>
                                <span className="text-[hsl(var(--fg-muted))] block mb-1">Counter-evidence records:</span>
                                <div className="flex flex-wrap gap-1.5">
                                    {finding.counter_evidence.map(id => (
                                        <EvidenceReference key={id} id={id} />
                                    ))}
                                </div>
                            </div>
                            <div>
                                <span className="text-[hsl(var(--fg-muted))] block mb-1">Unknown factor:</span>
                                <div className="text-[hsl(var(--fg-primary))] bg-[hsl(var(--amber-bg))] p-2 rounded border border-[hsl(var(--amber-border))] text-[11px]">
                                    {finding.unknown}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="sg-card p-5 space-y-4">
                        <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Assessment Breakdown</div>
                        <div className="space-y-2 text-[12px]">
                            <div className="flex items-center justify-between pb-2 border-b border-[hsl(var(--border-subtle))]">
                                <span className="text-[hsl(var(--fg-muted))]">Heuristic confidence band:</span>
                                <ConfidenceBand level={finding.assessment.band} />
                            </div>
                            <div className="flex items-center justify-between pb-2 border-b border-[hsl(var(--border-subtle))]">
                                <span className="text-[hsl(var(--fg-muted))]">Composite score:</span>
                                <span className="font-mono font-semibold text-[hsl(var(--primary))]">{finding.assessment.heuristic_score}</span>
                            </div>
                            <div className="text-[10px] text-[hsl(var(--fg-faint))] italic">
                                "{finding.assessment.disclaimer}"
                            </div>
                            <div className="space-y-1.5 pt-2">
                                <div className="text-[11px] font-medium text-[hsl(var(--fg-primary))]">Component support:</div>
                                {Object.entries(finding.assessment.components).map(([k, v]) => (
                                    <div key={k} className="text-[11px] flex justify-between gap-2">
                                        <span className="text-[hsl(var(--fg-muted))] capitalize">{k.replace('_', ' ')}:</span>
                                        <span className="text-right text-[hsl(var(--fg-secondary))] truncate max-w-[200px]" title={v}>{v}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* What would change this assessment */}
                <div className="sg-card p-5 space-y-3">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">What would change this assessment</div>
                    <ul className="space-y-1.5 text-[12px] list-disc list-inside text-[hsl(var(--fg-secondary))]">
                        {finding.change_conditions.map((cond, i) => (
                            <li key={i}>{cond}</li>
                        ))}
                    </ul>
                </div>

                {/* Controlled Decision Flow Gate */}
                <DecisionGate
                    requirements={[
                        { label: 'Supporting evidence records verified', met: true },
                        { label: 'Counter-evidence record EV-19882 inspected', met: true },
                        { label: 'Analyst credential (A. Rao · Editor) verified', met: true }
                    ]}
                    onDecision={handleDecisionRecorded}
                />
            </div>
        </div>
    );
}
