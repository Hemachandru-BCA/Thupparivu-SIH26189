/**
 * frontend/src/pages/workspace/crosscase-workspace.jsx
 * -----------------------------------------------------
 * Cross-Case Intelligence Workspace.
 *
 * Detects:
 *  - Shared entities, phone numbers, vehicles, accounts across multiple cases
 *  - Network topology similarity between independent cases
 *  - Cross-case identity reuse & modus operandi patterns
 */

import React, { useState } from 'react';
import {
    FolderOpen, GitCompare, ArrowRight, Users, Shield,
    Activity, Layers, Search, CheckCircle2, ChevronRight
} from 'lucide-react';
import { useCrossCase } from '@/api/intel';
import { useInvestigation } from '@/state/investigation-context';
import { formatNumber } from '@/components/app-shell';

const SAMPLE_REUSED_ENTITIES = [
    { entity_id: 'P000001', name: 'Ravi Kumar (RK-0172)', type: 'PERSON', cases: ['CASE-0421 (Active)', 'CASE-0182 (2025)', 'CASE-0091 (2024)'], role: 'Cross-Jurisdiction Logistics' },
    { entity_id: 'ACC_HYD_9912', name: 'Escrow Holdings Ltd', type: 'ACCOUNT', cases: ['CASE-0421 (Active)', 'CASE-0312 (Hawala)'], role: 'Layering Hub' },
    { entity_id: 'TWR-019', name: 'Sector 4 Cell Tower', type: 'LOCATION', cases: ['CASE-0421 (Active)', 'CASE-0214 (Narcotics)'], role: 'Shared Meeting Co-location' },
    { entity_id: 'VEH-KA-05-9921', name: 'White SUV (KA059921)', type: 'VEHICLE', cases: ['CASE-0421 (Active)', 'CASE-0182 (2025)'], role: 'Transport Asset' },
];

export default function CrossCaseWorkspace() {
    const { setSelectedEntity } = useInvestigation();
    const { data: crossData, isLoading } = useCrossCase();
    const [caseA, setCaseA] = useState('CASE-0421');
    const [caseB, setCaseB] = useState('CASE-0182');

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4 max-w-[1720px] mx-auto animate-fade-in">
            {/* ── HEADER ── */}
            <div className="tp-panel p-3.5 bg-bg-panel flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <FolderOpen size={16} className="text-primary" />
                        <span className="text-[14px] font-bold text-fg-primary">CROSS-CASE INTELLIGENCE & IDENTITY REUSE</span>
                        <span className="tp-badge tp-badge-blue">MULTI-CASE GRAPH</span>
                    </div>
                    <p className="text-[11px] text-fg-secondary mt-0.5">
                        Detect shared entities, organizations, bank accounts, and vehicles across multiple open or archived investigations.
                    </p>
                </div>
                <div className="text-[10px] font-mono text-fg-faint">
                    ACROSS 12 JURISDICTIONAL WORKSPACES
                </div>
            </div>

            {/* ── CASE COMPARISON TOOL ── */}
            <div className="tp-panel p-3.5 space-y-3">
                <div className="flex items-center justify-between">
                    <span className="tp-section-label">CROSS-CASE STRUCTURAL SIMILARITY COMPARATOR</span>
                    <span className="tp-badge tp-badge-green font-mono">SIMILARITY INDEX: 0.84</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                    <div className="p-3 rounded bg-bg-surface border border-border-subtle space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="font-mono text-[11px] font-bold text-primary">CASE A: {caseA}</span>
                            <span className="tp-badge tp-badge-amber">ACTIVE</span>
                        </div>
                        <div className="text-[11px] text-fg-secondary">
                            Operation Sentinel · 13,146 entities · 859 communities · Dominant relation: TRANSFERRED_TO
                        </div>
                    </div>
                    <div className="p-3 rounded bg-bg-surface border border-border-subtle space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="font-mono text-[11px] font-bold text-fg-secondary">CASE B: {caseB}</span>
                            <span className="tp-badge tp-badge-neutral">ARCHIVED (2025)</span>
                        </div>
                        <div className="text-[11px] text-fg-secondary">
                            Bengaluru Hawala Network · 4,210 entities · 192 communities · Dominant relation: USES_ACCOUNT
                        </div>
                    </div>
                </div>
            </div>

            {/* ── REUSED IDENTIFIERS TABLE ── */}
            <div className="tp-panel">
                <div className="tp-panel-header">
                    <span className="text-[11px] font-semibold text-fg-primary">DETECTED REUSED ENTITIES ACROSS CASES</span>
                    <span className="text-[10px] font-mono text-fg-faint">{SAMPLE_REUSED_ENTITIES.length} MATCHES</span>
                </div>
                <div className="overflow-x-auto">
                    <table className="tp-table">
                        <thead>
                            <tr>
                                <th>Entity ID</th>
                                <th>Canonical Name</th>
                                <th>Type</th>
                                <th>Linked Cases</th>
                                <th>Operational Role</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {SAMPLE_REUSED_ENTITIES.map((item, i) => (
                                <tr key={i} className="hover:bg-bg-hover">
                                    <td className="font-mono text-[11px] text-primary">{item.entity_id}</td>
                                    <td className="font-medium text-fg-primary">{item.name}</td>
                                    <td>
                                        <span className="tp-badge tp-badge-blue text-[8px]">{item.type}</span>
                                    </td>
                                    <td>
                                        <div className="flex flex-wrap gap-1">
                                            {item.cases.map((c, cIdx) => (
                                                <span key={cIdx} className="tp-badge tp-badge-neutral text-[9px]">{c}</span>
                                            ))}
                                        </div>
                                    </td>
                                    <td className="text-fg-secondary">{item.role}</td>
                                    <td>
                                        <button
                                            onClick={() => setSelectedEntity({ id: item.entity_id, label: item.name, type: item.type })}
                                            className="tp-btn h-5 text-[10px]"
                                        >
                                            Inspect
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
