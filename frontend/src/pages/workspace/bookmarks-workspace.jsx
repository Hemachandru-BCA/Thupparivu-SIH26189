/**
 * frontend/src/pages/workspace/bookmarks-workspace.jsx
 * ---------------------------------------------------
 * Bookmarks / My Findings — P0: Part 16.
 *
 * The investigator's working set. Bookmarked entities, hypotheses,
 * and notes, with links to navigate directly to the relevant context.
 */

import React, { useMemo, useState } from 'react';
import { useLocation } from 'wouter';
import {
    Bookmark, BookmarkCheck, ExternalLink, Trash2, Search, Filter, Users
} from 'lucide-react';
import { useInvestigation } from '@/state/investigation-context';
import { getEntityTypeColor } from '@/components/app-shell';

const TYPE_ICONS = {
    ENTITY: Users,
    HYPOTHESIS: Bookmark,
    EVIDENCE: Bookmark,
    CASE: Bookmark,
};

function BookmarkRow({ item, onNavigate, onRemove }) {
    const Icon = TYPE_ICONS[item.type] || Bookmark;
    return (
        <div className="p-3 flex items-start gap-3 border-b border-border-subtle last:border-b-0 hover:bg-bg-hover transition-colors">
            <div
                className="w-8 h-8 rounded flex items-center justify-center shrink-0"
                style={{ background: getEntityTypeColor(item.type || 'PERSON') + '20', border: `1px solid ${getEntityTypeColor(item.type || 'PERSON')}` }}
            >
                <Icon size={14} style={{ color: getEntityTypeColor(item.type || 'PERSON') }} />
            </div>
            <div className="flex-1 min-w-0">
                <div className="text-[11px] font-semibold text-fg-primary truncate">{item.title || item.refId}</div>
                <div className="text-[9px] font-mono text-fg-faint mt-0.5">{item.refId}</div>
                {item.note && (
                    <div className="text-[10px] text-fg-secondary mt-1 italic">"{item.note}"</div>
                )}
                <div className="text-[8px] font-mono text-fg-faint mt-1">
                    Added {item.added_at ? new Date(item.added_at).toLocaleString() : '—'}
                </div>
            </div>
            <div className="flex items-center gap-1 shrink-0 pt-0.5">
                <button
                    onClick={() => onNavigate(item)}
                    className="tp-btn h-5 text-[9px] px-2"
                    title="Open in context"
                >
                    <ExternalLink size={10} />
                </button>
                <button
                    onClick={() => onRemove(item)}
                    className="tp-btn-ghost p-1 text-fg-muted hover:text-red"
                    title="Remove bookmark"
                >
                    <Trash2 size={12} />
                </button>
            </div>
        </div>
    );
}

export default function BookmarksWorkspace() {
    const [, setLocation] = useLocation();
    const { bookmarks, toggleBookmark } = useInvestigation();
    const [filter, setFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('ALL');

    const filtered = useMemo(() => {
        let result = bookmarks;
        if (typeFilter !== 'ALL') {
            result = result.filter(b => b.type === typeFilter);
        }
        if (filter) {
            const q = filter.toLowerCase();
            result = result.filter(b =>
                (b.title || '').toLowerCase().includes(q) ||
                (b.refId || '').toLowerCase().includes(q) ||
                (b.note || '').toLowerCase().includes(q)
            );
        }
        return result;
    }, [bookmarks, typeFilter, filter]);

    const handleNavigate = (item) => {
        if (item.type === 'ENTITY') {
            setLocation(`/entity/${encodeURIComponent(item.refId)}`);
        } else if (item.type === 'HYPOTHESIS') {
            setLocation(`/findings/${encodeURIComponent(item.refId)}`);
        } else if (item.type === 'CASE') {
            setLocation('/cases');
        } else {
            setLocation('/evidence');
        }
    };

    const typeCounts = useMemo(() => {
        const counts = { ALL: bookmarks.length };
        bookmarks.forEach(b => { counts[b.type] = (counts[b.type] || 0) + 1; });
        return counts;
    }, [bookmarks]);

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4 max-w-[1200px] mx-auto animate-fade-in">
            {/* Header */}
            <div className="tp-panel p-3.5 bg-bg-panel flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <Bookmark size={16} className="text-amber" />
                        <span className="text-[14px] font-bold text-fg-primary">MY FINDINGS</span>
                        <span className="tp-badge tp-badge-amber">{bookmarks.length}</span>
                    </div>
                    <p className="text-[10px] text-fg-faint mt-0.5">Bookmarked entities, hypotheses, and notes — the investigator's working set.</p>
                </div>
            </div>

            {/* Filters */}
            <div className="tp-panel p-2.5 flex items-center gap-3">
                <div className="relative flex-1 max-w-xs">
                    <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint" />
                    <input
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        placeholder="Filter bookmarks…"
                        className="tp-input pl-7 h-6 text-[10px]"
                    />
                </div>
                <div className="flex gap-1">
                    {['ALL', 'ENTITY', 'HYPOTHESIS', 'CASE', 'EVIDENCE'].map(type => (
                        <button
                            key={type}
                            onClick={() => setTypeFilter(type)}
                            className={`tp-badge text-[9px] cursor-pointer transition-colors ${
                                typeFilter === type ? 'tp-badge-amber' : 'tp-badge-neutral'
                            }`}
                        >
                            {type} ({typeCounts[type] || 0})
                        </button>
                    ))}
                </div>
            </div>

            {/* Bookmark List */}
            <div className="tp-panel">
                {filtered.length > 0 ? (
                    <div className="max-h-[600px] overflow-y-auto">
                        {filtered.map(item => (
                            <BookmarkRow
                                key={item.id || item.refId}
                                item={item}
                                onNavigate={handleNavigate}
                                onRemove={(it) => toggleBookmark({ refId: it.refId })}
                            />
                        ))}
                    </div>
                ) : (
                    <div className="p-8 text-center space-y-2">
                        <Bookmark size={24} className="mx-auto text-fg-faint" />
                        <div className="text-[12px] font-semibold text-fg-secondary">No bookmarks yet</div>
                        <p className="text-[10px] text-fg-faint">
                            Bookmark entities, hypotheses, or findings from the inspector panel or entity analysis page.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
