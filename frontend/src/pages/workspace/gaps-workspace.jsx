/**
 * frontend/src/pages/workspace/gaps-workspace.jsx
 * ------------------------------------------------
 * Investigative Gaps & Uncertainty Management Workspace.
 *
 * Surfaces:
 *  - Unresolved entity types & aliases
 *  - Missing timestamps across historical datasets
 *  - Conflicting observations & source discrepancies
 *  - Next Best Analytical Action (estimated information gain)
 *  - Turn analytics into actionable investigator tasks
 */

import React, { useState } from 'react';
import {
    AlertCircle, HelpCircle, CheckCircle2, ArrowRight, Sparkles,
    Shield, Clock, Database, Users, FileText, AlertTriangle, ChevronRight
} from 'lucide-react';
import { useInvestigativeGaps } from '@/api/intel';
import { formatNumber } from '@/components/app-shell';

export default function GapsWorkspace() {
    const { data: gapsData, isLoading } = useInvestigativeGaps();
    const gaps = gapsData?.items || [];
    const [actionStatus, setActionStatus] = useState({});

    const handleAction = (idx, actionName) => {
        setActionStatus(prev => ({ ...prev, [idx]: 'REQUESTED' }));
    };

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4 max-w-[1720px] mx-auto animate-fade-in">
            {/* ── HEADER ── */}
            <div className="tp-panel p-3.5 bg-bg-panel flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <AlertCircle size={16} className="text-amber" />
                        <span className="text-[14px] font-bold text-fg-primary">INVESTIGATIVE GAPS & UNCERTAINTY</span>
                        <span className="tp-badge tp-badge-amber">OPEN QUESTIONS</span>
                    </div>
                    <p className="text-[11px] text-fg-secondary mt-0.5">
                        The system explicitly highlights what remains unknown, unresolved, or contradictory rather than manufacturing false certainty.
                    </p>
                </div>
                <div className="text-[10px] font-mono text-fg-faint">
                    UNCERTAINTY AS A FEATURE · PRINCIPLE 3
                </div>
            </div>

            {/* ── NEXT BEST REVIEW / INFORMATION GAIN ── */}
            <div className="tp-panel p-4 bg-bg-surface border-primary/40 space-y-3">
                <div className="flex items-center gap-2">
                    <Sparkles size={15} className="text-primary" />
                    <span className="text-[12px] font-bold text-fg-primary">RECOMMENDED NEXT ANALYTICAL ACTION (MAX INFORMATION GAIN)</span>
                    <span className="tp-badge tp-badge-blue">HIGH GAIN: ΔU ≈ -0.17</span>
                </div>
                <div className="text-[12px] text-fg-secondary leading-relaxed">
                    <strong>Action:</strong> Review CDR Tower logs between 2025-08-14 and 2025-08-20 for Candidate <strong>P000001</strong> and Community <strong>C03</strong>.
                    <br />
                    <strong>Analytical Value:</strong> Resolving the 3 missing call timestamps will confirm or refute the inferred bridge between Gang G001 and Gang G003, reducing overall network ambiguity.
                </div>
                <div className="pt-1 flex items-center gap-3">
                    <button className="tp-btn tp-btn-primary h-6 text-[11px] gap-1">
                        <span>Initiate Tower Review</span>
                        <ArrowRight size={12} />
                    </button>
                    <span className="text-[10px] font-mono text-fg-faint">Estimated review time: ~4 mins</span>
                </div>
            </div>

            {/* ── GAPS QUEUE TABLE ── */}
            <div className="tp-panel">
                <div className="tp-panel-header">
                    <span className="text-[11px] font-semibold text-fg-primary">OPEN ANALYTICAL GAPS QUEUE</span>
                    <span className="text-[10px] font-mono text-fg-faint">{gaps.length} IDENTIFIED GAPS</span>
                </div>
                <div className="overflow-x-auto">
                    <table className="tp-table">
                        <thead>
                            <tr>
                                <th>Severity</th>
                                <th>Category</th>
                                <th>Description</th>
                                <th>Recommended Request</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {gaps.map((gap, i) => (
                                <tr key={i} className="hover:bg-bg-hover">
                                    <td>
                                        <span className={`tp-badge ${
                                            gap.severity === 'HIGH' ? 'tp-badge-red' :
                                            gap.severity === 'MEDIUM' ? 'tp-badge-amber' : 'tp-badge-neutral'
                                        }`}>
                                            {gap.severity}
                                        </span>
                                    </td>
                                    <td className="font-mono text-[11px] text-fg-primary">{gap.type}</td>
                                    <td className="text-fg-secondary">{gap.description}</td>
                                    <td className="text-primary font-medium">{gap.request}</td>
                                    <td>
                                        <span className="tp-badge tp-badge-neutral font-mono">{gap.status}</span>
                                    </td>
                                    <td>
                                        {actionStatus[i] ? (
                                            <span className="text-green text-[10px] font-mono font-semibold flex items-center gap-1">
                                                <CheckCircle2 size={11} /> REQUESTED
                                            </span>
                                        ) : (
                                            <button
                                                onClick={() => handleAction(i, gap.request)}
                                                className="tp-btn h-5 text-[10px]"
                                            >
                                                Request
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                            {gaps.length === 0 && (
                                <tr>
                                    <td colSpan={6} className="text-center py-6 text-fg-faint">
                                        No active investigative gaps.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
