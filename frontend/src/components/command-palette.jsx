/**
 * frontend/src/components/command-palette.jsx
 * --------------------------------------------
 * Global Command Palette (Cmd+K / Ctrl+K / /).
 * Fast keyboard-driven command & search interface for the workstation.
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation } from 'wouter';
import {
    Search, LayoutDashboard, Network, Users, Clock, FileText, Brain,
    AlertTriangle, BarChart3, Zap, Waypoints, BookOpen, ClipboardList,
    Upload, Settings, Shield, ArrowRight, CornerDownLeft, Filter,
    Layers, DollarSign, Database, Activity, Sparkles, FolderOpen, AlertCircle
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { useGlobalSearch } from '@/api/xai';

const COMMANDS = [
    { id: 'desk', label: 'Investigation Desk', desc: 'Case overview & operational brief', path: '/', icon: LayoutDashboard, section: 'NAVIGATION' },
    { id: 'network', label: 'Network Canvas', desc: 'Link analysis & graph explorer', path: '/network', icon: Network, section: 'NAVIGATION' },
    { id: 'entities', label: 'Entity Directory', desc: 'Resolved entities & 360 profiles', path: '/entities', icon: Users, section: 'NAVIGATION' },
    { id: 'timeline', label: 'Timeline Replay', desc: 'Temporal event stream & replay', path: '/timeline', icon: Clock, section: 'NAVIGATION' },
    { id: 'evidence', label: 'Evidence Register', desc: 'Multi-source evidence provenance', path: '/evidence', icon: FileText, section: 'NAVIGATION' },
    { id: 'hypotheses', label: 'Hypotheses Engine', desc: 'Structured hypotheses & dispositions', path: '/findings', icon: Brain, section: 'NAVIGATION' },
    { id: 'anomalies', label: 'Anomalies & Ghosts', desc: 'Hidden intermediary candidates', path: '/ghosts', icon: AlertTriangle, section: 'NAVIGATION' },
    { id: 'communities', label: 'Communities & Evolution', desc: 'Louvain clusters & bridge roles', path: '/communities', icon: Waypoints, section: 'NAVIGATION' },
    { id: 'financial', label: 'Financial Flow Trace', desc: 'Account graph & money trail', path: '/financial', icon: DollarSign, section: 'NAVIGATION' },
    { id: 'gaps', label: 'Investigative Gaps', desc: 'Unresolved links & missing evidence', path: '/gaps', icon: AlertCircle, section: 'NAVIGATION' },
    { id: 'crosscase', label: 'Cross-Case Intelligence', desc: 'Entity reuse across cases', path: '/cross-case', icon: FolderOpen, section: 'NAVIGATION' },
    { id: 'simulation', label: 'Counterfactual Sandbox', desc: 'Node removal & network resilience', path: '/simulation', icon: Zap, section: 'NAVIGATION' },
    { id: 'analytics', label: 'Analysis Lab', desc: 'Centrality & graph metrics', path: '/analytics', icon: BarChart3, section: 'NAVIGATION' },
    { id: 'models', label: 'Model Registry & Benchmark', desc: 'Model cards & measured metrics', path: '/models', icon: Activity, section: 'NAVIGATION' },
    { id: 'reports', label: 'Intelligence Reports', desc: 'Evidence-grounded dossiers', path: '/dossiers', icon: BookOpen, section: 'NAVIGATION' },
    { id: 'judge', label: 'Judge / Presentation View', desc: 'Structured 10-step demo flow', path: '/judge', icon: Sparkles, section: 'NAVIGATION' },
    { id: 'audit', label: 'Audit Trail', desc: 'Investigator action log', path: '/audit', icon: ClipboardList, section: 'NAVIGATION' },
    { id: 'pipeline', label: 'Data Ingestion', desc: 'Pipeline status & execution', path: '/pipeline', icon: Upload, section: 'NAVIGATION' },
    { id: 'settings', label: 'Settings', desc: 'Workstation preferences', path: '/settings', icon: Settings, section: 'NAVIGATION' },
];

export function CommandPalette() {
    const [, setLocation] = useLocation();
    const { commandPaletteOpen, setCommandPaletteOpen, setSelectedEntity } = useInvestigation();
    const [query, setQuery] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef(null);

    // Live global search
    const { data: searchResults } = useGlobalSearch({ q: query }, { enabled: query.trim().length >= 2 });

    const filteredCommands = useMemo(() => {
        if (!query.trim()) return COMMANDS;
        const q = query.toLowerCase();
        return COMMANDS.filter(c =>
            c.label.toLowerCase().includes(q) ||
            c.desc.toLowerCase().includes(q) ||
            c.section.toLowerCase().includes(q)
        );
    }, [query]);

    // Combined items for selection
    const allItems = useMemo(() => {
        const items = [...filteredCommands];
        if (searchResults?.results?.length) {
            for (const r of searchResults.results.slice(0, 6)) {
                items.push({
                    id: `search-${r.id}`,
                    label: r.label || r.id,
                    desc: `${r.type || 'ENTITY'} · ${r.community_id != null ? `C${r.community_id}` : 'Graph Node'}`,
                    icon: Users,
                    section: 'GLOBAL SEARCH',
                    rawEntity: r,
                });
            }
        }
        return items;
    }, [filteredCommands, searchResults]);

    useEffect(() => {
        if (commandPaletteOpen) {
            setQuery('');
            setSelectedIndex(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [commandPaletteOpen]);

    useEffect(() => {
        setSelectedIndex(0);
    }, [query]);

    const handleSelect = (item) => {
        if (!item) return;
        setCommandPaletteOpen(false);
        if (item.path) {
            setLocation(item.path);
        } else if (item.rawEntity) {
            setSelectedEntity(item.rawEntity);
            setLocation(`/network?focus=${encodeURIComponent(item.rawEntity.id)}`);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex(prev => (prev + 1) % Math.max(allItems.length, 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex(prev => (prev - 1 + allItems.length) % Math.max(allItems.length, 1));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (allItems[selectedIndex]) {
                handleSelect(allItems[selectedIndex]);
            }
        }
    };

    if (!commandPaletteOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] bg-black/60 backdrop-blur-sm"
             onClick={() => setCommandPaletteOpen(false)}>
            <div className="relative w-full max-w-2xl bg-bg-panel border border-border-default rounded-md shadow-2xl overflow-hidden animate-slide-up flex flex-col"
                 style={{ maxHeight: '70vh' }}
                 onClick={e => e.stopPropagation()}>
                {/* Search Bar */}
                <div className="flex items-center gap-3 px-4 h-11 border-b border-border-default bg-bg-surface">
                    <Search size={15} className="text-fg-muted shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Type a command or search entities, cases, hypotheses, evidence..."
                        className="flex-1 bg-transparent text-[13px] text-fg-primary placeholder:text-fg-faint outline-none font-sans"
                    />
                    <kbd className="tp-kbd text-[10px]">ESC</kbd>
                </div>

                {/* Command & Result List */}
                <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                    {allItems.length === 0 ? (
                        <div className="py-8 text-center text-fg-faint text-xs font-mono">
                            NO COMMANDS OR ENTITIES MATCHED
                        </div>
                    ) : (
                        allItems.map((item, idx) => {
                            const isSelected = idx === selectedIndex;
                            const Icon = item.icon || ArrowRight;
                            return (
                                <div
                                    key={item.id}
                                    onClick={() => handleSelect(item)}
                                    onMouseEnter={() => setSelectedIndex(idx)}
                                    className={`flex items-center justify-between px-3 py-2 rounded cursor-pointer transition-colors text-[12px]
                                        ${isSelected ? 'bg-primary/15 text-fg-primary' : 'text-fg-secondary hover:bg-bg-hover'}`}
                                >
                                    <div className="flex items-center gap-2.5 min-w-0">
                                        <Icon size={14} className={isSelected ? 'text-primary' : 'text-fg-muted'} />
                                        <div className="min-w-0">
                                            <div className="font-medium text-fg-primary truncate">{item.label}</div>
                                            <div className="text-[10px] text-fg-muted truncate">{item.desc}</div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0 ml-3">
                                        <span className="tp-badge tp-badge-neutral text-[9px]">{item.section}</span>
                                        {isSelected && <CornerDownLeft size={12} className="text-fg-muted" />}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Footer hints */}
                <div className="flex items-center justify-between px-3 py-1.5 border-t border-border-subtle bg-bg-surface text-[10px] font-mono text-fg-faint">
                    <div className="flex items-center gap-3">
                        <span>↑↓ navigate</span>
                        <span>↵ select</span>
                        <span>esc close</span>
                    </div>
                    <span>THUPPARIVU WORKSTATION</span>
                </div>
            </div>
        </div>
    );
}
