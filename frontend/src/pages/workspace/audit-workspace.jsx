/**
 * Audit Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §15: Audit & Pipeline.
 * Audit Table: TIME, ACTOR, ACTION, TARGET, STATUS
 * Immutable notice banner for compliance audit logging.
 */
import React from 'react';
import { Activity, Shield, Lock, CheckCircle2, Clock, Play } from 'lucide-react';
import { SYNTHETIC_AUDIT_LOGS, SYNTHETIC_PIPELINE } from '@/state/synthetic-case-data';
import { StatusMark } from '@/components/shared';

export default function AuditWorkspace() {
    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[hsl(var(--border-default))]">
                <div className="flex items-center gap-2">
                    <Activity size={18} className="text-[hsl(var(--primary))]" />
                    <h1 className="text-[18px] font-semibold text-[hsl(var(--fg-primary))]">Audit & Pipeline Execution</h1>
                </div>
                <div className="text-[11px] font-mono text-[hsl(var(--fg-muted))]">
                    JOB-9421 · CASE-0421
                </div>
            </div>

            {/* Compliance Banner */}
            <div className="sg-info-banner">
                <Lock size={16} className="text-[hsl(var(--blue))] shrink-0 mt-0.5" />
                <div className="text-[12px]">
                    <span className="font-semibold">{SYNTHETIC_PIPELINE.retention}</span>
                    <div className="text-[11px] text-[hsl(var(--fg-secondary))] mt-0.5">
                        Human dispositions, exports, and draft regenerations are automatically written to an append-only cryptographic ledger. Actions cannot be edited or deleted.
                    </div>
                </div>
            </div>

            {/* Pipeline Stage Execution Card */}
            <div className="sg-card p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-[hsl(var(--border-subtle))] pb-3">
                    <div className="text-[13px] font-semibold text-[hsl(var(--fg-primary))]">
                        Pipeline Stages ({SYNTHETIC_PIPELINE.job_id})
                    </div>
                    <StatusMark status="running" label="Hypothesis detection running" />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
                    {SYNTHETIC_PIPELINE.stages.map((stg) => (
                        <div key={stg.num} className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))] space-y-1.5">
                            <div className="flex items-center justify-between text-[11px]">
                                <span className="font-mono text-[hsl(var(--fg-muted))]">Stage {stg.num}</span>
                                <StatusMark status={stg.status} />
                            </div>
                            <div className="font-semibold text-[12px] text-[hsl(var(--fg-primary))]">{stg.name}</div>
                            <div className="text-[10px] text-[hsl(var(--fg-faint))] font-mono">{stg.timestamp}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Immutable Audit Log Table */}
            <div className="sg-card">
                <div className="sg-card-header justify-between">
                    <div className="flex items-center gap-2">
                        <Shield size={15} className="text-[hsl(var(--primary))]" />
                        <span>Immutable Audit Log</span>
                    </div>
                    <span className="sg-badge sg-badge-neutral">{SYNTHETIC_AUDIT_LOGS.length} entries shown</span>
                </div>
                <div className="overflow-x-auto">
                    <table className="sg-table">
                        <thead>
                            <tr>
                                <th>TIME</th>
                                <th>ACTOR</th>
                                <th>ACTION</th>
                                <th>TARGET</th>
                                <th>STATUS</th>
                                <th>DETAILS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {SYNTHETIC_AUDIT_LOGS.map((log, idx) => (
                                <tr key={idx}>
                                    <td className="font-mono text-[11px] text-[hsl(var(--fg-muted))]">{log.time}</td>
                                    <td>
                                        <div className="font-medium text-[12px] text-[hsl(var(--fg-primary))]">{log.actor}</div>
                                        <div className="text-[10px] text-[hsl(var(--fg-faint))]">{log.role}</div>
                                    </td>
                                    <td className="font-mono text-[12px] font-semibold text-[hsl(var(--primary))]">{log.action}</td>
                                    <td className="font-mono text-[12px] text-[hsl(var(--fg-secondary))]">{log.target}</td>
                                    <td><StatusMark status={log.status} /></td>
                                    <td className="text-[11px] text-[hsl(var(--fg-muted))] truncate max-w-xs">{log.details}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
