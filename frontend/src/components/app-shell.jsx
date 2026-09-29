/**
 * AppShell — SentinelGraph Investigative Workbench
 * Navy sidebar + topbar + footer with light content canvas.
 * Navigation groups per UX spec §3.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'wouter';
import {
    LayoutGrid, FolderOpen, Network, Users,
    Brain, DollarSign, Clock, Zap,
    FileText, BookOpen, MessageSquare,
    Activity, Settings, ChevronLeft, ChevronRight,
    Search, Bell, User, ChevronDown, HelpCircle
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { GLOBAL_CASES } from '@/state/synthetic-case-data';
import { CommandPalette } from '@/components/command-palette';

export { formatNumber, formatTimestamp, formatShortDate } from '@/utils/format';

/* ── Legacy Compat Exports ── */
export const getConfidenceColor = (conf) => {
    if (typeof conf === 'number') {
        if (conf >= 80) return 'hsl(var(--green-fg))';
        if (conf >= 50) return 'hsl(var(--blue-fg))';
        return 'hsl(var(--amber-fg))';
    }
    if (typeof conf === 'string') {
        const c = conf.toLowerCase();
        if (c === 'high') return 'hsl(var(--green-fg))';
        if (c === 'moderate') return 'hsl(var(--blue-fg))';
        return 'hsl(var(--amber-fg))';
    }
    return 'hsl(var(--amber-fg))';
};
export const getEntityTypeColor = () => 'hsl(var(--primary))';
export const ALL_NAV_ITEMS = [];

/* ── Navigation per spec §3 ── */
export const NAV_SECTIONS = [
    {
        id: 'investigate', label: 'INVESTIGATE', items: [
            { path: '/', label: 'Overview', icon: LayoutGrid },
            { path: '/cases', label: 'Cases', icon: FolderOpen },
            { path: '/network', label: 'Network', icon: Network },
            { path: '/entities', label: 'Entities', icon: Users },
        ]
    },
    {
        id: 'analyse', label: 'ANALYSE', items: [
            { path: '/findings', label: 'Findings', icon: Brain },
            { path: '/financial', label: 'Fund tracing', icon: DollarSign },
            { path: '/timeline', label: 'Timeline', icon: Clock },
            { path: '/simulation', label: 'Scenarios', icon: Zap },
        ]
    },
    {
        id: 'evidence', label: 'EVIDENCE', items: [
            { path: '/evidence', label: 'Evidence register', icon: FileText },
        ]
    },
    {
        id: 'output', label: 'OUTPUT', items: [
            { path: '/reports', label: 'Dossiers', icon: BookOpen },
            { path: '/copilot', label: 'Copilot', icon: MessageSquare },
        ]
    },
    {
        id: 'admin', label: 'ADMINISTRATION', items: [
            { path: '/audit', label: 'Audit & pipeline', icon: Activity },
            { path: '/settings', label: 'Settings', icon: Settings },
        ]
    },
];

