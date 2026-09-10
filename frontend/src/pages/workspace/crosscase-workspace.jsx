/**
 * frontend/src/pages/workspace/crosscase-workspace.jsx
 * -----------------------------------------------------
 * Cross-Case Intelligence Workspace (P0.1).
 *
 * Detects:
 *  - Shared entities, identifiers across multiple cases
 *  - Cross-case link scoring
 *  - Case-to-entity-to-case graph abstraction
 *  - Shared entity drill-down
 */

import React, { useState, useMemo } from 'react';
import {
    FolderOpen, GitCompare, ArrowRight, Users, Shield,
    Activity, Layers, Search, CheckCircle2, ChevronRight,
    Link2, AlertTriangle, Eye, Network as NetworkIcon
} from 'lucide-react';
import { useCrossCase } from '@/api/intel';
import { useCases } from '@/api/xai';
import { useInvestigation } from '@/state/investigation-context';
import { formatNumber, getEntityTypeColor } from '@/components/app-shell';

/* ── Cross-Case Link Strength Scorer ── */
function computeLinkStrength(sharedEntities, totalCasesA, totalCasesB) {
    if (!sharedEntities || sharedEntities.length === 0) return { score: 0, label: 'NONE' };
    const entityScore = Math.min(sharedEntities.length / 5, 1) * 0.4;
    const breadthScore = Math.min(sharedEntities.length / Math.max(totalCasesA, totalCasesB, 1), 1) * 0.3;
    // Heuristic — not AI generated
    const raw = entityScore + breadthScore + 0.3;
    const score = Math.min(raw, 1);
    if (score >= 0.75) return { score, label: 'HIGH' };
    if (score >= 0.5) return { score, label: 'MEDIUM' };
    return { score, label: 'LOW' };
}

/* ── Case Card (compact) ── */
function CaseNode({ caseData, isSource, onClick, selected }) {
    const itemCount = caseData?.items_count ?? caseData?.items?.length ?? 0;
    return (
        <button
            onClick={() => onClick?.(caseData)}
            className={`tp-panel p-2.5 text-left transition-colors ${selected ? 'ring-1 ring-primary' : 'hover:bg-bg-hover'}`}
        >
            <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[11px] font-bold text-primary">{caseData.id}</span>
                <span className={`tp-badge text-[8px] ${caseData.status === 'ACTIVE' ? 'tp-badge-green' : caseData.status === 'CLOSED' ? 'tp-badge-neutral' : 'tp-badge-amber'}`}>
                    {caseData.status || 'UNKNOWN'}
                </span>
            </div>
            <div className="text-[10px] text-fg-secondary truncate">{caseData.title || 'Untitled'}</div>
            <div className="text-[9px] text-fg-faint mt-0.5 font-mono">{itemCount} entities · {caseData.priority || 'N/A'} priority</div>
        </button>
    );
}

/* ── Shared Entity Row ── */
function SharedEntityRow({ entity, cases, onSelect }) {
    return (
        <button
            onClick={() => onSelect?.(entity)}
            className="w-full px-3 py-2 flex items-center gap-3 hover:bg-bg-hover text-left border-b border-border-subtle last:border-b-0"
        >
            <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: getEntityTypeColor(entity.entity_type || 'PERSON') }} />
            <div className="flex-1 min-w-0">
                <div className="text-[11px] text-fg-primary font-medium truncate">{entity.label || entity.entity_id?.slice(0, 16)}</div>
                <div className="text-[9px] text-fg-faint font-mono">{entity.entity_id?.slice(0, 16)}…</div>
            </div>
            <div className="flex flex-wrap gap-1">
                {(cases || entity.cases || []).map((c, i) => (
                    <span key={i} className="tp-badge tp-badge-neutral text-[8px]">{typeof c === 'string' ? c : c.id}</span>
                ))}
            </div>
            <div className="text-[9px] text-fg-faint font-mono">{(cases || entity.cases || []).length} cases</div>
        </button>
    );
}

