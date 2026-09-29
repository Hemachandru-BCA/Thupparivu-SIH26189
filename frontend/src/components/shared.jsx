/**
 * Shared reusable components per UX spec §16.
 * EmptyState, LoadingState, ErrorState, StatusMark, ConfidenceBand,
 * ScopeCount, AuditStamp, DataFreshness, EvidenceReference, DecisionGate
 */
import React, { useState } from 'react';
import { AlertTriangle, Loader2, RefreshCw, Search, CheckCircle2, XCircle, Clock, Shield, FileText } from 'lucide-react';

/* ── Empty State ── */
export function EmptyState({ icon: Icon = Search, title = 'No results', description = 'Try adjusting your filters.', action, onAction }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
            <Icon size={28} className="text-[hsl(var(--fg-faint))] mb-3" />
            <div className="text-[13px] font-medium text-[hsl(var(--fg-secondary))] mb-1">{title}</div>
            <div className="text-[11px] text-[hsl(var(--fg-muted))] mb-4">{description}</div>
            {action && <button className="sg-btn sg-btn-sm" onClick={onAction}>{action}</button>}
        </div>
    );
}

/* ── Loading State ── */
export function LoadingState({ message = 'Loading…' }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
            <Loader2 size={20} className="text-[hsl(var(--primary))] animate-spin mb-3" />
            <div className="text-[12px] text-[hsl(var(--fg-muted))]">{message}</div>
        </div>
    );
}

/* ── Error State ── */
export function ErrorState({ message = 'Load failed', onRetry }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
            <XCircle size={24} className="text-[hsl(var(--red))] mb-3" />
            <div className="text-[13px] font-medium text-[hsl(var(--fg-secondary))] mb-1">{message}</div>
            <div className="text-[11px] text-[hsl(var(--fg-muted))] mb-4">Retry or open logs.</div>
            {onRetry && <button className="sg-btn sg-btn-sm" onClick={onRetry}><RefreshCw size={12} /> Retry</button>}
        </div>
    );
}

/* ── Status Mark: shape + label, never colour alone ── */
export function StatusMark({ status, label }) {
    const config = {
        active: { dot: 'sg-status-dot-green', text: label || 'Active', shape: '●' },
        running: { dot: 'sg-status-dot-blue', text: label || 'Running', shape: '▶' },
        success: { dot: 'sg-status-dot-green', text: label || 'Success', shape: '✓' },
        pending: { dot: 'sg-status-dot-amber', text: label || 'Pending', shape: '◐' },
        'in review': { dot: 'sg-status-dot-amber', text: label || 'In review', shape: '◐' },
        'awaiting review': { dot: 'sg-status-dot-amber', text: label || 'Awaiting review', shape: '◐' },
        error: { dot: 'sg-status-dot-red', text: label || 'Error', shape: '✗' },
        blocked: { dot: 'sg-status-dot-red', text: label || 'Blocked', shape: '■' },
        completed: { dot: 'sg-status-dot-green', text: label || 'Completed', shape: '✓' },
        idle: { dot: 'sg-status-dot-neutral', text: label || 'Idle', shape: '○' },
        observed: { dot: 'sg-status-dot-green', text: label || 'Observed', shape: '●' },
        inferred: { dot: 'sg-status-dot-blue', text: label || 'Inferred', shape: '◆' },
        hypothesised: { dot: 'sg-status-dot-amber', text: label || 'Hypothesised', shape: '△' },
        draft: { dot: 'sg-status-dot-amber', text: label || 'Draft', shape: '◐' },
    };
    const c = config[(status || '').toLowerCase()] || { dot: 'sg-status-dot-neutral', text: label || status, shape: '○' };
    return (
        <span className="sg-status">
            <span className={`sg-status-dot ${c.dot}`} aria-hidden="true" />
            <span>{c.text}</span>
        </span>
    );
}

/* ── Confidence Band ── */
export function ConfidenceBand({ level }) {
    const cls = {
        low: 'sg-confidence-low',
        moderate: 'sg-confidence-moderate',
        high: 'sg-confidence-high',
    }[(level || '').toLowerCase()] || '';
    return <span className={`sg-confidence ${cls}`}>{level}</span>;
}

/* ── Scope Count ── */
export function ScopeCount({ count, scope, className = '' }) {
    return (
        <span className={`text-[11px] text-[hsl(var(--fg-muted))] ${className}`}>
            <span className="font-mono font-medium text-[hsl(var(--fg-secondary))]">{typeof count === 'number' ? count.toLocaleString() : count}</span>
            {scope && <span className="ml-1">{scope}</span>}
        </span>
    );
}

/* ── Audit Stamp ── */
export function AuditStamp({ actor, timestamp, action }) {
    return (
        <div className="flex items-center gap-2 text-[11px] text-[hsl(var(--fg-muted))]">
            <Shield size={11} className="flex-shrink-0" />
            <span>{actor}</span>
            <span>·</span>
            <span>{action}</span>
            <span>·</span>
            <span className="font-mono">{timestamp}</span>
        </div>
    );
}

/* ── Data Freshness ── */
export function DataFreshness({ timestamp, pipelineState }) {
    return (
        <span className="flex items-center gap-1 text-[10px] text-[hsl(var(--chrome-fg-faint))]">
            <Clock size={10} />
            <span>{timestamp}</span>
            {pipelineState && (
                <>
                    <span>·</span>
                    <StatusMark status={pipelineState} />
                </>
            )}
        </span>
    );
}

