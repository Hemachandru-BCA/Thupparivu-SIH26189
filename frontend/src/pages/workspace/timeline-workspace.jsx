/**
 * Timeline Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §11: Timeline + Structural Diff.
 * 1 Aug 2026 → 26 Sep 2026, Snapshot 9 of 12 (18 Sep 2026).
 * Diff: +684 entities, -19 entities, +1204 rels, -87 rels, Largest shift: Community 6 gained 71 entities.
 */
import React, { useState } from 'react';
import { Clock, Play, Pause, ChevronLeft, ChevronRight, Layers, ArrowUpRight, ArrowDownRight, GitCommit } from 'lucide-react';
import { SYNTHETIC_TIMELINE } from '@/state/synthetic-case-data';

export default function TimelineWorkspace() {
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentStep, setCurrentStep] = useState(SYNTHETIC_TIMELINE.current_snapshot_index);

    const togglePlay = () => setIsPlaying(!isPlaying);

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[hsl(var(--border-default))]">
                <div className="flex items-center gap-2">
                    <Clock size={18} className="text-[hsl(var(--primary))]" />
                    <h1 className="text-[18px] font-semibold text-[hsl(var(--fg-primary))]">Timeline & Structural Diff</h1>
                </div>
                <div className="text-[12px] font-mono text-[hsl(var(--fg-muted))]">
                    {SYNTHETIC_TIMELINE.range}
                </div>
            </div>

            {/* Replay Control Deck */}
            <div className="sg-card p-5 space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <span className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Current Snapshot</span>
                        <div className="font-mono text-[16px] font-bold text-[hsl(var(--primary))] mt-0.5">
                            {SYNTHETIC_TIMELINE.current_snapshot_date} (Snapshot {currentStep} of {SYNTHETIC_TIMELINE.total_snapshots})
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button className="sg-btn sg-btn-sm" onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}>
                            <ChevronLeft size={13} /> Previous
                        </button>
                        <button className="sg-btn sg-btn-sm sg-btn-primary" onClick={togglePlay}>
                            {isPlaying ? <Pause size={13} /> : <Play size={13} />}
                            {isPlaying ? 'Pause replay' : 'Replay sequence'}
                        </button>
                        <button className="sg-btn sg-btn-sm" onClick={() => setCurrentStep(Math.min(SYNTHETIC_TIMELINE.total_snapshots, currentStep + 1))}>
                            Next <ChevronRight size={13} />
                        </button>
                    </div>
                </div>

                {/* Stepper Timeline Range */}
                <div className="space-y-2 pt-2">
                    <input
                        type="range"
                        min="1"
                        max="12"
                        value={currentStep}
                        onChange={e => setCurrentStep(Number(e.target.value))}
                        className="w-full h-1.5 bg-[hsl(var(--border-subtle))] rounded-lg appearance-none cursor-pointer accent-[hsl(var(--primary))]"
                    />
                    <div className="flex justify-between text-[10px] font-mono text-[hsl(var(--fg-faint))]">
                        <span>1 Aug 2026 (Baseline)</span>
                        <span>18 Sep 2026 (Current)</span>
                        <span>26 Sep 2026 (Latest)</span>
                    </div>
                </div>
            </div>

            {/* Snapshot Metrics & Structural Delta */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Snapshot Cumulative Totals */}
                <div className="sg-card p-5 space-y-4">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Snapshot State</div>
                    <div className="grid grid-cols-3 gap-3 text-center">
                        <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                            <div className="text-[10px] uppercase text-[hsl(var(--fg-muted))]">Entities</div>
                            <div className="font-mono text-[16px] font-semibold text-[hsl(var(--fg-primary))]">
                                {SYNTHETIC_TIMELINE.metrics.entities.toLocaleString()}
                            </div>
                        </div>
                        <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                            <div className="text-[10px] uppercase text-[hsl(var(--fg-muted))]">Relationships</div>
                            <div className="font-mono text-[16px] font-semibold text-[hsl(var(--fg-primary))]">
                                {SYNTHETIC_TIMELINE.metrics.relationships.toLocaleString()}
                            </div>
                        </div>
                        <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                            <div className="text-[10px] uppercase text-[hsl(var(--fg-muted))]">Communities</div>
                            <div className="font-mono text-[16px] font-semibold text-[hsl(var(--fg-primary))]">
                                {SYNTHETIC_TIMELINE.metrics.communities.toLocaleString()}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Structural Diff from Previous Window */}
                <div className="sg-card p-5 space-y-4">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Structural Diff (Δ vs Previous)</div>
                    <div className="grid grid-cols-2 gap-3 text-[12px]">
                        <div className="flex items-center gap-2 p-2 bg-[hsl(var(--green-bg))] rounded text-[hsl(var(--green-fg))]">
                            <ArrowUpRight size={15} />
                            <span>Added entities: <strong>+{SYNTHETIC_TIMELINE.diff.added_entities}</strong></span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-[hsl(var(--red-bg))] rounded text-[hsl(var(--red-fg))]">
                            <ArrowDownRight size={15} />
                            <span>Removed entities: <strong>-{SYNTHETIC_TIMELINE.diff.removed_entities}</strong></span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-[hsl(var(--green-bg))] rounded text-[hsl(var(--green-fg))]">
                            <ArrowUpRight size={15} />
                            <span>Added links: <strong>+{SYNTHETIC_TIMELINE.diff.added_relationships}</strong></span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-[hsl(var(--red-bg))] rounded text-[hsl(var(--red-fg))]">
                            <ArrowDownRight size={15} />
                            <span>Removed links: <strong>-{SYNTHETIC_TIMELINE.diff.removed_relationships}</strong></span>
                        </div>
                    </div>
                    <div className="text-[11px] font-medium text-[hsl(var(--primary))] pt-1 border-t border-[hsl(var(--border-subtle))]">
                        Shift alert: {SYNTHETIC_TIMELINE.diff.largest_shift}
                    </div>
                </div>
            </div>

            {/* Ingest Milestone Events */}
            <div className="sg-card p-5 space-y-3">
                <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Timeline Ingestion Events</div>
                <div className="divide-y divide-[hsl(var(--border-subtle))]">
                    {SYNTHETIC_TIMELINE.events.map((ev, i) => (
                        <div key={i} className="py-3 flex items-start gap-3">
                            <GitCommit size={15} className="text-[hsl(var(--primary))] shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-[11px] font-semibold text-[hsl(var(--fg-primary))]">{ev.date}</span>
                                    <span className="text-[12px] font-medium text-[hsl(var(--fg-secondary))]">· {ev.title}</span>
                                </div>
                                <div className="text-[11px] text-[hsl(var(--fg-muted))] mt-0.5">{ev.description}</div>
                            </div>
                            <div className="text-right text-[11px] font-mono shrink-0">
                                <span className="text-[hsl(var(--green-fg))]">{ev.entities_delta}</span> / <span className="text-[hsl(var(--primary))]">{ev.rel_delta}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
