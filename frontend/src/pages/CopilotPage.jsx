/**
 * Copilot Page — SentinelGraph Investigative Workbench
 * Matches PDF Spec §14: Copilot.
 * Header: CASE-0421, Entity: Nicole Jackson, Deterministic case queries, Citations on.
 * Answer: Moderate (no numeric decimals), uses EV-24091, EV-22704, EV-19882, FND-003.
 * Deterministic action trace + cited entities & records underneath.
 */
import React, { useState } from 'react';
import { MessageSquare, Send, Sparkles, Shield, FileText, CheckCircle2, ChevronDown, CornerDownRight } from 'lucide-react';
import { SYNTHETIC_COPILOT_QA } from '@/state/synthetic-case-data';
import { ConfidenceBand, EvidenceReference } from '@/components/shared';

export default function CopilotPage() {
    const [query, setQuery] = useState(SYNTHETIC_COPILOT_QA.question);
    const [qaData, setQaData] = useState(SYNTHETIC_COPILOT_QA);
    const [actionTraceExpanded, setActionTraceExpanded] = useState(true);

    const handleSubmit = (e) => {
        e.preventDefault();
        setQaData(SYNTHETIC_COPILOT_QA);
    };

    return (
        <div className="flex flex-col h-full bg-[hsl(var(--bg-root))] overflow-hidden animate-fade-in">
            {/* Header Deck */}
            <div className="p-4 bg-[hsl(var(--bg-surface))] border-b border-[hsl(var(--border-subtle))] flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <MessageSquare size={18} className="text-[hsl(var(--primary))]" />
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-[13px] font-bold text-[hsl(var(--primary))]">{qaData.header.case}</span>
                            <span className="text-[hsl(var(--fg-muted))]">·</span>
                            <span className="text-[12px] font-medium text-[hsl(var(--fg-secondary))]">Entity: {qaData.header.entity}</span>
                        </div>
                        <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-0.5 flex items-center gap-2">
                            <span>{qaData.header.mode}</span>
                            <span>·</span>
                            <span className="text-[hsl(var(--green-fg))] font-medium">{qaData.header.citations}</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[11px] text-[hsl(var(--fg-muted))]">Audited session:</span>
                    <span className="font-mono text-[11px] bg-[hsl(var(--bg-panel))] px-2 py-0.5 rounded border border-[hsl(var(--border-subtle))]">
                        JOB-9421
                    </span>
                </div>
            </div>

            {/* Conversation Flow Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto w-full">
                {/* User Query Message */}
                <div className="flex items-start gap-3 justify-end">
                    <div className="bg-[hsl(var(--primary-bg))] border border-[hsl(var(--primary-border))] p-4 rounded-lg max-w-xl text-[13px] text-[hsl(var(--fg-primary))]">
                        {qaData.question}
                    </div>
                </div>

                {/* Copilot Response Card */}
                <div className="sg-card p-5 space-y-4">
                    {/* Answer Header */}
                    <div className="flex items-center justify-between border-b border-[hsl(var(--border-subtle))] pb-3">
                        <div className="flex items-center gap-2">
                            <Sparkles size={16} className="text-[hsl(var(--primary))]" />
                            <span className="text-[13px] font-semibold text-[hsl(var(--fg-primary))]">Deterministic Analytical Assessment</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-[11px] text-[hsl(var(--fg-muted))]">Support Confidence:</span>
                            <ConfidenceBand level={qaData.answer_label} />
                        </div>
                    </div>

                    {/* Answer Body */}
                    <div className="text-[13px] text-[hsl(var(--fg-primary))] leading-relaxed whitespace-pre-line space-y-2">
                        {qaData.answer_text}
                    </div>

                    {/* Deterministic Action Trace */}
                    <div className="border-t border-[hsl(var(--border-subtle))] pt-3 space-y-2">
                        <button
                            className="flex items-center gap-1.5 text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider cursor-pointer hover:text-[hsl(var(--fg-primary))] transition-colors"
                            onClick={() => setActionTraceExpanded(!actionTraceExpanded)}
                        >
                            <ChevronDown size={13} className={`transform transition-transform ${actionTraceExpanded ? '' : '-rotate-90'}`} />
                            <span>Deterministic Action Trace ({qaData.action_trace.length} tool calls)</span>
                        </button>
                        {actionTraceExpanded && (
                            <div className="space-y-1.5 bg-[hsl(var(--bg-panel))] p-3 rounded border border-[hsl(var(--border-subtle))] font-mono text-[11px]">
                                {qaData.action_trace.map((tr, i) => (
                                    <div key={i} className="flex items-start gap-2">
                                        <CornerDownRight size={12} className="text-[hsl(var(--primary))] shrink-0 mt-0.5" />
                                        <span className="text-[hsl(var(--primary))] font-semibold">{tr.action}</span>
                                        <span className="text-[hsl(var(--fg-muted))]">→</span>
                                        <span className="text-[hsl(var(--fg-secondary))] truncate">{tr.result}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Cited Records & Entities */}
                    <div className="border-t border-[hsl(var(--border-subtle))] pt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <div className="text-[10px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1.5">Cited Evidence Records</div>
                            <div className="flex flex-wrap gap-1.5">
                                {qaData.cited_records.map(r => (
                                    <EvidenceReference key={r} id={r} />
                                ))}
                            </div>
                        </div>
                        <div>
                            <div className="text-[10px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1.5">Cited Entities</div>
                            <div className="flex flex-wrap gap-1.5">
                                {qaData.cited_entities.map(ent => (
                                    <span key={ent} className="px-2 py-0.5 text-[11px] bg-[hsl(var(--bg-panel))] border border-[hsl(var(--border-default))] rounded text-[hsl(var(--fg-secondary))]">
                                        {ent}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Input Bar */}
            <div className="p-4 bg-[hsl(var(--bg-surface))] border-t border-[hsl(var(--border-subtle))]">
                <form onSubmit={handleSubmit} className="max-w-4xl mx-auto flex items-center gap-3">
                    <input
                        className="sg-input flex-1"
                        placeholder="Ask a question about active case evidence, findings, or topologies…"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                    />
                    <button type="submit" className="sg-btn sg-btn-primary">
                        <Send size={13} />
                        Query
                    </button>
                </form>
            </div>
        </div>
    );
}
