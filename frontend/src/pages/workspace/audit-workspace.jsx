import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { request } from '@/api/client';
import { ClipboardList, Filter, RefreshCw } from 'lucide-react';
import { formatTimestamp } from '@/components/app-shell';

export default function AuditWorkspace() {
    const { data: auditData, isLoading, refetch } = useQuery({
        queryKey: ['/api/audit'],
        queryFn: () => request('/api/audit'),
        refetchInterval: 8000,
    });
    const entries = auditData?.results || auditData?.items || auditData || [];
    const [filterType, setFilterType] = useState('ALL');

    const filtered = filterType === 'ALL'
        ? entries
        : entries.filter(e => (e.actor || e.type || '').toUpperCase() === filterType);

    const types = ['ALL', 'USER', 'SYSTEM', 'MODEL'];

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <ClipboardList size={13} className="text-primary" />
                <span className="text-[11px] font-semibold text-fg-primary">AUDIT LOG</span>
                <span className="tp-badge tp-badge-neutral">{entries.length} events</span>
                <div className="w-px h-4 bg-border-default" />
                <div className="flex gap-0.5">
                    {types.map(t => (
                        <button key={t} onClick={() => setFilterType(t)}
                            className={`tp-btn text-[9px] h-5 px-2 ${filterType === t ? 'tp-btn-primary' : 'tp-btn-ghost'}`}>
                            {t}
                        </button>
                    ))}
                </div>
                <div className="flex-1" />
                <button onClick={() => refetch()} className="tp-btn tp-btn-ghost text-[10px] h-6">
                    <RefreshCw size={10} /> Refresh
                </button>
            </div>

            <div className="flex-1 overflow-y-auto">
                <table className="tp-table">
                    <thead>
                        <tr>
                            <th style={{width: 140}}>TIMESTAMP</th>
                            <th style={{width: 80}}>ACTOR</th>
                            <th>ACTION</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((entry, i) => (
                            <tr key={i}>
                                <td className="font-mono text-fg-faint text-[10px]">{formatTimestamp(entry.timestamp)}</td>
                                <td>
                                    <span className={`tp-badge ${
                                        (entry.actor || entry.type) === 'USER' ? 'tp-badge-blue' :
                                        (entry.actor || entry.type) === 'MODEL' ? 'tp-badge-purple' :
                                        'tp-badge-neutral'
                                    }`}>
                                        {entry.actor || entry.type || 'SYSTEM'}
                                    </span>
                                </td>
                                <td className="text-fg-secondary text-[11px]">{entry.action || entry.message || '—'}</td>
                            </tr>
                        ))}
                        {filtered.length === 0 && (
                            <tr><td colSpan={3} className="text-center py-8 text-fg-faint text-[10px]">No audit entries found</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
