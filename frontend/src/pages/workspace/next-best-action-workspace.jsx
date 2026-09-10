import React, { useState } from 'react';
import { Compass, Target, Clock3, AlertTriangle, CheckCircle2, XCircle, ChevronDown, ChevronRight, Eye, ExternalLink, Star } from 'lucide-react';
import { useRecommendations, submitRecommendationFeedback } from '@/api/intel';
import { useInvestigation } from '@/state/investigation-context';

function Panel({ title, icon: Icon, children, className = '' }) {
    return (
        <section className={`tp-panel p-3 ${className}`}>
            <div className="flex items-center gap-2 mb-3">
                <Icon size={14} className="text-primary" />
                <h2 className="text-[11px] font-semibold tracking-wide text-fg-primary">{title}</h2>
            </div>
            {children}
        </section>
    );
}

const PRIORITY_COLORS = {
    high: 'border-l-4 border-l-amber-400',
    medium: 'border-l-4 border-l-blue-400',
    low: 'border-l-4 border-l-border-subtle',
};

const ACTION_ICONS = {
    inspect_entity: Eye,
    expand_network: ExternalLink,
    inspect_evidence: Eye,
    review_contradiction: AlertTriangle,
    replay_timeline: Clock3,
    trace_financial_flow: Target,
    inspect_motif: Star,
    compare_case: ExternalLink,
    inspect_location: ExternalLink,
    review_data_quality: AlertTriangle,
    compare_methods: ExternalLink,
};

function ScoreBar({ label, value, maxLabel }) {
    return (
        <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[9px] text-fg-secondary">
                <span>{label}</span>
                <span className="font-mono">{value}</span>
            </div>
            <div className="h-1 bg-bg-root">
                <div className="h-full bg-primary" style={{ width: `${Math.min(100, value * 100)}%` }} />
            </div>
        </div>
    );
}

