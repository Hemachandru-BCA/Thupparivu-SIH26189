import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'wouter';
import {
    Network, Users, Clock, FileText, Brain,
    AlertTriangle, Zap, DollarSign, FolderOpen,
    BookOpen, Settings, ChevronLeft,
    ChevronRight, Search, MessageSquare,
    LayoutGrid, Layers, Target, Scale,
    BarChart3, Focus, Waypoints, Activity, Database, Shield, UserCheck
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { CommandPalette } from '@/components/command-palette';
import { useGetGraphOverview, useHealthCheck } from '@/api/graph';
export { formatNumber, formatTimestamp, formatShortDate } from '@/utils/format';

/* ── Navigation sections — exact reference ── */
export const NAV_SECTIONS = [
    { id: 'workspace', label: 'WORKSPACE', items: [
        { path: '/', label: 'Overview', icon: LayoutGrid, title: 'Investigation Overview' },
        { path: '/cases', label: 'Cases', icon: FolderOpen, title: 'All Cases' },
        { path: '/network', label: 'Network Explorer', icon: Network, title: 'Link Analysis & Graph' },
        { path: '/entities', label: 'Search', icon: Users, title: 'Entity Directory & Search' },
    ]},
    { id: 'intelligence', label: 'INTELLIGENCE', items: [
        { path: '/ghosts', label: 'Ghost Hypotheses', icon: AlertTriangle, title: 'Ghost Candidate Review' },
        { path: '/findings', label: 'Findings', icon: Brain, title: 'Analytical Findings' },
        { path: '/financial', label: 'Financial Intelligence', icon: DollarSign, title: 'Fund Flow Tracing' },
    ]},
    { id: 'evidence', label: 'EVIDENCE & ANALYSIS', items: [
        { path: '/evidence', label: 'Evidence', icon: FileText, title: 'Evidence Register' },
        { path: '/timeline', label: 'Timeline', icon: Clock, title: 'Temporal Event Replay' },
        { path: '/simulation', label: 'Counterfactuals', icon: Zap, title: 'Node Removal Scenarios' },
        { path: '/analytics', label: 'Graph Analytics', icon: BarChart3, title: 'Centrality & Topology' },
    ]},
    { id: 'copilot', label: 'COPILOT & OUTPUT', items: [
        { path: '/copilot', label: 'Copilot', icon: MessageSquare, title: 'AI Assistant' },
        { path: '/dossiers', label: 'Dossiers / Reports', icon: BookOpen, title: 'Report Packs' },
    ]},
    { id: 'system', label: 'SYSTEM', items: [
        { path: '/audit', label: 'Activity / Audit', icon: Activity, title: 'System Audit Trail' },
        { path: '/pipeline', label: 'Pipeline', icon: Database, title: 'Ingestion Console' },
        { path: '/settings', label: 'Settings', icon: Settings, title: 'Workstation Settings' },
    ]}
];

export const ALL_NAV_ITEMS = NAV_SECTIONS.flatMap(s => s.items);

const CASE_STATUS_COLORS = {
    ACTIVE: 'text-green border-green/30 bg-green-bg',
    PENDING: 'text-amber border-amber/30 bg-amber-bg',
    CLOSED: 'text-fg-muted border-border-default bg-bg-panel',
};

export function getEntityTypeColor(type) {
    const map = {
        PERSON: 'var(--entity-person)',
        PHONE: 'var(--entity-phone)',
        VEHICLE: 'var(--entity-vehicle)',
        LOCATION: 'var(--entity-location)',
        ORGANIZATION: 'var(--entity-org)',
        ACCOUNT: 'var(--entity-account)',
        DEVICE: 'var(--entity-device)',
        EVENT: 'var(--entity-event)',
    };
    return map[type?.toUpperCase()] || 'var(--primary)';
}

export function getConfidenceColor(conf) {
    if (conf >= 0.85) return 'hsl(var(--green))';
    if (conf >= 0.65) return 'hsl(var(--blue))';
    if (conf >= 0.45) return 'hsl(var(--amber))';
    return 'hsl(var(--red))';
}

/* ── App Shell ── */
export function AppShell({ children }) {
    const [location] = useLocation();
    const { activeCase, setCommandPaletteOpen, selectedEntity } = useInvestigation();
    const [railCollapsed, setRailCollapsed] = useState(() => {
        try { return localStorage.getItem('sg-rail-collapsed') === 'true'; } catch { return false; }
    });
    useEffect(() => {
        try { localStorage.setItem('sg-rail-collapsed', String(railCollapsed)); } catch {}
    }, [railCollapsed]);

    const { data: healthData } = useHealthCheck();
    const { data: overview } = useGetGraphOverview();

    const healthStatus = healthData ? (healthData.ok ? 'ok' : 'degraded') : 'loading';
    const nodeCount = overview?.nodeCount ?? overview?.totalNodes ?? null;

    useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setCommandPaletteOpen(true);
            }
            if (e.key === '/' && e.target === document.body) {
                e.preventDefault();
                setCommandPaletteOpen(true);
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [setCommandPaletteOpen]);

    const currentItem = ALL_NAV_ITEMS.find(item => item.path === location) || ALL_NAV_ITEMS[0];
    const pageTitle = currentItem?.label || 'Investigation Overview';

    return (
        <div className="flex flex-col h-screen w-screen bg-bg-root text-fg-primary overflow-hidden select-none">
            {/* ── TOP BAR ── */}
            <header className="flex items-center h-10 px-4 bg-bg-surface border-b border-border-default shrink-0 justify-between z-30">
                {/* Left: Breadcrumb + Screen Title */}
                <div className="flex items-center gap-3 min-w-0">
                    <div className="flex items-center gap-1.5 text-[11px] font-mono text-fg-muted">
                        <span>Workspace</span>
                        <span>/</span>
                        <span className="text-primary font-semibold">{activeCase?.id || 'CASE-0421'}</span>
                    </div>
                    <div className="w-px h-3.5 bg-border-default" />
                    <h1 className="text-[13px] font-semibold text-fg-primary uppercase font-mono tracking-wide truncate">
                        {pageTitle}
                    </h1>
                </div>

                {/* Center: Global Search Input */}
                <button
                    onClick={() => setCommandPaletteOpen(true)}
                    className="flex items-center gap-2 px-3 py-1 rounded bg-bg-panel border border-border-default text-fg-faint text-[11px] font-mono hover:border-primary/50 hover:text-fg-secondary transition-colors w-72 justify-between cursor-pointer"
                >
                    <div className="flex items-center gap-1.5">
                        <Search size={12} className="text-fg-faint" />
                        <span>Search entities, findings, evidence...</span>
                    </div>
                    <kbd className="px-1 py-0.5 rounded bg-bg-elevated border border-border-subtle text-[9px] font-mono text-fg-muted">⌘K</kbd>
                </button>

                {/* Right: Primary Action + Case Status */}
                <div className="flex items-center gap-3">
                    <Link href="/network">
                        <button className="tp-btn tp-btn-primary flex items-center gap-1.5 text-[11px] py-1 px-2.5 font-mono">
                            <Network size={12} /><span>Open network</span>
                        </button>
                    </Link>
                    <div className="flex items-center gap-1.5 text-[11px] font-mono bg-bg-panel px-2 py-0.5 rounded border border-border-default" title={`API ${healthStatus}`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${healthStatus === 'ok' ? 'bg-green' : 'bg-amber'}`} />
                        <span className="text-fg-muted">{activeCase?.status || 'ACTIVE'}</span>
                    </div>
                </div>
            </header>

            {/* ── MAIN LAYOUT ── */}
            <div className="flex flex-1 overflow-hidden">
                {/* LEFT SIDEBAR */}
                <nav className={`flex flex-col border-r border-border-default bg-bg-surface shrink-0 transition-all duration-150 overflow-y-auto overflow-x-hidden ${railCollapsed ? 'w-12' : 'w-56'}`}>
                    {/* Top Branding */}
                    <div className="p-3 border-b border-border-default shrink-0 bg-bg-panel">
                        <Link href="/" className="flex items-center gap-2 hover:opacity-90 cursor-pointer">
                            <div className="w-6 h-6 rounded bg-primary flex items-center justify-center text-primary-fg font-mono font-bold text-[11px] tracking-tighter shrink-0">SG</div>
                            {!railCollapsed && (
                                <div className="min-w-0">
                                    <div className="text-[12px] font-bold text-fg-primary tracking-tight leading-tight">SentinelGraph AI</div>
                                    <div className="text-[9px] font-mono text-fg-faint uppercase tracking-widest">INVESTIGATIVE WORKBENCH</div>
                                </div>
                            )}
                        </Link>
                    </div>

                    {/* Active Case Header Box */}
                    {!railCollapsed && activeCase && (
                        <div className="p-3 border-b border-border-default bg-bg-root shrink-0 space-y-1">
                            <div className="text-[9px] font-mono text-fg-faint uppercase tracking-wider font-semibold">CURRENT CASE</div>
                            <div className="text-[11px] font-mono font-bold text-primary">{activeCase.id}</div>
                            <div className="text-[11px] font-medium text-fg-primary leading-tight truncate">{activeCase.title}</div>
                        </div>
                    )}

                    {/* Navigation Items */}
                    <div className="flex-1 py-2 space-y-3 overflow-y-auto">
                        {NAV_SECTIONS.map((section) => (
                            <div key={section.id} className="px-2">
                                {!railCollapsed && (
                                    <div className="px-2 mb-1 text-[9px] font-mono text-fg-faint uppercase tracking-widest font-semibold">
                                        {section.label}
                                    </div>
                                )}
                                <div className="space-y-0.5">
                                    {section.items.map((item) => {
                                        const Icon = item.icon;
                                        const isActive = location === item.path;
                                        return (
                                            <Link key={item.path} href={item.path}>
                                                <div
                                                    className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-sm text-[12px] transition-colors cursor-pointer group ${
                                                        isActive
                                                            ? 'bg-primary/15 text-primary font-semibold border-l-2 border-primary'
                                                            : 'text-fg-secondary hover:bg-bg-hover hover:text-fg-primary'
                                                    }`}
                                                    title={railCollapsed ? item.title || item.label : undefined}
                                                >
                                                    <Icon size={14} className={`shrink-0 ${isActive ? 'text-primary' : 'text-fg-faint group-hover:text-fg-secondary'}`} />
                                                    {!railCollapsed && <span className="truncate">{item.label}</span>}
                                                </div>
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Bottom Analyst Profile */}
                    <div className="p-3 border-t border-border-default shrink-0 bg-bg-panel flex items-center justify-between">
                        {!railCollapsed ? (
                            <div className="flex items-center gap-2 min-w-0">
                                <div className="w-6 h-6 rounded-full bg-primary-bg border border-primary/30 flex items-center justify-center text-[10px] font-mono text-primary font-bold shrink-0">AR</div>
                                <div className="min-w-0">
                                    <div className="text-[11px] font-semibold text-fg-primary truncate">A. Rao</div>
                                    <div className="text-[9px] font-mono text-fg-faint truncate">Lead Analyst</div>
                                </div>
                            </div>
                        ) : (
                            <div className="w-6 h-6 rounded-full bg-primary-bg border border-primary/30 flex items-center justify-center text-[10px] font-mono text-primary font-bold mx-auto">AR</div>
                        )}
                        <button
                            onClick={() => setRailCollapsed(!railCollapsed)}
                            className="text-fg-faint hover:text-fg-primary p-1 cursor-pointer"
                            title={railCollapsed ? 'Expand navigation' : 'Collapse navigation'}
                        >
                            {railCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
                        </button>
                    </div>
                </nav>

                {/* CONTENT AREA */}
                <main className="flex-1 overflow-hidden relative bg-bg-root">
                    {children}
                </main>
            </div>

            <CommandPalette />
        </div>
    );
}
