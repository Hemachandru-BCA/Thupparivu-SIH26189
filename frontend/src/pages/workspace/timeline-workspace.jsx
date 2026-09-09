import { useState, useMemo } from 'react';
import { useGetGraphTimeline } from '@/api/graph';
import { Clock, Filter, ChevronRight, Download } from 'lucide-react';
import { formatTimestamp } from '@/components/app-shell';

export default function TimelineWorkspace() {
    const { data: timelineData, isLoading } = useGetGraphTimeline();
    const events = timelineData?.results || timelineData?.items || timelineData || [];
    const [typeFilter, setTypeFilter] = useState('ALL');
    const [dateRange, setDateRange] = useState({ from: '', to: '' });

    const eventTypes = useMemo(() => {
        const types = new Map();
        events.forEach(e => {
            const t = e.event_type || e.type || 'unknown';
            types.set(t, (types.get(t) || 0) + 1);
        });
        return Array.from(types.entries()).sort((a, b) => b[1] - a[1]);
    }, [events]);

    const filtered = useMemo(() => {
        let result = events;
        if (typeFilter !== 'ALL') {
            result = result.filter(e => (e.event_type || e.type) === typeFilter);
        }
        return result.sort((a, b) => {
            const da = new Date(a.timestamp || a.date || 0);
            const db = new Date(b.timestamp || b.date || 0);
            return da - db;
        });
    }, [events, typeFilter]);

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <Clock size={13} className="text-primary" />
                <span className="text-[11px] font-semibold text-fg-primary">TIMELINE</span>
                <span className="tp-badge tp-badge-neutral">{events.length} events</span>
                <div className="w-px h-4 bg-border-default" />
                <div className="flex gap-1">
                    {['ALL', ...eventTypes.map(([t]) => t)].slice(0, 6).map(t => (
                        <button key={t} onClick={() => setTypeFilter(t)}
                            className={`tp-btn text-[9px] h-5 px-2 ${typeFilter === t ? 'tp-btn-primary' : 'tp-btn-ghost'}`}>
                            {t}
                        </button>
                    ))}
                </div>
                <div className="flex-1" />
            </div>

            {/* Timeline visualization strip */}
            <div className="h-16 border-b border-border-subtle bg-bg-surface px-4 flex items-end overflow-x-auto">
                {filtered.length > 0 && (
                    <TimelineStrip events={filtered} />
                )}
            </div>

            {/* Event list */}
            <div className="flex-1 overflow-y-auto">
                {filtered.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <Clock size={24} className="text-fg-faint mb-3" />
                        <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">NO EVENTS</span>
                        <span className="text-[10px] text-fg-faint mt-1">No temporal events found in the current dataset</span>
                    </div>
                ) : (
                    <div className="relative">
                        {/* Timeline axis */}
                        <div className="absolute left-[120px] top-0 bottom-0 w-px bg-border-default" />
                        <div className="space-y-0">
                            {filtered.map((event, i) => (
                                <div key={i} className="flex items-start gap-3 px-4 py-2 hover:bg-bg-hover transition-colors">
                                    {/* Timestamp */}
                                    <div className="w-[100px] shrink-0 text-right pr-4">
                                        <div className="font-mono text-[10px] text-fg-faint">
                                            {formatTimestamp(event.timestamp || event.date)}
                                        </div>
                                    </div>
                                    {/* Dot */}
                                    <div className="relative z-1 mt-1.5">
                                        <div className="w-2 h-2 rounded-full bg-primary border-2 border-bg-root" />
                                    </div>
                                    {/* Content */}
                                    <div className="flex-1 min-w-0 ml-2">
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <span className="tp-badge tp-badge-blue" style={{fontSize: '8px'}}>
                                                {event.event_type || event.type || 'EVENT'}
                                            </span>
                                            {event.entity_id && (
                                                <span className="font-mono text-[9px] text-fg-faint">{event.entity_id}</span>
                                            )}
                                        </div>
                                        <div className="text-[11px] text-fg-secondary">{event.description || event.name || 'Event'}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

/* ── Mini timeline strip ── */
function TimelineStrip({ events }) {
    const width = 1200;
    const height = 50;

    // Group by time buckets
    const timestamps = events.map(e => new Date(e.timestamp || e.date || 0).getTime()).filter(t => !isNaN(t));
    if (timestamps.length === 0) return null;

    const minT = Math.min(...timestamps);
    const maxT = Math.max(...timestamps);
    const range = maxT - minT || 1;

    // Create histogram buckets
    const numBuckets = Math.min(60, events.length);
    const buckets = new Array(numBuckets).fill(0);
    events.forEach(e => {
        const t = new Date(e.timestamp || e.date || 0).getTime();
        if (isNaN(t)) return;
        const idx = Math.floor(((t - minT) / range) * (numBuckets - 1));
        buckets[idx]++;
    });
    const maxCount = Math.max(...buckets, 1);

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="none">
            {buckets.map((count, i) => {
                const barWidth = width / numBuckets - 1;
                const barHeight = (count / maxCount) * (height - 10);
                return (
                    <rect key={i}
                        x={i * (width / numBuckets)}
                        y={height - barHeight - 4}
                        width={barWidth}
                        height={barHeight}
                        fill={count > 0 ? 'hsl(var(--primary))' : 'transparent'}
                        opacity={0.6}
                        rx={1}
                    />
                );
            })}
            {/* Time labels */}
            <text x={4} y={10} fill="hsl(var(--fg-faint))" fontSize="8" fontFamily="var(--font-mono)">
                {new Date(minT).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
            </text>
            <text x={width - 4} y={10} fill="hsl(var(--fg-faint))" fontSize="8" fontFamily="var(--font-mono)" textAnchor="end">
                {new Date(maxT).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
            </text>
        </svg>
    );
}
