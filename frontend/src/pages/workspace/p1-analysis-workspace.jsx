import React, { useMemo, useState } from 'react';
import {
    Activity, AlertTriangle, ArrowRight, Clock3, DollarSign,
    GitCompare, Layers3, ShieldCheck, Waypoints,
} from 'lucide-react';
import {
    useCounterEvidence,
    useDataQuality,
    useFinancialSignals,
    useMethodAgreement,
    useMotifs,
    useReplayBuckets,
    useReplayDiff,
    useReplayEvents,
    useReplaySnapshot,
} from '@/api/intel';
import { useFindings } from '@/api/xai';
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

function Metric({ label, value, detail }) {
    return (
        <div className="border border-border-subtle bg-bg-root px-2 py-2">
            <div className="text-[9px] uppercase tracking-wide text-fg-faint">{label}</div>
            <div className="mt-1 text-[17px] font-mono text-fg-primary">{value}</div>
            {detail && <div className="mt-1 text-[9px] text-fg-faint">{detail}</div>}
        </div>
    );
}

function LoadingLine() {
    return <div className="h-2 w-24 animate-pulse bg-bg-hover" />;
}

export default function P1AnalysisWorkspace() {
    const { selectedEntity, selectedHypothesis } = useInvestigation();
    const [mode, setMode] = useState('cumulative');
    const [bucketIndex, setBucketIndex] = useState(0);
    const [findingId, setFindingId] = useState(selectedHypothesis?.id || '');

    const { data: bucketsData } = useReplayBuckets(12);
    const timestamps = bucketsData?.timestamps || [];
    const timestamp = timestamps[bucketIndex] || timestamps[timestamps.length - 1] || '';
    const previousTimestamp = timestamps[Math.max(bucketIndex - 1, 0)] || '';
    const { data: snapshot, isLoading: snapshotLoading } = useReplaySnapshot(timestamp, mode);
    const { data: diff } = useReplayDiff(previousTimestamp, timestamp);
    const { data: eventsData } = useReplayEvents();
    const { data: motifsData } = useMotifs({ limit: 24 });
    const { data: financialData } = useFinancialSignals();
    const { data: qualityData } = useDataQuality(selectedEntity?.id ? [selectedEntity.id] : undefined);
    const { data: agreementData } = useMethodAgreement(selectedEntity?.id ? [selectedEntity.id] : undefined);
    const { data: findingsData } = useFindings();
    const { data: counterEvidence } = useCounterEvidence(findingId);

    const events = eventsData?.events || [];
    const motifs = motifsData?.motifs || [];
    const signals = financialData?.signals || [];
    const dimensions = qualityData?.dimensions || [];
    const agreement = agreementData?.entities?.[0];
    const findings = findingsData?.items || findingsData?.findings || [];

    const selectedFinding = useMemo(
        () => findings.find((finding) => finding.id === findingId),
        [findings, findingId],
    );

    function selectFinding(id) {
        setFindingId(id);
    }

    return (
        <div className="h-full overflow-y-auto animate-fade-in">
            <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-bg-surface px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <Activity size={15} className="text-primary" />
                        <h1 className="text-[13px] font-semibold tracking-wide text-fg-primary">P1 ANALYTICAL WORKBENCH</h1>
                    </div>
                    <p className="mt-1 text-[10px] text-fg-faint">Observed change, structural patterns, flow, reliability, and counter-evidence.</p>
                </div>
                <div className="text-right text-[9px] text-fg-faint">
                    <div>FOCUS ENTITY</div>
                    <div className="mt-1 font-mono text-fg-secondary">{selectedEntity?.label || selectedEntity?.id || 'CASE NETWORK'}</div>
                </div>
            </div>

            <div className="grid gap-3 p-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,0.6fr)]">
                <div className="space-y-3">
                    <Panel title="NETWORK REPLAY" icon={Clock3}>
                        <div className="flex flex-wrap items-center gap-2">
                            <select value={mode} onChange={(event) => setMode(event.target.value)} className="tp-input h-7 text-[10px]">
                                <option value="cumulative">Cumulative</option>
                                <option value="snapshot">Snapshot</option>
                                <option value="sliding_window">Sliding window · 30 days</option>
                            </select>
                            <input
                                type="range"
                                min="0"
                                max={Math.max(timestamps.length - 1, 0)}
                                value={bucketIndex}
                                onChange={(event) => setBucketIndex(Number(event.target.value))}
                                className="min-w-[180px] flex-1 accent-[hsl(var(--primary))]"
                            />
                            <span className="font-mono text-[10px] text-fg-secondary">{timestamp || 'No timestamp'}</span>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                            <Metric label="Entities" value={snapshotLoading ? <LoadingLine /> : snapshot?.node_count ?? '—'} />
                            <Metric label="Relationships" value={snapshotLoading ? <LoadingLine /> : snapshot?.edge_count ?? '—'} />
                            <Metric label="Communities" value={snapshot?.communities ?? '—'} />
                            <Metric label="Change" value={diff?.edges_added != null ? `+${diff.edges_added}` : '—'} detail={diff?.summary} />
                        </div>
                        <div className="mt-3 flex items-start gap-2 border-l-2 border-primary pl-2 text-[10px] text-fg-secondary">
                            <GitCompare size={12} className="mt-0.5 shrink-0 text-primary" />
                            <span>{diff?.summary || 'Move the timeline to inspect structural change.'}</span>
                        </div>
                        <div className="mt-3 grid gap-1 sm:grid-cols-2">
                            {events.slice(0, 6).map((event) => (
                                <div key={event.event_id} className="border border-border-subtle bg-bg-root px-2 py-2">
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="tp-badge tp-badge-blue">{event.event_type}</span>
                                        <span className="font-mono text-[9px] text-fg-faint">{event.timestamp?.slice(0, 10)}</span>
                                    </div>
                                    <div className="mt-1 text-[10px] text-fg-secondary">{event.description}</div>
                                </div>
                            ))}
                        </div>
                    </Panel>

                    <div className="grid gap-3 lg:grid-cols-2">
                        <Panel title="MOTIF DETECTION" icon={Waypoints}>
                            <div className="mb-2 flex flex-wrap gap-1">
                                {Object.entries(motifsData?.summary || {}).map(([type, count]) => (
                                    <span key={type} className="tp-badge tp-badge-neutral">{type} {count}</span>
                                ))}
                            </div>
                            <div className="space-y-1.5">
                                {motifs.slice(0, 6).map((motif) => (
                                    <div key={motif.motif_id} className="flex items-start gap-2 border-b border-border-subtle pb-1.5">
                                        <span className="mt-0.5 text-[9px] font-mono text-primary">{motif.motif_type}</span>
                                        <span className="text-[10px] text-fg-secondary">{motif.description}</span>
                                    </div>
                                ))}
                                {!motifs.length && <div className="text-[10px] text-fg-faint">No motifs returned for this graph.</div>}
                            </div>
                        </Panel>

                        <Panel title="FINANCIAL FLOW SIGNALS" icon={DollarSign}>
                            <div className="mb-2 grid grid-cols-3 gap-1">
                                <Metric label="Signals" value={signals.length} />
                                <Metric label="Accounts" value={financialData?.summary?.total_accounts ?? '—'} />
                                <Metric label="Transfers" value={financialData?.summary?.total_transfers ?? '—'} />
                            </div>
                            <div className="space-y-1.5">
                                {signals.slice(0, 5).map((signal, index) => (
                                    <div key={`${signal.signal_type}-${index}`} className="flex items-start gap-2 border-b border-border-subtle pb-1.5">
                                        <span className="mt-0.5 text-[9px] font-mono text-amber-400">{signal.signal_type}</span>
                                        <span className="text-[10px] text-fg-secondary">{signal.description}</span>
                                    </div>
                                ))}
                                {!signals.length && <div className="text-[10px] text-fg-faint">No financial signals returned.</div>}
                            </div>
                        </Panel>
                    </div>
                </div>

                <div className="space-y-3">
                    <Panel title="DATA QUALITY INDICATORS" icon={ShieldCheck}>
                        <div className="mb-3 flex items-end justify-between border-b border-border-subtle pb-2">
                            <span className="text-[10px] text-fg-faint">Analytical readiness</span>
                            <span className="font-mono text-lg text-fg-primary">{qualityData?.overall_readiness != null ? `${Math.round(qualityData.overall_readiness * 100)}%` : '—'}</span>
                        </div>
                        <div className="space-y-2">
                            {dimensions.map((dimension) => (
                                <div key={dimension.name}>
                                    <div className="flex justify-between text-[9px] text-fg-secondary"><span>{dimension.name}</span><span className="font-mono">{Math.round(dimension.score * 100)}%</span></div>
                                    <div className="mt-1 h-1 bg-bg-root"><div className="h-full bg-primary" style={{ width: `${dimension.score * 100}%` }} /></div>
                                </div>
                            ))}
                        </div>
                        {qualityData?.limitations?.[0] && <div className="mt-3 text-[9px] text-fg-faint">{qualityData.limitations[0]}</div>}
                    </Panel>

                    <Panel title="METHOD AGREEMENT" icon={Layers3}>
                        {agreement ? (
                            <>
                                <div className="flex items-center justify-between border-b border-border-subtle pb-2">
                                    <div><div className="text-[10px] text-fg-secondary">{agreement.entity_label}</div><div className="mt-1 text-[9px] text-fg-faint">{agreement.agreement_level}</div></div>
                                    <div className="font-mono text-lg text-fg-primary">{Math.round(agreement.agreement_score * 100)}%</div>
                                </div>
                                <div className="mt-2 space-y-1">
                                    {agreement.rankings.map((ranking) => <div key={ranking.method} className="flex justify-between text-[10px] text-fg-secondary"><span>{ranking.method}</span><span className="font-mono">#{ranking.rank}</span></div>)}
                                </div>
                                <div className="mt-2 text-[10px] text-fg-faint">{agreement.interpretation}</div>
                            </>
                        ) : <div className="text-[10px] text-fg-faint">Select an entity to compare methods.</div>}
                    </Panel>

                    <Panel title="COUNTER-EVIDENCE" icon={AlertTriangle}>
                        <select value={findingId} onChange={(event) => selectFinding(event.target.value)} className="tp-input h-7 w-full text-[10px]">
                            <option value="">Select a finding</option>
                            {findings.slice(0, 30).map((finding) => <option key={finding.id} value={finding.id}>{finding.subject_label || finding.id}</option>)}
                        </select>
                        {counterEvidence && !counterEvidence.error ? (
                            <div className="mt-3 space-y-2">
                                <div className="grid grid-cols-3 gap-1 text-center">
                                    <Metric label="Supporting" value={counterEvidence.support_count} />
                                    <Metric label="Contradictory" value={counterEvidence.contradiction_count} />
                                    <Metric label="Unknown" value={counterEvidence.unknown_count} />
                                </div>
                                <div className="text-[10px] text-fg-secondary">{counterEvidence.summary}</div>
                                {counterEvidence.contradictory?.slice(0, 3).map((item) => <div key={item.evidence_id} className="border-l-2 border-red-400 bg-bg-root px-2 py-1.5 text-[9px] text-fg-secondary"><span className="font-mono text-red-300">{item.evidence_id}</span> · {item.impact}</div>)}
                            </div>
                        ) : <div className="mt-3 text-[10px] text-fg-faint">Choose a finding to inspect what may weaken it.</div>}
                    </Panel>
                </div>
            </div>
        </div>
    );
}
