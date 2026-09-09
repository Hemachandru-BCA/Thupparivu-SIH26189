import { useState } from 'react';
import { runNodeRemovalSimulation, runScenarioComparison } from '@/api/xai';
import { Zap, AlertTriangle, Play, RotateCcw } from 'lucide-react';
import { formatNumber } from '@/components/app-shell';

export default function SimulationWorkspace() {
    const [targetNode, setTargetNode] = useState('');
    const [depth, setDepth] = useState(2);
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleSimulate = async () => {
        if (!targetNode.trim()) return;
        setLoading(true);
        setError(null);
        try {
            const res = await runNodeRemovalSimulation({ target_node_id: targetNode.trim(), depth });
            setResults(res?.result || res);
        } catch (e) {
            setError(e.message || 'Simulation failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <Zap size={13} className="text-primary" />
                <span className="text-[11px] font-semibold text-fg-primary">SIMULATION</span>
                <span className="text-[10px] text-fg-faint">— Counterfactual analysis</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
                {/* Controls */}
                <div className="tp-panel p-4 mb-4">
                    <div className="tp-section-label mb-3">NODE REMOVAL SIMULATION</div>
                    <div className="flex items-end gap-3">
                        <div className="flex-1">
                            <label className="text-[10px] text-fg-faint font-mono uppercase mb-1 block">TARGET NODE</label>
                            <input value={targetNode} onChange={e => setTargetNode(e.target.value)}
                                placeholder="e.g. P-0172"
                                className="tp-input" />
                        </div>
                        <div className="w-32">
                            <label className="text-[10px] text-fg-faint font-mono uppercase mb-1 block">DEPTH</label>
                            <input type="number" min={1} max={5} value={depth}
                                onChange={e => setDepth(Number(e.target.value))}
                                className="tp-input" />
                        </div>
                        <button onClick={handleSimulate} disabled={loading || !targetNode.trim()}
                            className="tp-btn tp-btn-primary h-7">
                            {loading ? <RotateCcw size={11} className="animate-spin" /> : <Play size={11} />}
                            Run Simulation
                        </button>
                    </div>
                </div>

                {error && (
                    <div className="tp-panel p-3 border-red/30 bg-red-bg mb-4">
                        <div className="flex items-center gap-2 text-[11px] text-red">
                            <AlertTriangle size={12} />
                            {error}
                        </div>
                    </div>
                )}

                {/* Results */}
                {results && (
                    <div className="space-y-4">
                        {/* Key metrics */}
                        <div className="grid grid-cols-4 gap-3">
                            {[
                                { label: 'FRAGMENTATION', value: (results.fragmentation_score || 0).toFixed(3), color: 'text-red' },
                                { label: 'CONNECTIVITY CHANGE', value: `${((results.connectivity_change || 0) * 100).toFixed(1)}%`, color: 'text-amber' },
                                { label: 'AFFECTED NODES', value: formatNumber(results.affected_node_count), color: 'text-blue' },
                                { label: 'REROUTING SCORE', value: (results.rerouting_score || 0).toFixed(3), color: 'text-purple' },
                            ].map(m => (
                                <div key={m.label} className="tp-panel p-3">
                                    <div className="tp-grid-stat-label">{m.label}</div>
                                    <div className={`tp-grid-stat-value ${m.color}`}>{m.value}</div>
                                </div>
                            ))}
                        </div>

                        {/* Community changes */}
                        {results.community_changes && (
                            <div className="tp-panel">
                                <div className="tp-panel-header">
                                    <span className="text-[11px] font-semibold text-fg-primary">COMMUNITY IMPACT</span>
                                </div>
                                <div className="p-3 grid grid-cols-3 gap-4">
                                    <div>
                                        <div className="text-[10px] font-mono text-fg-faint">Before</div>
                                        <div className="text-[14px] font-mono font-semibold text-fg-primary">
                                            {results.community_changes.num_communities_before}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] font-mono text-fg-faint">After</div>
                                        <div className="text-[14px] font-mono font-semibold text-fg-primary">
                                            {results.community_changes.num_communities_after}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] font-mono text-fg-faint">NMI</div>
                                        <div className="text-[14px] font-mono font-semibold text-primary">
                                            {(results.community_changes.nmi_vs_baseline || 0).toFixed(3)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Affected nodes */}
                        {results.affected_nodes?.length > 0 && (
                            <div className="tp-panel">
                                <div className="tp-panel-header">
                                    <span className="text-[11px] font-semibold text-fg-primary">AFFECTED NODES</span>
                                    <span className="text-[10px] font-mono text-fg-faint">{results.affected_nodes.length}</span>
                                </div>
                                <div className="p-2 max-h-48 overflow-y-auto">
                                    {results.affected_nodes.slice(0, 20).map((n, i) => (
                                        <div key={i} className="px-2 py-1 text-[10px] font-mono text-fg-secondary flex items-center gap-2">
                                            <span className="tp-badge tp-badge-red" style={{fontSize: '8px'}}>AFFECTED</span>
                                            {typeof n === 'string' ? n : n.id || n.name || JSON.stringify(n)}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Disclaimer */}
                        {results.disclaimer && (
                            <div className="tp-panel p-3 border-amber/20 bg-amber-bg">
                                <div className="text-[10px] text-amber flex items-start gap-2">
                                    <AlertTriangle size={12} className="shrink-0 mt-0.5" />
                                    <span>{results.disclaimer}</span>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {!results && !loading && (
                    <div className="flex flex-col items-center justify-center h-64 text-center">
                        <Zap size={24} className="text-fg-faint mb-3" />
                        <span className="text-[11px] font-mono text-fg-faint uppercase tracking-wider">NO SIMULATION RESULTS</span>
                        <span className="text-[10px] text-fg-faint mt-1">Configure a target node and run a simulation</span>
                    </div>
                )}
            </div>
        </div>
    );
}
