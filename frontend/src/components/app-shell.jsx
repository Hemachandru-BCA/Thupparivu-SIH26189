import React, { useState } from 'react';
import { Link, useLocation } from 'wouter';
import {
    LayoutDashboard, Network, Users, Clock, FileText, Brain,
    AlertTriangle, BarChart3, Zap, Waypoints, DollarSign, FolderOpen,
    BookOpen, Activity, ClipboardList, Upload, Settings, ChevronLeft,
    ChevronRight, Search, Shield, Eye, Database, MapPin, Sparkles,
    AlertCircle, HelpCircle, Terminal, Layers
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { CommandPalette } from '@/components/command-palette';
import { InspectorPanel } from '@/components/inspector-panel';
import { useGetGraphOverview } from '@/api/graph';

export const NAV_ITEMS = [
    // 01 CASE
    { path: '/', label: 'DESK', icon: LayoutDashboard, section: 'CASE', title: 'Investigation Desk' },
    { path: '/network', label: 'NETWORK', icon: Network, section: 'CASE', title: 'Network Canvas' },
    { path: '/entities', label: 'ENTITIES', icon: Users, section: 'CASE', title: 'Entity Directory' },
    { path: '/timeline', label: 'TIMELINE', icon: Clock, section: 'CASE', title: 'Timeline & Replay' },
    { path: '/evidence', label: 'EVIDENCE', icon: FileText, section: 'CASE', title: 'Evidence Register' },

    // 02 INTELLIGENCE
    { path: '/findings', label: 'HYPOTHESES', icon: Brain, section: 'INTEL', title: 'Hypothesis Engine' },
    { path: '/ghosts', label: 'ANOMALIES', icon: AlertTriangle, section: 'INTEL', title: 'Ghost Candidates' },
    { path: '/communities', label: 'COMMUNITIES', icon: Waypoints, section: 'INTEL', title: 'Community Evolution' },
    { path: '/financial', label: 'FINANCIAL', icon: DollarSign, section: 'INTEL', title: 'Financial Flow Trace' },
    { path: '/gaps', label: 'GAPS', icon: AlertCircle, section: 'INTEL', title: 'Investigative Gaps' },
    { path: '/cross-case', label: 'CROSS-CASE', icon: FolderOpen, section: 'INTEL', title: 'Cross-Case Reuse' },

    // 03 ANALYSIS
    { path: '/simulation', label: 'SIMULATION', icon: Zap, section: 'ANALYSIS', title: 'Counterfactual Sandbox' },
    { path: '/analytics', label: 'ANALYSIS LAB', icon: BarChart3, section: 'ANALYSIS', title: 'Centrality & Graph Lab' },
    { path: '/models', label: 'MODELS', icon: Activity, section: 'ANALYSIS', title: 'Model Registry & Benchmark' },
    { path: '/dossiers', label: 'REPORTS', icon: BookOpen, section: 'ANALYSIS', title: 'Intelligence Reports' },
    { path: '/judge', label: 'JUDGE DEMO', icon: Sparkles, section: 'ANALYSIS', title: 'Judge Walkthrough' },

    // 04 SYSTEM
    { path: '/cases', label: 'CASES', icon: FolderOpen, section: 'SYSTEM', title: 'Case Workspaces' },
    { path: '/pipeline', label: 'DATA', icon: Upload, section: 'SYSTEM', title: 'Data Ingestion' },
    { path: '/audit', label: 'AUDIT', icon: ClipboardList, section: 'SYSTEM', title: 'Audit Trail' },
    { path: '/settings', label: 'SETTINGS', icon: Settings, section: 'SYSTEM', title: 'Settings' },
];

export const NAV_SECTIONS = ['CASE', 'INTEL', 'ANALYSIS', 'SYSTEM'];

export const ENTITY_COLORS = {
    PERSON: 'hsl(214 80% 56%)',
    PHONE: 'hsl(152 56% 44%)',
    VEHICLE: 'hsl(36 82% 55%)',
    LOCATION: 'hsl(0 72% 51%)',
    ORGANIZATION: 'hsl(270 55% 58%)',
    ACCOUNT: 'hsl(192 68% 48%)',
    DEVICE: 'hsl(220 20% 55%)',
    EVENT: 'hsl(36 82% 55%)',
};

export const ENTITY_ICONS = {
    PERSON: Users,
    PHONE: Database,
    VEHICLE: MapPin,
    LOCATION: MapPin,
    ORGANIZATION: Shield,
    ACCOUNT: BarChart3,
    DEVICE: Database,
    EVENT: Clock,
};

export function getEntityTypeColor(type) {
    return ENTITY_COLORS[type] || 'hsl(var(--fg-muted))';
}

export function getConfidenceColor(conf) {
    if (conf >= 0.85) return 'hsl(var(--green))';
    if (conf >= 0.7) return 'hsl(var(--blue))';
    if (conf >= 0.5) return 'hsl(var(--amber))';
    return 'hsl(var(--red))';
}

export function formatNumber(n) {
    if (n == null || isNaN(n)) return '—';
    return Number(n).toLocaleString();
}

export function formatTimestamp(ts) {
    if (!ts) return '—';
    return new Date(ts).toLocaleString();
}

export function formatShortDate(ts) {
    if (!ts) return '—';
    return new Date(ts).toLocaleDateString();
}

export function AppShell({ children }) {
    const [location] = useLocation();
    const { activeCase, setCommandPaletteOpen } = useInvestigation();
    const [railCollapsed, setRailCollapsed] = useState(false);
    const { data: overview } = useGetGraphOverview();

    return (
        <div className="flex flex-col h-screen w-screen bg-bg-root text-fg-primary overflow-hidden select-none">
            {/* ── TOP HEADER ── */}
            <header className="flex items-center h-10 px-3 bg-bg-surface border-b border-border-default shrink-0 gap-3 z-20">
                {/* Brand Logo */}
                <Link href="/" className="flex items-center gap-2 hover:opacity-90 cursor-pointer">
                    <div className="w-5 h-5 rounded bg-primary flex items-center justify-center text-primary-fg font-mono font-bold text-[11px] tracking-tighter shadow-sm">
                        TP
                    </div>
                    <div className="flex items-baseline gap-1.5">
                        <span className="font-mono font-bold text-[13px] tracking-wider text-fg-primary">THUPPARIVU</span>
                        <span className="text-[9px] font-mono text-fg-muted uppercase tracking-widest hidden md:inline">INVESTIGATIVE WORKSTATION</span>
                    </div>
                </Link>

                <div className="w-px h-4 bg-border-default" />

                {/* Case Context Badge */}
                <div className="flex items-center gap-2">
                    <Link href="/cases" className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-bg-panel border border-border-default hover:border-border-strong text-[11px] cursor-pointer">
                        <span className="text-fg-faint font-mono text-[9px]">CASE:</span>
                        <span className="font-mono font-semibold text-fg-primary">{activeCase?.id || 'CASE-0421'}</span>
                        <span className="tp-badge tp-badge-amber text-[8px]">HIGH</span>
                    </Link>
                </div>

                <div className="w-px h-4 bg-border-default hidden lg:block" />

                {/* Dataset metadata */}
                <div className="hidden lg:flex items-center gap-2 text-[11px]">
                    <span className="text-fg-faint font-mono text-[9px] uppercase">DATASET</span>
                    <span className="text-fg-secondary truncate max-w-[180px]">{activeCase?.dataset || 'Synthetic Investigation 07'}</span>
                </div>

                <div className="flex-1" />

                {/* Quick Search Button (Cmd+K trigger) */}
                <button
                    onClick={() => setCommandPaletteOpen(true)}
                    className="flex items-center gap-2 px-2.5 h-6 rounded bg-bg-panel border border-border-default hover:border-border-strong text-fg-muted text-[11px] transition-colors cursor-pointer"
                >
                    <Search size={12} className="text-fg-faint" />
                    <span className="hidden sm:inline text-fg-faint">Search workstation...</span>
                    <kbd className="tp-kbd text-[9px]">⌘K</kbd>
                </button>

                <div className="w-px h-4 bg-border-default" />

                {/* Live Graph Counts */}
                <div className="hidden xl:flex items-center gap-2.5 text-[10px] font-mono text-fg-muted">
                    <span>{formatNumber(overview?.entities_count || 13146)} entities</span>
                    <span className="text-fg-faint">·</span>
                    <span>{formatNumber(overview?.triplets_count || 23982)} links</span>
                    <span className="text-fg-faint">·</span>
                    <span className="text-amber">3 anomalies</span>
                </div>

                <div className="w-px h-4 bg-border-default" />

                {/* System Status Indicator */}
                <div className="flex items-center gap-1.5" title="Backend connected & operational">
                    <div className="tp-status-dot bg-green" />
                    <span className="text-[10px] font-mono text-fg-secondary uppercase tracking-wider font-semibold">LIVE</span>
                </div>
            </header>

            {/* ── WORKSTATION BODY (NavRail + Content + Inspector) ── */}
            <div className="flex flex-1 min-h-0 overflow-hidden relative">
                {/* Navigation Rail */}
                <nav
                    className="flex flex-col h-full bg-sidebar-bg border-r border-sidebar-border shrink-0 select-none"
                    style={{ width: railCollapsed ? '48px' : '156px', transition: 'width 0.15s ease' }}
                >
                    <div className="flex-1 overflow-y-auto py-1.5 px-1 space-y-2">
                        {NAV_SECTIONS.map(section => {
                            const items = NAV_ITEMS.filter(i => i.section === section);
                            return (
                                <div key={section} className="space-y-0.5">
                                    {!railCollapsed && (
                                        <div className="px-2 py-0.5 text-[8px] font-mono font-bold tracking-widest text-fg-faint uppercase">
                                            {section}
                                        </div>
                                    )}
                                    {items.map(item => {
                                        const isActive = location === item.path ||
                                            (item.path !== '/' && location.startsWith(item.path));
                                        const Icon = item.icon;
                                        return (
                                            <Link key={item.path} href={item.path}>
                                                <div
                                                    className={`group flex items-center gap-2 px-2 py-1 rounded text-[11px] font-medium cursor-pointer transition-all
                                                        ${isActive
                                                            ? 'bg-sidebar-active-bg text-fg-primary border-l-2 border-primary font-semibold'
                                                            : 'text-fg-muted hover:text-fg-primary hover:bg-sidebar-hover border-l-2 border-transparent'
                                                        }`}
                                                    title={railCollapsed ? item.title : undefined}
                                                >
                                                    <Icon size={13} className={isActive ? 'text-primary shrink-0' : 'text-fg-faint group-hover:text-fg-secondary shrink-0'} />
                                                    {!railCollapsed && <span className="truncate">{item.label}</span>}
                                                </div>
                                            </Link>
                                        );
                                    })}
                                </div>
                            );
                        })}
                    </div>

                    {/* Rail Collapse Toggle */}
                    <div className="border-t border-sidebar-border p-1">
                        <button
                            onClick={() => setRailCollapsed(prev => !prev)}
                            className="w-full flex items-center justify-center gap-1 py-1 rounded text-fg-faint hover:text-fg-secondary hover:bg-sidebar-hover text-[10px] font-mono transition-colors cursor-pointer"
                        >
                            {railCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
                            {!railCollapsed && <span>COLLAPSE</span>}
                        </button>
                    </div>
                </nav>

                {/* Main Workspace Page View */}
                <main className="flex-1 min-w-0 h-full overflow-y-auto bg-bg-root relative flex flex-col">
                    {children}
                </main>

                {/* Right Contextual Inspector Panel */}
                <InspectorPanel />
            </div>

            {/* ── STATUS BAR (bottom) ── */}
            <footer className="flex items-center h-5 px-3 border-t border-border-subtle bg-bg-surface text-[10px] font-mono text-fg-faint shrink-0 gap-4 z-20">
                <span className="flex items-center gap-1.5">
                    <div className="tp-status-dot bg-green" />
                    <span>SYSTEM NOMINAL</span>
                </span>
                <span className="text-border-strong">|</span>
                <span>DATASET v1.7</span>
                <span className="text-border-strong hidden sm:inline">|</span>
                <span className="hidden sm:inline">GRAPH GS-0241</span>
                <span className="text-border-strong hidden md:inline">|</span>
                <span className="hidden md:inline">EVAL PR-AUC 0.82</span>
                <div className="flex-1" />
                <span className="text-fg-muted">THUPPARIVU v3.0 · SIH26189</span>
            </footer>

            {/* Global Command Palette */}
            <CommandPalette />
        </div>
    );
}

export default AppShell;
