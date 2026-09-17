import React, { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { useGetGraphOverview, useGetGhosts, useListJobs } from '@/api/graph';
import { useFindings } from '@/api/xai';
import { useCases } from '@/api/xai';
import { useCaseBrief } from '@/api/intel';
import { useInvestigation } from '@/state/investigation-context';
import {
    Users, Network as NetworkIcon, Clock, FileText, Brain, AlertTriangle,
    ArrowRight, ChevronRight, Activity, FolderOpen, Play, GitCompare,
    Loader2
} from 'lucide-react';
import { formatNumber, formatTimestamp } from '@/components/app-shell';
import {
    PageHeader, StatusLabel, CompactMetric, NoticeBanner, DataGrid,
    LoadingState, EmptyState, ErrorState, SectionHeader, Tag
} from '@/components/ui';

/* ── Compact operational metric ── */
function OpMetric({ label, value, subtext, onClick }) {
    return (
        <button
            onClick={onClick}
            className="flex flex-col items-start px-4 py-2.5 border-r border-border-subtle last:border-r-0 hover:bg-[hsl(220,10%,10%)] transition-colors text-left cursor-pointer group"
        >
            <span className="text-[10px] text-fg-faint uppercase tracking-wide">{label}</span>
            <span className="text-[20px] font-semibold text-fg-primary font-mono leading-tight group-hover:text-primary transition-colors">
                {value ?? '—'}
            </span>
            {subtext && <span className="text-[10px] text-fg-muted">{subtext}</span>}
        </button>
    );
}

export default function InvestigationDesk() {
    const { activeCase } = useInvestigation();
    const { data: overview, isLoading: overviewLoading } = useGetGraphOverview();
    const { data: ghostsData } = useGetGhosts();
    const { data: findingsData } = useFindings();
    const { data: casesData } = useCases();
    const { data: briefData } = useCaseBrief(activeCase?.id);
    const { data: pipelineData } = useListJobs();

    const ghosts = ghostsData?.ghosts || ghostsData?.results || ghostsData?.items || [];
    const findings = findingsData?.findings || findingsData?.results || findingsData?.items || [];
    const cases = casesData?.results || casesData?.items || casesData || [];
    const jobs = Array.isArray(pipelineData) ? pipelineData : (pipelineData?.jobs || pipelineData?.results || []);

    /* Review queue — findings and hypotheses that need attention */
    const reviewQueue = useMemo(() => {
        const fromFindings = (findings || [])
            .filter(f => f.review_state === 'OPEN' || f.status === 'HYPOTHESIS' || f.review_state === 'PENDING')
            .slice(0, 5)
            .map(f => ({
                kind: 'Finding',
                subject: f.description || f.title || f.subject || f.finding_type || 'Finding',
                id: f.finding_id || f.id,
                state: f.status || 'HYPOTHESIS',
                updated: f.updated_at,
            }));
        const fromGhosts = (ghosts || [])
            .filter(g => g.review_status === 'OPEN' || g.review_status === 'PENDING' || !g.review_status)
            .slice(0, 4)
            .map(g => ({
                kind: 'Hypothesis',
                subject: g.label || g.title || g.description || `Ghost ${g.ghost_id || g.id || ''}`,
                id: g.ghost_id || g.id,
                state: 'HYPOTHESIS',
                updated: g.updated_at,
            }));
        return [...fromFindings, ...fromGhosts].slice(0, 8);
    }, [findings, ghosts]);

    const activeJobs = (jobs || []).filter(j => j.status === 'RUNNING' || j.status === 'running').length;

    return (
        <div className="min-h-full">
            {/* ── CONTEXT HEADER ── */}
            <PageHeader
                title="Command center"
                subtitle="Operational overview of the current investigation workspace"
                breadcrumbs={[{ label: 'Overview' }]}
                metadata={
                    <div className="flex items-center gap-2 mt-1.5">
                        <NoticeBanner variant="draft" className="!px-2 !py-1 text-[11px]">
                            Working file · not an official legal record
                        </NoticeBanner>
                    </div>
                }
                actions={
                    <Link href="/cases" className="inline-flex items-center gap-1.5 h-7 px-3 text-[12px] font-medium rounded-sm bg-primary text-primary-fg hover:bg-primary-hover transition-colors cursor-pointer">
                        <FolderOpen size={13} /> Manage cases
                    </Link>
                }
            />

            {/* ── OPERATIONAL STRIP ── */}
            <div className="flex divide-x divide-border-subtle border-b border-border-subtle bg-bg-surface">
                <OpMetric
                    label="Active cases"
                    value={Array.isArray(cases) ? cases.length : null}
                    subtext="Working files"
                    onClick={() => window.location.hash = '#/cases'}
                />
                <OpMetric
                    label="Findings"
                    value={Array.isArray(findings) ? findings.length : null}
                    subtext={`${reviewQueue.filter(r => r.kind === 'Finding').length} to review`}
                    onClick={() => window.location.hash = '#/findings'}
                />
                <OpMetric
                    label="Hypotheses"
                    value={Array.isArray(ghosts) ? ghosts.length : null}
                    subtext={`${reviewQueue.filter(r => r.kind === 'Hypothesis').length} open`}
                    onClick={() => window.location.hash = '#/ghosts'}
                />
                <OpMetric
                    label="Network"
                    value={overview ? formatNumber(overview.entities_count ?? overview.nodeCount) : null}
                    subtext={overview ? `${formatNumber(overview.triplets_count ?? overview.edgeCount)} relationships` : undefined}
                    onClick={() => window.location.hash = '#/network'}
                />
                <OpMetric
                    label="Evidence"
                    value={overview ? formatNumber(overview.evidence_count ?? overview.evidence_records) : null}
                    subtext={overview?.source_types ? `${overview.source_types} source types` : undefined}
                    onClick={() => window.location.hash = '#/evidence'}
                />
                <OpMetric
                    label="Pipeline"
                    value={activeJobs > 0 ? `${activeJobs} running` : 'Idle'}
                    subtext={jobs.length ? `${jobs.length} recent jobs` : 'No jobs'}
                    onClick={() => window.location.hash = '#/pipeline'}
                />
            </div>

            <div className="p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* ── REVIEW QUEUE (primary) ── */}
                <div className="lg:col-span-2">
                    <SectionHeader
                        label="Review queue"
                        action={<Link href="/findings" className="text-[11px] text-primary hover:text-primary-hover flex items-center gap-0.5 cursor-pointer">
                            View all <ArrowRight size={11} />
                        </Link>}
                    />
                    {overviewLoading ? (
                        <LoadingState message="Loading review queue…" />
                    ) : reviewQueue.length === 0 ? (
                        <EmptyState
                            title="Nothing awaiting review"
                            description="No open findings or hypotheses require attention."
                        />
                    ) : (
                        <div className="border border-border-default rounded-sm overflow-hidden">
                            <DataGrid
                                compact
                                columns={[
                                    { key: 'kind', label: 'Type', width: 90, render: r => <span className="text-fg-muted text-[11px]">{r.kind}</span> },
                                    { key: 'subject', label: 'Subject', render: r => (
                                        <span className="text-fg-primary truncate block">{r.subject}</span>
                                    )},
                                    { key: 'id', label: 'ID', width: 90, mono: true, render: r => <span className="text-fg-faint">{r.id}</span> },
                                    { key: 'state', label: 'State', width: 100, render: r => <StatusLabel status={r.state} /> },
                                    { key: 'updated', label: 'Updated', width: 100, render: r => <span className="text-fg-faint text-[11px]">{formatTimestamp(r.updated)}</span> },
                                ]}
                                rows={reviewQueue}
                                onRowClick={r => window.location.hash = `#/${r.kind === 'Finding' ? 'findings' : 'ghosts'}/${r.id}`}
                                emptyMessage="No items awaiting review"
                            />
                        </div>
                    )}

                    {/* ── ACTIVE CASES ── */}
                    <div className="mt-6">
                        <SectionHeader
                            label="Cases"
                            action={<Link href="/cases" className="text-[11px] text-primary hover:text-primary-hover flex items-center gap-0.5 cursor-pointer">
                                View all <ArrowRight size={11} />
                            </Link>}
                        />
                        {Array.isArray(cases) && cases.length > 0 ? (
                            <div className="border border-border-default rounded-sm overflow-hidden">
                                <DataGrid
                                    compact
                                    columns={[
                                        { key: 'case_id', label: 'Case ID', width: 110, mono: true, render: r => <span className="text-fg-primary font-mono">{r.case_id || r.id}</span> },
                                        { key: 'title', label: 'Title', render: r => <span className="text-fg-primary truncate block">{r.title || 'Untitled'}</span> },
                                        { key: 'status', label: 'Status', width: 100, render: r => <StatusLabel status={r.status} /> },
                                        { key: 'updated', label: 'Updated', width: 100, render: r => <span className="text-fg-faint text-[11px]">{formatTimestamp(r.updated_at || r.created_at)}</span> },
                                    ]}
                                    rows={cases.slice(0, 6)}
                                    onRowClick={r => window.location.hash = `#/cases/${r.case_id || r.id}`}
                                />
                            </div>
                        ) : (
                            <EmptyState
                                title="No cases yet"
                                description="Case workspaces are local working files used to group analytical objects."
                                action={<Link href="/cases" className="inline-flex items-center gap-1.5 h-7 px-3 text-[12px] font-medium rounded-sm bg-primary text-primary-fg hover:bg-primary-hover cursor-pointer">
                                    <FolderOpen size={13} /> Open cases
                                </Link>}
                            />
                        )}
                    </div>
                </div>

                {/* ── SECONDARY: SYSTEM STATE ── */}
                <div className="space-y-6">
                    {/* Pipeline status */}
                    <div>
                        <SectionHeader label="Pipeline" />
                        {Array.isArray(jobs) && jobs.length > 0 ? (
                            <div className="border border-border-default rounded-sm divide-y divide-border-subtle">
                                {jobs.slice(0, 4).map((j, i) => (
                                    <Link key={j.job_id || i} href="/pipeline" className="flex items-center justify-between px-3 py-2 hover:bg-[hsl(220,10%,10%)] transition-colors cursor-pointer">
                                        <div className="min-w-0">
                                            <div className="text-[12px] text-fg-primary truncate">{j.stage || j.name || `Job ${j.job_id || i}`}</div>
                                            <div className="text-[10px] text-fg-faint">{j.started_at ? formatTimestamp(j.started_at) : ''}</div>
                                        </div>
                                        <StatusLabel status={j.status} />
                                    </Link>
                                ))}
                            </div>
                        ) : (
                            <EmptyState title="No pipeline jobs" description="Run the pipeline to populate graph, ghosts, and findings." />
                        )}
                    </div>

                    {/* Case brief context */}
                    {briefData && (
                        <div>
                            <SectionHeader label="Case brief" />
                            <div className="border border-border-default rounded-sm p-3 space-y-2">
                                {briefData.summary && <p className="text-[12px] text-fg-secondary leading-relaxed">{briefData.summary}</p>}
                                <div className="flex flex-wrap gap-1.5 pt-1">
                                    {(briefData.focus_areas || []).slice(0, 5).map((f, i) => (
                                        <Tag key={i}>{f}</Tag>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* System notices */}
                    {(findings || []).some(f => f.counter_evidence?.length) && (
                        <NoticeBanner variant="warning" title="Counter-evidence present">
                            Some findings include contradicting evidence records. Review before use.
                        </NoticeBanner>
                    )}
                </div>
            </div>
        </div>
    );
}