/**
 * Financial Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §9: Fund Tracing.
 * Inputs: ACC-8814, 3 hops, INR 250,000
 * Critical Wording: "This is a graph pattern, not a financial determination."
 */
import React, { useState } from 'react';
import { DollarSign, ArrowRight, Shield, AlertTriangle, Layers, Info } from 'lucide-react';
import { SYNTHETIC_FUND_TRACE } from '@/state/synthetic-case-data';
import { StatusMark, EvidenceReference } from '@/components/shared';

export default function FinancialWorkspace() {
    const [sourceAccount, setSourceAccount] = useState('ACC-8814');
    const [maxHops, setMaxHops] = useState(3);
    const [minAmount, setMinAmount] = useState('250,000');
    const [traceResult, setTraceResult] = useState(SYNTHETIC_FUND_TRACE);

    const handleRunTrace = (e) => {
        e.preventDefault();
        setTraceResult(SYNTHETIC_FUND_TRACE);
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[hsl(var(--border-default))]">
                <div className="flex items-center gap-2">
                    <DollarSign size={18} className="text-[hsl(var(--primary))]" />
                    <h1 className="text-[18px] font-semibold text-[hsl(var(--fg-primary))]">Fund Tracing</h1>
                </div>
                <div className="text-[11px] font-mono text-[hsl(var(--fg-muted))]">
                    Multi-hop disbursement path analysis
                </div>
            </div>

            {/* Critical Disclaimer Banner */}
            <div className="sg-info-banner">
                <Info size={16} className="text-[hsl(var(--blue))] shrink-0" />
                <div className="text-[12px]">
                    <span className="font-semibold">{SYNTHETIC_FUND_TRACE.disclaimer}</span> Structural topological flow does not assert financial wrongdoing or criminal culpability.
                </div>
            </div>

            {/* Inputs Control Panel */}
            <form onSubmit={handleRunTrace} className="sg-card p-5 space-y-4">
                <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Trace Parameters</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label className="text-[11px] text-[hsl(var(--fg-muted))] block mb-1">Source account</label>
                        <input
                            className="sg-input font-mono"
                            value={sourceAccount}
                            onChange={e => setSourceAccount(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="text-[11px] text-[hsl(var(--fg-muted))] block mb-1">Maximum hops</label>
                        <select
                            className="sg-select w-full"
                            value={maxHops}
                            onChange={e => setMaxHops(Number(e.target.value))}
                        >
                            <option value={1}>1 hop</option>
                            <option value={2}>2 hops</option>
                            <option value={3}>3 hops</option>
                            <option value={4}>4 hops</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-[11px] text-[hsl(var(--fg-muted))] block mb-1">Minimum amount (INR)</label>
                        <input
                            className="sg-input font-mono"
                            value={minAmount}
                            onChange={e => setMinAmount(e.target.value)}
                        />
                    </div>
                </div>
                <div className="flex justify-end">
                    <button type="submit" className="sg-btn sg-btn-primary">
                        <ArrowRight size={13} /> Run fund flow trace
                    </button>
                </div>
            </form>

            {/* Trace Visualization & Ledger Path */}
            <div className="sg-card p-5 space-y-5">
                <div className="flex items-center justify-between border-b border-[hsl(var(--border-subtle))] pb-3">
                    <div className="text-[12px] font-semibold text-[hsl(var(--fg-primary))]">
                        Path Traversal Result ({traceResult.nodes.length} nodes, {traceResult.transfers.length} transfer hops)
                    </div>
                    <span className="text-[10px] font-mono text-[hsl(var(--fg-muted))]">Scope: Community 6</span>
                </div>

                {/* Node Flow Chain */}
                <div className="flex flex-wrap items-center gap-3 p-4 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))] justify-center">
                    {traceResult.nodes.map((n, i) => (
                        <React.Fragment key={n.id}>
                            <div className="p-3 bg-[hsl(var(--bg-surface))] border border-[hsl(var(--border-default))] rounded shadow-sm text-center min-w-[140px]">
                                <div className="font-mono text-[12px] font-bold text-[hsl(var(--primary))]">{n.label}</div>
                                <div className="text-[10px] text-[hsl(var(--fg-muted))] mt-0.5">{n.role}</div>
                                <div className="mt-1.5 flex justify-center gap-1">
                                    <StatusMark status={n.type} />
                                </div>
                            </div>
                            {i < traceResult.nodes.length - 1 && (
                                <div className="flex flex-col items-center">
                                    <ArrowRight size={16} className="text-[hsl(var(--fg-muted))]" />
                                    <span className="text-[10px] font-mono text-[hsl(var(--primary))] font-medium mt-0.5">
                                        {traceResult.transfers[i]?.amount}
                                    </span>
                                </div>
                            )}
                        </React.Fragment>
                    ))}
                </div>

                {/* Detailed Transfer Hops Table */}
                <div>
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-2">Verified Transfer Hops</div>
                    <table className="sg-table">
                        <thead>
                            <tr>
                                <th>FROM</th>
                                <th>TO</th>
                                <th>AMOUNT</th>
                                <th>STATUS</th>
                                <th>TIMESTAMP (UTC)</th>
                                <th>PROVENANCE REF</th>
                            </tr>
                        </thead>
                        <tbody>
                            {traceResult.transfers.map((t, idx) => (
                                <tr key={idx}>
                                    <td className="font-mono text-[12px] text-[hsl(var(--primary))] font-medium">{t.from}</td>
                                    <td className="font-mono text-[12px] text-[hsl(var(--primary))] font-medium">{t.to}</td>
                                    <td className="font-mono text-[12px] font-semibold text-[hsl(var(--fg-primary))]">{t.amount}</td>
                                    <td><StatusMark status={t.type} /></td>
                                    <td className="font-mono text-[11px] text-[hsl(var(--fg-muted))]">{t.timestamp}</td>
                                    <td><EvidenceReference id={t.ref} /></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
