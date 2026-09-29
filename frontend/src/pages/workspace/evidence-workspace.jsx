/**
 * Evidence Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §10: Evidence Register.
 * Columns: EVIDENCE, SOURCE, TYPE, TIMESTAMP (UTC), STATUS, LINKED
 * Detail drawer for EV-24091 with SHA-256 provenance hash, lineage, linked entities.
 */
import React, { useState } from 'react';
import { FileText, Search, Download, Shield, ExternalLink, CheckCircle2, ChevronRight, Hash } from 'lucide-react';
import { SYNTHETIC_EVIDENCE } from '@/state/synthetic-case-data';
import { StatusMark, Pagination } from '@/components/shared';

export default function EvidenceWorkspace() {
    const [selectedEvidenceId, setSelectedEvidenceId] = useState('EV-24091');
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedType, setSelectedType] = useState('ALL');
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    const types = ['ALL', 'Transaction source record', 'Corporate Filing', 'Wire Instruction', 'Regulatory Notice', 'Bank Registry Excerpt', 'Digital Forensics'];

    const filtered = SYNTHETIC_EVIDENCE.filter(e => {
        const matchesSearch = e.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
            e.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
            e.source.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesType = selectedType === 'ALL' || e.type === selectedType;
        return matchesSearch && matchesType;
    });

    const selectedEvidence = SYNTHETIC_EVIDENCE.find(e => e.id === selectedEvidenceId) || SYNTHETIC_EVIDENCE[0];

    const handleExportRegister = () => {
        const payload = {
            export_type: 'EVIDENCE_REGISTER',
            total_records: 40292,
            exported_at: new Date().toISOString(),
            actor: 'A. Rao',
            records: filtered
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `evidence_register_${Date.now()}.json`;
        a.click();
    };

    return (
        <div className="flex h-full overflow-hidden animate-fade-in bg-[hsl(var(--bg-root))]">
            {/* Main Table Area */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden border-r border-[hsl(var(--border-subtle))]">
                {/* Header & Controls */}
                <div className="p-4 bg-[hsl(var(--bg-surface))] border-b border-[hsl(var(--border-subtle))] space-y-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <FileText size={16} className="text-[hsl(var(--primary))]" />
                            <h1 className="text-[16px] font-semibold text-[hsl(var(--fg-primary))]">Evidence Register</h1>
                            <span className="sg-badge sg-badge-neutral">40,292 total records</span>
                        </div>
                        <button className="sg-btn sg-btn-sm" onClick={handleExportRegister}>
                            <Download size={12} />
                            Export register
                        </button>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <div className="relative flex-1 min-w-[200px]">
                            <Search size={13} className="absolute left-2.5 top-2 text-[hsl(var(--fg-faint))]" />
                            <input
                                className="sg-input pl-8"
                                placeholder="Search by evidence ID or description…"
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-[11px] text-[hsl(var(--fg-muted))]">Type:</label>
                            <select
                                className="sg-select text-[12px]"
                                value={selectedType}
                                onChange={e => setSelectedType(e.target.value)}
                            >
                                {types.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                        </div>
                    </div>
                </div>

                {/* Table */}
                <div className="flex-1 overflow-auto bg-[hsl(var(--bg-surface))]">
                    <table className="sg-table">
                        <thead>
                            <tr>
                                <th>EVIDENCE</th>
                                <th>SOURCE</th>
                                <th>TYPE</th>
                                <th>TIMESTAMP (UTC)</th>
                                <th>STATUS</th>
                                <th>LINKED</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map(e => {
                                const isSelected = e.id === selectedEvidence.id;
                                return (
                                    <tr
                                        key={e.id}
                                        className={isSelected ? 'selected' : ''}
                                        onClick={() => setSelectedEvidenceId(e.id)}
                                    >
                                        <td>
                                            <div className="font-mono text-[12px] font-semibold text-[hsl(var(--primary))]">{e.id}</div>
                                            <div className="text-[11px] text-[hsl(var(--fg-muted))] truncate max-w-xs">{e.title}</div>
                                        </td>
                                        <td className="text-[12px] text-[hsl(var(--fg-secondary))] truncate max-w-[150px]">{e.source}</td>
                                        <td><span className="sg-badge sg-badge-neutral">{e.type}</span></td>
                                        <td className="font-mono text-[11px] text-[hsl(var(--fg-muted))]">{e.timestamp.replace('T', ' ').slice(0, 16)}</td>
                                        <td><StatusMark status={e.status} /></td>
                                        <td>
                                            <span className="text-[11px] font-mono text-[hsl(var(--fg-muted))]">
                                                {e.linked_entities?.length || 0} ent · {e.linked_findings?.length || 0} fnd
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                <Pagination
                    page={page}
                    pageSize={pageSize}
                    total={40292}
                    onPageChange={p => setPage(p)}
                    onPageSizeChange={s => setPageSize(s)}
                />
            </div>

            {/* Selected Evidence Detail Drawer */}
            <div className="w-96 bg-[hsl(var(--bg-surface))] flex flex-col shrink-0 overflow-y-auto border-l border-[hsl(var(--border-subtle))] p-5 space-y-5">
                <div className="flex items-center justify-between pb-3 border-b border-[hsl(var(--border-subtle))]">
                    <div>
                        <div className="font-mono text-[14px] font-bold text-[hsl(var(--primary))]">{selectedEvidence.id}</div>
                        <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-0.5">{selectedEvidence.type}</div>
                    </div>
                    <StatusMark status={selectedEvidence.status} />
                </div>

                {/* Verification & SHA-256 Provenance */}
                <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))] space-y-2">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[hsl(var(--green-fg))]">
                        <CheckCircle2 size={13} />
                        <span>{selectedEvidence.verification}</span>
                    </div>
                    <div className="space-y-1">
                        <div className="text-[10px] uppercase font-mono text-[hsl(var(--fg-muted))]">SHA-256 Digest</div>
                        <div className="font-mono text-[10px] break-all bg-[hsl(var(--bg-surface))] p-1.5 rounded border border-[hsl(var(--border-subtle))] text-[hsl(var(--fg-secondary))]">
                            {selectedEvidence.sha256}
                        </div>
                    </div>
                </div>

                {/* Provenance Lineage */}
                <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Source Lineage</div>
                    <div className="text-[12px] text-[hsl(var(--fg-secondary))] leading-relaxed">
                        {selectedEvidence.source_lineage}
                    </div>
                    <div className="text-[11px] text-[hsl(var(--fg-muted))] pt-1">
                        {selectedEvidence.provenance_details}
                    </div>
                </div>

                {/* Linked Nodes */}
                <div className="space-y-3 pt-3 border-t border-[hsl(var(--border-subtle))]">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Linked Case Objects</div>
                    <div className="space-y-2 text-[12px]">
                        <div>
                            <span className="text-[hsl(var(--fg-muted))] block mb-1">Entities:</span>
                            <div className="flex flex-wrap gap-1">
                                {selectedEvidence.linked_entities?.map(ent => (
                                    <span key={ent} className="px-1.5 py-0.5 font-mono text-[11px] bg-[hsl(var(--bg-hover))] rounded border border-[hsl(var(--border-default))]">
                                        {ent}
                                    </span>
                                ))}
                            </div>
                        </div>
                        <div>
                            <span className="text-[hsl(var(--fg-muted))] block mb-1">Findings:</span>
                            <div className="flex flex-wrap gap-1">
                                {selectedEvidence.linked_findings?.map(fnd => (
                                    <span key={fnd} className="px-1.5 py-0.5 font-mono text-[11px] bg-[hsl(var(--primary-bg))] text-[hsl(var(--primary))] rounded border border-[hsl(var(--primary-border))]">
                                        {fnd}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
