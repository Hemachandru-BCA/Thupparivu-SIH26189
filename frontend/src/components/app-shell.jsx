import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Link, useLocation } from 'wouter';
import { useGetGraphOverview, useGetGraphNetwork } from '@/api/graph';
import {
    LayoutDashboard, Network, Users, FileText, Search, Clock, Brain,
    AlertTriangle, BarChart3, Upload, Shield, Settings, ChevronLeft,
    ChevronRight, PanelRightClose, PanelRightOpen, Bell, Activity,
    FolderOpen, GitBranch, Eye, Database, BookOpen, ClipboardList,
    Zap, Target, Waypoints, MapPin
} from 'lucide-react';

/* ──────────────────────────────────────────────────────────────
   NAVIGATION CONFIG
   ────────────────────────────────────────────────────────────── */

const NAV_ITEMS = [
    { path: '/', label: 'OVERVIEW', icon: LayoutDashboard, section: 'CASE' },
    { path: '/network', label: 'NETWORK', icon: Network, section: 'CASE' },
    { path: '/entities', label: 'ENTITIES', icon: Users, section: 'CASE' },
    { path: '/timeline', label: 'TIMELINE', icon: Clock, section: 'CASE' },
    { path: '/evidence', label: 'EVIDENCE', icon: FileText, section: 'CASE' },
    { path: '/findings', label: 'HYPOTHESES', icon: Brain, section: 'INTEL' },
    { path: '/ghosts', label: 'ANOMALIES', icon: AlertTriangle, section: 'INTEL' },
    { path: '/analytics', label: 'ANALYSIS', icon: BarChart3, section: 'TOOLS' },
    { path: '/simulation', label: 'SIMULATION', icon: Zap, section: 'TOOLS' },
    { path: '/communities', label: 'COMMUNITIES', icon: Waypoints, section: 'TOOLS' },
    { path: '/pipeline', label: 'DATA', icon: Upload, section: 'SYS' },
    { path: '/audit', label: 'AUDIT', icon: ClipboardList, section: 'SYS' },
    { path: '/dossiers', label: 'REPORTS', icon: BookOpen, section: 'SYS' },
    { path: '/settings', label: 'SETTINGS', icon: Settings, section: 'SYS' },
];

const NAV_SECTIONS = ['CASE', 'INTEL', 'TOOLS', 'SYS'];

/* ──────────────────────────────────────────────────────────────
   ROUTE METADATA
   ────────────────────────────────────────────────────────────── */

const ROUTE_META = {
    '/': { title: 'CASE OVERVIEW', description: 'Investigation summary and priority findings' },
    '/network': { title: 'NETWORK', description: 'Link analysis and relationship exploration' },
    '/entities': { title: 'ENTITIES', description: 'Entity directory and properties' },
    '/timeline': { title: 'TIMELINE', description: 'Temporal event analysis' },
    '/evidence': { title: 'EVIDENCE', description: 'Evidence register and provenance' },
    '/findings': { title: 'HYPOTHESES', description: 'Investigative hypotheses and confidence' },
    '/ghosts': { title: 'ANOMALIES', description: 'Ghost candidates and structural anomalies' },
    '/analytics': { title: 'ANALYSIS', description: 'Centrality, communities, and graph metrics' },
    '/simulation': { title: 'SIMULATION', description: 'Counterfactual analysis and node removal' },
    '/communities': { title: 'COMMUNITIES', description: 'Community structure and evolution' },
    '/pipeline': { title: 'DATA INGESTION', description: 'Pipeline monitoring and data sources' },
    '/audit': { title: 'AUDIT LOG', description: 'System activity and investigation trail' },
    '/dossiers': { title: 'REPORTS', description: 'Intelligence dossiers and exports' },
    '/settings': { title: 'SETTINGS', description: 'Workspace configuration' },
    '/search': { title: 'SEARCH', description: 'Global search across all data' },
};

/* ──────────────────────────────────────────────────────────────
   ENTITY TYPE ICONS & COLORS
   ────────────────────────────────────────────────────────────── */

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
    if (n == null) return '—';
    return n.toLocaleString();
}

export function formatTimestamp(ts) {
    if (!ts) return '—';
    try {
        const d = new Date(ts);
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) + ' ' +
               d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    } catch { return ts; }
}

export function formatShortDate(ts) {
    if (!ts) return '—';
    try {
        const d = new Date(ts);
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
    } catch { return ts; }
}

/* ──────────────────────────────────────────────────────────────
   CASE CONTEXT BAR (top)
   ────────────────────────────────────────────────────────────── */

