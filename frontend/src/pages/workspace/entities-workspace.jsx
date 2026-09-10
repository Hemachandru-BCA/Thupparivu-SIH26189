import { useState, useMemo } from 'react';
import { useLocation } from 'wouter';
import { useGetEntities } from '@/api/graph';
import { Users, Search, Filter, Download, ChevronDown } from 'lucide-react';
import { getEntityTypeColor, formatNumber } from '@/components/app-shell';

export default function EntitiesWorkspace() {
    const [, setLocation] = useLocation();
    const { data: entitiesData, isLoading } = useGetEntities();
    const entities = entitiesData?.results || entitiesData?.items || entitiesData || [];
    const [search, setSearch] = useState('');
    const [typeFilter, setTypeFilter] = useState('ALL');
    const [sortField, setSortField] = useState('name');
    const [sortDir, setSortDir] = useState('asc');

    const entityTypes = useMemo(() => {
        const types = new Map();
        entities.forEach(e => {
            const t = e.type || e.category || 'UNKNOWN';
            types.set(t, (types.get(t) || 0) + 1);
        });
        return Array.from(types.entries()).sort((a, b) => b[1] - a[1]);
    }, [entities]);

    const filtered = useMemo(() => {
        let result = entities;
        if (typeFilter !== 'ALL') {
            result = result.filter(e => (e.type || e.category) === typeFilter);
        }
        if (search) {
            const q = search.toLowerCase();
            result = result.filter(e =>
                (e.name || '').toLowerCase().includes(q) ||
                (e.id || '').toLowerCase().includes(q)
            );
        }
        result.sort((a, b) => {
            const aVal = a[sortField] || '';
            const bVal = b[sortField] || '';
            if (typeof aVal === 'number') return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
            return sortDir === 'asc' ? String(aVal).localeCompare(String(bVal)) : String(bVal).localeCompare(String(aVal));
        });
        return result;
    }, [entities, typeFilter, search, sortField, sortDir]);

    const handleSort = (field) => {
        if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setSortField(field); setSortDir('asc'); }
    };

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            {/* Toolbar */}
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <div className="flex items-center gap-2">
                    <Users size={13} className="text-primary" />
                    <span className="text-[11px] font-semibold text-fg-primary">ENTITIES</span>
                    <span className="tp-badge tp-badge-neutral">{entities.length}</span>
                </div>
                <div className="w-px h-4 bg-border-default" />
                <div className="relative flex-1 max-w-xs">
                    <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint" />
                    <input value={search} onChange={e => setSearch(e.target.value)}
                        placeholder="Filter entities..."
                        className="tp-input pl-7 h-7 text-[11px]" />
                </div>
                <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
                    className="tp-select h-7 text-[11px] w-auto">
                    <option value="ALL">All Types ({entities.length})</option>
                    {entityTypes.map(([t, c]) => (
                        <option key={t} value={t}>{t} ({c})</option>
                    ))}
                </select>
                <div className="flex-1" />
                <span className="text-[10px] font-mono text-fg-faint">{filtered.length} shown</span>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
                <table className="tp-table">
                    <thead>
                        <tr>
                            <th className="cursor-pointer" onClick={() => handleSort('id')}>
                                ID {sortField === 'id' && (sortDir === 'asc' ? '↑' : '↓')}
                            </th>
                            <th className="cursor-pointer" onClick={() => handleSort('name')}>
                                NAME {sortField === 'name' && (sortDir === 'asc' ? '↑' : '↓')}
                            </th>
                            <th className="cursor-pointer" onClick={() => handleSort('type')}>
                                TYPE {sortField === 'type' && (sortDir === 'asc' ? '↑' : '↓')}
                            </th>
                            <th>COMMUNITY</th>
                            <th className="cursor-pointer" onClick={() => handleSort('degree')}>
                                DEGREE {sortField === 'degree' && (sortDir === 'asc' ? '↑' : '↓')}
                            </th>
                            <th>PAGERANK</th>
                            <th>BETWEENNESS</th>
                            <th>MENTIONS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((entity, idx) => (
                            <tr key={entity.id || `entity-${idx}`} className="cursor-pointer"
                                onClick={() => setLocation(`/entity/${encodeURIComponent(entity.id)}`)}>
                                <td className="font-mono text-fg-faint">{entity.id}</td>
                                <td className="text-fg-primary font-medium">{entity.name || entity.id}</td>
                                <td>
                                    <span className="tp-badge" style={{
                                        color: getEntityTypeColor(entity.type || entity.category),
                                        background: `${getEntityTypeColor(entity.type || entity.category)}15`,
                                    }}>
                                        {entity.type || entity.category}
                                    </span>
                                </td>
                                <td className="font-mono text-fg-secondary">
                                    {entity.community_id != null ? `C${entity.community_id}` : '—'}
                                </td>
                                <td className="font-mono text-fg-secondary">{entity.degree || 0}</td>
                                <td className="font-mono text-fg-secondary">
                                    {(entity.metrics?.pagerank || 0).toFixed(4)}
                                </td>
                                <td className="font-mono text-fg-secondary">
                                    {(entity.metrics?.betweenness_centrality || 0).toFixed(4)}
                                </td>
                                <td className="font-mono text-fg-secondary">{entity.mention_count || 0}</td>
                            </tr>
                        ))}
                        {filtered.length === 0 && (
                            <tr>
                                <td colSpan={8} className="text-center py-8 text-fg-faint text-[11px]">
                                    No entities match the current filters
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
