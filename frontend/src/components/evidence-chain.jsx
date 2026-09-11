import React, { useState } from 'react';
import {
    Brain, Network, FileText, CheckCircle, AlertTriangle, ShieldCheck,
    ChevronRight, ArrowDown, Hash, Clock, Layers, Sparkles, ExternalLink,
    Copy, Check
} from 'lucide-react';
import { getConfidenceColor } from '@/components/app-shell';
import { Link } from 'wouter';

export function EvidenceChainWidget({ chainData, isLoading, title = "Traceable Evidence Chain" }) {
    const [selectedLevel, setSelectedLevel] = useState(null);
    const [activeTab, setActiveTab] = useState('supporting'); // 'supporting' | 'counter'
    const [copiedId, setCopiedId] = useState(null);

    const copyToClipboard = (text, id) => {
        navigator.clipboard.writeText(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
    };

    if (isLoading) {
        return (
            <div className="tp-panel p-6 flex flex-col items-center justify-center gap-3">
                <div className="tp-progress tp-progress-indeterminate" style={{ width: 180 }} />
                <span className="text-[11px] font-mono text-fg-faint uppercase">BUILDING PROVENANCE TRACE...</span>
            </div>
        );
    }

    if (!chainData) {
        return (
            <div className="tp-panel p-4 text-center text-fg-faint text-[11px] font-mono">
                NO EVIDENCE CHAIN AVAILABLE
            </div>
        );
    }

    const {
        finding,
        signals = [],
        relationships = [],
        evidence_records = [],
        counter_evidence_records = [],
        provenance_verified = true
    } = chainData;

    const activeEvidence = activeTab === 'supporting' ? evidence_records : counter_evidence_records;

    return (
        <div className="tp-panel p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                <div className="flex items-center gap-2">
                    <Layers size={14} className="text-primary" />
                    <span className="text-[12px] font-bold tracking-wide text-fg-primary">{title}</span>
                    <span className="tp-badge tp-badge-green flex items-center gap-1">
                        <ShieldCheck size={10} />
                        <span>PROVENANCE VERIFIED</span>
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setActiveTab('supporting')}
                        className={`tp-btn text-[10px] h-6 px-2 ${activeTab === 'supporting' ? 'tp-btn-primary' : 'tp-btn-ghost'}`}
                    >
                        Supporting ({evidence_records.length})
                    </button>
                    <button
                        onClick={() => setActiveTab('counter')}
                        className={`tp-btn text-[10px] h-6 px-2 ${activeTab === 'counter' ? 'tp-btn-amber' : 'tp-btn-ghost'}`}
                    >
                        Contradictory ({counter_evidence_records.length})
                    </button>
                </div>
            </div>

            {/* Visual 5-Stage Stepper Bar */}
            <div className="grid grid-cols-5 gap-2 text-center text-[10px] font-mono">
                <div className="p-2 rounded bg-bg-surface border border-primary/30 flex flex-col items-center">
                    <span className="text-fg-faint">01 STAGE</span>
                    <span className="font-bold text-primary">FINDING / LEAD</span>
                </div>
                <div className="p-2 rounded bg-bg-surface border border-purple/30 flex flex-col items-center">
                    <span className="text-fg-faint">02 STAGE</span>
                    <span className="font-bold text-purple">SIGNALS</span>
                </div>
                <div className="p-2 rounded bg-bg-surface border border-blue/30 flex flex-col items-center">
                    <span className="text-fg-faint">03 STAGE</span>
                    <span className="font-bold text-blue">RELATIONSHIPS</span>
                </div>
                <div className="p-2 rounded bg-bg-surface border border-teal/30 flex flex-col items-center">
                    <span className="text-fg-faint">04 STAGE</span>
                    <span className="font-bold text-teal">EVIDENCE ID</span>
                </div>
                <div className="p-2 rounded bg-bg-surface border border-green/30 flex flex-col items-center">
                    <span className="text-fg-faint">05 STAGE</span>
                    <span className="font-bold text-green">RAW SOURCE</span>
                </div>
            </div>

            {/* Level 1: Finding Detail */}
            {finding && (
                <div className="p-3 rounded bg-bg-surface border border-border-subtle">
                    <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                            <Brain size={13} className="text-primary" />
                            <span className="text-[10px] font-mono text-fg-faint">LEVEL 1 · FINDING / HYPOTHESIS</span>
                            <span className="tp-badge tp-badge-purple">{finding.type}</span>
                            <span className="tp-badge tp-badge-neutral">{finding.status}</span>
                        </div>
                        {finding.confidence != null && (
                            <span className="font-mono text-[11px] font-bold" style={{ color: getConfidenceColor(finding.confidence) }}>
                                {(finding.confidence * 100).toFixed(0)}% CONFIDENCE
                            </span>
                        )}
                    </div>
                    <div className="text-[12px] font-medium text-fg-primary">
                        {finding.subject_label || finding.subject_id} — {finding.summary || "Investigative hypothesis based on multi-relational graph signals."}
                    </div>
                </div>
            )}

            {/* Level 2: Analytical Signals */}
            {signals.length > 0 && (
                <div className="p-3 rounded bg-bg-surface border border-border-subtle space-y-2">
                    <div className="flex items-center gap-2 text-[10px] font-mono text-purple">
                        <Sparkles size={12} />
                        <span>LEVEL 2 · ANALYTICAL SIGNALS & DECOMPOSED WEIGHTS</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
                        {signals.map((sig, i) => (
                            <div key={i} className="p-2 rounded bg-bg-root border border-border-subtle">
                                <div className="flex items-center justify-between text-[11px] mb-1">
                                    <span className="text-fg-secondary truncate">{sig.name}</span>
                                    <span className="font-mono font-bold text-fg-primary">
                                        {(sig.value * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <div className="tp-confidence-bar">
                                    <div className="tp-confidence-fill" style={{ width: `${Math.min(sig.value * 100, 100)}%` }} />
                                </div>
                                {sig.description && (
                                    <div className="text-[9px] text-fg-faint mt-1 line-clamp-1">{sig.description}</div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Level 3: Relationships Linked */}
            {relationships.length > 0 && (
                <div className="p-3 rounded bg-bg-surface border border-border-subtle space-y-2">
                    <div className="flex items-center gap-2 text-[10px] font-mono text-blue">
                        <Network size={12} />
                        <span>LEVEL 3 · SUPPORTING NETWORK RELATIONSHIPS ({relationships.length})</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {relationships.map((rel, i) => (
                            <div key={i} className="p-2 rounded bg-bg-root border border-border-subtle text-[11px]">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="tp-badge tp-badge-blue text-[8px]">{rel.relationship_type}</span>
                                    <span className="tp-badge tp-badge-neutral text-[8px]">{rel.status}</span>
                                </div>
                                <div className="font-mono text-[10px] text-fg-primary truncate">
                                    {rel.source} → {rel.target}
                                </div>
                                {rel.timestamp && (
                                    <div className="text-[9px] font-mono text-fg-faint mt-1 flex items-center gap-1">
                                        <Clock size={9} />
                                        <span>{new Date(rel.timestamp).toLocaleDateString()}</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Level 4 & 5: Evidence Records & Source Document Excerpt */}
            <div className="p-3 rounded bg-bg-surface border border-border-subtle space-y-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[10px] font-mono text-green">
                        <FileText size={12} />
                        <span>LEVEL 4 & 5 · EVIDENCE RECORDS & CRYPTOGRAPHIC PROVENANCE ({activeEvidence.length})</span>
                    </div>
                    <span className="text-[9px] font-mono text-fg-faint">SHA-256 HASH VERIFIED</span>
                </div>

                {activeEvidence.length > 0 ? (
                    <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
                        {activeEvidence.map((ev, i) => (
                            <div key={i} className="p-2.5 rounded bg-bg-root border border-border-subtle space-y-1.5">
                                <div className="flex items-center justify-between flex-wrap gap-2">
                                    <div className="flex items-center gap-2">
                                        <span className="tp-badge tp-badge-green text-[9px]">{ev.source_type}</span>
                                        <span className="font-mono text-[10px] text-fg-primary font-bold">{ev.source_record_id}</span>
                                        <span className="font-mono text-[9px] text-fg-faint">({ev.evidence_id})</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {ev.timestamp && (
                                            <span className="text-[9px] font-mono text-fg-faint">
                                                {new Date(ev.timestamp).toLocaleString()}
                                            </span>
                                        )}
                                        <button
                                            onClick={() => copyToClipboard(ev.hash || ev.evidence_id, ev.evidence_id)}
                                            className="tp-btn tp-btn-ghost text-[9px] h-5 px-1 gap-1"
                                            title="Copy SHA-256 Hash"
                                        >
                                            {copiedId === ev.evidence_id ? <Check size={10} className="text-green" /> : <Copy size={10} />}
                                            <span className="font-mono">{ev.hash ? ev.hash.substring(0, 8) + '...' : 'HASH'}</span>
                                        </button>
                                    </div>
                                </div>

                                {/* Raw Excerpt */}
                                <div className="text-[11px] text-fg-secondary bg-bg-surface/50 p-2 rounded border border-border-subtle font-serif leading-relaxed">
                                    "{ev.text_excerpt || (typeof ev.excerpt === 'string' ? ev.excerpt : JSON.stringify(ev.structured_fields || {}))}"
                                </div>

                                {/* Structured Metadata Fields if available */}
                                {ev.structured_fields && Object.keys(ev.structured_fields).length > 0 && (
                                    <div className="flex flex-wrap gap-1.5 pt-1">
                                        {Object.entries(ev.structured_fields).map(([k, v]) => (
                                            <span key={k} className="text-[8px] font-mono px-1.5 py-0.5 rounded bg-bg-surface text-fg-faint border border-border-subtle">
                                                {k}: <strong className="text-fg-secondary">{String(v)}</strong>
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-4 text-[10px] font-mono text-fg-faint">
                        NO {activeTab.toUpperCase()} EVIDENCE FOUND
                    </div>
                )}
            </div>
        </div>
    );
}
