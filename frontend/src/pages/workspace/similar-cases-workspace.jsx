import React, { useState } from 'react';
import { GitCompareArrows, BarChart3, Network, TrendingUp, Users, Layers, DollarSign, Clock3, ArrowRight, Eye } from 'lucide-react';
import { useCaseFingerprint, useCaseSimilarity, useCaseCompare } from '@/api/intel';
import { useInvestigation } from '@/state/investigation-context';

function Panel({ title, icon: Icon, children, className = '' }) {
    return (
        <section className={`tp-panel p-3 ${className}`}>
            <div className="flex items-center gap-2 mb-3">
                <Icon size={14} className="text-primary" />
                <h2 className="text-[11px] font-semibold tracking-wide text-fg-primary">{title}</h2>
            </div>
            {children}
        </section>
    );
}

function Stat({ label, value, accent }) {
    return (
        <div className="border border-border-subtle bg-bg-root px-2 py-2">
            <div className="text-[9px] uppercase tracking-wide text-fg-faint">{label}</div>
            <div className={`mt-1 text-[15px] font-mono ${accent || 'text-fg-primary'}`}>{value}</div>
        </div>
    );
}

function SimilarityBar({ label, value }) {
    return (
        <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[9px] text-fg-secondary">
                <span>{label}</span>
                <span className="font-mono">{Math.round(value * 100)}%</span>
            </div>
            <div className="h-1 bg-bg-root">
                <div className="h-full bg-primary transition-all" style={{ width: `${value * 100}%` }} />
            </div>
        </div>
    );
}

function SimilarCaseRow({ sim, onSelect, isSelected }) {
    return (
        <div className={`border px-2 py-2 cursor-pointer transition-colors ${isSelected ? 'border-primary bg-primary/5' : 'border-border-subtle bg-bg-root hover:bg-bg-hover'}`} onClick={() => onSelect(sim.case_id)}>
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <Network size={12} className="text-primary" />
                    <span className="text-[10px] font-mono text-fg-primary">{sim.case_id}</span>
                </div>
                <span className={`tp-badge ${sim.similarity >= 0.75 ? 'tp-badge-green' : sim.similarity >= 0.5 ? 'tp-badge-yellow' : 'tp-badge-neutral'}`}>
                    {Math.round(sim.similarity * 100)}%
                </span>
            </div>
            <div className="mt-2 space-y-1">
                <SimilarityBar label="Structural" value={sim.structural} />
                <SimilarityBar label="Financial" value={sim.financial} />
                <SimilarityBar label="Temporal" value={sim.temporal} />
            </div>
            {sim.why_similar?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                    {sim.why_similar.map((reason, i) => <span key={i} className="tp-badge tp-badge-blue text-[8px]">{reason}</span>)}
                </div>
            )}
        </div>
    );
}

function ComparisonView({ comparison }) {
    if (!comparison) return null;
    return (
        <Panel title={`${comparison.case_a} vs ${comparison.case_b}`} icon={GitCompareArrows}>
            <div className="mb-3 text-center">
                <span className="text-[22px] font-mono text-primary">{Math.round(comparison.similarity * 100)}%</span>
                <div className="text-[9px] text-fg-faint mt-1">Overall Similarity</div>
            </div>
            <div className="space-y-1.5 mb-3">
                {Object.entries(comparison.dimensions || {}).map(([dim, val]) => (
                    <SimilarityBar key={dim} label={dim.replace(/_/g, ' ')} value={val} />
                ))}
            </div>
            {/* Why similar */}
            {comparison.why_similar?.length > 0 && (
                <div className="mb-2">
                    <div className="text-[9px] font-semibold text-emerald-400 mb-1">WHY SIMILAR</div>
                    {comparison.why_similar.map((reason, i) => (
                        <div key={i} className="text-[10px] text-fg-secondary">+ {reason}</div>
                    ))}
                </div>
            )}
            {/* Differences */}
            {comparison.differences?.length > 0 && (
                <div className="mb-2">
                    <div className="text-[9px] font-semibold text-rose-400 mb-1">DIFFERENCES</div>
                    {comparison.differences.map((diff, i) => (
                        <div key={i} className="text-[10px] text-fg-secondary">- {diff}</div>
                    ))}
                </div>
            )}
            {/* Side-by-side stats */}
            <div className="grid grid-cols-2 gap-1 mt-2">
                <div className="text-[9px] text-fg-faint font-semibold border-b border-border-subtle pb-1">{comparison.case_a}</div>
                <div className="text-[9px] text-fg-faint font-semibold border-b border-border-subtle pb-1">{comparison.case_b}</div>
                {Object.entries(comparison.a_only || {}).map(([key, val]) => (
                    <React.Fragment key={key}>
                        <div className="text-[10px] text-fg-secondary">{key}: <span className="font-mono">{typeof val === 'number' ? val.toFixed?.(3) ?? val : val}</span></div>
                        <div className="text-[10px] text-fg-secondary">{key}: <span className="font-mono">{typeof comparison.b_only?.[key] === 'number' ? comparison.b_only[key].toFixed?.(3) ?? comparison.b_only[key] : comparison.b_only?.[key] ?? '—'}</span></div>
                    </React.Fragment>
                ))}
            </div>
        </Panel>
    );
}

