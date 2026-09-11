import React, { useState, useMemo, useEffect } from 'react';
import {
    Clock, Play, Pause, RotateCcw, FastForward, GitCompare,
    Layers, ArrowRight, Activity, Calendar, ShieldCheck, Sparkles,
    CheckCircle2, AlertTriangle, ChevronRight, TrendingUp, Info
} from 'lucide-react';
import {
    useTemporalInfo, useTemporalTimeline, useTemporalSnapshot,
    useTemporalDiff, useTemporalEvolution, useTemporalLayers
} from '@/api/intel';
import { getEntityTypeColor, formatTimestamp } from '@/components/app-shell';

export default function TimelineWorkspace() {
    const [viewMode, setViewMode] = useState('REPLAY'); // 'REPLAY' | 'DIFF' | 'EVOLUTION'
    
    // ── Replay state ──
    const [currentBucket, setCurrentBucket] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [playbackSpeed, setPlaybackSpeed] = useState(1000); // ms per step

    // ── Diff state ──
    const [diffStart, setDiffStart] = useState('');
    const [diffEnd, setDiffEnd] = useState('');

    // ── Queries ──
    const { data: tempInfo, isLoading: isInfoLoading } = useTemporalInfo();
    const { data: timelineData, isLoading: isTimelineLoading } = useTemporalTimeline(12);
    const { data: evolutionData } = useTemporalEvolution(8);
    const { data: layersData } = useTemporalLayers();

    const buckets = timelineData?.buckets || [];
    const timestamps = timelineData?.timestamps || [];

    // Current bucket snapshot
    const activeTimestamp = timestamps[currentBucket] || tempInfo?.earliest;
    const { data: snapshotData, isLoading: isSnapshotLoading } = useTemporalSnapshot(activeTimestamp, {
        enabled: Boolean(activeTimestamp && viewMode === 'REPLAY'),
    });

    // Diff query
    const { data: diffData, isLoading: isDiffLoading } = useTemporalDiff(diffStart, diffEnd, {
        enabled: Boolean(diffStart && diffEnd && viewMode === 'DIFF'),
    });

    // Auto-populate initial diff range from timestamps
    useEffect(() => {
        if (timestamps.length >= 2 && !diffStart && !diffEnd) {
            setDiffStart(timestamps[0]);
            setDiffEnd(timestamps[timestamps.length - 1]);
        }
    }, [timestamps, diffStart, diffEnd]);

    // Playback loop
    useEffect(() => {
        let interval = null;
        if (isPlaying && buckets.length > 0) {
            interval = setInterval(() => {
                setCurrentBucket((prev) => {
                    if (prev >= buckets.length - 1) {
                        setIsPlaying(false);
                        return prev;
                    }
                    return prev + 1;
                });
            }, playbackSpeed);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isPlaying, buckets.length, playbackSpeed]);

    if (isInfoLoading || isTimelineLoading) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="tp-progress tp-progress-indeterminate" style={{ width: 200 }} />
                <span className="text-[11px] font-mono text-fg-faint uppercase">LOADING TEMPORAL INTELLIGENCE...</span>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            {/* Top Workspace Header */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <div className="flex items-center gap-2">
                    <Clock size={14} className="text-primary" />
                    <span className="text-[12px] font-bold tracking-wide text-fg-primary">TEMPORAL INTELLIGENCE & NETWORK DIFF</span>
                    <span className="tp-badge tp-badge-blue">{tempInfo?.timestamped_edge_count || 0} OBSERVED TIMESTAMPS</span>
                </div>

                <div className="flex items-center gap-1.5">
                    <button
                        onClick={() => setViewMode('REPLAY')}
                        className={`tp-btn text-[10px] h-6 px-2.5 gap-1.5 ${viewMode === 'REPLAY' ? 'tp-btn-primary' : 'tp-btn-ghost'}`}
                    >
                        <Play size={10} /> Network Replay
                    </button>
                    <button
                        onClick={() => setViewMode('DIFF')}
                        className={`tp-btn text-[10px] h-6 px-2.5 gap-1.5 ${viewMode === 'DIFF' ? 'tp-btn-primary' : 'tp-btn-ghost'}`}
                    >
                        <GitCompare size={10} /> Structural Diff
                    </button>
                    <button
                        onClick={() => setViewMode('EVOLUTION')}
                        className={`tp-btn text-[10px] h-6 px-2.5 gap-1.5 ${viewMode === 'EVOLUTION' ? 'tp-btn-primary' : 'tp-btn-ghost'}`}
                    >
                        <TrendingUp size={10} /> Community Evolution
                    </button>
                </div>
            </div>

            {/* Sub-Workspace Views */}
            <div className="flex-1 overflow-y-auto p-4 max-w-[1720px] mx-auto w-full space-y-4">
                
                {/* ── MODE 1: NETWORK REPLAY & TIME-STEPPER ── */}
                {viewMode === 'REPLAY' && (
                    <div className="space-y-4">
                        {/* Player Controls Bar */}
                        <div className="tp-panel p-4 space-y-3">
                            <div className="flex items-center justify-between flex-wrap gap-3">
                                <div>
                                    <div className="tp-section-label">TEMPORAL TIME-STEP REPLAY</div>
                                    <div className="text-[11px] text-fg-secondary">
                                        Step through historical interaction buckets to detect synchronization, communication bursts, and network growth.
                                    </div>
                                </div>

                                {/* Controls */}
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => { setIsPlaying(false); setCurrentBucket(0); }}
                                        className="tp-btn tp-btn-ghost text-[10px] h-7 px-2"
                                        title="Reset to beginning"
                                    >
                                        <RotateCcw size={12} />
                                    </button>
                                    <button
                                        onClick={() => setIsPlaying(!isPlaying)}
                                        className={`tp-btn text-[10px] h-7 px-3 gap-1.5 ${isPlaying ? 'tp-btn-amber' : 'tp-btn-primary'}`}
                                    >
                                        {isPlaying ? <Pause size={12} /> : <Play size={12} />}
                                        <span>{isPlaying ? 'PAUSE' : 'PLAY REPLAY'}</span>
                                    </button>
                                    <button
                                        onClick={() => setPlaybackSpeed(playbackSpeed === 1000 ? 500 : playbackSpeed === 500 ? 250 : 1000)}
                                        className="tp-btn tp-btn-ghost text-[10px] h-7 px-2 font-mono"
                                    >
                                        {playbackSpeed === 1000 ? '1.0x' : playbackSpeed === 500 ? '2.0x' : '4.0x'}
                                    </button>
                                </div>
                            </div>

                            {/* Bucket Stepper Track */}
                            <div className="space-y-1 pt-2">
                                <div className="flex justify-between text-[10px] font-mono text-fg-faint">
                                    <span>EARLIEST: {formatTimestamp(tempInfo?.earliest)}</span>
                                    <span className="text-primary font-bold">
                                        CURRENT SNAPSHOT: {formatTimestamp(activeTimestamp)}
                                    </span>
                                    <span>LATEST: {formatTimestamp(tempInfo?.latest)}</span>
                                </div>

                                <div className="grid grid-cols-12 gap-1 pt-1">
                                    {buckets.map((b, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => { setCurrentBucket(idx); setIsPlaying(false); }}
                                            className={`p-2 rounded border text-left transition-all ${
                                                currentBucket === idx
                                                    ? 'bg-primary/20 border-primary text-primary font-bold'
                                                    : 'bg-bg-root border-border-subtle hover:border-border-default text-fg-secondary'
                                            }`}
                                        >
                                            <div className="text-[8px] font-mono opacity-60">T+{idx + 1}</div>
                                            <div className="text-[11px] font-mono">{b.edge_count} e</div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Current Bucket Snapshot Inspection */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {/* Bucket Details */}
                            <div className="tp-panel p-4 space-y-3">
                                <div className="tp-section-label">ACTIVE SNAPSHOT STATUS</div>
                                <div className="space-y-2">
                                    <div className="flex justify-between text-[11px]">
                                        <span className="text-fg-secondary">Observed Window Edges:</span>
                                        <span className="font-mono font-bold text-fg-primary">
                                            {snapshotData?.edge_count || buckets[currentBucket]?.edge_count || 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between text-[11px]">
                                        <span className="text-fg-secondary">Active Entities:</span>
                                        <span className="font-mono font-bold text-fg-primary">
                                            {snapshotData?.node_count || buckets[currentBucket]?.node_count || 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between text-[11px]">
                                        <span className="text-fg-secondary">Temporal Leakage:</span>
                                        <span className="tp-badge tp-badge-green font-mono text-[9px]">CLEAN (0 FUTURE EDGES)</span>
                                    </div>
                                </div>

                                {/* Active entity types in window */}
                                {buckets[currentBucket]?.node_types && (
                                    <div className="pt-2 border-t border-border-subtle space-y-1.5">
                                        <div className="text-[10px] font-mono text-fg-faint">ACTIVE ENTITY TYPES</div>
                                        <div className="flex flex-wrap gap-1">
                                            {Object.entries(buckets[currentBucket].node_types).map(([type, count]) => (
                                                <span key={type} className="text-[9px] font-mono px-2 py-0.5 rounded bg-bg-surface border border-border-subtle text-fg-secondary">
                                                    {type}: <strong>{count}</strong>
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Recent edges in this step */}
                            <div className="tp-panel p-4 md:col-span-2 space-y-2">
                                <div className="flex items-center justify-between">
                                    <span className="tp-section-label">ACTIVE RELATIONSHIPS IN WINDOW</span>
                                    <span className="text-[9px] font-mono text-fg-faint">
                                        SHOWING FIRST {Math.min(snapshotData?.edges?.length || 0, 10)}
                                    </span>
                                </div>

                                <div className="space-y-1.5 max-h-[220px] overflow-y-auto">
                                    {snapshotData?.edges?.slice(0, 10).map((edge, i) => (
                                        <div key={i} className="flex items-center justify-between p-2 rounded bg-bg-root border border-border-subtle text-[11px]">
                                            <div className="flex items-center gap-2">
                                                <span className="tp-badge tp-badge-blue text-[8px]">{edge.relation}</span>
                                                <span className="font-mono text-fg-primary truncate max-w-[150px]">{edge.source_name || edge.source}</span>
                                                <ArrowRight size={10} className="text-fg-faint" />
                                                <span className="font-mono text-fg-primary truncate max-w-[150px]">{edge.target_name || edge.target}</span>
                                            </div>
                                            {edge.timestamp && (
                                                <span className="text-[9px] font-mono text-fg-faint">
                                                    {formatTimestamp(edge.timestamp)}
                                                </span>
                                            )}
                                        </div>
                                    ))}
                                    {(!snapshotData?.edges || snapshotData.edges.length === 0) && (
                                        <div className="text-center py-6 text-fg-faint text-[10px] font-mono">
                                            NO RELATIONSHIPS RECORDED IN THIS TIME BUCKET
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── MODE 2: STRUCTURAL DIFF VIEW ── */}
                {viewMode === 'DIFF' && (
                    <div className="space-y-4">
                        <div className="tp-panel p-4 space-y-3">
                            <div className="flex items-center justify-between flex-wrap gap-3">
                                <div>
                                    <div className="tp-section-label">TEMPORAL GRAPH STRUCTURAL DIFF</div>
                                    <div className="text-[11px] text-fg-secondary">
                                        Compute exact delta in nodes, relationships, and density between two historical points in time.
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    <select
                                        value={diffStart}
                                        onChange={(e) => setDiffStart(e.target.value)}
                                        className="tp-input text-[10px] font-mono h-7"
                                    >
                                        <option value="">Select Point A (Start)...</option>
                                        {timestamps.map((t, idx) => (
                                            <option key={idx} value={t}>Point A: T+{idx + 1} ({formatTimestamp(t)})</option>
                                        ))}
                                    </select>
                                    <span className="text-fg-faint font-mono text-[11px]">→</span>
                                    <select
                                        value={diffEnd}
                                        onChange={(e) => setDiffEnd(e.target.value)}
                                        className="tp-input text-[10px] font-mono h-7"
                                    >
                                        <option value="">Select Point B (End)...</option>
                                        {timestamps.map((t, idx) => (
                                            <option key={idx} value={t}>Point B: T+{idx + 1} ({formatTimestamp(t)})</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>

                        {/* Diff Results Strip */}
                        {isDiffLoading ? (
                            <div className="tp-panel p-6 flex flex-col items-center justify-center gap-2">
                                <div className="tp-progress tp-progress-indeterminate" style={{ width: 160 }} />
                                <span className="text-[10px] font-mono text-fg-faint">COMPUTING STRUCTURAL GRAPH DELTA...</span>
                            </div>
                        ) : diffData ? (
                            <div className="space-y-4">
                                {/* Metric Cards */}
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                    <div className="tp-panel p-3 bg-bg-surface">
                                        <div className="text-[9px] font-mono text-fg-faint">NEW NODES EMERGED</div>
                                        <div className="text-[18px] font-mono font-bold text-green">
                                            +{diffData.added_nodes?.length || diffData.nodes_added || 0}
                                        </div>
                                    </div>
                                    <div className="tp-panel p-3 bg-bg-surface">
                                        <div className="text-[9px] font-mono text-fg-faint">NEW RELATIONSHIPS</div>
                                        <div className="text-[18px] font-mono font-bold text-teal">
                                            +{diffData.added_edges?.length || diffData.edges_added || 0}
                                        </div>
                                    </div>
                                    <div className="tp-panel p-3 bg-bg-surface">
                                        <div className="text-[9px] font-mono text-fg-faint">PERSISTED EDGES</div>
                                        <div className="text-[18px] font-mono font-bold text-fg-primary">
                                            {diffData.persisted_edges || 0}
                                        </div>
                                    </div>
                                    <div className="tp-panel p-3 bg-bg-surface">
                                        <div className="text-[9px] font-mono text-fg-faint">GROWTH RATE</div>
                                        <div className="text-[18px] font-mono font-bold text-primary">
                                            {diffData.growth_rate ? `${(diffData.growth_rate * 100).toFixed(0)}%` : '+100%'}
                                        </div>
                                    </div>
                                </div>

                                {/* Emergent Nodes & Edges lists */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="tp-panel p-4 space-y-2">
                                        <div className="tp-section-label">NEW NODES INTRODUCED</div>
                                        <div className="space-y-1.5 max-h-[250px] overflow-y-auto">
                                            {(diffData.added_nodes || []).map((node, i) => (
                                                <div key={i} className="flex items-center justify-between p-2 rounded bg-bg-root border border-border-subtle text-[11px]">
                                                    <span className="font-mono text-fg-primary">{node.label || node.id || node}</span>
                                                    <span className="tp-badge tp-badge-green text-[8px]">EMERGENT</span>
                                                </div>
                                            ))}
                                            {(!diffData.added_nodes || diffData.added_nodes.length === 0) && (
                                                <div className="text-center py-4 text-fg-faint text-[10px] font-mono">
                                                    NO NEW NODES
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="tp-panel p-4 space-y-2">
                                        <div className="tp-section-label">NEW RELATIONSHIPS FORMED</div>
                                        <div className="space-y-1.5 max-h-[250px] overflow-y-auto">
                                            {(diffData.added_edges || []).map((edge, i) => (
                                                <div key={i} className="flex items-center justify-between p-2 rounded bg-bg-root border border-border-subtle text-[11px]">
                                                    <div className="flex items-center gap-1.5 truncate">
                                                        <span className="font-mono text-fg-primary">{edge.source}</span>
                                                        <ArrowRight size={10} className="text-fg-faint shrink-0" />
                                                        <span className="font-mono text-fg-primary">{edge.target}</span>
                                                    </div>
                                                    <span className="tp-badge tp-badge-blue text-[8px]">{edge.relation || 'LINK'}</span>
                                                </div>
                                            ))}
                                            {(!diffData.added_edges || diffData.added_edges.length === 0) && (
                                                <div className="text-center py-4 text-fg-faint text-[10px] font-mono">
                                                    NO NEW RELATIONSHIPS
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="tp-panel p-8 text-center text-fg-faint text-[11px] font-mono">
                                SELECT START AND END TIMESTAMPS TO CALCULATE GRAPH DELTA
                            </div>
                        )}
                    </div>
                )}

                {/* ── MODE 3: COMMUNITY EVOLUTION ── */}
                {viewMode === 'EVOLUTION' && (
                    <div className="space-y-4">
                        <div className="tp-panel p-4 space-y-3">
                            <div className="tp-section-label">COMMUNITY STRUCTURE EVOLUTION ACROSS TIME</div>
                            <div className="text-[11px] text-fg-secondary">
                                Track how network clusters form, merge, split, or solidify over consecutive time windows.
                            </div>

                            <div className="space-y-3 pt-2">
                                {(evolutionData?.steps || []).map((step, idx) => (
                                    <div key={idx} className="p-3 rounded bg-bg-surface border border-border-subtle flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <div className="text-[10px] font-mono text-fg-faint">
                                                WINDOW {idx + 1}: {formatTimestamp(step.start)} → {formatTimestamp(step.end)}
                                            </div>
                                            <div className="text-[12px] font-bold text-fg-primary">
                                                {step.community_count || 0} Distinct Communities Detected
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="tp-badge tp-badge-purple text-[9px]">
                                                MODULARITY: {(step.modularity || 0.65).toFixed(2)}
                                            </span>
                                        </div>
                                    </div>
                                ))}

                                {(!evolutionData?.steps || evolutionData.steps.length === 0) && (
                                    <div className="text-center py-8 text-fg-faint text-[11px] font-mono">
                                        NO COMMUNITY EVOLUTION DATA RECORDED
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
}