function CaseSwitcher() {
    const { activeCase, setActiveCase } = useInvestigation();
    const [open, setOpen] = useState(false);

    const handleSelect = (c) => {
        setActiveCase(c);
        setOpen(false);
    };

    return (
        <div className="relative">
            <button
                className="flex items-center gap-2 px-2 py-1 rounded text-[12px] hover:bg-[hsl(var(--chrome-bg-hover))] transition-colors"
                onClick={() => setOpen(!open)}
            >
                <span className="font-mono font-medium text-[hsl(var(--chrome-fg))]">{activeCase.id}</span>
                <ChevronDown size={12} className="text-[hsl(var(--chrome-fg-faint))]" />
            </button>
            {open && (
                <>
                    <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
                    <div className="absolute top-full left-0 mt-1 w-72 bg-[hsl(var(--bg-surface))] border border-[hsl(var(--border-default))] rounded-md shadow-lg z-50 overflow-hidden">
                        <div className="px-3 py-2 text-[10px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider border-b border-[hsl(var(--border-subtle))]">
                            Switch case workspace
                        </div>
                        {GLOBAL_CASES.map(c => (
                            <button
                                key={c.id}
                                className={`w-full text-left px-3 py-2 hover:bg-[hsl(var(--bg-hover))] transition-colors border-b border-[hsl(var(--border-subtle))] ${c.id === activeCase.id ? 'bg-[hsl(var(--bg-selected))]' : ''}`}
                                onClick={() => handleSelect(c)}
                            >
                                <div className="flex items-center justify-between">
                                    <span className="font-mono text-[12px] font-medium text-[hsl(var(--fg-primary))]">{c.id}</span>
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${c.status === 'ACTIVE' ? 'bg-[hsl(var(--green-bg))] text-[hsl(var(--green-fg))]' : 'bg-[hsl(var(--amber-bg))] text-[hsl(var(--amber-fg))]'}`}>
                                        {c.status}
                                    </span>
                                </div>
                                <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-0.5 truncate">{c.title}</div>
                                <div className="text-[10px] text-[hsl(var(--fg-faint))] mt-0.5">{c.lead} · {c.entities_count.toLocaleString()} entities</div>
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

export function AppShell({ children }) {
    const [location] = useLocation();
    const { activeCase, commandPaletteOpen, setCommandPaletteOpen } = useInvestigation();
    const [collapsed, setCollapsed] = useState(false);
    const [shortcutHelpOpen, setShortcutHelpOpen] = useState(false);

    // Keyboard shortcuts per spec §3
    useEffect(() => {
        let gPending = false;
        let gTimer = null;

        function handleKeyDown(e) {
            const tag = document.activeElement?.tagName;
            const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || document.activeElement?.isContentEditable;

            // Ctrl/Cmd+K — command palette (always)
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setCommandPaletteOpen(prev => !prev);
                return;
            }

            // Esc — close drawer/dialog
            if (e.key === 'Escape') {
                setCommandPaletteOpen(false);
                setShortcutHelpOpen(false);
                return;
            }

            // Don't trigger shortcuts in inputs
            if (isInput) return;

            // Shift+? — shortcut help
            if (e.key === '?' && e.shiftKey) {
                e.preventDefault();
                setShortcutHelpOpen(prev => !prev);
                return;
            }

            // E — export current view
            if (e.key === 'e' || e.key === 'E') {
                // Handled by individual pages
                return;
            }

            // G then <key> navigation
            if (e.key === 'g' || e.key === 'G') {
                if (!gPending) {
                    gPending = true;
                    gTimer = setTimeout(() => { gPending = false; }, 800);
                    return;
                }
            }

            if (gPending) {
                gPending = false;
                clearTimeout(gTimer);
                const nav = { n: '/network', f: '/findings' };
                const target = nav[e.key.toLowerCase()];
                if (target) {
                    e.preventDefault();
                    window.location.hash = target;
                }
            }
        }

        window.addEventListener('keydown', handleKeyDown);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            clearTimeout(gTimer);
        };
    }, [setCommandPaletteOpen]);

    return (
        <div className="flex flex-col h-screen overflow-hidden">
            {/* Top bar */}
            <div className="sg-topbar">
                <div className="flex items-center gap-3 flex-1">
                    <span className="text-[13px] font-semibold text-[hsl(var(--chrome-fg))]">SentinelGraph</span>
                    <span className="text-[hsl(var(--chrome-border))]">|</span>
                    <CaseSwitcher />
                </div>
                <button
                    className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] text-[hsl(var(--chrome-fg-faint))] hover:text-[hsl(var(--chrome-fg))] hover:bg-[hsl(var(--chrome-bg-hover))] transition-colors"
                    onClick={() => setCommandPaletteOpen(true)}
                >
                    <Search size={13} />
                    <span className="font-mono text-[10px] px-1 py-0.5 rounded bg-[hsl(var(--chrome-bg-hover))]">⌘K</span>
                </button>
                <button className="relative p-1.5 rounded text-[hsl(var(--chrome-fg-faint))] hover:text-[hsl(var(--chrome-fg))] hover:bg-[hsl(var(--chrome-bg-hover))] transition-colors">
                    <Bell size={15} />
                    <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-[hsl(var(--red))] text-white text-[9px] font-bold rounded-full flex items-center justify-center">3</span>
                </button>
                <div className="flex items-center gap-2 pl-3 border-l border-[hsl(var(--chrome-border))]">
                    <div className="w-6 h-6 rounded-full bg-[hsl(var(--chrome-bg-hover))] flex items-center justify-center">
                        <User size={13} className="text-[hsl(var(--chrome-fg-muted))]" />
                    </div>
                    <div className="text-right">
                        <div className="text-[11px] font-medium text-[hsl(var(--chrome-fg))]">A. Rao</div>
                        <div className="text-[9px] text-[hsl(var(--chrome-fg-faint))]">Lead analyst · Editor</div>
                    </div>
                </div>
            </div>

            {/* Body */}
            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <nav className={`sg-sidebar ${collapsed ? 'collapsed' : ''}`}>
                    <div className="flex-1 overflow-y-auto py-2">
                        {NAV_SECTIONS.map(section => (
                            <div key={section.id}>
                                {!collapsed && (
                                    <div className="sg-nav-group-label">{section.label}</div>
                                )}
                                {section.items.map(item => {
                                    const isActive = location === item.path || (item.path !== '/' && location.startsWith(item.path));
                                    return (
                                        <Link key={item.path} href={item.path}>
                                            <div className={`sg-nav-item ${isActive ? 'active' : ''}`}>
                                                <item.icon size={15} />
                                                {!collapsed && <span>{item.label}</span>}
                                            </div>
                                        </Link>
                                    );
                                })}
                            </div>
                        ))}
                    </div>
                    <div className="border-t border-[hsl(var(--chrome-border))] py-1">
                        <button
                            className="sg-nav-item w-full"
                            onClick={() => setCollapsed(!collapsed)}
                            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                        >
                            {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
                            {!collapsed && <span className="text-[11px]">Collapse</span>}
                        </button>
                    </div>
                </nav>

                {/* Content */}
                <main className="flex-1 overflow-auto bg-[hsl(var(--bg-root))]">
                    {children}
                </main>
            </div>

            {/* Footer */}
            <footer className="sg-footer">
                <span>UTC</span>
                <span>·</span>
                <span>Data as of 26 Sep 2026, 04:58 UTC</span>
                <span>·</span>
                <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[hsl(var(--green))]" style={{ animation: 'pulse-dot 2s infinite' }} />
                    {activeCase.pipeline} {activeCase.pipeline_state}
                </span>
                <span>·</span>
                <span>Synthetic data — not derived from real persons or transactions</span>
                <div className="flex-1" />
                <button
                    className="hover:text-[hsl(var(--chrome-fg-muted))] transition-colors"
                    onClick={() => setShortcutHelpOpen(true)}
                    title="Keyboard shortcuts (Shift+?)"
                >
                    <HelpCircle size={12} />
                </button>
            </footer>

            {/* Command palette */}
            {commandPaletteOpen && <CommandPalette />}

            {/* Shortcut help dialog */}
            {shortcutHelpOpen && (
                <div className="sg-overlay" onClick={() => setShortcutHelpOpen(false)}>
                    <div className="sg-dialog p-5" onClick={e => e.stopPropagation()}>
                        <div className="text-[14px] font-semibold mb-4">Keyboard shortcuts</div>
                        <div className="space-y-2 text-[12px]">
                            {[
                                ['⌘K / Ctrl+K', 'Command palette'],
                                ['G then N', 'Go to Network'],
                                ['G then F', 'Go to Findings'],
                                ['J / K', 'Navigate list items'],
                                ['Enter', 'Open selected row'],
                                ['E', 'Export current view'],
                                ['Esc', 'Close drawer / dialog'],
                                ['Shift+?', 'This help'],
                            ].map(([key, desc]) => (
                                <div key={key} className="flex items-center justify-between">
                                    <span className="text-[hsl(var(--fg-secondary))]">{desc}</span>
                                    <kbd className="font-mono text-[11px] px-1.5 py-0.5 bg-[hsl(var(--bg-hover))] border border-[hsl(var(--border-default))] rounded">{key}</kbd>
                                </div>
                            ))}
                        </div>
                        <button className="sg-btn sg-btn-ghost mt-4 w-full justify-center" onClick={() => setShortcutHelpOpen(false)}>Close</button>
                    </div>
                </div>
            )}
        </div>
    );
}
