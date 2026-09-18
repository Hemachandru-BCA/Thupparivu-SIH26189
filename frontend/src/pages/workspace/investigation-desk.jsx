/**
 * investigation-desk.jsx  (REDESIGNED)
 * Primary investigation workspace — case-centric, NOT a KPI dashboard.
 * Shows: case context, workflow navigation, findings queue, anomaly queue, graph state.
 */

import React from "react";
import { Link, useLocation } from "wouter";
import { useGetGraphOverview, useGetGhosts, useListJobs } from "@/api/graph";
import { useFindings, useCases } from "@/api/xai";
import { useCaseBrief } from "@/api/intel";
import { useInvestigation } from "@/state/investigation-context";
import {
    Users, Network as NetworkIcon, Clock, FileText, Brain, AlertTriangle,
    ArrowRight, ChevronRight, FolderOpen, Loader2,
    DollarSign, Layers, BookOpen, Zap, MessageSquare, CornerDownRight
} from "lucide-react";
import { formatNumber } from "@/utils/format";

function WorkflowCard({ label, description, href, icon: Icon, count = null, status = null }) {
    const leftCls = { active: "border-l-primary", warning: "border-l-amber", empty: "border-l-border-strong" }[status] || "border-l-border-strong";
    return (
        <Link href={href}>
            <div className={`flex items-center gap-3 px-3 py-2 border-b border-border-subtle hover:bg-bg-hover transition-colors cursor-pointer group border-l-2 ${leftCls}`}>
                <Icon size={13} className="shrink-0 text-fg-faint group-hover:text-primary transition-colors" />
                <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-medium text-fg-primary leading-tight">{label}</div>
                    <div className="text-[10px] text-fg-muted truncate">{description}</div>
                </div>
                {count != null && <span className="text-[11px] font-mono text-fg-faint shrink-0">{count}</span>}
                <ArrowRight size={11} className="text-fg-faint group-hover:text-fg-secondary shrink-0 transition-colors" />
            </div>
        </Link>
    );
}

function StatusRow({ label, value, color = "text-fg-primary" }) {
    return (
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-border-subtle last:border-b-0">
            <span className="text-[10px] text-fg-faint uppercase tracking-wide">{label}</span>
            <span className={`text-[12px] font-mono font-semibold ${color}`}>{value ?? "—"}</span>
        </div>
    );
}

function FindingRow({ finding, onClick }) {
    const conf = finding.confidence || 0;
    const confColor = conf >= 0.8 ? "text-green" : conf >= 0.6 ? "text-blue" : conf >= 0.4 ? "text-amber" : "text-red";
    return (
        <button onClick={onClick} className="w-full text-left flex items-start gap-3 px-3 py-1.5 border-b border-border-subtle hover:bg-bg-hover transition-colors cursor-pointer group">
            <span className={`text-[10px] font-mono shrink-0 pt-0.5 ${confColor}`}>{(conf * 100).toFixed(0)}%</span>
            <div className="flex-1 min-w-0">
                <div className="text-[11px] text-fg-primary truncate">{finding.subject_label || finding.subject_id}</div>
                <div className="text-[10px] text-fg-muted truncate">{finding.finding_type || "Finding"}</div>
            </div>
            <ChevronRight size={11} className="text-fg-faint group-hover:text-fg-secondary shrink-0 mt-0.5 transition-colors" />
        </button>
    );
}

function GhostRow({ ghost, onClick }) {
    const conf = ghost.confidence || 0;
    return (
        <button onClick={onClick} className="w-full text-left flex items-start gap-3 px-3 py-1.5 border-b border-border-subtle hover:bg-bg-hover transition-colors cursor-pointer group">
            <AlertTriangle size={12} className="text-amber shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
                <div className="text-[11px] text-fg-primary truncate">{ghost.label || ghost.ghost_id}</div>
                <div className="text-[10px] text-fg-muted truncate">{ghost.subtype || "Anomalous entity"}</div>
            </div>
            <span className="text-[10px] font-mono text-amber shrink-0">{(conf * 100).toFixed(0)}%</span>
        </button>
    );
}