function RecommendationCard({ rec, onAction }) {
    const [expanded, setExpanded] = useState(false);
    const [feedback, setFeedback] = useState(null);
    const ActionIcon = ACTION_ICONS[rec.action_type] || Compass;
    const priorityClass = PRIORITY_COLORS[rec.priority] || PRIORITY_COLORS.medium;

    async function handleFeedback(action) {
        try {
            await submitRecommendationFeedback(rec.recommendation_id, action);
            setFeedback(action);
        } catch (e) {
            console.error(e);
        }
    }

    return (
        <div className={`bg-bg-root border border-border-subtle px-3 py-2 ${priorityClass}`}>
            <div className="flex items-start gap-2">
                <ActionIcon size={14} className="mt-0.5 shrink-0 text-primary" />
                <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-semibold text-fg-primary">{rec.title}</div>
                    <div className="text-[9px] text-fg-faint mt-0.5">{rec.reason}</div>
                    <div className="flex items-center gap-2 mt-1">
                        <span className={`tp-badge ${rec.priority === 'high' ? 'tp-badge-yellow' : rec.priority === 'medium' ? 'tp-badge-blue' : 'tp-badge-neutral'}`}>
                            {rec.priority}
                        </span>
                        <span className="tp-badge tp-badge-green">{rec.action_type}</span>
                        {rec.confidence && <span className="text-[9px] text-fg-faint font-mono">conf: {(rec.confidence * 100).toFixed(0)}%</span>}
                    </div>
                </div>
                <button onClick={() => setExpanded(!expanded)} className="text-fg-faint hover:text-fg-secondary">
                    {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
            </div>

            {expanded && (
                <div className="mt-3 space-y-2 border-t border-border-subtle pt-2">
                    {/* Score components */}
                    {rec.score_components && (
                        <div className="space-y-1">
                            <div className="text-[9px] font-semibold text-fg-faint">WHY THIS IS SUGGESTED</div>
                            <ScoreBar label="Evidence value" value={rec.score_components.evidence_value || 0} />
                            <ScoreBar label="Information gain" value={rec.score_components.information_gain || 0} />
                            <ScoreBar label="Cross-case relevance" value={rec.score_components.cross_case_relevance || 0} />
                            <ScoreBar label="Temporal relevance" value={rec.score_components.temporal_relevance || 0} />
                            <ScoreBar label="Unresolved uncertainty" value={rec.score_components.unresolved_uncertainty || 0} />
                        </div>
                    )}

                    {/* Context */}
                    {rec.context && (
                        <div className="text-[9px] text-fg-faint">
                            {rec.context.case_id && <div>Case: {rec.context.case_id}</div>}
                            {rec.context.entity_id && <div>Entity: {rec.context.entity_id}</div>}
                        </div>
                    )}

                    {/* Feedback buttons */}
                    {!feedback ? (
                        <div className="flex items-center gap-1.5 pt-1">
                            <span className="text-[9px] text-fg-faint mr-1">Action:</span>
                            {[
                                { key: 'open', label: 'Open', icon: ExternalLink },
                                { key: 'dismiss', label: 'Dismiss', icon: XCircle },
                                { key: 'defer', label: 'Defer', icon: Clock3 },
                                { key: 'completed', label: 'Done', icon: CheckCircle2 },
                            ].map(({ key, label, icon: Icon }) => (
                                <button key={key} onClick={() => handleFeedback(key)} className="tp-button h-5 text-[9px] flex items-center gap-0.5">
                                    <Icon size={10} />{label}
                                </button>
                            ))}
                        </div>
                    ) : (
                        <div className="flex items-center gap-1 text-[9px] text-emerald-400 pt-1">
                            <CheckCircle2 size={10} />
                            <span>Recorded: {feedback}</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default function NextBestActionWorkspace() {
    const { activeCase, selectedEntity, selectedHypothesis } = useInvestigation();
    const [filterType, setFilterType] = useState('');
    const [filterPriority, setFilterPriority] = useState('');

    const caseId = activeCase?.id || 'CASE-0421';
    const entityId = selectedEntity?.id;

    const params = { case_id: caseId, limit: 25 };
    if (entityId) params.entity_id = entityId;
    if (filterType) params.action_type = filterType;
    if (filterPriority) params.min_priority = filterPriority;

    const { data, isLoading } = useRecommendations(params);
    const recommendations = data?.recommendations || [];

    // Group by priority
    const high = recommendations.filter((r) => r.priority === 'high');
    const medium = recommendations.filter((r) => r.priority === 'medium');
    const low = recommendations.filter((r) => r.priority === 'low' || !['high', 'medium'].includes(r.priority));

    return (
        <div className="h-full overflow-y-auto animate-fade-in">
            <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-bg-surface px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <Compass size={15} className="text-primary" />
                        <h1 className="text-[13px] font-semibold tracking-wide text-fg-primary">NEXT-BEST ANALYTICAL ACTION</h1>
                    </div>
                    <p className="mt-1 text-[10px] text-fg-faint">Contextual recommendations for what to explore next.</p>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[9px] text-fg-faint font-mono">{caseId}</span>
                    {entityId && <span className="tp-badge tp-badge-blue">FOCUSED: {selectedEntity?.label || entityId}</span>}
                </div>
            </div>

            <div className="grid gap-3 p-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
                <div className="space-y-3">
                    {isLoading && (
                        <div className="text-[10px] text-fg-faint py-8 text-center">Generating recommendations...</div>
                    )}

                    {/* High priority */}
                    {high.length > 0 && (
                        <Panel title={`HIGH PRIORITY (${high.length})`} icon={Star} className="border-l-2 border-l-amber-400">
                            <div className="space-y-2">
                                {high.map((rec) => <RecommendationCard key={rec.recommendation_id} rec={rec} />)}
                            </div>
                        </Panel>
                    )}

                    {/* Medium priority */}
                    {medium.length > 0 && (
                        <Panel title={`MEDIUM PRIORITY (${medium.length})`} icon={Target}>
                            <div className="space-y-2">
                                {medium.map((rec) => <RecommendationCard key={rec.recommendation_id} rec={rec} />)}
                            </div>
                        </Panel>
                    )}

                    {/* Low priority */}
                    {low.length > 0 && (
                        <Panel title={`LOW PRIORITY (${low.length})`} icon={Compass}>
                            <div className="space-y-2">
                                {low.map((rec) => <RecommendationCard key={rec.recommendation_id} rec={rec} />)}
                            </div>
                        </Panel>
                    )}

                    {!isLoading && recommendations.length === 0 && (
                        <div className="text-[10px] text-fg-faint py-8 text-center">
                            No recommendations at this time.
                            <div className="mt-2">Try selecting an entity or expanding the network.</div>
                        </div>
                    )}
                </div>

                {/* Sidebar */}
                <div className="space-y-3">
                    <Panel title="RECOMMENDATION SUMMARY" icon={Compass}>
                        <div className="grid grid-cols-2 gap-1.5">
                            <div className="border border-border-subtle bg-bg-root px-2 py-2">
                                <div className="text-[9px] text-fg-faint">Total</div>
                                <div className="text-[16px] font-mono text-fg-primary">{recommendations.length}</div>
                            </div>
                            <div className="border border-border-subtle bg-bg-root px-2 py-2">
                                <div className="text-[9px] text-fg-faint">High</div>
                                <div className="text-[16px] font-mono text-amber-400">{high.length}</div>
                            </div>
                            <div className="border border-border-subtle bg-bg-root px-2 py-2">
                                <div className="text-[9px] text-fg-faint">Medium</div>
                                <div className="text-[16px] font-mono text-blue-400">{medium.length}</div>
                            </div>
                            <div className="border border-border-subtle bg-bg-root px-2 py-2">
                                <div className="text-[9px] text-fg-faint">Low</div>
                                <div className="text-[16px] font-mono text-fg-secondary">{low.length}</div>
                            </div>
                        </div>
                    </Panel>

                    <Panel title="FILTERS" icon={Target}>
                        <div className="space-y-2">
                            <div>
                                <div className="text-[9px] text-fg-faint mb-1">Action type</div>
                                <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="tp-input h-6 w-full text-[10px]">
                                    <option value="">All types</option>
                                    <option value="inspect_entity">Inspect entity</option>
                                    <option value="expand_network">Expand network</option>
                                    <option value="inspect_evidence">Inspect evidence</option>
                                    <option value="review_contradiction">Review contradiction</option>
                                    <option value="replay_timeline">Replay timeline</option>
                                    <option value="trace_financial_flow">Trace financial flow</option>
                                    <option value="inspect_motif">Inspect motif</option>
                                    <option value="compare_case">Compare case</option>
                                    <option value="review_data_quality">Review data quality</option>
                                    <option value="compare_methods">Compare methods</option>
                                </select>
                            </div>
                        </div>
                    </Panel>

                    <Panel title="HOW THIS WORKS" icon={Compass}>
                        <div className="space-y-1.5 text-[9px] text-fg-faint">
                            <div>• Recommendations use current investigation context</div>
                            <div>• Score components are transparent and explainable</div>
                            <div>• Feedback is recorded but does not automatically retrain</div>
                            <div>• All suggestions are analytical steps only</div>
                            <div className="text-rose-400 mt-2">• No enforcement recommendations are ever generated</div>
                        </div>
                    </Panel>
                </div>
            </div>
        </div>
    );
}
