import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'wouter';
import {
    LayoutDashboard, Network, Users, Clock, FileText, Brain,
    AlertTriangle, BarChart3, Zap, Waypoints, DollarSign, FolderOpen,
    BookOpen, Activity, ClipboardList, Settings, ChevronLeft,
    ChevronRight, Search, Shield, Database, MapPin,
    AlertCircle, MessageSquare, GitCompare
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { CommandPalette } from '@/components/command-palette';
import { useGetGraphOverview, useHealthCheck } from '@/api/graph';

/* ── Navigation sections ── */
export const NAV_SECTIONS = [
    { id: 'workspace', label: 'WORKSPACE', items: [
        { path: '/', label: 'Overview', icon: LayoutDashboard, title: 'Command center' },
        { path: '/cases', label: 'Cases', icon: FolderOpen, title: 'Case management' },
        { path: '/network', label: 'Network', icon: Network, title: 'Network explorer' },
        { path: '/entities', label: 'Entities', icon: Users, title: 'Entity directory' },
        { path: '/timeline', label: 'Timeline', icon: Clock, title: 'Evidence timeline' },
    ]},
    { id: 'analysis', label: 'ANALYSIS', items: [
        { path: '/evidence', label: 'Evidence', icon: FileText, title: 'Evidence register' },
        { path: '/findings', label: 'Findings', icon: Brain, title: 'Analytical findings' },
        { path: '/ghosts', label: 'Hypotheses', icon: AlertTriangle, title: 'Ghost candidates' },
        { path: '/simulation', label: 'Simulation', icon: Zap, title: 'Counterfactual sandbox' },
        { path: '/dossiers', label: 'Dossiers', icon: BookOpen, title: 'Report dossiers' },
    ]},
    { id: 'intelligence', label: 'INTELLIGENCE', items: [
        { path: '/financial', label: 'Financial', icon: DollarSign, title: 'Financial flows' },
        { path: '/communities', label: 'Communities', icon: Waypoints, title: 'Community structure' },
        { path: '/analytics', label: 'Analytics', icon: BarChart3, title: 'Network analytics' },
        { path: '/cross-case', label: 'Cross-case', icon: GitCompare, title: 'Cross-case links' },
        { path: '/copilot', label: 'Copilot', icon: MessageSquare, title: 'Investigative assistant' },
        { path: '/gaps', label: 'Gaps', icon: AlertCircle, title: 'Investigative gaps' },
    ]},
    { id: 'operations', label: 'OPERATIONS', items: [
        { path: '/pipeline', label: 'Pipeline', icon: Activity, title: 'Pipeline monitor' },
        { path: '/audit', label: 'Audit', icon: ClipboardList, title: 'Audit log' },
    ]},
];
export const ALL_NAV_ITEMS = NAV_SECTIONS.flatMap(s => s.items);
/* Back-compat: flat list used by command palette */
export const NAV_ITEMS = ALL_NAV_ITEMS;

/* ── Entity colors ── */
export const ENTITY_COLORS = {
    PERSON: 'hsl(214 80% 56%)',
    PHONE: 'hsl(36 82% 55%)',
    VEHICLE: 'hsl(152 56% 44%)',
    LOCATION: 'hsl(152 56% 44%)',
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
    try {
        const d = new Date(ts);
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
            + ' · ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    } catch { return String(ts); }
}

export function formatShortDate(ts) {
    if (!ts) return '—';
    return new Date(ts).toLocaleDateString();
}

/* ── App Shell ── */
export function AppShell({ children }) {
    const [location] = useLocation();
    const { activeCase, setCommandPaletteOpen } = useInvestigation();
    const [railCollapsed, setRailCollapsed] = useState(false);
    const { data: healthData } = useHealthCheck();
    const { data: overview } = useGetGraphOverview();

    const healthStatus = healthData ? (healthData.ok ? 'connected' : 'degraded') : 'loading';
    const nodeCount = overview?.nodeCount ?? overview?.totalNodes ?? null;
    const edgeCount = overview?.edgeCount ?? overview?.totalEdges ?? null;

    useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setCommandPaletteOpen(true);
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [setCommandPaletteOpen]);

    return (
        <div className="flex flex-col h-screen w-screen bg-bg-root text-fg-primary overflow-hidden select-none">
            {/* GLOBAL HEADER */}
            <header className="flex items-center h-11 px-3 bg-bg-surface border-b border-border-default shrink-0 gap-3 z-30">
                <Link href="/" className="flex items-center gap-2 hover:opacity-90 cursor-pointer shrink-0">
                    <div className="w-5 h-5 rounded-sm bg-primary flex items-center justify-center text-primary-fg font-mono font-bold text-[10px] tracking-tighter">SG</div>
                    <span className="text-[13px] font-semibold text-fg-primary hidden sm:inline">SentinelGraph</span>
                </Link>
                <div className="w-px h-4 bg-border-default hidden lg:block" />
                <Link href="/cases" className="flex items-center gap-1.5 text-[11px] hover:opacity-80 cursor-pointer">
                    <span className="text-fg-faint">Case</span>
                    <span className="font-mono font-semibold text-fg-primary">{activeCase?.id || '—'}</span>
                </Link>
                <div className="w-px h-4 bg-border-default hidden lg:block" />
                <div className="hidden lg:flex items-center gap-2 text-[11px]">
                    <span className="text-fg-faint font-mono text-[9px] uppercase">Dataset</span>
                    <span className="text-fg-secondary truncate max-w-[160px]">{activeCase?.dataset || 'Synthetic Investigation 07'}</span>
                </div>
                <div className="flex-1" />
                <button
                    onClick={() => setCommandPaletteOpen(true)}
                    className="flex items-center gap-2 px-2.5 h-6 rounded-sm bg-[hsl(220,13%,10%)] border border-border-default hover:border-border-strong text-fg-muted text-[11px] transition-colors cursor-pointer"
                >
                    <Search size={11} className="text-fg-faint" />
                    <span className="hidden sm:inline text-fg-faint">Search…</span>
                    <kbd className="text-[9px] text-fg-faint font-mono bg-[hsl(220,10%,16%)] px-1 rounded-sm">⌘K</kbd>
                </button>
                <div className="flex items-center gap-1.5 text-[10px] font-mono">
                    <div className={`w-1.5 h-1.5 rounded-full ${healthStatus === 'connected' ? 'bg-green' : healthStatus === 'degraded' ? 'bg-amber' : 'bg-fg-faint'}`} />
                    <span className="text-fg-faint hidden md:inline">
                        {healthStatus === 'connected' ? 'API' : healthStatus === 'degraded' ? 'Degraded' : 'Connecting'}
                    </span>
                </div>
            </header>

            <div className="flex flex-1 min-h-0">
                {/* LEFT NAV RAIL */}
                <nav className={`flex flex-col border-r border-border-default bg-bg-surface shrink-0 transition-all duration-fast overflow-y-auto overflow-x-hidden ${railCollapsed ? 'w-10' : 'w-48'}`}>
                    {NAV_SECTIONS.map((section) => (
                        <div key={section.id} className="py-1.5">
                            {!railCollapsed && (
                                <div className="px-3 py-1 text-[9px] font-semibold text-fg-faint uppercase tracking-widest">{section.label}</div>
                            )}
                            {section.items.map((item) => {
                                const Icon = item.icon;
                                const isActive = location === item.path || (item.path !== '/' && location.startsWith(item.path));
                                return (
                                    <Link key={item.path} href={item.path}>
                                        <div
                                            className={`flex items-center gap-2 mx-1.5 px-2 py-1.5 rounded-sm text-[12px] transition-colors cursor-pointer group
                                                ${isActive
                                                    ? 'bg-[hsl(220,10%,12%)] text-fg-primary border-l-2 border-l-primary'
                                                    : 'text-fg-muted hover:text-fg-primary hover:bg-[hsl(220,10%,11%)] border-l-2 border-l-transparent'}`}
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
                    <div className="border-t border-border-subtle py-1.5">
                        <Link href="/settings">
                            <div className={`flex items-center gap-2 mx-1.5 px-2 py-1.5 rounded-sm text-[12px] transition-colors cursor-pointer
                                ${location === '/settings' ? 'bg-[hsl(220,10%,12%)] text-fg-primary' : 'text-fg-muted hover:text-fg-primary hover:bg-[hsl(220,10%,11%)]'}`}>
                                <Settings size={13} className="text-fg-faint shrink-0" />
                                {!railCollapsed && <span>Settings</span>}
                            </div>
                        </Link>
                        <button
                            onClick={() => setRailCollapsed(c => !c)}
                            className="flex items-center gap-2 mx-1.5 px-2 py-1.5 rounded-sm text-[11px] text-fg-faint hover:text-fg-secondary transition-colors cursor-pointer w-full"
                        >
                            {railCollapsed ? <ChevronRight size={12} /> : <><ChevronLeft size={12} /><span>Collapse</span></>}
                        </button>
                    </div>
                </nav>

                {/* MAIN CONTENT */}
                <main className="flex-1 min-w-0 overflow-auto bg-bg-root">
                    {children}
                </main>
            </div>

            {/* STATUS BAR */}
            <footer className="flex items-center h-5 px-3 border-t border-border-subtle bg-bg-surface text-[10px] font-mono text-fg-faint shrink-0 gap-4 z-30">
                <span className="flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full ${healthStatus === 'connected' ? 'bg-green' : healthStatus === 'degraded' ? 'bg-amber' : 'bg-red'}`} />
                    <span>{healthStatus === 'connected' ? 'SYSTEM NOMINAL' : healthStatus === 'degraded' ? 'DEGRADED' : 'RECONNECTING'}</span>
                </span>
                <span className="text-border-strong">|</span>
                {nodeCount != null && <span>{formatNumber(nodeCount)} nodes · {formatNumber(edgeCount)} edges</span>}
                <div className="flex-1" />
                {overview?.lastUpdated && <span>Updated {formatTimestamp(overview.lastUpdated)}</span>}
            </footer>

            <CommandPalette />
        </div>
    );
}