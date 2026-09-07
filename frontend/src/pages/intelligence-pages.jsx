// src/pages/intelligence-pages.jsx
// XAI surfaces: FindingsPage, DossiersPage, EvidencePage, SimulationPage,
// SearchPage (Phases E, F/G, C, J/L/M, X).
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useParams } from 'wouter';
import {
    AlertTriangle, CheckCircle2, FileSearch, FileText, FlaskConical, Lightbulb,
    Activity, Scale, ShieldQuestion, Sigma, Zap,
} from 'lucide-react';
import { EmptyState, ErrorState, LoadingRows, PageShell, Panel, Pill, SectionHeading } from '@/components/graph-shell';
import {
    generateDossier,
    reviewDossier,
    runScenarioComparison,
    runNodeRemovalSimulation,
    useDossierDetail,
    useDossiers,
    useEvidenceDetail,
    useEvidenceSearch,
    useEvidenceTimeline,
    useFindingDetail,
    useFindings,
    useGlobalSearch,
} from '@/api/xai';
import { useEvidenceForNode } from '@/api/xai';
import { request } from '@/api/client';

// ------------------------------------------------------------------ Findings --
export function FindingsPage() {
    const [, navigate] = useLocation();
    const findings = useFindings({ page: 1, page_size: 50 });

    return (
        <PageShell>
            <SectionHeading
                eyebrow="Explainable intelligence"
                title="Model findings"
                description="Every model output is a labelled hypothesis: observed facts cite evidence, inferred claims stay inferences, and unknowns are explicit. Confidence is a weighted component breakdown, not a probability of guilt."
            />
            {findings.isLoading && <Panel><LoadingRows count={6} /></Panel>}
            {findings.isError && <Panel><ErrorState onRetry={() => findings.refetch()} /></Panel>}
            {findings.data && findings.data.total === 0 && (
                <Panel>
                    <EmptyState
                        title="No findings yet"
                        description="Run the ghost pipeline and POST /api/findings/generate to build findings from ghost candidates."
                        icon={Lightbulb}
                    />
                </Panel>
            )}
            <div className="grid gap-4 lg:grid-cols-2">
                {(findings.data?.items ?? []).map((f) => (
                    <Panel
                        key={f.id}
                        title={f.subject_label || f.subject_id}
                        subtitle={`${f.finding_type} · ${f.method}`}
                        action={<Pill tone="amber">{f.status}</Pill>}
                    >
                        <div className="space-y-3 p-4">
                            <div className="flex items-center gap-3">
                                <div className="font-mono-ui text-2xl font-semibold">{(f.confidence * 100).toFixed(0)}%</div>
                                <div className="flex-1 space-y-1">
                                    {(f.confidence_components ?? []).slice(0, 4).map((c) => (
                                        <div key={c.name} className="flex items-center gap-2">
                                            <div className="w-36 truncate font-mono-ui text-[9px] uppercase text-muted-foreground">{c.name.replace(/_/g, ' ')}</div>
                                            <div className="h-1.5 flex-1 overflow-hidden rounded bg-muted">
                                                <div className="h-full rounded bg-primary/70" style={{ width: `${Math.min(100, c.value * 100)}%` }} />
                                            </div>
                                            <div className="w-9 text-right font-mono-ui text-[9px]">{c.value?.toFixed?.(2)}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="grid gap-2 text-xs sm:grid-cols-3">
                                <CountChip label="observed" value={f.observed?.length ?? 0} tone="teal" />
                                <CountChip label="inferred" value={f.inferred?.length ?? 0} tone="amber" />
                                <CountChip label="unknown" value={f.unknown?.length ?? 0} tone="neutral" />
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="font-mono-ui text-[9px] uppercase text-muted-foreground">
                                    {f.supporting_evidence_ids?.length ?? 0} evidence · {f.counter_evidence_ids?.length ?? 0} counter
                                </span>
                                <button
                                    onClick={() => navigate(`/findings/${f.id}`)}
                                    className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground"
                                >
                                    Open finding
                                </button>
                            </div>
                        </div>
                    </Panel>
                ))}
            </div>
        </PageShell>
    );
}

function CountChip({ label, value, tone }) {
    return (
        <div className="flex items-center justify-between rounded-md bg-muted/60 px-2.5 py-1.5">
            <Pill tone={tone}>{label}</Pill>
            <span className="font-mono-ui text-xs font-semibold">{value}</span>
        </div>
    );
}

export function FindingDetailPage() {
    const { id } = useParams();
    const finding = useFindingDetail(id);
    if (finding.isLoading) return <Panel><LoadingRows count={8} /></Panel>;
    if (finding.isError) return <Panel><ErrorState onRetry={() => finding.refetch()} /></Panel>;
    const f = finding.data;
    if (!f) return <Panel><EmptyState title="Finding not found" description={`No finding with id ${id}.`} /></Panel>;

    return (
        <PageShell>
            <SectionHeading
                eyebrow={`Finding ${f.id}`}
                title={f.subject_label || f.subject_id}
                description={`${f.finding_type} · method ${f.method} · model ${f.model_version}`}
                action={<Pill tone="amber">{f.status} — human review required</Pill>}
            />
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="What was observed?" subtitle="Concrete facts, each bound to evidence">
                    <div className="space-y-2 p-4">
                        {(f.observed ?? []).map((claim, i) => (
                            <div key={i} className="rounded-md border border-border/70 p-2.5">
                                <div className="mb-1 flex items-center gap-2"><Pill tone="teal">OBSERVED</Pill></div>
                                <div className="text-xs leading-5">{claim.text}</div>
                                <div className="mt-1 flex flex-wrap gap-1">
                                    {(claim.evidence_ids ?? []).map((eid) => (
                                        <EvidenceChip key={eid} id={eid} />
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </Panel>
                <Panel title="What was inferred?" subtitle="Explicit hypotheses — never presented as fact">
                    <div className="space-y-2 p-4">
                        {(f.inferred ?? []).map((claim, i) => (
                            <div key={i} className="rounded-md border border-primary/25 bg-primary/5 p-2.5">
                                <div className="mb-1"><Pill tone="amber">INFERRED</Pill></div>
                                <div className="text-xs leading-5">{claim.text}</div>
                            </div>
                        ))}
                    </div>
                </Panel>
                <Panel title="Why? Graph signals" subtitle="Structural features behind the hypothesis">
                    <div className="space-y-2 p-4">
                        {(f.graph_signals ?? []).map((s, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                                <Sigma size={13} className="mt-0.5 shrink-0 text-primary" />
                                <div>
                                    <div className="font-mono-ui text-[9px] uppercase text-muted-foreground">{s.signal_type.replace(/_/g, ' ')}</div>
                                    <div>{s.description}</div>
                                </div>
                            </div>
                        ))}
                        <div className="mt-3 space-y-1">
                            <div className="font-mono-ui text-[9px] uppercase text-muted-foreground">confidence components</div>
                            {(f.confidence_components ?? []).map((c) => (
                                <div key={c.name} className="flex items-center gap-2 text-xs">
                                    <span className="w-44 truncate">{c.name.replace(/_/g, ' ')}</span>
                                    <div className="h-1.5 flex-1 overflow-hidden rounded bg-muted">
                                        <div className="h-full rounded bg-chart-3/80" style={{ width: `${Math.min(100, (c.value ?? 0) * 100)}%` }} />
                                    </div>
                                    <span className="w-20 text-right font-mono-ui text-[9px] text-muted-foreground">w {c.weight}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </Panel>
                <Panel title="Counter-evidence & unknowns" subtitle="What weakens the hypothesis / what we cannot know">
                    <div className="space-y-2 p-4 text-xs">
                        {(f.counter_evidence_ids ?? []).map((eid) => (
                            <div key={eid} className="flex items-center gap-2">
                                <AlertTriangle size={13} className="text-chart-4" />
                                <EvidenceChip id={eid} />
                            </div>
                        ))}
                        {(f.unknown ?? []).map((claim, i) => (
                            <div key={i} className="rounded-md border border-dashed border-border p-2.5">
                                <div className="mb-1"><Pill tone="neutral">UNKNOWN</Pill></div>
                                <div>{claim.text ?? claim}</div>
                            </div>
                        ))}
                    </div>
                </Panel>
                <Panel title="Limitations" className="lg:col-span-2">
                    <ul className="list-disc space-y-1 p-4 pl-9 text-xs leading-5 text-muted-foreground">
                        {(f.limitations ?? []).map((l, i) => <li key={i}>{l}</li>)}
                    </ul>
                </Panel>
            </div>
        </PageShell>
    );
}

function EvidenceChip({ id }) {
    const [, navigate] = useLocation();
    return (
        <button
            onClick={() => navigate(`/evidence?focus=${encodeURIComponent(id)}`)}
            className="rounded border border-border bg-muted/60 px-1.5 py-0.5 font-mono-ui text-[9px] text-primary hover:border-primary/60"
        >
            {id.slice(0, 16)}…
        </button>
    );
}

// ------------------------------------------------------------------ Dossiers --
export function DossiersPage() {
    const [location] = useLocation();
    const dossiers = useDossiers();
    const [subjectId, setSubjectId] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const params = new URLSearchParams(location.split('?')[1] ?? '');
    const prefill = params.get('subject');
    useEffect(() => {
        if (prefill && !subjectId) setSubjectId(prefill);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [prefill]);

    const generate = async () => {
        if (!subjectId.trim()) return;
        setBusy(true);
        setError(null);
        try {
            await generateDossier({ subject_id: subjectId.trim() });
            await dossiers.refetch();
        } catch (cause) {
            setError(cause.message);
        } finally {
            setBusy(false);
        }
    };

    return (
        <PageShell>
            <SectionHeading
                eyebrow="Evidence-grounded reporting"
                title="Intelligence dossiers"
                description="Dossiers consolidate findings, evidence timelines, counter-evidence and methodology. Every factual statement maps to an evidence id. Output is always DRAFT — HUMAN REVIEW REQUIRED."
            />
            <Panel title="Generate a dossier" subtitle="Subject = node guid or ghost id">
                <div className="flex flex-wrap items-center gap-2 p-4">
                    <input
                        data-testid="input-dossier-subject"
                        value={subjectId}
                        onChange={(e) => setSubjectId(e.target.value)}
                        placeholder="e.g. e1e815f1-4d25-5a12-b5d7-75a89104234f"
                        className="min-w-[320px] flex-1 rounded-md border border-input bg-background px-3 py-2 font-mono-ui text-xs outline-none focus:border-primary"
                    />
                    <button onClick={generate} disabled={busy || !subjectId.trim()} data-testid="button-generate-dossier" className="rounded-md bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-40">
                        {busy ? 'Generating…' : 'Generate dossier'}
                    </button>
                    {error && <span className="text-xs text-destructive">{error}</span>}
                </div>
            </Panel>

            {dossiers.isLoading && <Panel><LoadingRows count={4} /></Panel>}
            <div className="grid gap-4 lg:grid-cols-2">
                {(dossiers.data?.items ?? []).map((d) => (
                    <DossierCard key={d.id} dossier={d} onChanged={dossiers.refetch} />
                ))}
            </div>
        </PageShell>
    );
}

function DossierCard({ dossier, onChanged }) {
    const detail = useDossierDetail(dossier.id);
    const [open, setOpen] = useState(false);
    const [reviewBusy, setReviewBusy] = useState(false);

    const endorse = async () => {
        setReviewBusy(true);
        try {
            await reviewDossier(dossier.id, { reviewer: 'A. Rivera', decision: 'endorsed', note: 'Reviewed by lead analyst.' });
            await detail.refetch();
            onChanged?.();
        } finally {
            setReviewBusy(false);
        }
    };

    return (
        <Panel
            title={dossier.title}
            subtitle={`${dossier.id} · confidence ${dossier.confidence ?? '—'}`}
            action={<Pill tone={dossier.status === 'DRAFT_FOR_HUMAN_REVIEW' ? 'amber' : 'teal'}>{dossier.status === 'DRAFT_FOR_HUMAN_REVIEW' ? 'DRAFT — HUMAN REVIEW REQUIRED' : dossier.status}</Pill>}
        >
            <div className="space-y-3 p-4 text-xs">
                <p className="leading-5 text-foreground/90">{detail.data?.executive_summary?.slice(0, 260)}{(detail.data?.executive_summary?.length ?? 0) > 260 ? '…' : ''}</p>
                <div className="flex flex-wrap items-center gap-2">
                    <Pill tone="neutral">{detail.data?.supporting_evidence?.length ?? 0} supporting</Pill>
                    <Pill tone="neutral">{detail.data?.counter_evidence?.length ?? 0} counter</Pill>
                    <Pill tone="neutral">{detail.data?.timeline?.length ?? 0} timeline events</Pill>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => setOpen(!open)} className="rounded-md border border-border px-3 py-1.5 hover:border-primary/60">
                        {open ? 'Collapse' : 'Open dossier'}
                    </button>
                    {detail.data?.human_review?.required && (
                        <button onClick={endorse} disabled={reviewBusy} className="rounded-md bg-primary/90 px-3 py-1.5 font-semibold text-primary-foreground disabled:opacity-40">
                            {reviewBusy ? 'Recording…' : 'Record human review'}
                        </button>
                    )}
                </div>
                {open && detail.data && (
                    <div className="space-y-3 border-t border-border pt-3">
                        {detail.data.sections?.map((section, si) => (
                            <div key={si}>
                                <div className="mb-1 font-mono-ui text-[9px] uppercase tracking-wide text-primary">{section.title}</div>
                                <div className="space-y-1.5">
                                    {section.items?.slice(0, 6).map((item, ii) => (
                                        <div key={ii} className="rounded-md border border-border/60 p-2">
                                            <div className="mb-0.5 flex items-center gap-1.5">
                                                <Pill tone={item.label === 'OBSERVED' ? 'teal' : item.label === 'INFERRED' ? 'amber' : item.label === 'CONTRADICTED' ? 'rose' : 'neutral'}>{item.label}</Pill>
                                            </div>
                                            <div className="leading-5">{item.text}</div>
                                            {(item.evidence_ids ?? []).length > 0 && (
                                                <div className="mt-1 flex flex-wrap gap-1">
                                                    {item.evidence_ids.map((eid) => <EvidenceChip key={eid} id={eid} />)}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                        <div>
                            <div className="mb-1 font-mono-ui text-[9px] uppercase tracking-wide text-primary">Limitations</div>
                            <ul className="list-disc space-y-0.5 pl-5 text-[11px] text-muted-foreground">
                                {(detail.data.limitations ?? []).slice(0, 6).map((l, i) => <li key={i}>{l}</li>)}
                            </ul>
                        </div>
                        {detail.data.human_review?.decision && (
                            <div className="flex items-center gap-2 rounded-md bg-primary/10 p-2">
                                <CheckCircle2 size={14} className="text-primary" />
                                <span>Review: {detail.data.human_review.decision} by {detail.data.human_review.reviewer}</span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </Panel>
    );
}

// ------------------------------------------------------------------ Evidence --
export function EvidencePage() {
    const [location] = useLocation();
    const params = new URLSearchParams(location.split('?')[1] ?? '');
    const focus = params.get('focus');
    const edge = params.get('edge');
    const [query, setQuery] = useState('');
    const [debounced, setDebounced] = useState('');
    useEffect(() => {
        const t = window.setTimeout(() => setDebounced(query), 300);
        return () => window.clearTimeout(t);
    }, [query]);

    const detail = useEvidenceDetail(focus, { query: { enabled: Boolean(focus && focus.startsWith('EV-')) } });
    const nodeEvidence = useEvidenceForNode(focus, { query: { enabled: Boolean(focus && !focus.startsWith('EV-')) } });
    const search = useEvidenceSearch({ q: debounced, limit: 25 }, { query: { enabled: debounced.length >= 2 } });

    return (
        <PageShell>
            <SectionHeading
                eyebrow="Provenance"
                title="Evidence register"
                description="Every graph conclusion traces back to these source records. Records carry source type, id, excerpt, hash and provenance flags."
            />
            <Panel title="Search evidence">
                <div className="flex items-center gap-2 p-4">
                    <FileSearch size={14} className="text-muted-foreground" />
                    <input
                        data-testid="input-evidence-search"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder='Try "called", "transferred", a record id…'
                        className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-xs outline-none focus:border-primary"
                    />
                </div>
            </Panel>

            {focus?.startsWith('EV-') && detail.data && (
                <Panel title={`Evidence ${detail.data.evidence_id}`} subtitle={detail.data.source_uri}>
                    <div className="space-y-2 p-4 text-xs">
                        <div className="flex flex-wrap gap-2">
                            <Pill tone="teal">{detail.data.source_type}</Pill>
                            <Pill tone="neutral">{detail.data.source_record_id}</Pill>
                            <Pill tone="neutral">{detail.data.timestamp ?? 'no timestamp'}</Pill>
                            <Pill tone="neutral">{detail.data.provenance}</Pill>
                        </div>
                        <p className="rounded-md bg-muted/60 p-3 leading-5">{detail.data.text_excerpt}</p>
                        <div className="font-mono-ui text-[9px] text-muted-foreground">hash {detail.data.hash?.slice(0, 32)}…</div>
                    </div>
                </Panel>
            )}

            {edge && (
                <Panel title={`Evidence for edge ${edge.slice(0, 18)}…`}>
                    <EdgeEvidence edgeId={edge} />
                </Panel>
            )}

            {search.data && (
                <Panel title={`Search results (${search.data.total})`}>
                    <EvidenceTable items={search.data.items} />
                </Panel>
            )}

            {nodeEvidence.data && (
                <Panel title={`Evidence for node (${nodeEvidence.data.total})`}>
                    <EvidenceTable items={nodeEvidence.data.items} />
                </Panel>
            )}
        </PageShell>
    );
}

function EdgeEvidence({ edgeId }) {
    // Reuse the for-edge endpoint directly.
    const [items, setItems] = useState(null);
    const [error, setError] = useState(null);
    useEffect(() => {
        let cancelled = false;
        request(`/api/evidence/for-edge/${encodeURIComponent(edgeId)}`)
            .then((data) => !cancelled && setItems(data.items))
            .catch((cause) => !cancelled && setError(cause.message));
        return () => {
            cancelled = true;
        };
    }, [edgeId]);
    if (error) return <div className="p-4 text-xs text-destructive">No evidence bound to this edge ({error}).</div>;
    if (!items) return <LoadingRows count={2} />;
    return <EvidenceTable items={items} />;
}

function EvidenceTable({ items }) {
    if (!items?.length) return <EmptyState title="No evidence" description="Nothing matched the current query." icon={FileText} />;
    return (
        <div className="divide-y divide-border/60">
            {items.map((rec) => (
                <div key={rec.evidence_id} className="flex items-start gap-3 px-5 py-3">
                    <Pill tone="teal">{rec.source_type}</Pill>
                    <div className="min-w-0 flex-1">
                        <div className="text-xs leading-5">{rec.text_excerpt}</div>
                        <div className="mt-0.5 font-mono-ui text-[9px] text-muted-foreground">
                            {rec.evidence_id} · {rec.source_record_id} · {rec.timestamp ?? '—'} · {rec.provenance}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}

// ----------------------------------------------------------------- Simulation --
export function SimulationPage() {
    const [location] = useLocation();
    const params = new URLSearchParams(location.split('?')[1] ?? '');
    const [nodeId, setNodeId] = useState(params.get('node') ?? '');
    const [result, setResult] = useState(null);
    const [compareIds, setCompareIds] = useState('');
    const [comparison, setComparison] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (params.get('node') && !nodeId) setNodeId(params.get('node'));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [params]);

    const run = async () => {
        if (!nodeId.trim()) return;
        setBusy(true);
        setError(null);
        try {
            const payload = await runNodeRemovalSimulation({ node_id: nodeId.trim(), depth: 2, include_reranking: true });
            setResult(payload);
        } catch (cause) {
            setError(cause.message);
        } finally {
            setBusy(false);
        }
    };

    const compare = async () => {
        const ids = compareIds.split(',').map((s) => s.trim()).filter(Boolean).slice(0, 5);
        if (!ids.length) return;
        setBusy(true);
        setError(null);
        try {
            const payload = await runScenarioComparison(ids);
            setComparison(payload);
        } catch (cause) {
            setError(cause.message);
        } finally {
            setBusy(false);
        }
    };

    return (
        <PageShell>
            <SectionHeading
                eyebrow="Counterfactual sandbox"
                title="Network disruption simulation"
                description="Simulate node removal and compare hypothetical scenarios. Results are analytical counterfactuals about network structure — explicitly NOT enforcement recommendations and NOT predictions of real behaviour."
                action={<Pill tone="rose">network effect score</Pill>}
            />
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Simulate node removal" subtitle="POST /api/simulation/node-removal">
                    <div className="space-y-3 p-4">
                        <input
                            data-testid="input-simulation-node"
                            value={nodeId}
                            onChange={(e) => setNodeId(e.target.value)}
                            placeholder="Node guid…"
                            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono-ui text-xs outline-none focus:border-primary"
                        />
                        <button onClick={run} disabled={busy || !nodeId.trim()} data-testid="button-run-simulation" className="flex items-center gap-2 rounded-md bg-chart-4/15 px-4 py-2 text-xs font-semibold text-chart-4 disabled:opacity-40">
                            <Zap size={14} /> {busy ? 'Running…' : 'Run counterfactual'}
                        </button>
                        {error && <div className="rounded-md bg-destructive/10 p-2 text-xs text-destructive">{error}</div>}
                    </div>
                </Panel>
                <Panel title="Scenario comparison" subtitle="Up to 5 nodes, comma separated (Phase M)">
                    <div className="space-y-3 p-4">
                        <input
                            value={compareIds}
                            onChange={(e) => setCompareIds(e.target.value)}
                            placeholder="guid-1, guid-2, guid-3"
                            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono-ui text-xs outline-none focus:border-primary"
                        />
                        <button onClick={compare} disabled={busy || !compareIds.trim()} className="rounded-md border border-border px-4 py-2 text-xs hover:border-primary/60">
                            Compare scenarios
                        </button>
                    </div>
                </Panel>
            </div>

            {result && (
                <Panel title={`Simulation ${result.simulation_id}`} subtitle={`Removed: ${result.target_name || result.target_node_id} · depth ${result.depth}`}>
                    <div className="space-y-4 p-4">
                        <div className="grid gap-3 sm:grid-cols-4">
                            <Metric label="Fragmentation" value={num(result.fragmentation_score)} />
                            <Metric label="Connectivity loss" value={num(result.connectivity_change)} />
                            <Metric label="GCC loss" value={result.delta?.gcc_size_loss ?? '—'} />
                            <Metric label="Rerouting score" value={num(result.rerouting_score)} />
                        </div>
                        <div className="grid gap-3 text-xs sm:grid-cols-3">
                            <div className="rounded-md border border-border p-3">
                                <div className="mb-1 font-mono-ui text-[9px] uppercase text-muted-foreground">community changes</div>
                                <div>{result.community_changes?.num_communities_before} → {result.community_changes?.num_communities_after} communities</div>
                                <div className="text-muted-foreground">NMI {num(result.community_changes?.nmi_vs_baseline)} · {result.community_changes?.split_baseline_communities?.length ?? 0} split</div>
                            </div>
                            <div className="rounded-md border border-border p-3">
                                <div className="mb-1 font-mono-ui text-[9px] uppercase text-muted-foreground">new brokers</div>
                                {(result.new_brokers ?? []).slice(0, 4).map((b) => (
                                    <div key={b.guid} className="flex items-center justify-between gap-2">
                                        <span className="truncate">{b.name}</span>
                                        <span className="font-mono-ui text-[10px] text-chart-3">+{num(b.betweenness_gain)}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="rounded-md border border-border p-3">
                                <div className="mb-1 font-mono-ui text-[9px] uppercase text-muted-foreground">alternate paths</div>
                                {(result.alternate_paths ?? []).slice(0, 3).map((p, i) => (
                                    <div key={i} className="truncate text-muted-foreground">
                                        {p.source.slice(0, 8)}… → {p.target.slice(0, 8)}… ({p.length} hops)
                                    </div>
                                ))}
                                {!result.alternate_paths?.length && <div className="text-muted-foreground">None found.</div>}
                            </div>
                        </div>
                        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-[11px] leading-5 text-amber-200/90">
                            <div className="mb-1 flex items-center gap-2 font-semibold"><FlaskConical size={13} /> SIMULATED OUTCOME — {result.disclaimer}</div>
                            {(result.warnings ?? []).map((w, i) => <div key={i}>• {w}</div>)}
                        </div>
                    </div>
                </Panel>
            )}

            {comparison && (
                <Panel title="Scenario comparison" subtitle={comparison.ranking_note}>
                    <div className="divide-y divide-border/60">
                        {comparison.scenarios?.map((s) => (
                            <div key={s.node_id} className="flex flex-wrap items-center gap-4 px-5 py-3 text-xs">
                                {s.error ? (
                                    <span className="text-destructive">{s.node_id}: {s.error}</span>
                                ) : (
                                    <>
                                        <Pill tone="teal">rank {s.network_effect_rank}</Pill>
                                        <span className="font-mono-ui text-[10px]">{s.node_id.slice(0, 14)}…</span>
                                        <span>fragmentation {num(s.fragmentation_score)}</span>
                                        <span>connectivity loss {num(s.connectivity_change)}</span>
                                        <span>{s.affected_node_count} affected</span>
                                    </>
                                )}
                            </div>
                        ))}
                    </div>
                </Panel>
            )}
        </PageShell>
    );
}

// --------------------------------------------------------------------- Search --
export function SearchPage() {
    const [query, setQuery] = useState('');
    const [debounced, setDebounced] = useState('');
    const [, navigate] = useLocation();
    useEffect(() => {
        const t = window.setTimeout(() => setDebounced(query), 300);
        return () => window.clearTimeout(t);
    }, [query]);
    const search = useGlobalSearch({ q: debounced, limit: 40 }, { query: { enabled: debounced.length >= 2 } });

    return (
        <PageShell>
            <SectionHeading eyebrow="Global search" title="Find anything" description="Persons, organizations, phones, accounts, locations, documents, evidence ids and ghost candidates — one query." />
            <Panel>
                <div className="flex items-center gap-2 p-4">
                    <ShieldQuestion size={14} className="text-muted-foreground" />
                    <input
                        data-testid="input-global-search-page"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Name, id, ghost, evidence…"
                        className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-xs outline-none focus:border-primary"
                    />
                </div>
            </Panel>
            <Panel title={`Results ${search.data ? `(${search.data.total})` : ''}`}>
                {search.isFetching && <LoadingRows count={3} />}
                {search.data && search.data.total === 0 && <EmptyState title="No results" description="Nothing matched this query." />}
                <div className="divide-y divide-border/60">
                    {(search.data?.items ?? []).map((item) => (
                        <button
                            key={`${item.result_type}-${item.id}`}
                            onClick={() => {
                                if (item.result_type === 'evidence') navigate(`/evidence?focus=${encodeURIComponent(item.id)}`);
                                else if (item.result_type === 'ghost') navigate(`/ghosts?focus=${encodeURIComponent(item.id)}`);
                                else navigate(`/explorer?focus=${encodeURIComponent(item.id)}`);
                            }}
                            className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-muted"
                        >
                            <Pill tone={item.result_type === 'ghost' ? 'amber' : item.result_type === 'evidence' ? 'teal' : 'neutral'}>{item.result_type}</Pill>
                            <div className="min-w-0 flex-1">
                                <div className="truncate text-xs font-semibold">{item.display_name || item.id}</div>
                                <div className="truncate font-mono-ui text-[9px] text-muted-foreground">
                                    {item.entity_type}{item.confidence !== undefined ? ` · confidence ${item.confidence}` : ''}{item.excerpt ? ` · ${item.excerpt}` : ''}
                                </div>
                            </div>
                            <span className="font-mono-ui text-[9px] uppercase text-primary">{item.quick_action}</span>
                        </button>
                    ))}
                </div>
            </Panel>
        </PageShell>
    );
}

function Metric({ label, value }) {
    return (
        <div className="rounded-md border border-card-border bg-muted/40 p-3">
            <div className="font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className="mt-1 font-mono-ui text-lg font-semibold">{value}</div>
        </div>
    );
}

function num(value) {
    const n = Number(value);
    if (value === null || value === undefined || Number.isNaN(n)) return '—';
    return n.toFixed(3);
}