/* ── Case Connection Graph (simplified CASE→ENTITY→CASE view) ── */
function CaseConnectionGraph({ cases, sharedEntities }) {
    if (!cases || cases.length === 0) return null;

    // Group shared entities by case pair
    const connections = useMemo(() => {
        const map = {};
        for (const ent of sharedEntities || []) {
            const caseIds = ent.cases || [];
            for (let i = 0; i < caseIds.length; i++) {
                for (let j = i + 1; j < caseIds.length; j++) {
                    const key = [caseIds[i], caseIds[j]].sort().join('↔');
                    if (!map[key]) map[key] = { cases: [caseIds[i], caseIds[j]], entities: [] };
                    map[key].entities.push(ent);
                }
            }
        }
        return Object.values(map);
    }, [sharedEntities]);

    if (connections.length === 0) return null;

    return (
        <div className="tp-panel p-3">
            <div className="tp-panel-header">
                <span className="text-[11px] font-semibold text-fg-primary">CROSS-CASE CONNECTION GRAPH</span>
                <span className="text-[10px] font-mono text-fg-faint">{connections.length} LINKS</span>
            </div>
            <div className="space-y-3 pt-2">
                {connections.map((conn, i) => {
                    const strength = computeLinkStrength(conn.entities);
                    return (
                        <div key={i} className="p-2.5 rounded border border-border-subtle bg-bg-surface space-y-2">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-[10px] font-bold text-primary">{conn.cases[0]}</span>
                                    <Link2 size={12} className="text-fg-faint" />
                                    <span className="font-mono text-[10px] font-bold text-primary">{conn.cases[1]}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <span className={`tp-badge text-[8px] font-mono ${
                                        strength.label === 'HIGH' ? 'tp-badge-amber' :
                                        strength.label === 'MEDIUM' ? 'tp-badge-blue' : 'tp-badge-neutral'
                                    }`}>
                                        LINK: {strength.label}
                                    </span>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-1">
                                {conn.entities.map((e, j) => (
                                    <span key={j} className="text-[9px] px-1.5 py-0.5 rounded bg-bg-panel text-fg-secondary border border-border-subtle font-mono">
                                        {e.label || e.entity_id?.slice(0, 12)}
                                    </span>
                                ))}
                            </div>
                            <div className="text-[9px] text-fg-faint">
                                Shared entities: {conn.entities.length}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

/* ══════════════════════════════════════════════════════════════
   MAIN WORKSPACE
══════════════════════════════════════════════════════════════ */
export default function CrossCaseWorkspace() {
    const { setSelectedEntity } = useInvestigation();
    const { data: crossData, isLoading } = useCrossCase();
    const { data: casesData } = useCases();
    const [selectedCaseA, setSelectedCaseA] = useState(null);
    const [selectedCaseB, setSelectedCaseB] = useState(null);
    const [filter, setFilter] = useState('');

    const cases = casesData?.items || casesData || [];
    const reusedEntities = crossData?.reused_entities || [];
    const totalReused = crossData?.total_reused || reusedEntities.length;
    const caseCount = crossData?.case_count || cases.length;

    // Filter shared entities
    const filteredEntities = useMemo(() => {
        if (!filter) return reusedEntities;
        const q = filter.toLowerCase();
        return reusedEntities.filter(e =>
            (e.entity_id || '').toLowerCase().includes(q) ||
            (e.label || '').toLowerCase().includes(q) ||
            (e.cases || []).some(c => (typeof c === 'string' ? c : c.id || '').toLowerCase().includes(q))
        );
    }, [reusedEntities, filter]);

    if (isLoading) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="flex flex-col gap-2 text-fg-secondary">
                    <div className="text-[11px] font-semibold tracking-wide text-fg-primary">LOADING CROSS-CASE DATA</div>
                    <div className="text-[10px] text-fg-faint">Resolving shared entities across investigations…</div>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4 max-w-[1720px] mx-auto animate-fade-in">
            {/* ── HEADER ── */}
            <div className="tp-panel p-3.5 bg-bg-panel flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <FolderOpen size={16} className="text-primary" />
                        <span className="text-[14px] font-bold text-fg-primary">CROSS-CASE INTELLIGENCE</span>
                        <span className="tp-badge tp-badge-blue">MULTI-CASE GRAPH</span>
                    </div>
                    <p className="text-[11px] text-fg-secondary mt-0.5">
                        {totalReused} shared entities detected across {caseCount} investigations.
                        Shared entities, organizations, and accounts reveal cross-case links.
                    </p>
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono text-fg-faint">
                    <div>{caseCount} CASES</div>
                    <div className="w-px h-3 bg-border-subtle" />
                    <div>{totalReused} SHARED</div>
                </div>
            </div>

            {/* ── CASE OVERVIEW (mini graph abstraction) ── */}
            <div className="tp-panel p-3">
                <div className="tp-panel-header">
                    <span className="text-[11px] font-semibold text-fg-primary">CASE → ENTITY → CASE MAP</span>
                </div>
                {cases.length > 0 ? (
                    <div className="flex flex-wrap gap-2 pt-2">
                        {cases.map((c) => {
                            const sharedWith = reusedEntities.filter(e => (e.cases || []).includes(c.id)).length;
                            const itemCount = c.items_count ?? c.items?.length ?? 0;
                            return (
                                <button
                                    key={c.id}
                                    className={`tp-panel p-2.5 text-left min-w-[200px] transition-colors ${selectedCaseA?.id === c.id || selectedCaseB?.id === c.id ? 'ring-1 ring-primary' : 'hover:bg-bg-hover'}`}
                                    onClick={() => {
                                        if (!selectedCaseA || selectedCaseA.id === c.id) setSelectedCaseA(c);
                                        else if (!selectedCaseB || selectedCaseB.id === c.id) setSelectedCaseB(c);
                                        else { setSelectedCaseA(c); setSelectedCaseB(null); }
                                    }}
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="font-mono text-[10px] font-bold text-primary">{c.id}</span>
                                        <span className={`tp-badge text-[8px] ${c.status === 'ACTIVE' ? 'tp-badge-green' : 'tp-badge-neutral'}`}>{c.status}</span>
                                    </div>
                                    <div className="text-[10px] text-fg-secondary mt-0.5 truncate">{c.title}</div>
                                    <div className="text-[9px] text-fg-faint mt-0.5">
                                        {itemCount} entities · {sharedWith} shared
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-[10px] text-fg-faint py-3 text-center">No cases found</div>
                )}
            </div>

            {/* ── CONNECTION GRAPH ── */}
            <CaseConnectionGraph cases={cases} sharedEntities={reusedEntities} />

            {/* ── SHARED ENTITIES TABLE ── */}
            <div className="tp-panel">
                <div className="tp-panel-header">
                    <span className="text-[11px] font-semibold text-fg-primary">SHARED ENTITIES ACROSS CASES</span>
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-fg-faint">{filteredEntities.length} MATCHES</span>
                        <div className="relative">
                            <Search size={11} className="absolute left-1.5 top-1/2 -translate-y-1/2 text-fg-faint" />
                            <input
                                type="text"
                                placeholder="Filter entities…"
                                value={filter}
                                onChange={(e) => setFilter(e.target.value)}
                                className="tp-input h-5 text-[10px] pl-5 w-32"
                            />
                        </div>
                    </div>
                </div>
                {filteredEntities.length > 0 ? (
                    <div className="max-h-[400px] overflow-y-auto">
                        {filteredEntities.map((item, i) => (
                            <SharedEntityRow
                                key={item.entity_id || i}
                                entity={item}
                                cases={item.cases}
                                onSelect={(ent) => setSelectedEntity({ id: ent.entity_id, label: ent.label || ent.entity_id, type: 'PERSON' })}
                            />
                        ))}
                    </div>
                ) : (
                    <div className="p-6 text-center text-[10px] text-fg-faint">
                        {filter ? 'No entities match the current filter.' : 'No shared entities detected between cases.'}
                    </div>
                )}
            </div>

            {/* ── LEGEND ── */}
            <div className="tp-panel p-2.5">
                <div className="flex items-center gap-4 text-[9px] text-fg-faint">
                    <span className="font-semibold">INTERPRETATION GUIDE</span>
                    <span>• Heuristic link scores — not AI-generated</span>
                    <span>• Requires investigator review</span>
                </div>
            </div>
        </div>
    );
}