function CaseContextBar({ overview, collapsed }) {
    const stats = {
        entity_count: overview?.entities_count,
        triplet_count: overview?.triplets_count,
        ghost_count: overview?.ghost_predictions_count,
        community_count: overview?.metadata?.num_communities,
    };
    return (
        <header className="flex items-center gap-4 h-9 px-4 border-b border-border-subtle bg-bg-surface shrink-0">
            {/* Brand */}
            <div className="flex items-center gap-2 mr-2">
                <div className="w-5 h-5 rounded-sm bg-primary flex items-center justify-center">
                    <Eye size={11} className="text-primary-fg" />
                </div>
                {!collapsed && (
                    <span className="font-mono text-[10px] font-semibold tracking-wider text-fg-primary">
                        THUPPARIVU
                    </span>
                )}
            </div>

            <div className="w-px h-4 bg-border-default" />

            {/* Case context */}
            <div className="flex items-center gap-3 text-[11px]">
                <span className="text-fg-muted font-mono uppercase tracking-wider" style={{fontSize: '9px'}}>CASE</span>
                <span className="text-fg-primary font-mono text-[11px] font-medium">SIH-26189</span>
                <span className="text-fg-faint">·</span>
                <span className="text-fg-secondary">Criminal Network Analysis</span>
            </div>

            <div className="w-px h-4 bg-border-default" />

            {/* Dataset */}
            <div className="flex items-center gap-3 text-[11px]">
                <span className="text-fg-muted font-mono uppercase tracking-wider" style={{fontSize: '9px'}}>DATASET</span>
                <span className="text-fg-secondary">Synthetic Investigation 07</span>
            </div>

            <div className="flex-1" />

            {/* Graph summary — compact */}
            {stats.entity_count != null && (
                <div className="flex items-center gap-3 text-[11px] font-mono">
                    <span className="text-fg-muted">{formatNumber(stats.entity_count)} entities</span>
                    <span className="text-fg-faint">·</span>
                    <span className="text-fg-muted">{formatNumber(stats.triplet_count)} links</span>
                    <span className="text-fg-faint">·</span>
                    <span className="text-fg-muted">{formatNumber(stats.ghost_count)} anomalies</span>
                </div>
            )}

            <div className="w-px h-4 bg-border-default" />

            {/* Status */}
            <div className="flex items-center gap-1.5">
                <div className="tp-status-dot bg-green" />
                <span className="text-[10px] font-mono text-fg-muted uppercase">LIVE</span>
            </div>
        </header>
    );
}

/* ──────────────────────────────────────────────────────────────
   NAVIGATION RAIL (left)
   ────────────────────────────────────────────────────────────── */

