import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'wouter';
import { getSearchGraphQueryKey, useSearchGraph } from '@/api/graph';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bell,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  CircleHelp,
  Compass,
  Cpu,
  Database,
  ExternalLink,
  FileCheck,
  FileSearch,
  FileText,
  Filter,
  GitBranch,
  Globe2,
  History,
  Info,
  Layers3,
  LayoutDashboard,
  Lightbulb,
  Link2,
  Menu,
  Network,
  RefreshCw,
  Search,
  Settings2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Table2,
  Terminal,
  Users,
  X,
  Zap,
} from 'lucide-react';

/* ---------------------------------------------------------------------------
   Navigation Structure (Compact & Premium Terminal Sidebar)
--------------------------------------------------------------------------- */
export const NAV_SECTIONS = [
  {
    id: 'command-center',
    title: 'COMMAND CENTER',
    items: [
      { href: '/', label: 'Overview', icon: LayoutDashboard },
      { href: '/explorer', label: 'Network Explorer', icon: Network, altHrefs: ['/network', '/network-legacy'] },
    ],
  },
  {
    id: 'intelligence',
    title: 'INTELLIGENCE',
    items: [
      { href: '/ghosts', label: 'Ghost Candidates', icon: Sparkles },
      { href: '/findings', label: 'Findings', icon: ShieldAlert, matchPrefix: true },
      { href: '/evidence', label: 'Evidence', icon: FileSearch },
      { href: '/dossiers', label: 'Dossiers', icon: FileText },
    ],
  },
  {
    id: 'analysis',
    title: 'ANALYSIS',
    items: [
      { href: '/simulation', label: 'Counterfactual Sandbox', icon: Zap },
      { href: '/analytics', label: 'Analytics', icon: BarChart3 },
      { href: '/communities', label: 'Communities', icon: Users },
    ],
  },
  {
    id: 'system',
    title: 'SYSTEM',
    items: [
      { href: '/pipeline', label: 'Data Pipeline', icon: GitBranch },
      { href: '/audit', label: 'Audit Log', icon: History },
      { href: '/settings', label: 'System Health', icon: ShieldCheck },
    ],
  },
];

/* ---------------------------------------------------------------------------
   Route Metadata Map for Top Bar Breadcrumbs & Titles
--------------------------------------------------------------------------- */
const ROUTE_INFO = {
  '/': { section: 'COMMAND CENTER', title: 'Overview', desc: 'Real-time investigative summary & intelligence telemetry' },
  '/explorer': { section: 'COMMAND CENTER', title: 'Network Explorer', desc: 'Interactive graph visualization & neighborhood traversal' },
  '/network': { section: 'COMMAND CENTER', title: 'Network Explorer', desc: 'Interactive graph visualization & neighborhood traversal' },
  '/network-legacy': { section: 'COMMAND CENTER', title: 'Network Explorer (Legacy)', desc: 'Radial graph view' },
  '/ghosts': { section: 'INTELLIGENCE', title: 'Ghost Candidates', desc: 'Explainable hypotheses for unobserved intermediaries' },
  '/findings': { section: 'INTELLIGENCE', title: 'Findings', desc: 'Evidence-grounded XAI findings & claims' },
  '/evidence': { section: 'INTELLIGENCE', title: 'Evidence', desc: 'Cryptographic provenance register & chain-of-custody' },
  '/dossiers': { section: 'INTELLIGENCE', title: 'Dossiers', desc: 'Bounded-context intelligence briefs & automated reports' },
  '/simulation': { section: 'ANALYSIS', title: 'Counterfactual Sandbox', desc: 'Intervention simulations & alternate path rerouting' },
  '/analytics': { section: 'ANALYSIS', title: 'Analytics', desc: 'Centrality rankings & graph topological distributions' },
  '/communities': { section: 'ANALYSIS', title: 'Communities', desc: 'Detected graph clusters & modularity groups' },
  '/pipeline': { section: 'SYSTEM', title: 'Data Pipeline', desc: 'Ingestion, resolution, and ETL pipeline telemetry' },
  '/audit': { section: 'SYSTEM', title: 'Audit Log', desc: 'Append-only immutable record of investigator actions' },
  '/settings': { section: 'SYSTEM', title: 'System Health', desc: 'API connectivity, graph health & workstation config' },
  // Preserved data & workspace routes
  '/entities': { section: 'DATA', title: 'Entities', desc: 'Resolved entity database & identity catalog' },
  '/cases': { section: 'WORKSPACE', title: 'Cases', desc: 'Analyst working files & case binders' },
  '/communications': { section: 'DATA', title: 'Communications', desc: 'Call records & telecommunication metadata' },
  '/transactions': { section: 'DATA', title: 'Transactions', desc: 'Financial routing records & transfers' },
  '/timeline': { section: 'ANALYSIS', title: 'Timeline', desc: 'Temporal event choreography' },
  '/search': { section: 'COMMAND CENTER', title: 'Global Search', desc: 'Multi-index entity & evidence queries' },
};