function SectionHead({ label, href, count }) {
    return (
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-border-default bg-bg-surface shrink-0">
            <span className="text-[10px] font-semibold text-fg-faint uppercase tracking-widest">{label}</span>
            <div className="flex items-center gap-2">
                {count != null && <span className="text-[10px] font-mono text-fg-faint">{count}</span>}
                {href && <Link href={href}><span className="text-[10px] text-primary hover:underline cursor-pointer">All</span></Link>}
            </div>
        </div>
    );
}

function ActionLink({ href, icon: Icon, label }) {
    return (
        <Link href={href}>
            <div className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-bg-hover transition-colors cursor-pointer group">
                <Icon size={12} className="text-fg-faint group-hover:text-primary shrink-0 transition-colors" />
                <span className="text-[11px] text-fg-muted group-hover:text-fg-primary transition-colors">{label}</span>
                <CornerDownRight size={10} className="text-fg-faint group-hover:text-primary ml-auto shrink-0 transition-colors" />
            </div>
        </Link>
    );
}

export default function InvestigationDesk() {
    const [, navigate] = useLocation();
    const { activeCase, setSelectedHypothesis, setInspectorOpen } = useInvestigation();
    const { data: overview, isLoading: overviewLoading } = useGetGraphOverview();
    const { data: ghostsData } = useGetGhosts();
    const { data: findingsData } = useFindings();
    const { data: casesData } = useCases();
    const { data: briefData } = useCaseBrief(activeCase?.id);
    const { data: pipelineData } = useListJobs();

    const ghosts = ghostsData?.results || ghostsData?.items || ghostsData || [];
    const findings = findingsData?.results || findingsData?.items || findingsData || [];
    const cases = casesData?.results || casesData?.items || casesData || [];
    const brief = briefData?.result || briefData;
    const jobs = pipelineData?.results || pipelineData?.items || pipelineData || [];

    const highGhosts = ghosts.filter(g => (g.confidence || 0) >= 0.7);
    const pendingJobs = jobs.filter(j => j.status === "running" || j.status === "pending");
    const recentFindings = findings.slice(0, 8);
    const topGhosts = highGhosts.slice(0, 6);

    return (
        <div className="h-full flex overflow-hidden animate-fade-in bg-bg-root">
            <div className="w-64 border-r border-border-default flex flex-col bg-bg-surface shrink-0 overflow-y-auto">
                <div className="px-3 py-3 border-b border-border-default shrink-0">
                    {activeCase ? (
                        <>
                            <div className="flex items-center gap-2 mb-1">
                                <FolderOpen size={11} className="text-primary shrink-0" />
                                <span className="text-[10px] font-mono text-primary font-semibold">{activeCase.id}</span>
                                <span className="text-[9px] px-1.5 py-0.5 rounded border border-green/40 text-green bg-green-bg font-mono ml-auto">{activeCase.status}</span>
                            </div>
                            <div className="text-[12px] text-fg-primary font-medium leading-snug">{activeCase.title}</div>
                            <div className="mt-0.5 text-[10px] text-fg-muted">{activeCase.jurisdiction}</div>
                            {activeCase.classification && (
                                <div className="mt-1.5 text-[9px] font-mono text-amber bg-amber-bg border border-amber/30 px-1.5 py-0.5 rounded inline-block">
                                    {activeCase.classification}
                                </div>
                            )}
                        </>
                    ) : (
                        <Link href="/cases"><div className="flex items-center gap-2 text-[11px] text-primary hover:underline cursor-pointer"><FolderOpen size={12} /><span>Open a case to begin</span></div></Link>
                    )}
                </div>
                <SectionHead label="Investigate" />
                <WorkflowCard label="Search entities" description="Persons, orgs, accounts, locations" href="/entities" icon={Users} count={formatNumber(overview?.nodeCount ?? overview?.totalNodes)} status={overview ? "active" : "empty"} />
                <WorkflowCard label="Network graph" description="Relationships and connections" href="/network" icon={NetworkIcon} status="active" />
                <WorkflowCard label="Timeline" description="Chronological event analysis" href="/timeline" icon={Clock} status="active" />
                <WorkflowCard label="Evidence" description="Source records and documents" href="/evidence" icon={FileText} status="active" />
                <SectionHead label="Intelligence" />
                <WorkflowCard label="Findings" description="Detected patterns and assessments" href="/findings" icon={Brain} count={findings.length || null} status={findings.length > 0 ? "active" : "empty"} />
                <WorkflowCard label="Anomalies" description="Suspicious entities for review" href="/ghosts" icon={AlertTriangle} count={highGhosts.length > 0 ? highGhosts.length : null} status={highGhosts.length > 0 ? "warning" : "empty"} />
                <WorkflowCard label="Financial flows" description="Account transfers and fund tracing" href="/financial" icon={DollarSign} status="active" />
                <WorkflowCard label="Communities" description="Clusters and group analysis" href="/communities" icon={Layers} status="active" />
                <SectionHead label="Output" />
                <WorkflowCard label="Dossiers" description="Case reports and packages" href="/dossiers" icon={BookOpen} status="active" />
                <WorkflowCard label="Simulation" description="Counterfactual analysis" href="/simulation" icon={Zap} status="active" />
                <WorkflowCard label="Assistant" description="Context-aware queries" href="/copilot" icon={MessageSquare} status="active" />
            </div>

            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                <div className="px-4 py-3 border-b border-border-default bg-bg-surface shrink-0">
                    <div className="text-[10px] font-semibold text-fg-faint uppercase tracking-widest mb-1.5">Case Brief</div>
                    {brief?.summary ? (
                        <p className="text-[12px] text-fg-secondary leading-relaxed max-w-2xl">{brief.summary}</p>
                    ) : overviewLoading ? (
                        <div className="flex items-center gap-2 text-[11px] text-fg-faint"><Loader2 size={12} className="animate-spin" /><span>Loading...</span></div>
                    ) : (
                        <p className="text-[12px] text-fg-muted italic">No case brief available. Begin by searching for entities.</p>
                    )}
                </div>
                <div className="flex flex-1 overflow-hidden">
                    <div className="flex-1 overflow-y-auto">
                        <div className="border-b border-border-default">
                            <SectionHead label="Graph state" href="/network" />
                            {overviewLoading ? (
                                <div className="flex items-center gap-2 p-3 text-[11px] text-fg-faint"><Loader2 size={12} className="animate-spin" /><span>Loading...</span></div>
                            ) : overview ? (
                                <div className="divide-y divide-border-subtle">
                                    <StatusRow label="Entities (nodes)" value={formatNumber(overview.nodeCount ?? overview.totalNodes)} />
                                    <StatusRow label="Relationships (edges)" value={formatNumber(overview.edgeCount ?? overview.totalEdges)} color="text-fg-secondary" />
                                    <StatusRow label="Findings" value={findings.length || "—"} color={findings.length > 0 ? "text-blue" : "text-fg-muted"} />
                                    <StatusRow label="High-confidence anomalies" value={highGhosts.length || "None"} color={highGhosts.length > 0 ? "text-amber" : "text-fg-muted"} />
                                    {pendingJobs.length > 0 && <StatusRow label="Pipeline jobs running" value={pendingJobs.length} color="text-blue" />}
                                </div>
                            ) : (
                                <div className="px-3 py-3 text-[11px] text-fg-muted italic">Graph data unavailable — check API connection.</div>
                            )}
                        </div>
                        {overview?.entityCounts && Object.keys(overview.entityCounts).length > 0 && (
                            <div className="border-b border-border-default">
                                <SectionHead label="Entity types" href="/entities" />
                                {Object.entries(overview.entityCounts).sort(([,a],[,b]) => b - a).slice(0, 10).map(([type, count]) => (
                                    <Link key={type} href={`/entities?type=${type}`}>
                                        <div className="flex items-center justify-between px-3 py-1.5 hover:bg-bg-hover cursor-pointer border-b border-border-subtle last:border-b-0">
                                            <span className="text-[11px] text-fg-secondary font-mono">{type}</span>
                                            <span className="text-[11px] font-mono text-fg-muted">{count}</span>
                                        </div>
                                    </Link>
                                ))}
                            </div>
                        )}
                        {cases.length > 0 && (
                            <div>
                                <SectionHead label="Cases" href="/cases" count={cases.length} />
                                {cases.slice(0, 5).map(c => (
                                    <Link key={c.id || c.case_id} href="/cases">
                                        <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-hover cursor-pointer border-b border-border-subtle last:border-b-0">
                                            <FolderOpen size={11} className="text-fg-faint shrink-0" />
                                            <span className="text-[11px] text-fg-primary truncate flex-1">{c.title || c.case_id || c.id}</span>
                                            <span className={`text-[9px] font-mono px-1 rounded border shrink-0 ${(c.status||"ACTIVE")==="ACTIVE" ? "text-green border-green/40 bg-green-bg" : "text-fg-muted border-border-subtle"}`}>{c.status || "ACTIVE"}</span>
                                        </div>
                                    </Link>
                                ))}
                            </div>
                        )}
                    </div>
                    <div className="w-px bg-border-default shrink-0" />
                    <div className="w-64 flex flex-col overflow-hidden shrink-0">
                        <div className="flex-1 overflow-y-auto border-b border-border-default">
                            <SectionHead label="Recent findings" href="/findings" count={findings.length || null} />
                            {recentFindings.length > 0 ? recentFindings.map(f => (
                                <FindingRow key={f.finding_id || f.id} finding={f} onClick={() => navigate(`/findings/${f.finding_id || f.id}`)} />
                            )) : <div className="px-3 py-4 text-[11px] text-fg-faint italic text-center">No findings</div>}
                        </div>
                        <div className="flex-1 overflow-y-auto">
                            <SectionHead label="Anomaly queue" href="/ghosts" count={topGhosts.length || null} />
                            {topGhosts.length > 0 ? topGhosts.map(g => (
                                <GhostRow key={g.ghost_id || g.id} ghost={g} onClick={() => { setSelectedHypothesis(g); setInspectorOpen(true); }} />
                            )) : <div className="px-3 py-4 text-[11px] text-fg-faint italic text-center">No high-priority anomalies</div>}
                        </div>
                    </div>
                </div>
            </div>

            <div className="w-52 border-l border-border-default flex flex-col bg-bg-surface shrink-0 overflow-y-auto">
                <div className="px-3 py-2 border-b border-border-default shrink-0">
                    <span className="text-[10px] font-semibold text-fg-faint uppercase tracking-widest">Start here</span>
                </div>
                <div className="p-2 space-y-0.5">
                    <ActionLink href="/entities" icon={Users} label="Search for an entity" />
                    <ActionLink href="/network" icon={NetworkIcon} label="Open network graph" />
                    <ActionLink href="/ghosts" icon={AlertTriangle} label="Review anomalies" />
                    <ActionLink href="/findings" icon={Brain} label="Inspect findings" />
                    <ActionLink href="/timeline" icon={Clock} label="Explore timeline" />
                    <ActionLink href="/evidence" icon={FileText} label="Search evidence" />
                    <ActionLink href="/financial" icon={DollarSign} label="Trace financial flows" />
                    <ActionLink href="/dossiers" icon={BookOpen} label="Generate dossier" />
                    <ActionLink href="/simulation" icon={Zap} label="Run simulation" />
                    <ActionLink href="/copilot" icon={MessageSquare} label="Ask the assistant" />
                </div>
                <div className="px-3 py-2 border-t border-border-default mt-auto">
                    <p className="text-[9px] text-fg-faint leading-relaxed">
                        Press <kbd className="font-mono bg-bg-elevated px-1 rounded">⌘K</kbd> or <kbd className="font-mono bg-bg-elevated px-1 rounded">/</kbd> to search
                    </p>
                </div>
            </div>
        </div>
    );
}
