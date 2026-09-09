import { useState, useMemo } from 'react';
import { useGetCentrality, useGetCommunities, useGetGraphOverview } from '@/api/graph';
import { BarChart3, Users, TrendingUp, Waypoints, Activity } from 'lucide-react';

function MetricBar({ label, value, maxValue, color }) {
    const pct = maxValue > 0 ? (value / maxValue) * 100 : 0;
    return (
        <div className="flex items-center gap-3 text-[10px]">
            <span className="w-24 text-fg-faint font-mono truncate shrink-0">{label}</span>
            <div className="flex-1 tp-confidence-bar">
                <div className="tp-confidence-fill" style={{ width: `${pct}%`, background: color || 'hsl(var(--primary))' }} />
            </div>
            <span className="w-14 text-right font-mono text-fg-secondary shrink-0">{value.toFixed(4)}</span>
        </div>
    );
}

export default function AnalyticsWorkspace() {
    const { data: centralityData } = useGetCentrality();
    const { data: communityData } = useGetCommunities();
    const { data: overview } = useGetGraphOverview();
    const [activeTab, setActiveTab] = useState('centrality');

    const centrality = centralityData?.results || centralityData?.items || centralityData || [];
    const communities = communityData?.results || communityData?.items || communityData || [];

    // Sort centrality by betweenness
    const sortedCentrality = useMemo(() => {
        return [...centrality].sort((a, b) => (b.betweenness_centrality || 0) - (a.betweenness_centrality || 0)).slice(0, 30);
    }, [centrality]);

    // Community sizes
    const communitySizes = useMemo(() => {
        const map = new Map();
        centrality.forEach(n => {
            const c = n.community_id ?? 'unknown';
            map.set(c, (map.get(c) || 0) + 1);
        });
        return Array.from(map.entries()).map(([id, size]) => ({ id, size })).sort((a, b) => b.size - a.size);
    }, [centrality]);

    const tabs = [
        { id: 'centrality', label: 'CENTRALITY', icon: TrendingUp },
        { id: 'communities', label: 'COMMUNITIES', icon: Waypoints },
        { id: 'distribution', label: 'DISTRIBUTION', icon: BarChart3 },
    ];

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <BarChart3 size={13} className="text-primary" />
                <span className="text-[11px] font-semibold text-fg-primary">ANALYSIS</span>
                <div className="w-px h-4 bg-border-default" />
                <div className="flex gap-0.5">
                    {tabs.map(tab => {
                        const Icon = tab.icon;
                        return (
                            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                                className={`tp-btn text-[9px] h-6 px-2.5 gap-1 ${activeTab === tab.id ? 'tp-btn-primary' : 'tp-btn-ghost'}`}>
                                <Icon size={10} />
                                {tab.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
                {activeTab === 'centrality' && (
                    <div className="space-y-4">
                        <div className="tp-panel">
                            <div className="tp-panel-header">
                                <span className="text-[11px] font-semibold text-fg-primary">CENTRALITY METRICS</span>
                                <span className="text-[10px] font-mono text-fg-faint">{sortedCentrality.length} nodes</span>
                            </div>
                            <div className="p-3">
                                <table className="tp-table">
                                    <thead>
                                        <tr>
                                            <th>#</th>
                                            <th>ENTITY</th>
                                            <th>TYPE</th>
                                            <th>COMMUNITY</th>
                                            <th>DEGREE</th>
                                            <th>BETWEENNESS</th>
                                            <th>PAGERANK</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {sortedCentrality.map((node, i) => (
                                            <tr key={node.id}>
                                                <td className="font-mono text-fg-faint">{i + 1}</td>
                                                <td className="text-fg-primary font-medium">{node.name || node.id}</td>
                                                <td><span className="tp-badge tp-badge-blue">{node.type || node.label}</span></td>
                                                <td className="font-mono text-fg-secondary">{node.community_id != null ? `C${node.community_id}` : '—'}</td>
                                                <td className="font-mono text-fg-secondary">{node.degree || 0}</td>
                                                <td className="font-mono text-fg-secondary">{(node.betweenness_centrality || 0).toFixed(4)}</td>
                                                <td className="font-mono text-fg-secondary">{(node.pagerank || 0).toFixed(4)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'communities' && (
                    <div className="space-y-4">
                        <div className="grid grid-cols-3 gap-3">
                            <div className="tp-panel p-3">
                                <div className="tp-grid-stat-label">COMMUNITIES</div>
                                <div className="tp-grid-stat-value">{communitySizes.length}</div>
                            </div>
                            <div className="tp-panel p-3">
                                <div className="tp-grid-stat-label">LARGEST</div>
                                <div className="tp-grid-stat-value">{communitySizes[0]?.size || 0}</div>
                            </div>
                            <div className="tp-panel p-3">
                                <div className="tp-grid-stat-label">AVG SIZE</div>
                                <div className="tp-grid-stat-value">
                                    {communitySizes.length > 0
                                        ? (communitySizes.reduce((s, c) => s + c.size, 0) / communitySizes.length).toFixed(0)
                                        : 0}
                                </div>
                            </div>
                        </div>

                        <div className="tp-panel">
                            <div className="tp-panel-header">
                                <span className="text-[11px] font-semibold text-fg-primary">COMMUNITY DIRECTORY</span>
                            </div>
                            <div className="p-3 grid grid-cols-4 gap-3">
                                {communitySizes.map(c => {
                                    const maxSize = communitySizes[0]?.size || 1;
                                    return (
                                        <div key={c.id} className="tp-panel p-2.5">
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="font-mono text-[10px] text-fg-muted">C{c.id}</span>
                                                <span className="font-mono text-[12px] text-fg-primary font-semibold">{c.size}</span>
                                            </div>
                                            <div className="tp-confidence-bar">
                                                <div className="tp-confidence-fill" style={{
                                                    width: `${(c.size / maxSize) * 100}%`,
                                                    background: 'hsl(var(--primary))'
                                                }} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'distribution' && (
                    <div className="space-y-4">
                        <div className="tp-panel">
                            <div className="tp-panel-header">
                                <span className="text-[11px] font-semibold text-fg-primary">DEGREE DISTRIBUTION</span>
                            </div>
                            <div className="p-3">
                                <div className="space-y-1">
                                    {sortedCentrality.slice(0, 20).map(node => (
                                        <MetricBar key={node.id} label={node.name || node.id}
                                            value={node.degree || 0}
                                            maxValue={Math.max(...sortedCentrality.map(n => n.degree || 0), 1)}
                                            color="hsl(var(--primary))" />
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="tp-panel">
                            <div className="tp-panel-header">
                                <span className="text-[11px] font-semibold text-fg-primary">BETWEENNESS CENTRALITY</span>
                            </div>
                            <div className="p-3">
                                <div className="space-y-1">
                                    {sortedCentrality.slice(0, 20).map(node => (
                                        <MetricBar key={node.id} label={node.name || node.id}
                                            value={node.betweenness_centrality || 0}
                                            maxValue={Math.max(...sortedCentrality.map(n => n.betweenness_centrality || 0), 0.001)}
                                            color="hsl(var(--amber))" />
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