function resolveRouteMeta(pathname) {
  if (ROUTE_INFO[pathname]) {
    return { ...ROUTE_INFO[pathname], detailId: null };
  }
  if (pathname.startsWith('/findings/')) {
    const id = decodeURIComponent(pathname.replace('/findings/', ''));
    return { section: 'INTELLIGENCE', title: 'Finding Detail', desc: `Finding ${id}`, detailId: id };
  }
  if (pathname.startsWith('/cases/')) {
    const id = decodeURIComponent(pathname.replace('/cases/', ''));
    return { section: 'WORKSPACE', title: 'Case File', desc: `Case ${id}`, detailId: id };
  }
  return { section: 'COMMAND CENTER', title: 'Analytical Terminal', desc: 'THUPPARIVU Workstation', detailId: null };
}

function isNavActive(item, currentPath) {
  if (item.href === '/') return currentPath === '/';
  if (item.href === '/explorer') return currentPath === '/explorer' || currentPath === '/network';
  if (item.altHrefs && item.altHrefs.includes(currentPath)) return true;
  if (item.matchPrefix) return currentPath === item.href || currentPath.startsWith(item.href + '/');
  return currentPath === item.href;
}

/* ---------------------------------------------------------------------------
   Shell Component
--------------------------------------------------------------------------- */
export function Shell({ children }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [globalQuery, setGlobalQuery] = useState('');
  const [debouncedGlobalQuery, setDebouncedGlobalQuery] = useState('');
  const [location] = useLocation();

  const searchContainerRef = useRef(null);
  const searchInputRef = useRef(null);
  const notificationsRef = useRef(null);

  const routeMeta = resolveRouteMeta(location);

  // Debounce global search
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedGlobalQuery(globalQuery), 220);
    return () => window.clearTimeout(timer);
  }, [globalQuery]);

  const globalSearch = useSearchGraph(
    { q: debouncedGlobalQuery },
    {
      query: {
        queryKey: getSearchGraphQueryKey({ q: debouncedGlobalQuery }),
        enabled: debouncedGlobalQuery.trim().length > 1,
      },
    }
  );

  // Keyboard shortcuts: Cmd+K / Ctrl+K / '/' to focus search, Esc to dismiss
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
        setSearchFocused(true);
      } else if (
        e.key === '/' &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        searchInputRef.current?.focus();
        setSearchFocused(true);
      } else if (e.key === 'Escape') {
        setSearchFocused(false);
        setNotificationsOpen(false);
        searchInputRef.current?.blur();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Dismiss dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setSearchFocused(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(e.target)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="min-h-[100dvh] bg-[#080b11] text-[#e1e7f0] flex">
      {/* ---------------------------------------------------------------------
          1. LEFT SIDEBAR (Compact & Premium Analytical Terminal)
      --------------------------------------------------------------------- */}
      <aside
        className={`${
          collapsed ? 'w-[64px]' : 'w-[220px]'
        } ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        } fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[#1a2232] bg-[#090d16] text-[#c9d3e0] transition-[width,transform] duration-200 ease-out select-none`}
      >
        {/* Terminal Brand Header */}
        <div className="flex h-13 items-center justify-between border-b border-[#1a2232] px-3.5">
          <Link href="/" className="flex items-center gap-2.5 min-w-0 group">
            <div className="relative grid h-7 w-7 shrink-0 place-items-center rounded-md border border-cyan-500/40 bg-cyan-950/40 text-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.2)] transition-transform group-hover:scale-105">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 2 7 12 12 22 7 12 2" />
                <polyline points="2 17 12 22 22 17" />
                <polyline points="2 12 12 17 22 12" />
              </svg>
              <span className="absolute -top-0.5 -right-0.5 h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.9)]" />
            </div>

            {!collapsed && (
              <div className="leading-tight min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono-ui text-[11px] font-bold tracking-[0.14em] text-white">THUPPARIVU</span>
                </div>
                <div className="font-mono-ui text-[8px] uppercase tracking-[0.2em] text-muted-foreground/50 truncate">
                  ANALYTICAL TERMINAL
                </div>
              </div>
            )}
          </Link>

          <button
            type="button"
            data-testid="button-close-mobile-nav"
            onClick={() => setMobileOpen(false)}
            className="rounded p-1 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground md:hidden"
            aria-label="Close sidebar"
          >
            <X size={16} />
          </button>
        </div>

        {/* Navigation Sections */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-4 scrollbar-thin scrollbar-thumb-white/10">
          {NAV_SECTIONS.map((section) => (
            <div key={section.id}>
              {!collapsed ? (
                <div className="px-2.5 pb-1 font-mono-ui text-[9px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/45 flex items-center gap-1.5">
                  <span className="h-1 w-1 rounded-full bg-cyan-500/40" />
                  {section.title}
                </div>
              ) : (
                <div className="my-1.5 mx-auto w-5 h-px bg-[#1a2232]" />
              )}

              <nav className="space-y-0.5">
                {section.items.map((item) => {
                  const active = isNavActive(item, location);
                  return (
                    <NavItem
                      key={item.href}
                      {...item}
                      active={active}
                      collapsed={collapsed}
                    />
                  );
                })}
              </nav>
            </div>
          ))}
        </div>

        {/* Sidebar Footer (Terminal Security & Telemetry) */}
        <div className="border-t border-[#1a2232] p-2.5 bg-[#070a12]/60">
          {!collapsed ? (
            <div className="flex items-center justify-between rounded-md border border-[#1a2436] bg-[#0c121e]/80 px-2.5 py-1.5">
              <div className="flex items-center gap-2">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500 shadow-[0_0_6px_rgba(52,211,153,0.9)]" />
                </span>
                <span className="font-mono-ui text-[9px] font-medium tracking-wider text-muted-foreground/80">
                  LIVE CLUSTER
                </span>
              </div>
              <span className="font-mono-ui text-[8px] font-semibold text-cyan-400/90 bg-cyan-950/60 border border-cyan-500/20 rounded px-1.5 py-0.5">
                13.1k NODES
              </span>
            </div>
          ) : (
            <div className="flex justify-center py-1">
              <span className="relative flex h-2 w-2" title="Cluster live · 13.1k nodes">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
            </div>
          )}
        </div>

        {/* Minimal Desktop Sidebar Collapse Toggle */}
        <button
          type="button"
          data-testid="button-collapse-sidebar"
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-2.5 top-[58px] hidden md:grid h-5 w-5 place-items-center rounded-full border border-[#232f44] bg-[#090d16] text-muted-foreground/80 shadow-md hover:text-white hover:border-cyan-500/60 z-50 transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={11} /> : <ChevronLeft size={11} />}
        </button>
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          data-testid="button-mobile-overlay"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-30 bg-black/70 backdrop-blur-sm md:hidden"
        />
      )}

      {/* ---------------------------------------------------------------------
          MAIN WRAPPER (Top Bar Header + Main Content Container)
      --------------------------------------------------------------------- */}
      <div
        className={`${
          collapsed ? 'md:pl-[64px]' : 'md:pl-[220px]'
        } flex-1 min-h-[100dvh] flex flex-col transition-[padding] duration-200 ease-out`}
      >
        {/* -------------------------------------------------------------------
            2. TOP HEADER (Minimal Terminal Command Bar)
        ------------------------------------------------------------------- */}
        <header className="sticky top-0 z-30 flex h-13 items-center justify-between border-b border-[#1a2232] bg-[#080b11]/85 backdrop-blur-md px-4 md:px-6">
          {/* Left: Current Page + Breadcrumb */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              data-testid="button-open-mobile-nav"
              onClick={() => setMobileOpen(true)}
              className="rounded p-1.5 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground md:hidden"
              aria-label="Open navigation"
            >
              <Menu size={18} />
            </button>

            <div className="flex items-center gap-2 min-w-0">
              <span className="font-mono-ui text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-400 shrink-0">
                {routeMeta.section}
              </span>
              <span className="text-muted-foreground/30 font-mono-ui text-[11px] shrink-0">/</span>
              <h1 className="text-[13px] font-semibold text-foreground tracking-tight truncate">
                {routeMeta.title}
              </h1>
              {routeMeta.detailId && (
                <>
                  <span className="text-muted-foreground/30 font-mono-ui text-[11px] shrink-0">/</span>
                  <span className="font-mono-ui text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/25 text-cyan-400 shrink-0 truncate max-w-[140px]">
                    {routeMeta.detailId}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Center: Global Entity / Evidence Search */}
          <div ref={searchContainerRef} className="flex-1 max-w-[420px] mx-4 relative hidden sm:block">
            <div className="relative flex items-center w-full h-[32px] rounded-md border border-[#202b3d] bg-[#0c121e]/90 hover:border-cyan-500/40 focus-within:border-cyan-500/80 focus-within:ring-1 focus-within:ring-cyan-500/30 transition-all px-2.5">
              <Search size={13} className="text-muted-foreground/60 shrink-0 mr-2" />
              <input
                ref={searchInputRef}
                type="text"
                data-testid="input-global-search"
                value={globalQuery}
                onChange={(e) => setGlobalQuery(e.target.value)}
                onFocus={() => setSearchFocused(true)}
                placeholder="Search entities, evidence, ghosts... (Press /)"
                className="w-full bg-transparent text-xs text-foreground placeholder:text-muted-foreground/45 outline-none border-none"
              />
              {globalQuery ? (
                <button
                  type="button"
                  onClick={() => setGlobalQuery('')}
                  className="p-0.5 text-muted-foreground hover:text-foreground"
                >
                  <X size={12} />
                </button>
              ) : (
                <kbd className="hidden md:inline-flex items-center font-mono-ui text-[9px] px-1.5 py-0.5 rounded border border-border/60 bg-muted/40 text-muted-foreground/60 shrink-0">
                  ⌘K
                </kbd>
              )}
            </div>

            {/* Interactive Search Dropdown */}
            {searchFocused && globalQuery.trim().length > 1 && (
              <div className="absolute left-0 right-0 top-10 z-50 overflow-hidden rounded-lg border border-[#223048] bg-[#0d1424] shadow-2xl backdrop-blur-md">
                <div className="border-b border-[#1b2538] px-3 py-2 flex items-center justify-between bg-[#080d18]">
                  <span className="font-mono-ui text-[9px] uppercase tracking-wider text-muted-foreground">
                    Search Results: <span className="text-cyan-400 font-semibold">{debouncedGlobalQuery}</span>
                  </span>
                  <span className="font-mono-ui text-[9px] text-muted-foreground/50">ESC to close</span>
                </div>

                <div className="max-h-72 overflow-y-auto p-1.5 divide-y divide-border/20">
                  {globalSearch.isLoading ? (
                    <div className="p-3 text-center font-mono-ui text-xs text-muted-foreground animate-pulse">
                      Querying knowledge graph index…
                    </div>
                  ) : globalSearch.isError ? (
                    <div className="p-3 text-center text-xs text-destructive">
                      Search index unavailable. Use Network Explorer directly.
                    </div>
                  ) : globalSearch.data?.length ? (
                    globalSearch.data.slice(0, 8).map((entity) => (
                      <Link
                        key={entity.id}
                        href={`/network?focus=${encodeURIComponent(entity.id)}`}
                        onClick={() => {
                          setSearchFocused(false);
                          setGlobalQuery('');
                        }}
                        className="flex items-center gap-3 rounded-md px-3 py-2 hover:bg-white/[0.05] transition-colors group"
                      >
                        <div className="grid h-7 w-7 shrink-0 place-items-center rounded bg-cyan-500/10 border border-cyan-500/25 font-mono-ui text-[10px] font-bold text-cyan-400 group-hover:border-cyan-400">
                          {(entity.name || entity.id).slice(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-xs font-semibold text-foreground group-hover:text-cyan-400 transition-colors">
                            {entity.name || entity.id}
                          </div>
                          <div className="flex items-center gap-2 font-mono-ui text-[9px] uppercase text-muted-foreground/70">
                            <span>{entity.type || entity.category || 'entity'}</span>
                            <span>·</span>
                            <span className="truncate">{entity.id}</span>
                          </div>
                        </div>
                        <ArrowRight size={12} className="text-muted-foreground/40 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-all" />
                      </Link>
                    ))
                  ) : (
                    <div className="p-4 text-center text-xs text-muted-foreground">
                      No matching records found for "{debouncedGlobalQuery}".
                    </div>
                  )}
                </div>

                <div className="border-t border-[#1b2538] p-2 bg-[#080d18] text-right">
                  <Link
                    href={`/search?q=${encodeURIComponent(debouncedGlobalQuery)}`}
                    onClick={() => setSearchFocused(false)}
                    className="inline-flex items-center gap-1 font-mono-ui text-[10px] text-cyan-400 hover:underline"
                  >
                    Open advanced search <ArrowRight size={11} />
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* Right: System Status, Notifications, User/Session */}
          <div className="flex items-center gap-2.5 shrink-0">
            {/* System Status Pill */}
            <div
              className="hidden sm:flex items-center gap-2 rounded-md border border-emerald-500/25 bg-emerald-500/5 px-2.5 py-1 text-[10px] font-mono-ui text-emerald-400"
              title="API connection active · 13,146 nodes in graph"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
              </span>
              <span className="tracking-wide font-semibold">SYS: NOMINAL</span>
              <span className="hidden xl:inline text-emerald-500/70 border-l border-emerald-500/20 pl-2">13.1k NODES</span>
            </div>

            {/* Notifications Menu */}
            <div ref={notificationsRef} className="relative">
              <button
                type="button"
                data-testid="button-notifications"
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                className="relative grid h-8 w-8 place-items-center rounded-md text-muted-foreground/80 hover:bg-white/[0.05] hover:text-foreground transition-colors"
                aria-label="Intelligence alerts"
              >
                <Bell size={15} />
                <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.9)] ring-2 ring-[#080b11]" />
              </button>

              {notificationsOpen && (
                <div className="absolute right-0 top-10 z-50 w-80 overflow-hidden rounded-lg border border-[#223048] bg-[#0d1424] shadow-2xl">
                  <div className="border-b border-[#1b2538] px-3.5 py-2.5 flex items-center justify-between bg-[#080d18]">
                    <div className="font-mono-ui text-[10px] font-semibold uppercase tracking-wider text-foreground">
                      Operational Feeds
                    </div>
                    <span className="font-mono-ui text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                      3 PENDING
                    </span>
                  </div>

                  <div className="divide-y divide-[#1b2538] text-xs">
                    <div className="p-3 hover:bg-white/[0.03] transition-colors">
                      <div className="flex items-center gap-1.5 text-cyan-400 font-medium">
                        <Sparkles size={13} />
                        <span>Ghost Hypothesis Flagged</span>
                      </div>
                      <p className="mt-1 text-muted-foreground text-[11px] leading-relaxed">
                        Intermediary candidate <span className="font-mono-ui text-foreground">e1e815f1</span> between Community 5 & 8 ready for review.
                      </p>
                      <div className="mt-1.5 flex items-center gap-2 font-mono-ui text-[9px] text-muted-foreground/60">
                        <span>Confidence: 0.529</span>
                        <span>·</span>
                        <Link href="/ghosts" onClick={() => setNotificationsOpen(false)} className="text-cyan-400 hover:underline">
                          View details
                        </Link>
                      </div>
                    </div>

                    <div className="p-3 hover:bg-white/[0.03] transition-colors">
                      <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                        <CheckCircle2 size={13} />
                        <span>XAI Findings Verified</span>
                      </div>
                      <p className="mt-1 text-muted-foreground text-[11px] leading-relaxed">
                        Integrity contract pass: 30 evidence-grounded claims anchored.
                      </p>
                      <div className="mt-1.5 font-mono-ui text-[9px] text-muted-foreground/60">
                        <Link href="/findings" onClick={() => setNotificationsOpen(false)} className="text-cyan-400 hover:underline">
                          Review findings register
                        </Link>
                      </div>
                    </div>

                    <div className="p-3 hover:bg-white/[0.03] transition-colors">
                      <div className="flex items-center gap-1.5 text-amber-400 font-medium">
                        <Zap size={13} />
                        <span>Simulation Cached</span>
                      </div>
                      <p className="mt-1 text-muted-foreground text-[11px] leading-relaxed">
                        Removal scenario for node <span className="font-mono-ui text-foreground">06a1573c</span> baseline ready.
                      </p>
                      <div className="mt-1.5 font-mono-ui text-[9px] text-muted-foreground/60">
                        <Link href="/simulation" onClick={() => setNotificationsOpen(false)} className="text-cyan-400 hover:underline">
                          Open sandbox
                        </Link>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-[#1b2538] p-2 bg-[#080d18] text-center">
                    <button
                      type="button"
                      onClick={() => setNotificationsOpen(false)}
                      className="font-mono-ui text-[10px] text-muted-foreground hover:text-foreground"
                    >
                      Dismiss alerts
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="h-4 w-px bg-[#1a2232] hidden sm:block" />

            {/* User / Session Badge */}
            <div className="flex items-center gap-2 pl-1">
              <div className="grid h-7 w-7 place-items-center rounded border border-cyan-500/35 bg-cyan-500/10 font-mono-ui text-[10px] font-bold text-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.15)]">
                AR
              </div>
              <div className="hidden lg:block leading-none text-left">
                <div className="text-[11px] font-medium text-foreground">A. Rivera</div>
                <div className="font-mono-ui text-[8px] text-muted-foreground/70 mt-0.5 tracking-wider">TS//SCI · S-8902</div>
              </div>
            </div>
          </div>
        </header>

        {/* -------------------------------------------------------------------
            3. MAIN CONTENT CONTAINER (Generous but Controlled Spacing)
            4. GLOBAL PAGE TRANSITIONS (Smooth Keyframe Animation)
        ------------------------------------------------------------------- */}
        <main className="flex-1 p-5 md:p-6 lg:p-7 max-w-[1720px] mx-auto w-full transition-all">
          <div key={location} className="animate-terminal-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   5. NAVIGATION STATES (Subtle Illuminated State NavItem)
--------------------------------------------------------------------------- */
export function NavItem({ href, label, icon: Icon, active, collapsed }) {
  return (
    <Link
      href={href}
      data-testid={`link-nav-${label.toLowerCase().replace(/\s+/g, '-')}`}
      className={`sg-nav-item ${active ? 'sg-nav-item-active' : ''} ${
        collapsed ? 'sg-tooltip justify-center px-1.5' : ''
      }`}
      data-tooltip={collapsed ? label : undefined}
      aria-current={active ? 'page' : undefined}
    >
      <Icon
        size={15}
        strokeWidth={active ? 2.1 : 1.75}
        className={`sg-nav-icon shrink-0 ${active ? 'text-cyan-400' : 'text-muted-foreground/75'}`}
      />
      <span className={`truncate text-xs ${collapsed ? 'sr-only' : ''}`}>
        {label}
      </span>
      {!collapsed && active && (
        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.9)]" />
      )}
    </Link>
  );
}

/* ---------------------------------------------------------------------------
   Preserved Workstation Primitives (Compatible with all application pages)
--------------------------------------------------------------------------- */
export function SectionHeading({ eyebrow, title, description, action }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-[#1a2232]/80 pb-4">
      <div>
        {eyebrow && (
          <div className="mb-1.5 font-mono-ui text-[9px] uppercase tracking-[0.2em] text-cyan-400 font-semibold flex items-center gap-1.5">
            <span className="h-1 w-1 rounded-full bg-cyan-400 shadow-[0_0_4px_rgba(34,211,238,0.8)]" />
            {eyebrow}
          </div>
        )}
        <h2 className="text-xl font-semibold tracking-tight md:text-[23px] text-white">{title}</h2>
        {description && <p className="mt-1 max-w-2xl text-xs text-muted-foreground/80 leading-relaxed">{description}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

export function Panel({ children, className = '', title, subtitle, action }) {
  return (
    <section className={`rounded-lg border border-[#1a2333] bg-[#0c121e]/85 backdrop-blur-sm shadow-sm ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between border-b border-[#182130] px-5 py-3.5">
          <div>
            {title && <h3 className="text-xs font-semibold tracking-tight text-white">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-[11px] text-muted-foreground/75">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Metric({ label, value, detail, accent = 'primary', icon: Icon }) {
  const colors = {
    primary: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-400',
    accent: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
    blue: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
    rose: 'border-rose-500/30 bg-rose-500/10 text-rose-400',
  };
  return (
    <div className="rounded-lg border border-[#1a2333] bg-[#0c121e]/90 p-4 transition-all hover:border-cyan-500/35 hover:shadow-[0_0_15px_rgba(34,211,238,0.06)]">
      <div className="flex items-start justify-between">
        <div className="font-mono-ui text-[9px] uppercase tracking-[0.16em] text-muted-foreground/75">
          {label}
        </div>
        {Icon && (
          <div className={`grid h-7 w-7 place-items-center rounded-md border ${colors[accent] || colors.primary}`}>
            <Icon size={14} />
          </div>
        )}
      </div>
      <div className="mt-2 text-2xl font-bold tracking-tight text-white font-mono-ui">{value}</div>
      {detail && <div className="mt-1 text-[11px] text-muted-foreground/70">{detail}</div>}
    </div>
  );
}

export function EmptyState({ title, description, icon: Icon = Database }) {
  return (
    <div className="flex min-h-[170px] flex-col items-center justify-center px-6 py-9 text-center">
      <div className="mb-2.5 grid h-10 w-10 place-items-center rounded-lg border border-[#1f2b3e] bg-[#0f1624] text-muted-foreground">
        <Icon size={18} />
      </div>
      <h3 className="text-xs font-semibold text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-[11px] leading-5 text-muted-foreground/75">{description}</p>
    </div>
  );
}

export function LoadingRows({ count = 4 }) {
  return (
    <div className="space-y-2.5 p-5">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="flex animate-pulse items-center gap-3">
          <div className="h-7 w-7 rounded-md bg-[#162030]" />
          <div className="flex-1 space-y-2">
            <div className="h-2.5 w-1/3 rounded bg-[#162030]" />
            <div className="h-2 w-1/2 rounded bg-[#162030]" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ErrorState({ onRetry }) {
  return (
    <div className="flex min-h-[170px] flex-col items-center justify-center px-6 py-9 text-center">
      <div className="mb-2.5 grid h-10 w-10 place-items-center rounded-lg border border-destructive/30 bg-destructive/10 text-destructive">
        <Globe2 size={18} />
      </div>
      <h3 className="text-xs font-semibold text-foreground">Signal unavailable</h3>
      <p className="mt-1 max-w-sm text-[11px] leading-5 text-muted-foreground">
        The graph service did not return a response. Check connection and try again.
      </p>
      {onRetry && (
        <Button data-testid="button-retry" variant="primary" onClick={onRetry} className="mt-3">
          Retry request
        </Button>
      )}
    </div>
  );
}

export function Pill({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'text-muted-foreground bg-muted/60 border-border/60',
    teal: 'text-cyan-400 bg-cyan-950/50 border-cyan-500/30',
    amber: 'text-amber-400 bg-amber-950/50 border-amber-500/30',
    blue: 'text-blue-400 bg-blue-950/50 border-blue-500/30',
    rose: 'text-rose-400 bg-rose-950/50 border-rose-500/30',
    accent: 'text-purple-400 bg-purple-950/50 border-purple-500/30',
    success: 'text-emerald-400 bg-emerald-950/50 border-emerald-500/30',
  };
  return (
    <span
      className={`inline-flex items-center gap-1 border rounded px-1.5 py-0.5 font-mono-ui text-[9px] font-semibold uppercase tracking-wider ${
        tones[tone] || tones.neutral
      }`}
    >
      {children}
    </span>
  );
}

export function PageShell({ children }) {
  return <div className="animate-terminal-in">{children}</div>;
}

export function Button({ children, variant = 'default', className = '', type = 'button', ...props }) {
  return (
    <button
      type={type}
      className={`sg-button ${
        variant === 'primary' ? 'sg-button-primary' : variant === 'quiet' ? 'sg-button-quiet' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function StatusIndicator({ label, status = 'info', className = '' }) {
  return (
    <span className={`sg-status sg-status-${status} ${className}`}>
      <span className="sg-status-dot" aria-hidden="true" />
      {label}
    </span>
  );
}

export function ConfidenceIndicator({ value, label = 'confidence' }) {
  const normalized = Math.max(0, Math.min(1, Number(value) || 0));
  return (
    <div className="sg-confidence" aria-label={`${label}: ${Math.round(normalized * 100)} percent`}>
      <div className="flex items-center justify-between font-mono-ui text-[9px] uppercase tracking-wide text-muted-foreground">
        <span>{label}</span>
        <span className="text-cyan-400 font-semibold">{Math.round(normalized * 100)}%</span>
      </div>
      <div className="sg-confidence-track">
        <div className="sg-confidence-fill" style={{ width: `${normalized * 100}%` }} />
      </div>
    </div>
  );
}

export function TextInput({ className = '', ...props }) {
  return <input className={`sg-input ${className}`} {...props} />;
}

export function SelectField({ className = '', children, ...props }) {
  return (
    <select className={`sg-select ${className}`} {...props}>
      {children}
    </select>
  );
}

export function Tooltip({ label, children, className = '' }) {
  return (
    <span className={`sg-tooltip ${className}`} data-tooltip={label}>
      {children}
    </span>
  );
}

export function Drawer({ open, title, onClose, children, className = '' }) {
  if (!open) return null;
  return (
    <>
      <button type="button" aria-label="Close drawer" className="sg-drawer-backdrop" onClick={onClose} />
      <aside className={`sg-drawer ${className}`} aria-label={title}>
        <div className="sg-panel-header flex items-center justify-between px-5 py-3.5">
          <h2 className="text-xs font-semibold text-white">{title}</h2>
          <Button variant="quiet" aria-label="Close drawer" onClick={onClose}>
            ×
          </Button>
        </div>
        {children}
      </aside>
    </>
  );
}