/* ── Evidence Reference ── */
export function EvidenceReference({ id, type, onClick }) {
    return (
        <button
            className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-mono font-medium text-[hsl(var(--primary))] bg-[hsl(var(--primary-bg))] border border-[hsl(var(--primary-border))] rounded cursor-pointer hover:bg-[hsl(var(--bg-hover))] transition-colors"
            onClick={onClick}
        >
            <FileText size={10} />
            {id}
        </button>
    );
}

/* ── Decision Gate ── */
export function DecisionGate({ requirements = [], onDecision, disabled = false }) {
    const [decision, setDecision] = useState(null);
    const [rationale, setRationale] = useState('');
    const [counterEvidenceReviewed, setCounterEvidenceReviewed] = useState(false);

    const unmetRequirements = requirements.filter(r => !r.met);
    const canRecord = decision && rationale.trim().length > 10 && counterEvidenceReviewed && unmetRequirements.length === 0;

    return (
        <div className="sg-card">
            <div className="sg-card-header">
                <Shield size={14} />
                Record decision
            </div>
            <div className="sg-card-body space-y-4">
                {/* Requirements */}
                {requirements.length > 0 && (
                    <div className="space-y-1">
                        <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Requirements</div>
                        {requirements.map((r, i) => (
                            <div key={i} className="flex items-center gap-2 text-[12px]">
                                {r.met ? <CheckCircle2 size={13} className="text-[hsl(var(--green))]" /> : <XCircle size={13} className="text-[hsl(var(--red))]" />}
                                <span className={r.met ? 'text-[hsl(var(--fg-secondary))]' : 'text-[hsl(var(--fg-primary))]'}>{r.label}</span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Decision buttons */}
                <div className="space-y-2">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Decision</div>
                    <div className="flex gap-2">
                        {['Supported', 'Needs further analysis', 'Rejected'].map(d => (
                            <button
                                key={d}
                                className={`sg-btn sg-btn-sm ${decision === d ? 'sg-btn-primary' : ''}`}
                                onClick={() => setDecision(d)}
                            >{d}</button>
                        ))}
                    </div>
                </div>

                {/* Rationale */}
                <div className="space-y-1">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Rationale <span className="text-[hsl(var(--red))]">*</span></div>
                    <textarea
                        className="sg-textarea"
                        placeholder="Provide rationale for this decision (minimum 10 characters)…"
                        value={rationale}
                        onChange={e => setRationale(e.target.value)}
                        rows={3}
                    />
                </div>

                {/* Counter-evidence confirmation */}
                <label className="flex items-start gap-2 text-[12px] cursor-pointer">
                    <input
                        type="checkbox"
                        checked={counterEvidenceReviewed}
                        onChange={e => setCounterEvidenceReviewed(e.target.checked)}
                        className="mt-0.5"
                    />
                    <span>I confirm that counter-evidence has been reviewed before recording this decision.</span>
                </label>

                {/* Record button */}
                <button
                    className="sg-btn sg-btn-primary w-full justify-center"
                    disabled={!canRecord || disabled}
                    onClick={() => onDecision?.({ decision, rationale, counterEvidenceReviewed, timestamp: new Date().toISOString(), actor: 'A. Rao' })}
                >
                    <Shield size={13} />
                    Record decision
                </button>

                {!canRecord && (
                    <div className="text-[11px] text-[hsl(var(--fg-muted))] italic">
                        All requirements must be met, a decision selected, rationale provided, and counter-evidence reviewed before recording.
                    </div>
                )}
            </div>
        </div>
    );
}

/* ── Pagination ── */
export function Pagination({ page, pageSize, total, onPageChange, onPageSizeChange }) {
    const totalPages = Math.ceil(total / pageSize);
    const start = (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, total);

    return (
        <div className="sg-pagination justify-between">
            <span>Showing {start.toLocaleString()}–{end.toLocaleString()} of {total.toLocaleString()}</span>
            <div className="flex items-center gap-2">
                <select className="sg-select" style={{ width: 80 }} value={pageSize} onChange={e => onPageSizeChange?.(Number(e.target.value))}>
                    <option value={10}>10 / page</option>
                    <option value={25}>25 / page</option>
                    <option value={50}>50 / page</option>
                </select>
                <span className="text-[11px]">Page {page} of {totalPages.toLocaleString()}</span>
                <button className="sg-btn sg-btn-sm sg-btn-ghost" disabled={page <= 1} onClick={() => onPageChange?.(page - 1)}>‹</button>
                <button className="sg-btn sg-btn-sm sg-btn-ghost" disabled={page >= totalPages} onClick={() => onPageChange?.(page + 1)}>›</button>
            </div>
        </div>
    );
}

/* ── Bulk Action Bar ── */
export function BulkActionBar({ count, onClear, actions = [] }) {
    if (count === 0) return null;
    return (
        <div className="flex items-center gap-3 px-3 py-2 bg-[hsl(var(--primary-bg))] border border-[hsl(var(--primary-border))] rounded-md animate-fade-in">
            <span className="text-[12px] font-medium text-[hsl(var(--primary))]">{count} selected</span>
            <div className="flex gap-2 flex-1">
                {actions.map(a => (
                    <button key={a.label} className="sg-btn sg-btn-sm" onClick={a.onClick}>{a.label}</button>
                ))}
            </div>
            <button className="sg-btn sg-btn-sm sg-btn-ghost" onClick={onClear}>Clear selection</button>
        </div>
    );
}
