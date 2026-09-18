import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'wouter';
import {
    Network, Users, Clock, FileText, Brain,
    AlertTriangle, Zap, DollarSign, FolderOpen,
    BookOpen, Settings, ChevronLeft,
    ChevronRight, Search, MessageSquare,
    LayoutGrid, Layers, Target, Scale
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { CommandPalette } from '@/components/command-palette';
import { useGetGraphOverview, useHealthCheck } from '@/api/graph';
export { formatNumber, formatTimestamp, formatShortDate } from '@/utils/format';

/* ── Navigation sections — task-oriented ── */
export const NAV_SECTIONS = [
    { id: 'cases', label: 'CASES', items: [
        { path: '/cases', label: 'Cases', icon: FolderOpen, title: 'All cases' },
    ]},
    { id: 'investigate', label: 'INVESTIGATE', items: [
        { path: '/', label: 'Workspace', icon: LayoutGrid, title: 'Investigation workspace' },
        { path: '/entities', label: 'Entities', icon: Users, title: 'Entity directory' },
        { path: '/network', label: 'Network', icon: Network, title: 'Network explorer' },
        { path: '/timeline', label: 'Timeline', icon: Clock, title: 'Evidence timeline' },
    ]},
    { id: 'intelligence', label: 'INTELLIGENCE', items: [
        { path: '/findings', label: 'Findings', icon: Brain, title: 'Analytical findings' },
        { path: '/ghosts', label: 'Anomalies', icon: AlertTriangle, title: 'Anomaly review queue' },
        { path: '/financial', label: 'Financial', icon: DollarSign, title: 'Financial flows' },
        { path: '/communities', label: 'Communities', icon: Layers, title: 'Community structure' },
    ]},
    { id: 'evidence', label: 'EVIDENCE', items: [
        { path: '/evidence', label: 'Evidence', icon: FileText, title: 'Evidence register' },
    ]},
    { id: 'reporting', label: 'REPORTING', items: [
        { path: '/dossiers', label: 'Dossiers', icon: BookOpen, title: 'Report dossiers' },
    ]},
    { id: 'tools', label: 'TOOLS', items: [
        { path: '/simulation', label: 'Simulation', icon: Zap, title: 'Counterfactual sandbox' },
        { path: '/copilot', label: 'Assistant', icon: MessageSquare, title: 'Investigative assistant' },
        { path: '/settings', label: 'Settings', icon: Settings, title: 'Settings' },
    ]},
];
export const ALL_NAV_ITEMS = NAV_SECTIONS.flatMap(s => s.items);
/* Back-compat: flat list used by command palette */
export const NAV_ITEMS = ALL_NAV_ITEMS;

// Entity colors and icons — canonical source is now @/utils/tokens
// Re-exported here for backwards compatibility
export { getEntityColor as getEntityTypeColor, ENTITY_ICONS } from '@/utils/tokens';
/** @deprecated Use getEntityColor from @/utils/tokens */
export { getEntityColor as ENTITY_COLORS_COMPAT } from '@/utils/tokens';

export function getConfidenceColor(conf) {
    if (conf >= 0.85) return 'hsl(var(--green))';
    if (conf >= 0.7) return 'hsl(var(--blue))';
    if (conf >= 0.5) return 'hsl(var(--amber))';
    return 'hsl(var(--red))';
}

import { formatNumber, formatTimestamp, formatShortDate } from '@/utils/format';

/* ── Case status label ── */
const CASE_STATUS_COLORS = {
    ACTIVE: 'text-green border-green/40 bg-green-bg',
    CLOSED: 'text-fg-muted border-border-subtle bg-bg-panel',
    REVIEW: 'text-amber border-amber/40 bg-amber-bg',
    PENDING: 'text-blue border-blue/40 bg-blue-bg',
};

/* ── App Shell ── */
export function AppShell({ children }) {
    const [location] = useLocation();
    const { activeCase, setCommandPaletteOpen, selectedEntity } = useInvestigation();
    const [railCollapsed, setRailCollapsed] = useState(false);
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

    const caseStatusCls = CASE_STATUS_COLORS[activeCase?.status] || CASE_STATUS_COLORS.ACTIVE;

    return (
        <div className="flex flex-col h-screen w-screen bg-bg-root text-fg-primary overflow-hidden select-none">
            {/* ── GLOBAL HEADER — always visible ── */}
            <header className="flex items-center h-9 px-3 bg-bg-surface border-b border-border-default shrink-0 gap-2 z-30">
                {/* App identity */}
                <Link href="/" className="flex items-center gap-1.5 hover:opacity-90 cursor-pointer shrink-0">
                    <div className="w-5 h-5 rounded-sm bg-primary flex items-center justify-center text-primary-fg font-mono font-bold text-[10px] tracking-tighter">SG</div>
                    <span className="text-[12px] font-semibold text-fg-primary hidden sm:inline">SentinelGraph</span>
                </Link>

                <div className="w-px h-4 bg-border-default mx-1" />

                {/* Active case — always visible, links to case detail */}
                {activeCase && (
                    <Link href="/cases" className="flex items-center gap-2 min-w-0 hover:opacity-80 cursor-pointer group">
                        <span className="text-[10px] text-fg-faint shrink-0 hidden md:inline">CASE</span>
                        <span className="font-mono text-[11px] text-primary shrink-0">{activeCase.id}</span>
                        <span className="text-[11px] text-fg-secondary truncate max-w-[240px] hidden lg:inline">
                            {activeCase.title}
                        </span>
                        <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border shrink-0 ${caseStatusCls}`}>
                            {activeCase.status}
                        </span>
                    </Link>
                )}

                {/* Focused entity breadcrumb — shown when something is selected */}
                {selectedEntity && (
                    <>
                        <div className="w-px h-4 bg-border-subtle mx-1 hidden lg:block" />
                        <span className="text-[10px] text-fg-faint hidden lg:inline shrink-0">ENTITY</span>
                        <span className="text-[11px] text-fg-secondary truncate max-w-[180px] hidden lg:inline font-mono">
                            {selectedEntity.name || selectedEntity.id}
                        </span>
                    </>
                )}

                <div className="flex-1" />

                {/* Search */}
                <button
                    onClick={() => setCommandPaletteOpen(true)}
                    className="flex items-center gap-1.5 px-2 py-1 rounded border border-border-subtle text-fg-faint text-[11px] hover:border-border-default hover:text-fg-secondary transition-colors"
                >
                    <Search size={11} />
                    <span className="hidden md:inline">Search</span>
                    <kbd className="hidden lg:inline text-[9px] font-mono text-fg-faint bg-bg-elevated px-1 rounded">⌘K</kbd>
                </button>

                <div className="w-px h-4 bg-border-subtle mx-1" />

                {/* Health indicator */}
                <div className="flex items-center gap-1.5 text-[10px] shrink-0" title={`API ${healthStatus} · ${nodeCount != null ? `${nodeCount} nodes` : '...'}`}>
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                        healthStatus === 'ok' ? 'bg-green' :
                        healthStatus === 'degraded' ? 'bg-amber' : 'bg-fg-faint animate-pulse'
                    }`} />
                    <span className="hidden md:inline text-fg-faint font-mono">
                        {healthStatus === 'ok' ? (nodeCount != null ? `${nodeCount}n` : 'ok') : healthStatus}
                    </span>
                </div>
            </header>

            {/* ── MAIN LAYOUT ── */}
            <div className="flex flex-1 overflow-hidden">
                {/* LEFT NAV RAIL */}
                <nav className={`flex flex-col border-r border-border-default bg-bg-surface shrink-0 transition-all duration-150 overflow-y-auto overflow-x-hidden ${railCollapsed ? 'w-9' : 'w-44'}`}>
                    {NAV_SECTIONS.map((section) => (
                        <div key={section.id} className="py-1">
                            {!railCollapsed && (
                                <div className="px-3 pt-2 pb-0.5 text-[9px] font-semibold text-fg-faint uppercase tracking-widest">{section.label}</div>
                            )}
                            {section.items.map((item) => {
                                const Icon = item.icon;
                                const isActive = location === item.path || (item.path !== '/' && location.startsWith(item.path));
                                return (
                                    <Link key={item.path} href={item.path}>
                                        <div
                                            className={`flex items-center gap-2 mx-1 px-2 py-1.5 rounded-sm text-[12px] transition-colors cursor-pointer group
                                                ${isActive
                                                    ? 'bg-bg-elevated text-fg-primary border-l-2 border-l-primary'
                                                    : 'text-fg-muted hover:text-fg-primary hover:bg-bg-hover border-l-2 border-l-transparent'}`}
                                            title={railCollapsed ? item.title || item.label : undefined}
                                        >
                                            <Icon size={13} className={isActive ? 'text-primary shrink-0' : 'text-fg-faint group-hover:text-fg-secondary shrink-0'} />
                                            {!railCollapsed && <span className="truncate">{item.label}</span>}
                                        </div>
                                    </Link>
                                );
                            })}
                        </div>
                    ))}

                    <div className="flex-1" />

                    {/* Collapse toggle */}
                    <div className="border-t border-border-subtle pb-2">
                        <button
                            onClick={() => setRailCollapsed(c => !c)}
                            className="flex items-center gap-2 mx-1 px-2 py-1.5 rounded-sm text-[11px] text-fg-faint hover:text-fg-secondary transition-colors cursor-pointer w-[calc(100%-8px)] mt-1"
                            title={railCollapsed ? 'Expand navigation' : 'Collapse navigation'}
                        >
                            {railCollapsed ? <ChevronRight size={12} /> : <><ChevronLeft size={12} /><span>Collapse</span></>}
                        </button>
                    </div>
                </nav>

                {/* CONTENT AREA */}
                <main className="flex-1 overflow-hidden relative">
                    {children}
                </main>
            </div>

            <CommandPalette />
        </div>
    );
}
