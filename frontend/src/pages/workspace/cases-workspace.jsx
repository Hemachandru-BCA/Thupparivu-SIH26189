/**
 * Cases Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §5: Cases screen.
 * Table: CASE, STATUS, LEAD, ENTITIES, EVIDENCE, OPEN FINDINGS, UPDATED
 * Detail drawer & cross-case links statement.
 */
import React, { useState } from 'react';
import { FolderOpen, Filter, Search, ChevronRight, X, Shield, Info, Download } from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { GLOBAL_CASES } from '@/state/synthetic-case-data';
import { StatusMark } from '@/components/shared';

export default function CasesWorkspace() {
    const { activeCase, setActiveCase } = useInvestigation();
    const [selectedCaseId, setSelectedCaseId] = useState(activeCase.id);
    const [filterStatus, setFilterStatus] = useState('ALL');
    const [searchTerm, setSearchTerm] = useState('');

    const selectedCase = GLOBAL_CASES.find(c => c.id === selectedCaseId) || activeCase;

    const filteredCases = GLOBAL_CASES.filter(c => {
        const matchesStatus = filterStatus === 'ALL' || c.status === filterStatus;
        const matchesSearch = c.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
            c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
            c.lead.toLowerCase().includes(searchTerm.toLowerCase());
        return matchesStatus && matchesSearch;
    });

    const activeCount = GLOBAL_CASES.filter(c => c.status === 'ACTIVE').length;
    const reviewCount = GLOBAL_CASES.filter(c => c.status === 'IN REVIEW').length;
    const archivedCount = GLOBAL_CASES.filter(c => c.status === 'ARCHIVED').length;

    const handleSelectCase = (c) => {
        setSelectedCaseId(c.id);
        setActiveCase(c); // Selecting a case updates global workspace scope
    };

    return (
        <div className="flex h-full overflow-hidden animate-fade-in">
            {/* Main Table View */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden border-r border-[hsl(var(--border-subtle))]">
                {/* Header & Filter Toolbar */}
                <div className="p-4 bg-[hsl(var(--bg-surface))] border-b border-[hsl(var(--border-subtle))] space-y-3 shrink-0">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <FolderOpen size={16} className="text-[hsl(var(--primary))]" />
                            <h1 className="text-[16px] font-semibold text-[hsl(var(--fg-primary))]">Cases</h1>
                            <span className="sg-badge sg-badge-neutral">{GLOBAL_CASES.length} total</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-[11px] text-[hsl(var(--fg-muted))]">Active scope:</span>
                            <span className="font-mono text-[12px] font-semibold text-[hsl(var(--primary))]">{activeCase.id}</span>
                        </div>
                    </div>

                    {/* Filter Pills & Search */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                        <div className="flex items-center gap-1.5 text-[12px]">
                            <button
                                className={`sg-btn sg-btn-sm ${filterStatus === 'ALL' ? 'sg-btn-primary' : ''}`}
                                onClick={() => setFilterStatus('ALL')}
                            >
                                All ({GLOBAL_CASES.length})
                            </button>
                            <button
                                className={`sg-btn sg-btn-sm ${filterStatus === 'ACTIVE' ? 'sg-btn-primary' : ''}`}
                                onClick={() => setFilterStatus('ACTIVE')}
                            >
                                Active ({activeCount})
                            </button>
                            <button
                                className={`sg-btn sg-btn-sm ${filterStatus === 'IN REVIEW' ? 'sg-btn-primary' : ''}`}
                                onClick={() => setFilterStatus('IN REVIEW')}
                            >
                                In review ({reviewCount})
                            </button>
                            <button
                                className={`sg-btn sg-btn-sm ${filterStatus === 'ARCHIVED' ? 'sg-btn-primary' : ''}`}
                                onClick={() => setFilterStatus('ARCHIVED')}
                            >
                                Archived ({archivedCount})
                            </button>
                        </div>
                        <div className="relative w-64">
                            <Search size={13} className="absolute left-2.5 top-2 text-[hsl(var(--fg-faint))]" />
                            <input
                                className="sg-input pl-8"
                                placeholder="Filter cases by ID or lead…"
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>
                </div>

                {/* Table */}
                <div className="flex-1 overflow-auto">
                    <table className="sg-table">
                        <thead>
                            <tr>
                                <th>CASE</th>
                                <th>STATUS</th>
                                <th>LEAD</th>
                                <th>ENTITIES</th>
                                <th>EVIDENCE</th>
                                <th>OPEN FINDINGS</th>
                                <th>UPDATED</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredCases.map(c => {
                                const isSelected = c.id === selectedCase.id;
                                const isActiveWorkspace = c.id === activeCase.id;
                                return (
                                    <tr
                                        key={c.id}
                                        className={isSelected ? 'selected' : ''}
                                        onClick={() => handleSelectCase(c)}
                                    >
                                        <td>
                                            <div className="flex items-center gap-2">
                                                <span className="font-mono font-semibold text-[hsl(var(--primary))]">{c.id}</span>
                                                {isActiveWorkspace && (
                                                    <span className="px-1.5 py-0.2 text-[9px] bg-[hsl(var(--primary-bg))] text-[hsl(var(--primary))] border border-[hsl(var(--primary-border))] rounded">
                                                        Active
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-[11px] text-[hsl(var(--fg-muted))] truncate max-w-xs">{c.title}</div>
                                        </td>
                                        <td><StatusMark status={c.status} /></td>
                                        <td className="text-[12px]">{c.lead}</td>
                                        <td className="font-mono text-[12px]">{c.entities_count.toLocaleString()}</td>
                                        <td className="font-mono text-[12px]">{c.evidence_count.toLocaleString()}</td>
                                        <td className="font-mono text-[12px]">
                                            {c.open_findings > 0 ? (
                                                <span className="text-[hsl(var(--amber-fg))] font-semibold">{c.open_findings}</span>
                                            ) : (
                                                <span className="text-[hsl(var(--fg-faint))]">0</span>
                                            )}
                                        </td>
                                        <td className="text-[11px] text-[hsl(var(--fg-muted))] font-mono">{c.updated}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {/* Cross-case link clarification note */}
                <div className="p-3 bg-[hsl(var(--bg-panel))] border-t border-[hsl(var(--border-subtle))] text-[11px] text-[hsl(var(--fg-muted))] flex items-center gap-2">
                    <Info size={13} className="text-[hsl(var(--primary))] shrink-0" />
                    <span>{activeCase.cross_case_links_notice}</span>
                </div>
            </div>

            {/* Selected Case Detail Drawer */}
            <div className="w-96 bg-[hsl(var(--bg-surface))] flex flex-col shrink-0 overflow-y-auto border-l border-[hsl(var(--border-subtle))]">
                <div className="p-4 border-b border-[hsl(var(--border-subtle))] flex items-center justify-between">
                    <div>
                        <div className="font-mono text-[13px] font-bold text-[hsl(var(--primary))]">{selectedCase.id}</div>
                        <div className="text-[12px] text-[hsl(var(--fg-muted))] mt-0.5">{selectedCase.scope}</div>
                    </div>
                    <StatusMark status={selectedCase.status} />
                </div>

                <div className="p-4 space-y-5 flex-1">
                    {/* Case Title & Context */}
                    <div>
                        <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-1">Context</div>
                        <div className="text-[13px] font-medium text-[hsl(var(--fg-primary))] mb-2">{selectedCase.title}</div>
                        <p className="text-[11px] text-[hsl(var(--fg-secondary))] leading-relaxed">{selectedCase.context}</p>
                    </div>

                    {/* Key Attributes */}
                    <div className="space-y-2 pt-3 border-t border-[hsl(var(--border-subtle))]">
                        <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-2">Scope & Activity</div>
                        <div className="grid grid-cols-2 gap-2 text-[11px]">
                            <div>
                                <span className="text-[hsl(var(--fg-muted))]">Lead analyst:</span>
                                <div className="font-medium text-[hsl(var(--fg-primary))]">{selectedCase.lead}</div>
                            </div>
                            <div>
                                <span className="text-[hsl(var(--fg-muted))]">Role:</span>
                                <div className="font-medium text-[hsl(var(--fg-primary))]">{selectedCase.role}</div>
                            </div>
                            <div>
                                <span className="text-[hsl(var(--fg-muted))]">Snapshot:</span>
                                <div className="font-mono text-[hsl(var(--fg-primary))]">{selectedCase.snapshot}</div>
                            </div>
                            <div>
                                <span className="text-[hsl(var(--fg-muted))]">Pipeline:</span>
                                <div className="font-mono text-[hsl(var(--fg-primary))]">{selectedCase.pipeline}</div>
                            </div>
                        </div>
                    </div>

                    {/* Network & Evidence Counts */}
                    <div className="space-y-2 pt-3 border-t border-[hsl(var(--border-subtle))]">
                        <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider mb-2">Case metrics</div>
                        <div className="grid grid-cols-2 gap-2 text-[11px]">
                            <div className="p-2 bg-[hsl(var(--bg-hover))] rounded">
                                <div className="text-[hsl(var(--fg-muted))]">Entities</div>
                                <div className="font-mono text-[14px] font-semibold text-[hsl(var(--fg-primary))]">{selectedCase.entities_count.toLocaleString()}</div>
                            </div>
                            <div className="p-2 bg-[hsl(var(--bg-hover))] rounded">
                                <div className="text-[hsl(var(--fg-muted))]">Communities</div>
                                <div className="font-mono text-[14px] font-semibold text-[hsl(var(--fg-primary))]">{selectedCase.communities_count.toLocaleString()}</div>
                            </div>
                            <div className="p-2 bg-[hsl(var(--bg-hover))] rounded">
                                <div className="text-[hsl(var(--fg-muted))]">Evidence records</div>
                                <div className="font-mono text-[14px] font-semibold text-[hsl(var(--fg-primary))]">{selectedCase.evidence_count.toLocaleString()}</div>
                            </div>
                            <div className="p-2 bg-[hsl(var(--bg-hover))] rounded">
                                <div className="text-[hsl(var(--fg-muted))]">Open review</div>
                                <div className="font-mono text-[14px] font-semibold text-[hsl(var(--amber-fg))]">{selectedCase.open_findings}</div>
                            </div>
                        </div>
                    </div>

                    {/* Jurisdictions */}
                    <div className="space-y-1.5 pt-3 border-t border-[hsl(var(--border-subtle))]">
                        <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Jurisdictions</div>
                        <div className="flex flex-wrap gap-1">
                            {selectedCase.jurisdictions?.map(j => (
                                <span key={j} className="sg-badge sg-badge-neutral">{j}</span>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Footer Action */}
                <div className="p-4 border-t border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-panel))]">
                    <button
                        className="sg-btn sg-btn-primary w-full justify-center"
                        onClick={() => handleSelectCase(selectedCase)}
                    >
                        Set active workspace to {selectedCase.id}
                    </button>
                </div>
            </div>
        </div>
    );
}