function NavRail({ currentPath, collapsed, onToggle }) {
    return (
        <nav className="flex flex-col h-full bg-sidebar-bg border-r border-sidebar-border shrink-0"
             style={{ width: collapsed ? '48px' : '160px', transition: 'width 0.15s ease' }}>
            {/* Nav items */}
            <div className="flex-1 overflow-y-auto py-2 px-1.5">
                {NAV_SECTIONS.map(section => {
                    const items = NAV_ITEMS.filter(i => i.section === section);
                    return (
                        <div key={section} className="mb-2">
                            {!collapsed && (
                                <div className="px-2 py-1 text-[8px] font-mono font-semibold tracking-widest text-fg-faint uppercase">
                                    {section}
                                </div>
                            )}
                            {items.map(item => {
                                const isActive = currentPath === item.path ||
                                    (item.path !== '/' && currentPath.startsWith(item.path));
                                const Icon = item.icon;
                                return (
                                    <Link key={item.path} href={item.path}>
                                        <div className={`group flex items-center gap-2 px-2 py-1.5 rounded text-[11px] font-medium cursor-pointer transition-all
                                            ${isActive
                                                ? 'bg-sidebar-active-bg text-fg-primary border-l-2 border-sidebar-active-border'
                                                : 'text-fg-faint hover:text-fg-secondary hover:bg-sidebar-hover border-l-2 border-transparent'
                                            }`}
                                            data-tooltip={collapsed ? item.label : undefined}>
                                            <Icon size={14} className={isActive ? 'text-primary' : 'text-fg-faint group-hover:text-fg-muted'} />
                                            {!collapsed && <span>{item.label}</span>}
                                        </div>
                                    </Link>
                                );
                            })}
                        </div>
                    );
                })}
            </div>

            {/* Collapse toggle */}
            <div className="border-t border-sidebar-border p-1.5">
                <button onClick={onToggle}
                    className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded text-fg-faint hover:text-fg-secondary hover:bg-sidebar-hover transition-colors text-[10px]">
                    {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
                    {!collapsed && <span>Collapse</span>}
                </button>
            </div>
        </nav>
    );
}

/* ──────────────────────────────────────────────────────────────
   STATUS BAR (bottom)
   ────────────────────────────────────────────────────────────── */

function StatusBar({ overview }) {
    const stats = {
        entity_count: overview?.entities_count,
        triplet_count: overview?.triplets_count,
        community_count: overview?.metadata?.num_communities,
        ghost_count: overview?.ghost_predictions_count,
    };
    return (
        <footer className="flex items-center h-6 px-3 border-t border-border-subtle bg-bg-surface text-[10px] font-mono text-fg-faint shrink-0 gap-4">
            <span className="flex items-center gap-1.5">
                <div className="tp-status-dot bg-green" />
                SYSTEM NOMINAL
            </span>
            <span className="text-border-strong">|</span>
            <span>{formatNumber(stats.entity_count)} ENTITIES</span>
            <span className="text-border-strong">|</span>
            <span>{formatNumber(stats.triplet_count)} LINKS</span>
            <span className="text-border-strong">|</span>
            <span>{formatNumber(stats.community_count)} COMMUNITIES</span>
            <span className="text-border-strong">|</span>
            <span>{formatNumber(stats.ghost_count)} GHOST CANDIDATES</span>
            <div className="flex-1" />
            <span className="text-fg-muted">MODEL RUN MR-0247</span>
            <span className="text-border-strong">|</span>
            <span>v1.0</span>
        </footer>
    );
}

/* ──────────────────────────────────────────────────────────────
   CONTEXTUAL INSPECTOR (right panel)
   ────────────────────────────────────────────────────────────── */

function Inspector({ entity, onClose }) {
    if (!entity) return (
        <div className="h-full bg-inspector-bg border-l border-border-subtle p-4 flex flex-col items-center justify-center text-center" style={{width: 280}}>
            <Eye size={20} className="text-fg-faint mb-2" />
            <span className="text-[10px] font-mono text-fg-faint uppercase tracking-wider">NO SELECTION</span>
            <span className="text-[11px] text-fg-faint mt-1">Select an entity to inspect</span>
        </div>
    );

    return (
        <div className="h-full bg-inspector-bg border-l border-border-subtle flex flex-col" style={{width: 280}}>
            <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle">
                <span className="text-[10px] font-mono text-fg-muted uppercase tracking-wider">INSPECTOR</span>
                <button onClick={onClose} className="tp-btn-ghost p-0.5">
                    <PanelRightClose size={12} />
                </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-4">
                {/* Entity header */}
                <div>
                    <div className="text-[11px] font-mono text-fg-muted uppercase mb-1">ENTITY</div>
                    <div className="text-[14px] font-semibold text-fg-primary">{entity.name || entity.id}</div>
                    <div className="flex items-center gap-1.5 mt-1">
                        <span className="tp-badge tp-badge-blue">{entity.type || entity.label || 'UNKNOWN'}</span>
                        {entity.community_id != null && (
                            <span className="tp-badge tp-badge-neutral">C{entity.community_id}</span>
                        )}
                    </div>
                </div>

                {/* Identity */}
                <div>
                    <div className="tp-section-label mb-2">IDENTITY</div>
                    <div className="space-y-1.5 text-[11px]">
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Canonical ID</span>
                            <span className="font-mono text-fg-secondary">{entity.id}</span>
                        </div>
                        {entity.metrics?.pagerank != null && (
                            <div className="flex justify-between">
                                <span className="text-fg-faint">PageRank</span>
                                <span className="font-mono text-fg-secondary">{entity.metrics.pagerank?.toFixed(2)}</span>
                            </div>
                        )}
                        {entity.metrics?.betweenness_centrality != null && (
                            <div className="flex justify-between">
                                <span className="text-fg-faint">Betweenness</span>
                                <span className="font-mono text-fg-secondary">{entity.metrics.betweenness_centrality?.toFixed(2)}</span>
                            </div>
                        )}
                        {entity.degree != null && (
                            <div className="flex justify-between">
                                <span className="text-fg-faint">Degree</span>
                                <span className="font-mono text-fg-secondary">{entity.degree}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Network role */}
                <div>
                    <div className="tp-section-label mb-2">NETWORK ROLE</div>
                    <div className="space-y-1.5 text-[11px]">
                        {entity.community_id != null && (
                            <div className="flex justify-between">
                                <span className="text-fg-faint">Community</span>
                                <span className="font-mono text-fg-secondary">C{entity.community_id}</span>
                            </div>
                        )}
                        {entity.mention_count != null && (
                            <div className="flex justify-between">
                                <span className="text-fg-faint">Mentions</span>
                                <span className="font-mono text-fg-secondary">{entity.mention_count}</span>
                            </div>
                        )}
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Ghost</span>
                            <span className={`font-mono ${entity.is_ghost ? 'text-amber' : 'text-fg-faint'}`}>
                                {entity.is_ghost ? 'YES' : 'NO'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────
   SEARCH PALETTE
   ────────────────────────────────────────────────────────────── */

function SearchPalette({ open, onClose }) {
    const [query, setQuery] = useState('');
    const inputRef = useRef(null);

    useEffect(() => {
        if (open && inputRef.current) {
            inputRef.current.focus();
        }
    }, [open]);

    useEffect(() => {
        function handleKey(e) {
            if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.target.closest('input, textarea, select')) {
                e.preventDefault();
                if (!open) onClose?.();
            }
            if (e.key === 'Escape' && open) onClose?.();
        }
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]" onClick={onClose}>
            <div className="absolute inset-0 bg-black/50" />
            <div className="relative w-full max-w-xl bg-bg-panel border border-border-default rounded-lg shadow-2xl overflow-hidden animate-slide-up"
                 onClick={e => e.stopPropagation()}>
                <div className="flex items-center gap-2 px-4 h-10 border-b border-border-subtle">
                    <Search size={14} className="text-fg-faint" />
                    <input ref={inputRef}
                        value={query} onChange={e => setQuery(e.target.value)}
                        placeholder="Search entities, evidence, hypotheses..."
                        className="flex-1 bg-transparent text-[13px] text-fg-primary placeholder:text-fg-faint outline-none" />
                    <span className="tp-kbd">ESC</span>
                </div>
                <div className="px-4 py-3 text-[11px] text-fg-faint">
                    {query.length === 0 ? 'Type to search across all investigation data' : `Searching for "${query}"...`}
                </div>
            </div>
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────
   APP SHELL — main layout
   ────────────────────────────────────────────────────────────── */

export function AppShell({ children }) {
    const [location] = useLocation();
    const [navCollapsed, setNavCollapsed] = useState(false);
    const [inspectorOpen, setInspectorOpen] = useState(true);
    const [inspectorEntity, setInspectorEntity] = useState(null);
    const [searchOpen, setSearchOpen] = useState(false);

    const { data: overview } = useGetGraphOverview();
    const meta = ROUTE_META[location] || ROUTE_META['/'];

    // Global keyboard shortcuts
    useEffect(() => {
        function handleKey(e) {
            // Don't trigger if inside an input
            if (e.target.closest('input, textarea, select')) return;

            if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                setSearchOpen(true);
            }
        }
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, []);

    // Expose inspector controls via window for child pages
    useEffect(() => {
        window.__thupparivu = {
            setInspectorEntity: (entity) => {
                setInspectorEntity(entity);
                setInspectorOpen(true);
            },
            clearInspector: () => setInspectorEntity(null),
        };
        return () => { delete window.__thupparivu; };
    }, []);

    return (
        <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg-root">
            {/* Top: Case Context Bar */}
            <CaseContextBar overview={overview} collapsed={navCollapsed} />

            <div className="flex flex-1 min-h-0">
                {/* Left: Navigation Rail */}
                <NavRail currentPath={location} collapsed={navCollapsed} onToggle={() => setNavCollapsed(!navCollapsed)} />

                {/* Center: Main Workspace */}
                <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
                    {/* Workspace header */}
                    <div className="flex items-center justify-between h-8 px-4 border-b border-border-subtle bg-bg-surface shrink-0">
                        <div className="flex items-center gap-2">
                            <span className="text-[11px] font-semibold text-fg-primary">{meta.title}</span>
                            {meta.description && (
                                <span className="text-[10px] text-fg-faint">— {meta.description}</span>
                            )}
                        </div>
                        <div className="flex items-center gap-1">
                            <button onClick={() => setSearchOpen(true)}
                                className="tp-btn tp-btn-ghost h-6 px-2 text-[10px] gap-1">
                                <Search size={11} />
                                <span className="text-fg-faint">Search</span>
                                <span className="tp-kbd ml-1">/</span>
                            </button>
                            <button onClick={() => setInspectorOpen(!inspectorOpen)}
                                className="tp-btn tp-btn-ghost h-6 px-1.5">
                                {inspectorOpen ? <PanelRightClose size={12} /> : <PanelRightOpen size={12} />}
                            </button>
                        </div>
                    </div>

                    {/* Page content */}
                    <div className="flex-1 overflow-auto">
                        {children}
                    </div>
                </main>

                {/* Right: Inspector */}
                {inspectorOpen && (
                    <Inspector entity={inspectorEntity} onClose={() => setInspectorOpen(false)} />
                )}
            </div>

            {/* Bottom: Status Bar */}
            <StatusBar overview={overview} />

            {/* Search Palette */}
            <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
        </div>
    );
}

export default AppShell;
