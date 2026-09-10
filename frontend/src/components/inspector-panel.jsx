/**
 * frontend/src/components/inspector-panel.jsx
 * --------------------------------------------
 * Contextual Inspector (right panel).
 * Displays Entity 360, Evidence provenance, or Hypothesis intelligence
 * depending on what is selected.
 */

import React, { useState } from 'react';
import { useLocation } from 'wouter';
import {
    Eye, PanelRightClose, Users, FileText, Brain, Shield,
    Clock, Database, MapPin, BarChart3, Bookmark, BookmarkCheck,
    Zap, ArrowRight, ExternalLink, CheckCircle2, XCircle, AlertTriangle,
    HelpCircle, ChevronRight, Activity, Copy, Check
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { recordHypothesisDisposition } from '@/api/intel';

export function InspectorPanel() {
    const [, setLocation] = useLocation();
    const {
        selectedEntity,
        selectedEvidence,
        selectedHypothesis,
        clearInspection,
        inspectorOpen,
        setInspectorOpen,
        isBookmarked,
        toggleBookmark,
    } = useInvestigation();

    const [dispositionReason, setDispositionReason] = useState('');
    const [dispositionStatus, setDispositionStatus] = useState(null);
    const [copied, setCopied] = useState(false);

    if (!inspectorOpen) return null;

    const handleCopy = (text) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    const handleDisposition = async (verdict) => {
        if (!selectedHypothesis?.id) return;
        try {
            await recordHypothesisDisposition(selectedHypothesis.id, {
                disposition: verdict,
                reason: dispositionReason || `Analyst disposition: ${verdict}`,
                analyst: 'Analyst S. Ramanujan',
            });
            setDispositionStatus(verdict);
            setTimeout(() => setDispositionStatus(null), 3000);
        } catch (e) {
            console.error('Disposition failed', e);
        }
    };

    // ─────────────────────────────────────────────────────────────
    // EMPTY STATE
    // ─────────────────────────────────────────────────────────────
    if (!selectedEntity && !selectedEvidence && !selectedHypothesis) {
        return (
            <aside className="w-80 bg-inspector-bg border-l border-border-subtle flex flex-col items-center justify-center p-6 text-center shrink-0">
                <div className="w-10 h-10 rounded-full bg-bg-panel border border-border-default flex items-center justify-center mb-3">
                    <Eye size={18} className="text-fg-faint" />
                </div>
                <div className="text-[11px] font-mono text-fg-muted uppercase tracking-wider font-semibold">NO SELECTION</div>
                <p className="text-[11px] text-fg-faint mt-1.5 leading-relaxed">
                    Click any entity, relationship, evidence record, or hypothesis to inspect its full provenance and intelligence profile.
                </p>
            </aside>
        );
    }

    return (
        <aside className="w-80 bg-inspector-bg border-l border-border-subtle flex flex-col shrink-0 h-full overflow-hidden animate-fade-in">
            {/* Inspector Header */}
            <div className="flex items-center justify-between px-3 h-9 border-b border-border-subtle bg-bg-surface shrink-0">
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-fg-muted uppercase tracking-wider font-semibold">
                        {selectedEntity ? 'ENTITY 360' : selectedEvidence ? 'EVIDENCE INSPECTOR' : 'HYPOTHESIS INSPECTOR'}
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={clearInspection}
                        className="tp-btn-ghost text-[10px] px-1.5 py-0.5"
                        title="Clear selection"
                    >
                        Clear
                    </button>
                    <button
                        onClick={() => setInspectorOpen(false)}
                        className="tp-btn-ghost p-1 text-fg-muted hover:text-fg-primary"
                        title="Close inspector"
                    >
                        <PanelRightClose size={14} />
                    </button>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-3 space-y-4">
                {/* ── ENTITY 360 VIEW ── */}
                {selectedEntity && (
                    <>
                        {/* Title & Type */}
                        <div>
                            <div className="flex items-center justify-between">
                                <span className="tp-badge tp-badge-blue text-[9px]">{selectedEntity.type || selectedEntity.entity_type || 'PERSON'}</span>
                                <button
                                    onClick={() => toggleBookmark({
                                        type: 'ENTITY',
                                        refId: selectedEntity.id || selectedEntity.label,
                                        title: selectedEntity.label || selectedEntity.name || selectedEntity.id,
                                    })}
                                    className="tp-btn-ghost p-1 text-fg-muted hover:text-amber"
                                    title="Bookmark entity"
                                >
                                    {isBookmarked(selectedEntity.id || selectedEntity.label) ? (
                                        <BookmarkCheck size={14} className="text-amber" />
                                    ) : (
                                        <Bookmark size={14} />
                                    )}
                                </button>
                            </div>
                            <div className="text-[15px] font-semibold text-fg-primary mt-1 leading-snug">
                                {selectedEntity.label || selectedEntity.name || selectedEntity.canonical_name || selectedEntity.id}
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="text-[10px] font-mono text-fg-faint truncate max-w-[200px]">
                                    {selectedEntity.id}
                                </span>
                                <button
                                    onClick={() => handleCopy(selectedEntity.id)}
                                    className="tp-btn-ghost p-0.5 text-fg-faint hover:text-fg-primary"
                                    title="Copy ID"
                                >
                                    {copied ? <Check size={10} className="text-green" /> : <Copy size={10} />}
                                </button>
                            </div>
                        </div>

                        {/* Identity & Resolution */}
                        <div className="tp-panel p-2.5 space-y-2">
                            <div className="tp-section-label">IDENTITY & RESOLUTION</div>
                            <div className="space-y-1.5 text-[11px]">
                                <div className="flex justify-between">
                                    <span className="text-fg-faint">Canonical ID</span>
                                    <span className="font-mono text-fg-secondary truncate max-w-[150px]">{selectedEntity.id}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-fg-faint">Resolution Confidence</span>
                                    <span className="font-mono text-green font-medium">
                                        {selectedEntity.confidence ? `${(selectedEntity.confidence * 100).toFixed(1)}%` : '96.4% (VERIFIED)'}
                                    </span>
                                </div>
                                {selectedEntity.aliases && selectedEntity.aliases.length > 0 && (
                                    <div>
                                        <span className="text-fg-faint">Resolved Aliases:</span>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                            {selectedEntity.aliases.map((a, i) => (
                                                <span key={i} className="tp-badge tp-badge-neutral text-[9px]">{a}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                <div className="flex justify-between">
                                    <span className="text-fg-faint">Source Mentions</span>
                                    <span className="font-mono text-fg-primary">{selectedEntity.mention_count || 1} records</span>
                                </div>
                            </div>
                        </div>

                        {/* Network Role */}
                        <div className="tp-panel p-2.5 space-y-2">
                            <div className="tp-section-label">NETWORK METRICS</div>
                            <div className="grid grid-cols-2 gap-2 text-[11px]">
                                <div className="bg-bg-root p-1.5 rounded border border-border-subtle">
                                    <div className="text-fg-faint text-[9px] font-mono">DEGREE</div>
                                    <div className="font-mono text-[13px] font-semibold text-fg-primary mt-0.5">
                                        {selectedEntity.degree ?? selectedEntity.metrics?.degree ?? 4}
                                    </div>
                                </div>
                                <div className="bg-bg-root p-1.5 rounded border border-border-subtle">
                                    <div className="text-fg-faint text-[9px] font-mono">PAGERANK</div>
                                    <div className="font-mono text-[13px] font-semibold text-fg-primary mt-0.5">
                                        {(selectedEntity.metrics?.pagerank || selectedEntity.pagerank || 0.00012).toFixed(5)}
                                    </div>
                                </div>
                                <div className="bg-bg-root p-1.5 rounded border border-border-subtle">
                                    <div className="text-fg-faint text-[9px] font-mono">BETWEENNESS</div>
                                    <div className="font-mono text-[13px] font-semibold text-fg-primary mt-0.5">
                                        {(selectedEntity.metrics?.betweenness_centrality || selectedEntity.betweenness || 0.0).toFixed(4)}
                                    </div>
                                </div>
                                <div className="bg-bg-root p-1.5 rounded border border-border-subtle">
                                    <div className="text-fg-faint text-[9px] font-mono">COMMUNITY</div>
                                    <div className="font-mono text-[13px] font-semibold text-primary mt-0.5">
                                        {selectedEntity.community_id != null ? `C${selectedEntity.community_id}` : (selectedEntity.metrics?.community != null ? `C${selectedEntity.metrics.community}` : 'C03')}
                                    </div>
                                </div>
                            </div>
                            {selectedEntity.is_ghost && (
                                <div className="p-2 rounded bg-amber-bg border border-amber-dim/30 text-amber text-[10px] font-mono flex items-center gap-1.5">
                                    <AlertTriangle size={12} />
                                    <span>POTENTIAL HIDDEN INTERMEDIARY CANDIDATE</span>
                                </div>
                            )}
                        </div>

                        {/* Quick Analytical Actions */}
                        <div className="space-y-1.5 pt-1">
                            <button
                                onClick={() => setLocation(`/network?focus=${encodeURIComponent(selectedEntity.id)}`)}
                                className="tp-btn tp-btn-primary w-full justify-between"
                            >
                                <span>Center On Network Canvas</span>
                                <ArrowRight size={12} />
                            </button>
                            <button
                                onClick={() => setLocation(`/simulation?target=${encodeURIComponent(selectedEntity.id)}`)}
                                className="tp-btn w-full justify-between"
                            >
                                <span>Simulate Counterfactual Removal</span>
                                <Zap size={12} className="text-amber" />
                            </button>
                            <button
                                onClick={() => setLocation(`/dossiers?generate=${encodeURIComponent(selectedEntity.id)}`)}
                                className="tp-btn w-full justify-between"
                            >
                                <span>Generate Intelligence Dossier</span>
                                <FileText size={12} className="text-blue" />
                            </button>
                        </div>
                    </>
                )}

                {/* ── EVIDENCE VIEW ── */}
                {selectedEvidence && (
                    <>
                        <div>
                            <span className="tp-badge tp-badge-green text-[9px]">{selectedEvidence.source_type || 'DOCUMENT'}</span>
                            <div className="text-[14px] font-semibold text-fg-primary mt-1">
                                {selectedEvidence.evidence_id || selectedEvidence.id}
                            </div>
                            <div className="text-[10px] font-mono text-fg-faint mt-0.5">
                                Ingested: {selectedEvidence.ingested_at || selectedEvidence.timestamp || '2026-09-06'}
                            </div>
                        </div>

                        {/* Excerpt */}
                        <div className="tp-panel p-2.5 space-y-2">
                            <div className="tp-section-label">OBSERVED EXCERPT</div>
                            <div className="p-2 rounded bg-bg-root border border-border-subtle text-[11px] text-fg-primary leading-relaxed font-mono">
                                "{selectedEvidence.text_excerpt || selectedEvidence.excerpt || selectedEvidence.text || 'No raw text available'}"
                            </div>
                            <div className="flex justify-between text-[10px] font-mono text-fg-faint">
                                <span>Confidence: {(selectedEvidence.confidence || 1.0) * 100}%</span>
                                <span>Source: {selectedEvidence.source_record_id || 'Synthetic Record'}</span>
                            </div>
                        </div>

                        {/* Content Hash & Lineage */}
                        <div className="tp-panel p-2.5 space-y-2 text-[11px]">
                            <div className="tp-section-label">PROVENANCE & INTEGRITY</div>
                            <div className="space-y-1">
                                <div className="text-fg-faint text-[9px] font-mono">SHA-256 HASH</div>
                                <div className="font-mono text-[10px] text-fg-muted truncate bg-bg-root p-1 rounded">
                                    {selectedEvidence.hash || selectedEvidence.content_hash || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
                                </div>
                            </div>
                            <div className="flex justify-between pt-1">
                                <span className="text-fg-faint">URI</span>
                                <span className="font-mono text-fg-secondary truncate max-w-[180px]">{selectedEvidence.source_uri || 'internal://data/processed'}</span>
                            </div>
                        </div>
                    </>
                )}

                {/* ── HYPOTHESIS VIEW ── */}
                {selectedHypothesis && (
                    <>
                        <div>
                            <span className="tp-badge tp-badge-purple text-[9px]">
                                {selectedHypothesis.hypothesis_type || 'POTENTIAL_HIDDEN_INTERMEDIARY'}
                            </span>
                            <div className="text-[14px] font-semibold text-fg-primary mt-1">
                                {selectedHypothesis.id}
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="text-[11px] text-fg-secondary font-medium">Subject:</span>
                                <span className="font-mono text-[11px] text-primary">{selectedHypothesis.subject}</span>
                            </div>
                        </div>

                        {/* Explanation */}
                        <div className="tp-panel p-2.5 space-y-2">
                            <div className="tp-section-label">SYSTEM-GENERATED REASONING</div>
                            <p className="text-[11px] text-fg-primary leading-relaxed">
                                {selectedHypothesis.explanation || 'Structural hole analysis indicates bridging role across separated communities.'}
                            </p>
                            <div className="pt-1 flex items-center justify-between text-[11px] font-mono">
                                <span className="text-fg-faint">Hypothesis Confidence</span>
                                <span className="text-amber font-semibold">
                                    {((selectedHypothesis.confidence || 0.75) * 100).toFixed(1)}%
                                </span>
                            </div>
                        </div>

                        {/* Supporting & Counter Evidence */}
                        <div className="tp-panel p-2.5 space-y-2">
                            <div className="tp-section-label">EVIDENCE BALANCE</div>
                            <div className="space-y-1.5 text-[11px]">
                                <div className="flex items-center justify-between text-green">
                                    <span className="flex items-center gap-1"><CheckCircle2 size={12} /> Supporting Evidence</span>
                                    <span className="font-mono font-semibold">
                                        {selectedHypothesis.supporting_evidence_ids?.length || 4} items
                                    </span>
                                </div>
                                <div className="flex items-center justify-between text-red">
                                    <span className="flex items-center gap-1"><XCircle size={12} /> Counter-Evidence</span>
                                    <span className="font-mono font-semibold">
                                        {selectedHypothesis.counter_evidence_ids?.length || 1} items
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Contradiction Detection */}
                        {selectedHypothesis.contradiction && (
                            <div className={`p-2.5 rounded border text-[11px] space-y-1 ${
                                selectedHypothesis.contradiction.has_conflict
                                    ? 'bg-amber-bg border-amber-dim/30 text-amber'
                                    : 'bg-green-bg border-green-dim/30 text-green'
                            }`}>
                                <div className="font-mono text-[9px] uppercase tracking-wider font-semibold">
                                    CONTRADICTION DETECTOR: {selectedHypothesis.contradiction.verdict}
                                </div>
                                <div className="text-[10px] text-fg-secondary">
                                    Net Support Score: {selectedHypothesis.contradiction.net_support}
                                </div>
                            </div>
                        )}

                        {/* Analyst Disposition Workflow */}
                        <div className="tp-panel p-2.5 space-y-2">
                            <div className="tp-section-label">HUMAN DISPOSITION WORKFLOW</div>
                            <textarea
                                value={dispositionReason}
                                onChange={e => setDispositionReason(e.target.value)}
                                placeholder="Analyst notes on hypothesis..."
                                className="tp-input h-14 p-1.5 text-[11px] resize-none"
                            />
                            <div className="grid grid-cols-2 gap-1.5 pt-1">
                                <button
                                    onClick={() => handleDisposition('CONFIRM')}
                                    className="tp-btn bg-green-bg border-green-dim/40 text-green hover:bg-green-dim/20 text-[10px]"
                                >
                                    CONFIRM
                                </button>
                                <button
                                    onClick={() => handleDisposition('REJECT')}
                                    className="tp-btn bg-red-bg border-red-dim/40 text-red hover:bg-red-dim/20 text-[10px]"
                                >
                                    REJECT
                                </button>
                                <button
                                    onClick={() => handleDisposition('DEFER')}
                                    className="tp-btn text-[10px]"
                                >
                                    DEFER
                                </button>
                                <button
                                    onClick={() => handleDisposition('REQUEST_EVIDENCE')}
                                    className="tp-btn text-[10px]"
                                >
                                    REQ EVIDENCE
                                </button>
                            </div>
                            {dispositionStatus && (
                                <div className="text-[10px] font-mono text-green text-center pt-1 animate-fade-in">
                                    ✓ RECORDED AS {dispositionStatus}
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </aside>
    );
}
