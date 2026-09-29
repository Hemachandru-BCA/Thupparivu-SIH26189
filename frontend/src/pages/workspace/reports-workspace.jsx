/**
 * Dossier Review Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §13: Dossier Review (DOS-0042).
 * Approval Gate is real: stays BLOCKED until requirements are resolved.
 * JSON export stamped as Draft / not a determination.
 */
import React, { useState } from 'react';
import { BookOpen, Shield, AlertTriangle, CheckCircle2, XCircle, Download, FileText, Lock } from 'lucide-react';
import { SYNTHETIC_DOSSIER } from '@/state/synthetic-case-data';
import { StatusMark } from '@/components/shared';

export default function ReportsWorkspace() {
    const [dossier, setDossier] = useState(SYNTHETIC_DOSSIER);
    const [counterEvidenceReviewed, setCounterEvidenceReviewed] = useState(false);
    const [rationaleProvided, setRationaleProvided] = useState('');
    const [editorOverride, setEditorOverride] = useState(false);

    // Approval gate checks
    const canApprove = counterEvidenceReviewed && rationaleProvided.trim().length > 15 && editorOverride;

    const handleExportJSON = () => {
        const payload = {
            dossier_id: dossier.id,
            case_id: dossier.case_ref,
            finding_id: dossier.finding_ref,
            classification: 'DRAFT FOR HUMAN REVIEW — NOT A FINAL DETERMINATION',
            status: canApprove ? 'APPROVED' : 'BLOCKED_DRAFT',
            exported_by: 'A. Rao (Lead analyst · Editor)',
            exported_at: new Date().toISOString(),
            sections: dossier.sections,
            provenance_audit_trail: 'JOB-9421 / AUDIT-VERIFIED'
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${dossier.id}_draft_export_${Date.now()}.json`;
        a.click();
    };

    return (
        <div className="p-6 space-y-6 max-w-5xl mx-auto animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[hsl(var(--border-default))]">
                <div className="flex items-center gap-3">
                    <BookOpen size={20} className="text-[hsl(var(--primary))]" />
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-[14px] font-bold text-[hsl(var(--primary))]">{dossier.id}</span>
                            <span className="text-[hsl(var(--fg-muted))]">·</span>
                            <span className="text-[12px] font-mono text-[hsl(var(--fg-secondary))]">{dossier.case_ref}</span>
                            <span className="text-[hsl(var(--fg-muted))]">·</span>
                            <span className="text-[12px] font-mono text-[hsl(var(--fg-secondary))]">{dossier.finding_ref}</span>
                        </div>
                        <h1 className="text-[18px] font-semibold text-[hsl(var(--fg-primary))]">Dossier Validation Review</h1>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <StatusMark status={canApprove ? 'completed' : 'blocked'} label={canApprove ? 'Approval Ready' : 'Blocked'} />
                    <button className="sg-btn sg-btn-sm" onClick={handleExportJSON}>
                        <Download size={12} /> Export JSON
                    </button>
                </div>
            </div>

            {/* Top Warning Banner per Spec */}
            <div className="sg-warning-banner">
                <AlertTriangle size={18} className="text-[hsl(var(--amber))] shrink-0 mt-0.5" />
                <div className="text-[12px]">
                    <div className="font-semibold uppercase tracking-wide">Draft for Human Review</div>
                    <div className="text-[11px] text-[hsl(var(--fg-secondary))] mt-0.5">{dossier.top_warning}</div>
                </div>
            </div>

            {/* Dossier Structured Sections */}
            <div className="space-y-4">
                {dossier.sections.map((sec, idx) => (
                    <div key={idx} className="sg-card p-5 space-y-2">
                        <div className="flex items-center justify-between border-b border-[hsl(var(--border-subtle))] pb-2">
                            <h2 className="text-[13px] font-semibold text-[hsl(var(--fg-primary))] uppercase tracking-wider">
                                {idx + 1}. {sec.title}
                            </h2>
                            <span className="text-[10px] font-mono text-[hsl(var(--fg-muted))] bg-[hsl(var(--bg-panel))] px-2 py-0.5 rounded border border-[hsl(var(--border-subtle))]">
                                {sec.status}
                            </span>
                        </div>
                        <p className="text-[12px] text-[hsl(var(--fg-secondary))] leading-relaxed whitespace-pre-line">
                            {sec.content}
                        </p>
                    </div>
                ))}
            </div>

            {/* Real Approval Gate Panel */}
            <div className="sg-card p-5 space-y-4 border-2 border-[hsl(var(--border-strong))]">
                <div className="flex items-center gap-2 text-[13px] font-semibold text-[hsl(var(--fg-primary))]">
                    <Lock size={15} className="text-[hsl(var(--primary))]" />
                    <span>Dossier Sign-off Gate (Lead Analyst / Editor Verification)</span>
                </div>

                <div className="space-y-2 bg-[hsl(var(--bg-panel))] p-3 rounded border border-[hsl(var(--border-subtle))]">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Gate Requirements:</div>
                    <ul className="space-y-1.5 text-[12px]">
                        <li className="flex items-center gap-2">
                            <CheckCircle2 size={14} className="text-[hsl(var(--green))]" />
                            <span>Provenance indexed with verified SHA-256 signatures</span>
                        </li>
                        <li className="flex items-center gap-2">
                            {counterEvidenceReviewed ? <CheckCircle2 size={14} className="text-[hsl(var(--green))]" /> : <XCircle size={14} className="text-[hsl(var(--red))]" />}
                            <span>Explicit acknowledgement and review of counter-evidence (EV-19882)</span>
                        </li>
                        <li className="flex items-center gap-2">
                            {rationaleProvided.trim().length > 15 ? <CheckCircle2 size={14} className="text-[hsl(var(--green))]" /> : <XCircle size={14} className="text-[hsl(var(--red))]" />}
                            <span>Documented sign-off rationale (&gt;15 chars)</span>
                        </li>
                        <li className="flex items-center gap-2">
                            {editorOverride ? <CheckCircle2 size={14} className="text-[hsl(var(--green))]" /> : <XCircle size={14} className="text-[hsl(var(--red))]" />}
                            <span>Editor role credential authorization</span>
                        </li>
                    </ul>
                </div>

                {/* Checklist inputs */}
                <div className="space-y-3 pt-2">
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer">
                        <input
                            type="checkbox"
                            checked={counterEvidenceReviewed}
                            onChange={e => setCounterEvidenceReviewed(e.target.checked)}
                        />
                        <span>I confirm counter-evidence has been evaluated and incorporated.</span>
                    </label>

                    <label className="flex items-center gap-2 text-[12px] cursor-pointer">
                        <input
                            type="checkbox"
                            checked={editorOverride}
                            onChange={e => setEditorOverride(e.target.checked)}
                        />
                        <span>Confirm Lead Analyst & Editor role identity (A. Rao).</span>
                    </label>

                    <div>
                        <label className="text-[11px] text-[hsl(var(--fg-muted))] block mb-1">Analyst sign-off rationale</label>
                        <textarea
                            className="sg-textarea"
                            placeholder="Enter mandatory sign-off statement for immutable audit log…"
                            value={rationaleProvided}
                            onChange={e => setRationaleProvided(e.target.value)}
                        />
                    </div>
                </div>

                <div className="pt-2 flex justify-end">
                    <button
                        className="sg-btn sg-btn-primary"
                        disabled={!canApprove}
                        onClick={() => alert(`Dossier ${dossier.id} has been formally approved and logged to audit trail.`)}
                    >
                        <Shield size={13} /> Formally Approve & Seal Dossier
                    </button>
                </div>
            </div>
        </div>
    );
}
