import { useState, useMemo } from 'react';
import { useGetCommunities, useGetGraphOverview } from '@/api/graph';
import { Waypoints, Search, Filter } from 'lucide-react';

export default function CommunitiesWorkspace() {
    const { data: communityData, isLoading } = useGetCommunities();
    const { data: overview } = useGetGraphOverview();
    const communities = communityData?.results || communityData?.items || communityData || [];
    const [search, setSearch] = useState('');

    const communityMap = useMemo(() => {
        const map = new Map();
        communities.forEach(n => {
            const c = n.community_id ?? 'unknown';
            if (!map.has(c)) map.set(c, { id: c, members: [], types: new Map() });
            const comm = map.get(c);
            comm.members.push(n);
            const t = n.type || n.label || 'unknown';
            comm.types.set(t, (comm.types.get(t) || 0) + 1);
        });
        return Array.from(map.values()).sort((a, b) => b.members.length - a.members.length);
    }, [communities]);

    const filtered = useMemo(() => {
        if (!search) return communityMap;
        return communityMap.filter(c => String(c.id).includes(search));
    }, [communityMap, search]);

    const stats = useMemo(() => ({
        total: communityMap.length,
        largest: communityMap[0]?.members.length || 0,
        avgSize: communityMap.length > 0
            ? (communityMap.reduce((s, c) => s + c.members.length, 0) / communityMap.length).toFixed(0)
            : 0,
    }), [communityMap]);

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <Waypoints size={13} className="text-cyan" />
                <span className="text-[11px] font-semibold text-fg-primary">COMMUNITIES</span>
                <span className="tp-badge tp-badge-cyan">{stats.total} clusters</span>
                <div className="w-px h-4 bg-border-default" />
                <span className="text-[10px] font-mono text-fg-faint">LARGEST: {stats.largest} · AVG: {stats.avgSize}</span>
                <div className="flex-1" />
                <div className="relative max-w-xs">
                    <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint" />
                    <input value={search} onChange={e => setSearch(e.target.value)}
                        placeholder="Filter community..."
                        className="tp-input pl-7 h-7 text-[11px]" />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
                <div className="grid grid-cols-4 gap-3">
                    {filtered.map(comm => {
                        const types = Array.from(comm.types.entries()).sort((a, b) => b[1] - a[1]);
                        const maxSize = communityMap[0]?.members.length || 1;
                        return (
                            <div key={comm.id} className="tp-panel p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-mono text-[11px] text-fg-muted">C{comm.id}</span>
                                    <span className="font-mono text-[13px] text-fg-primary font-semibold">{comm.members.length}</span>
                                </div>
                                <div className="tp-confidence-bar mb-2">
                                    <div className="tp-confidence-fill" style={{
                                        width: `${(comm.members.length / maxSize) * 100}%`,
                                        background: 'hsl(var(--cyan))'
                                    }} />
                                </div>
                                <div className="space-y-0.5">
                                    {types.slice(0, 4).map(([type, count]) => (
                                        <div key={type} className="flex items-center justify-between text-[9px]">
                                            <span className="text-fg-faint">{type}</span>
                                            <span className="font-mono text-fg-secondary">{count}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
