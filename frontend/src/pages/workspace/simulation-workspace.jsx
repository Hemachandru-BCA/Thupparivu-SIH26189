/**
 * Scenarios Workspace — SentinelGraph Investigative Workbench
 * Matches PDF Spec §12: Scenarios.
 * Subject: Nicole Jackson (ENT-1042)
 * Baseline vs Simulated comparison (14→19 components, 12,704→11,982 largest, 847 affected, 63 rerouted).
 */
import React, { useState } from 'react';
import { Zap, AlertTriangle, Shield, Play, Save, Info, ArrowRight } from 'lucide-react';
import { SYNTHETIC_SCENARIO } from '@/state/synthetic-case-data';

export default function SimulationWorkspace() {
    const [scenarioRun, setScenarioRun] = useState(true);
    const [selectedSubject, setSelectedSubject] = useState(SYNTHETIC_SCENARIO.primary_subject.name);

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[hsl(var(--border-default))]">
                <div className="flex items-center gap-2">
                    <Zap size={18} className="text-[hsl(var(--primary))]" />
                    <h1 className="text-[18px] font-semibold text-[hsl(var(--fg-primary))]">Counterfactual Scenarios</h1>
                </div>
                <span className="px-2 py-0.5 text-[11px] font-semibold bg-[hsl(var(--amber-bg))] text-[hsl(var(--amber-fg))] border border-[hsl(var(--amber-border))] rounded">
                    SIMULATED
                </span>
            </div>

            {/* Simulated Result Notice Banner */}
            <div className="sg-warning-banner">
                <AlertTriangle size={16} className="text-[hsl(var(--amber))] shrink-0 mt-0.5" />
                <div className="text-[12px] space-y-0.5">
                    <div className="font-semibold">{SYNTHETIC_SCENARIO.notice}</div>
                    <div className="text-[11px] text-[hsl(var(--fg-secondary))]">{SYNTHETIC_SCENARIO.disclaimer}</div>
                </div>
            </div>

            {/* Scenario Configuration Deck */}
            <div className="sg-card p-5 space-y-4">
                <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Scenario Setup</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="text-[11px] text-[hsl(var(--fg-muted))] block mb-1">Target entity subject</label>
                        <input
                            className="sg-input font-medium"
                            value={selectedSubject}
                            onChange={e => setSelectedSubject(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="text-[11px] text-[hsl(var(--fg-muted))] block mb-1">Analytical action</label>
                        <select className="sg-select w-full">
                            <option>{SYNTHETIC_SCENARIO.action}</option>
                            <option>Isolate community cluster</option>
                            <option>Sever cross-border bridge edges</option>
                        </select>
                    </div>
                </div>
                <div className="flex justify-end gap-2">
                    <button className="sg-btn" onClick={() => alert('Scenario configuration saved as draft.')}>
                        <Save size={13} /> Save scenario
                    </button>
                    <button className="sg-btn sg-btn-primary" onClick={() => setScenarioRun(true)}>
                        <Play size={13} /> Run scenario
                    </button>
                </div>
            </div>

            {/* Structural Impact: Baseline vs Simulated */}
            <div className="sg-card p-5 space-y-4">
                <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">
                    Structural Impact: Baseline vs Simulated
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                        <div className="text-[11px] text-[hsl(var(--fg-muted))]">Connected components</div>
                        <div className="font-mono text-[16px] font-bold text-[hsl(var(--fg-primary))] mt-1">
                            {SYNTHETIC_SCENARIO.baseline.connected_components} <span className="text-[hsl(var(--primary))] font-normal">→ {SYNTHETIC_SCENARIO.simulated.connected_components}</span>
                        </div>
                    </div>
                    <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                        <div className="text-[11px] text-[hsl(var(--fg-muted))]">Largest component size</div>
                        <div className="font-mono text-[16px] font-bold text-[hsl(var(--fg-primary))] mt-1">
                            {SYNTHETIC_SCENARIO.baseline.largest_component.toLocaleString()} <span className="text-[hsl(var(--red-fg))] font-normal">→ {SYNTHETIC_SCENARIO.simulated.largest_component.toLocaleString()}</span>
                        </div>
                    </div>
                    <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                        <div className="text-[11px] text-[hsl(var(--fg-muted))]">Affected entities</div>
                        <div className="font-mono text-[16px] font-bold text-[hsl(var(--amber-fg))] mt-1">
                            {SYNTHETIC_SCENARIO.simulated.affected_entities.toLocaleString()}
                        </div>
                    </div>
                    <div className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))]">
                        <div className="text-[11px] text-[hsl(var(--fg-muted))]">Shortest paths rerouted</div>
                        <div className="font-mono text-[16px] font-bold text-[hsl(var(--primary))] mt-1">
                            {SYNTHETIC_SCENARIO.simulated.shortest_paths_rerouted}
                        </div>
                    </div>
                </div>
            </div>

            {/* Impact Details: Most Affected & Communities */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Most Affected Entities */}
                <div className="sg-card p-5 space-y-3">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Most Affected Neighbors</div>
                    <div className="divide-y divide-[hsl(var(--border-subtle))]">
                        {SYNTHETIC_SCENARIO.most_affected.map(a => (
                            <div key={a.id} className="py-2.5 flex items-center justify-between text-[12px]">
                                <div>
                                    <span className="font-mono text-[hsl(var(--primary))] font-medium">{a.id}</span>
                                    <span className="font-medium text-[hsl(var(--fg-primary))] ml-2">{a.name}</span>
                                </div>
                                <span className="text-[11px] text-[hsl(var(--fg-muted))]">{a.impact}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Community Conductance Shift */}
                <div className="sg-card p-5 space-y-3">
                    <div className="text-[11px] font-semibold text-[hsl(var(--fg-muted))] uppercase tracking-wider">Community Conductance Shift</div>
                    <div className="space-y-3 pt-1">
                        {SYNTHETIC_SCENARIO.community_impact.map(c => (
                            <div key={c.community} className="p-3 bg-[hsl(var(--bg-panel))] rounded border border-[hsl(var(--border-subtle))] flex items-center justify-between">
                                <span className="text-[12px] font-medium text-[hsl(var(--fg-primary))]">{c.community}</span>
                                <span className="font-mono text-[12px] text-[hsl(var(--amber-fg))] font-semibold">
                                    {c.affected} entities disconnected/shifted
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
