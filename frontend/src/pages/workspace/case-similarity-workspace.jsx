import React, { useState, useMemo } from 'react';
import { Dna, GitCompare, Network, ArrowRight, Clock3, DollarSign, Users, Waypoints, AlertCircle } from 'lucide-react';
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
            <div className={`mt-1 text-[16px] font-mono ${accent || 'text-fg-primary'}`}>{value}</div>
        </div>
    );
}

function SimilarityBar({ label, value }) {
    const pct = Math.round((value || 0) * 100);
    return (
        <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[9px] text-fg-secondary">
                <span>{label}</span>
                <span className="font-mono">{pct}%</span>
            </div>
            <div className="h-1 bg-bg-root">
                <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
            </div>
        </div>
    );
}

function SimilarityCard({ item, onCompare }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <div className="bg-bg-root border border-border-subtle px-3 py-2 hover:border-border-strong">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Network size={13} className="text-primary" />
                    <div>
                        <div className="text-[10px] font-semibold text-fg-primary">{item.case_id}</div>
                        <div className="text-[9px] text-fg-faint">{item.title || 'Similar case'}</div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="tp-badge tp-badge-blue font-mono">{Math.round(item.overall_similarity * 100)}%</span>
                    <button className="tp-button tp-button-ghost text-[9px] px-2 py-0.5" onClick={() => onCompare(item.case_id)}>COMPARE</button>
                </div>
            </div>
            <button className="mt-1.5 text-[9px] text-primary flex items-center gap-1" onClick={() => setExpanded(!expanded)}>
                {expanded ? 'Hide' : 'Show'} dimensions
            </button>
            {expanded && (
                <div className="mt-2 space-y-1.5">
                    {item.dimensions?.map((dim) => (
                        <SimilarityBar key={dim.dimension} label={dim.dimension.replace(/_/g, ' ')} value={dim.similarity} />
                    ))}
                    {item.similarities?.slice(0, 5).map((sim) => (
                        <div key={sim.dimension} className="border-t border-border-subtle pt-1">
                            <div className="text-[9px] font-semibold text-fg-secondary">{sim.dimension.replace(/_/g, ' ')}</div>
                            {sim.similarities?.slice(0, 3).map((s) => (
                                <div key={s.feature} className="flex justify-between text-[9px] text-fg-faint">
                                    <span>{s.feature}</span>
                                    <span className="font-mono">{Math.round(s.score * 100)}%</span>
                                </div>
                            ))}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function CaseSimilarityWorkspace() {
    const { activeCase } = useInvestigation();
    const [compareTarget, setCompareTarget] = useState('');
    const [weights, setWeights] = useState({
        structural: 0.35, financial: 0.20, temporal: 0.15,
        entity_composition: 0.15, motif: 0.15,
    });

    const caseId = activeCase?.id || 'CASE-0421';
    const { data: fingerprint, isLoading: fpLoading } = useCaseFingerprint(caseId);
    const { data: similarityData, isLoading: simLoading } = useCaseSimilarity(caseId, weights);
    const { data: compareData } = useCaseCompare(caseId, compareTarget);

    const similarCases = similarityData?.similarities || [];

    const dnaStats = useMemo(() => {
        if (!fingerprint) return [];
        const features = fingerprint.features || {};
        return [
            { label: 'ENTITIES', value: features.entity_count ?? '—' },
            { label: 'COMMUNITIES', value: features.community_count ?? '—' },
            { label: 'BRIDGES', value: features.bridge_count ?? '—' },
            { label: 'DENSITY', value: features.network_density != null ? features.network_density.toFixed(3) : '—' },
            { label: 'MOTIFS', value: features.motif_count ?? '—' },
            { label: 'CROSS-CASE', value: features.cross_case_overlap != null ? `${Math.round(features.cross_case_overlap * 100)}%` : '—' },
        ];
    }, [fingerprint]);

    return (
        <div className="h-full overflow-y-auto animate-fade-in">
            <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-bg-surface px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <Dna size={15} className="text-primary" />
                        <h1 className="text-[13px] font-semibold tracking-wide text-fg-primary">CASE SIMILARITY / NETWORK DNA</h1>
                    </div>
                    <p className="mt-1 text-[10px] text-fg-faint">Have we seen a network like this before?</p>
                </div>
                <span className="tp-badge tp-badge-blue">{caseId}</span>
            </div>

            <div className="grid gap-3 p-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
                {/* Left: Fingerprint + Similar Cases */}
                <div className="space-y-3">
                    <Panel title="NETWORK DNA — CASE FINGERPRINT" icon={Dna}>
                        {fpLoading ? (
                            <div className="h-20 animate-pulse bg-bg-hover" />
                        ) : fingerprint?.error ? (
                            <div className="text-[10px] text-fg-faint">{fingerprint.error}</div>
                        ) : (
                            <>
                                <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                                    {dnaStats.map((s) => <Stat key={s.label} label={s.label} value={s.value} />)}
                                </div>
                                {fingerprint?.limitations?.[0] && (
                                    <div className="mt-2 text-[9px] text-fg-faint">{fingerprint.limitations[0]}</div>
                                )}
                            </>
                        )}
                    </Panel>

                    <Panel title="SIMILAR CASES" icon={GitCompare}>
                        {/* Weight controls */}
                        <div className="mb-3 grid grid-cols-5 gap-1">
                            {Object.entries(weights).map(([key, val]) => (
                                <div key={key} className="text-center">
                                    <div className="text-[8px] uppercase text-fg-faint">{key.replace(/_/g, ' ')}</div>
                                    <div className="text-[11px] font-mono text-fg-primary">{Math.round(val * 100)}%</div>
                                </div>
                            ))}
                        </div>
                        {simLoading ? (
                            <div className="space-y-2">
                                {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse bg-bg-hover" />)}
                            </div>
                        ) : similarCases.length === 0 ? (
                            <div className="text-[10px] text-fg-faint">No similar cases found.</div>
                        ) : (
                            <div className="space-y-2">
                                {similarCases.map((item) => (
                                    <SimilarityCard key={item.case_id} item={item} onCompare={(id) => setCompareTarget(id)} />
                                ))}
                            </div>
                        )}
                    </Panel>
                </div>

                {/* Right: Comparison + Explainability */}
                <div className="space-y-3">
                    <Panel title="CASE COMPARISON" icon={GitCompare}>
                        <div className="flex items-center gap-2 mb-3">
                            <span className="tp-badge tp-badge-blue">{caseId}</span>
                            <ArrowRight size={12} className="text-fg-faint" />
                            <select
                                value={compareTarget}
                                onChange={(e) => setCompareTarget(e.target.value)}
                                className="tp-input h-7 text-[10px] flex-1"
                            >
                                <option value="">Select case to compare</option>
                                {similarCases.map((s) => (
                                    <option key={s.case_id} value={s.case_id}>{s.case_id} ({Math.round(s.overall_similarity * 100)}%)</option>
                                ))}
                            </select>
                        </div>
                        {compareData && !compareData.error ? (
                            <div className="space-y-3">
                                <div className="grid grid-cols-2 gap-2">
                                    <div className="border border-border-subtle bg-bg-root p-2">
                                        <div className="text-[9px] text-fg-faint font-semibold">{compareData.case_a}</div>
                                        <div className="mt-1 space-y-1">
                                            {compareData.comparison?.map((c) => (
                                                <div key={c.feature} className="flex justify-between text-[9px]">
                                                    <span className="text-fg-secondary">{c.feature.replace(/_/g, ' ')}</span>
                                                    <span className="font-mono text-fg-primary">{c.case_a_value ?? '—'}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="border border-border-subtle bg-bg-root p-2">
                                        <div className="text-[9px] text-fg-faint font-semibold">{compareData.case_b}</div>
                                        <div className="mt-1 space-y-1">
                                            {compareData.comparison?.map((c) => (
                                                <div key={c.feature} className="flex justify-between text-[9px]">
                                                    <span className="text-fg-secondary">{c.feature.replace(/_/g, ' ')}</span>
                                                    <span className="font-mono text-fg-primary">{c.case_b_value ?? '—'}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                                {compareData.explanation && (
                                    <div className="border-l-2 border-primary pl-2 text-[10px] text-fg-secondary">
                                        {compareData.explanation}
                                    </div>
                                )}
                                {compareData.similarities?.length > 0 && (
                                    <div className="space-y-1">
                                        {compareData.similarities.map((s) => (
                                            <SimilarityBar key={s.dimension} label={s.dimension.replace(/_/g, ' ')} value={s.overall_similarity} />
                                        ))}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-[10px] text-fg-faint">Select a similar case above to compare.</div>
                        )}
                    </Panel>

                    <Panel title="SIMILARITY EXPLANATION" icon={AlertCircle}>
                        {compareData?.similarities?.[0]?.similarities?.length > 0 ? (
                            <div className="space-y-2">
                                {compareData.similarities[0].similarities.filter((s) => s.score > 0.7).slice(0, 4).map((s) => (
                                    <div key={s.feature} className="flex items-start gap-2 border-b border-border-subtle pb-1">
                                        <span className="text-[10px] text-green-400">+</span>
                                        <span className="text-[10px] text-fg-secondary">Similar {s.feature.replace(/_/g, ' ')}</span>
                                        <span className="text-[9px] font-mono text-fg-faint ml-auto">{Math.round(s.score * 100)}%</span>
                                    </div>
                                ))}
                                {compareData.similarities[0].similarities.filter((s) => s.score < 0.5).slice(0, 4).map((s) => (
                                    <div key={s.feature} className="flex items-start gap-2 border-b border-border-subtle pb-1">
                                        <span className="text-[10px] text-amber-400">-</span>
                                        <span className="text-[10px] text-fg-secondary">Different {s.feature.replace(/_/g, ' ')}</span>
                                        <span className="text-[9px] font-mono text-fg-faint ml-auto">{Math.round(s.score * 100)}%</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-[10px] text-fg-faint">Select two cases to see why they are similar or different.</div>
                        )}
                    </Panel>
                </div>
            </div>
        </div>
    );
}
