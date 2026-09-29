/**
 * Settings Workspace — SentinelGraph Investigative Workbench
 * Matches light theme styling and enterprise workbench configuration.
 */
import React from 'react';
import { Settings, Server, Shield, CheckCircle2 } from 'lucide-react';
import { StatusMark } from '@/components/shared';

export default function SettingsWorkspace() {
    return (
        <div className="p-6 space-y-6 max-w-4xl mx-auto animate-fade-in">
            <div className="flex items-center gap-2 pb-4 border-b border-[hsl(var(--border-default))]">
                <Settings size={18} className="text-[hsl(var(--primary))]" />
                <h1 className="text-[18px] font-semibold text-[hsl(var(--fg-primary))]">System & Workbench Settings</h1>
            </div>

            <div className="sg-card p-5 space-y-4">
                <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Investigator Profile</div>
                <div className="grid grid-cols-2 gap-4 text-[12px]">
                    <div>
                        <span className="text-[hsl(var(--fg-muted))] block mb-1">Authenticated Analyst:</span>
                        <div className="font-semibold text-[hsl(var(--fg-primary))]">A. Rao (Lead analyst · Editor)</div>
                    </div>
                    <div>
                        <span className="text-[hsl(var(--fg-muted))] block mb-1">Role Permissions:</span>
                        <div className="text-[hsl(var(--fg-secondary))]">Dossier Approval, Case Export, Pipeline Tracing</div>
                    </div>
                </div>
            </div>

            <div className="sg-card p-5 space-y-4">
                <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">System Environment</div>
                <div className="space-y-3 text-[12px]">
                    <div className="flex items-center justify-between pb-2 border-b border-[hsl(var(--border-subtle))]">
                        <span className="text-[hsl(var(--fg-secondary))]">API Gateway Endpoint:</span>
                        <span className="font-mono text-[hsl(var(--fg-primary))]">https://api.sentinelgraph.internal/v1</span>
                    </div>
                    <div className="flex items-center justify-between pb-2 border-b border-[hsl(var(--border-subtle))]">
                        <span className="text-[hsl(var(--fg-secondary))]">Graph Store Backend:</span>
                        <span className="font-mono text-[hsl(var(--fg-primary))]">Indexed Graph Engine (JOB-9421)</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-[hsl(var(--fg-secondary))]">Connection State:</span>
                        <StatusMark status="active" label="Connected & Synchronized (UTC)" />
                    </div>
                </div>
            </div>
        </div>
    );
}