export default function SimilarCasesWorkspace() {
    const { activeCase } = useInvestigation();
    const [selectedCase, setSelectedCase] = useState(null);
    const [structuralW, setStructuralW] = useState(35);
    const [financialW, setFinancialW] = useState(20);
    const [temporalW, setTemporalW] = useState(15);
    const [entityW, setEntityW] = useState(15);
    const [motifW, setMotifW] = useState(15);

    const caseId = activeCase?.id || 'CASE-0421';
    const { data: fingerprint, isLoading: fpLoading } = useCaseFingerprint(caseId);
    const { data: similarityData, isLoading: simLoading } = useCaseSimilarity(caseId, {
        structural: structuralW / 100,
        financial: financialW / 100,
        temporal: temporalW / 100,
        entity_composition: entityW / 100,
        motif: motifW / 100,
    });
    const { data: comparison } = useCaseCompare(caseId, selectedCase);

    const similarCases = similarityData?.results || [];
    const fp = fingerprint;

    return (
        <div className="h-full overflow-y-auto animate-fade-in">
            <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-bg-surface px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <GitCompareArrows size={15} className="text-primary" />
                        <h1 className="text-[13px] font-semibold tracking-wide text-fg-primary">CASE SIMILARITY / NETWORK DNA</h1>
                    </div>
                    <p className="mt-1 text-[10px] text-fg-faint">Structural fingerprints, cross-case similarity, and comparison.</p>
                </div>
                <span className="text-[9px] text-fg-faint font-mono">{caseId}</span>
            </div>

            <div className="grid gap-3 p-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
                {/* Main */}
                <div className="space-y-3">
                    {/* Fingerprint */}
                    <Panel title="CASE NETWORK DNA" icon={BarChart3}>
                        {fp && !fpLoading ? (
                            <div className="grid grid-cols-3 sm:grid-cols-5 gap-1.5">
                                <Stat label="Entities" value={fp.entity_count} />
                                <Stat label="Relationships" value={fp.relationship_count} />
                                <Stat label="Communities" value={fp.community_count} />
                                <Stat label="Avg Degree" value={fp.avg_degree?.toFixed(2)} />
                                <Stat label="Centralization" value={`${(fp.centralization * 100).toFixed(0)}%`} />
                                <Stat label="Bridges" value={fp.bridge_count} />
                                <Stat label="Density" value={fp.network_density?.toFixed(3)} />
                                <Stat label="Cycles" value={fp.cycle_count} />
                                <Stat label="Burst Index" value={fp.temporal_burst_index?.toFixed(2)} />
                                <Stat label="Confidence" value={fp.avg_edge_confidence?.toFixed(2)} />
                            </div>
                        ) : (
                            <div className="text-[10px] text-fg-faint py-4 text-center">Loading fingerprint...</div>
                        )}
                    </Panel>

                    {/* Similar Cases List */}
                    <Panel title={`SIMILAR CASES (${similarCases.length})`} icon={Network}>
                        <div className="space-y-1.5 max-h-[400px] overflow-y-auto">
                            {similarCases.map((sim) => (
                                <SimilarCaseRow key={sim.case_id} sim={sim} onSelect={setSelectedCase} isSelected={selectedCase === sim.case_id} />
                            ))}
                            {!similarCases.length && !simLoading && (
                                <div className="text-[10px] text-fg-faint py-4 text-center">No other cases found for comparison.</div>
                            )}
                        </div>
                    </Panel>

                    {/* Comparison */}
                    {comparison && <ComparisonView comparison={comparison} />}
                </div>

                {/* Sidebar */}
                <div className="space-y-3">
                    <Panel title="SIMILARITY WEIGHTS" icon={Layers}>
                        <div className="space-y-2">
                            {[
                                { label: 'Structural', value: structuralW, set: setStructuralW },
                                { label: 'Financial', value: financialW, set: setFinancialW },
                                { label: 'Temporal', value: temporalW, set: setTemporalW },
                                { label: 'Entity Comp.', value: entityW, set: setEntityW },
                                { label: 'Motifs', value: motifW, set: setMotifW },
                            ].map(({ label, value, set }) => (
                                <div key={label}>
                                    <div className="flex items-center justify-between text-[9px] text-fg-secondary">
                                        <span>{label}</span>
                                        <span className="font-mono">{value}%</span>
                                    </div>
                                    <input type="range" min="0" max="100" value={value} onChange={(e) => set(Number(e.target.value))} className="w-full accent-[hsl(var(--primary))]" />
                                </div>
                            ))}
                            <div className="text-[9px] text-fg-faint">Total weight: {structuralW + financialW + temporalW + entityW + motifW}%</div>
                        </div>
                    </Panel>

                    <Panel title="MOTIF DISTRIBUTION" icon={TrendingUp}>
                        {fp?.motif_distribution ? (
                            <div className="space-y-1">
                                {Object.entries(fp.motif_distribution).map(([type, count]) => (
                                    <div key={type} className="flex items-center justify-between text-[10px] text-fg-secondary">
                                        <span>{type}</span>
                                        <span className="font-mono">{count}</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-[10px] text-fg-faint">No motif data.</div>
                        )}
                    </Panel>

                    <Panel title="ENTITY COMPOSITION" icon={Users}>
                        {fp?.entity_type_composition ? (
                            <div className="space-y-1">
                                {Object.entries(fp.entity_type_composition).sort(([, a], [, b]) => b - a).map(([type, ratio]) => (
                                    <div key={type}>
                                        <div className="flex items-center justify-between text-[10px] text-fg-secondary">
                                            <span>{type}</span>
                                            <span className="font-mono">{(ratio * 100).toFixed(0)}%</span>
                                        </div>
                                        <div className="h-1 bg-bg-root"><div className="h-full bg-primary" style={{ width: `${ratio * 100}%` }} /></div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-[10px] text-fg-faint">No composition data.</div>
                        )}
                    </Panel>
                </div>
            </div>
        </div>
    );
}
