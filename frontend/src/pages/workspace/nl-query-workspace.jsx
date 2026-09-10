import React, { useState, useCallback, useRef } from 'react';
import { Brain, Play, Clock3, AlertTriangle, MapPin, Search, Trash2, Copy, Send, ChevronDown, ChevronRight, Eye, ArrowRight } from 'lucide-react';
import { useDemoQueries, askAnalystQuery } from '@/api/intel';
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

const CATEGORY_ICONS = {
    entity: Search,
    relationship: ArrowRight,
    temporal: Clock3,
    evidence: Eye,
    financial: ArrowRight,
    geographic: MapPin,
    cross_case: Copy,
    contradiction: AlertTriangle,
    motif: Brain,
    network: ArrowRight,
};

const CATEGORY_COLORS = {
    entity: 'text-blue-400',
    relationship: 'text-emerald-400',
    temporal: 'text-amber-400',
    evidence: 'text-purple-400',
    financial: 'text-amber-400',
    geographic: 'text-emerald-400',
    cross_case: 'text-rose-400',
    contradiction: 'text-rose-400',
    motif: 'text-purple-400',
    network: 'text-blue-400',
};

function InterpretationView({ interpretation }) {
    const [expanded, setExpanded] = useState(false);
    if (!interpretation) return null;

    return (
        <div className="mt-3 border border-border-subtle bg-bg-root p-3 space-y-2">
            <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
                <div className="flex items-center gap-2">
                    <Eye size={12} className="text-primary" />
                    <span className="text-[10px] font-semibold text-fg-primary">INTERPRETED AS</span>
                </div>
                {expanded ? <ChevronDown size={12} className="text-fg-faint" /> : <ChevronRight size={12} className="text-fg-faint" />}
            </div>
            {expanded && (
                <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                    {interpretation.intent && <div><span className="text-fg-faint">Intent:</span> <span className="text-fg-secondary">{interpretation.intent}</span></div>}
                    {interpretation.entities?.length > 0 && <div><span className="text-fg-faint">Entities:</span> <span className="text-fg-secondary">{interpretation.entities.join(', ')}</span></div>}
                    {interpretation.relationship_types?.length > 0 && <div><span className="text-fg-faint">Relationships:</span> <span className="text-fg-secondary">{interpretation.relationship_types.join(', ')}</span></div>}
                    {interpretation.time_range?.start && <div><span className="text-fg-faint">From:</span> <span className="text-fg-secondary font-mono">{interpretation.time_range.start?.slice(0, 10)}</span></div>}
                    {interpretation.time_range?.end && <div><span className="text-fg-faint">To:</span> <span className="text-fg-secondary font-mono">{interpretation.time_range.end?.slice(0, 10)}</span></div>}
                    {interpretation.filters && Object.keys(interpretation.filters).length > 0 && (
                        <div className="col-span-2"><span className="text-fg-faint">Filters:</span> <span className="text-fg-secondary font-mono">{JSON.stringify(interpretation.filters)}</span></div>
                    )}
                    <div><span className="text-fg-faint">Max results:</span> <span className="text-fg-secondary">{interpretation.max_results}</span></div>
                    {interpretation.notes && <div className="col-span-2 text-fg-faint italic">{interpretation.notes}</div>}
                </div>
            )}
        </div>
    );
}

function ResultItem({ item, index }) {
    return (
        <div className="flex items-start gap-2 border-b border-border-subtle pb-1.5 px-1">
            <span className="mt-0.5 text-[9px] font-mono text-primary">{index + 1}</span>
            <div className="flex-1 min-w-0">
                <div className="text-[10px] text-fg-secondary">{item.label || item.id || item.evidence_id}</div>
                <div className="flex gap-1 mt-0.5 flex-wrap">
                    {item.type && <span className="tp-badge tp-badge-blue">{item.type}</span>}
                    {item.relation && <span className="tp-badge tp-badge-green">{item.relation}</span>}
                    {item.confidence && <span className="text-[9px] text-fg-faint font-mono">conf: {(item.confidence * 100).toFixed(0)}%</span>}
                    {item.source && <span className="tp-badge tp-badge-neutral">{item.source}</span>}
                </div>
                {item.description && <div className="mt-0.5 text-[9px] text-fg-faint">{item.description}</div>}
            </div>
        </div>
    );
}

function HistoryItem({ entry, onRerun }) {
    return (
        <div className="border border-border-subtle bg-bg-root p-2 space-y-1">
            <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-fg-secondary truncate">{entry.query}</span>
                <button onClick={() => onRerun(entry.query)} className="tp-button h-5 text-[9px]">Re-run</button>
            </div>
            <div className="text-[9px] text-fg-faint">{entry.result_count} results · {entry.interpretation?.intent || '—'}</div>
        </div>
    );
}

export default function NLQueryWorkspace() {
    const { activeCase } = useInvestigation();
    const [query, setQuery] = useState('');
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [history, setHistory] = useState([]);
    const inputRef = useRef(null);

    const { data: demoData } = useDemoQueries();
    const demoQueries = demoData?.demo_queries || [];

    const runQuery = useCallback(async (q) => {
        const text = (q || query).trim();
        if (!text) return;
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const data = await askAnalystQuery(text);
            setResult(data);
            setHistory((prev) => [{ query: text, result_count: data.result_count || 0, interpretation: data.interpretation, timestamp: data.timestamp }, ...prev].slice(0, 20));
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [query]);

    function handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            runQuery();
        }
    }

    return (
        <div className="h-full overflow-y-auto animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-bg-surface px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <Brain size={15} className="text-primary" />
                        <h1 className="text-[13px] font-semibold tracking-wide text-fg-primary">ANALYST QUERY</h1>
                    </div>
                    <p className="mt-1 text-[10px] text-fg-faint">Ask analytical questions in natural language — structured queries, deterministic execution.</p>
                </div>
                <span className="text-[9px] text-fg-faint font-mono">{activeCase?.id || 'CASE-0421'}</span>
            </div>

            <div className="grid gap-3 p-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,0.6fr)]">
                {/* Main area */}
                <div className="space-y-3">
                    {/* Input */}
                    <Panel title="ASK A QUESTION" icon={Brain}>
                        <div className="flex items-start gap-2">
                            <textarea
                                ref={inputRef}
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Show financial connections of P-0172..."
                                className="tp-input min-h-[60px] flex-1 text-[11px] resize-y"
                                rows={2}
                            />
                            <button
                                onClick={() => runQuery()}
                                disabled={loading || !query.trim()}
                                className="tp-button tp-button-primary h-8 mt-auto flex items-center gap-1 text-[10px]"
                            >
                                <Send size={12} />
                                {loading ? 'Running...' : 'Ask'}
                            </button>
                        </div>
                        {/* Demo queries */}
                        {demoQueries.length > 0 && (
                            <div className="mt-3">
                                <div className="text-[9px] text-fg-faint mb-1">TRY THESE</div>
                                <div className="flex flex-wrap gap-1">
                                    {demoQueries.map((dq, i) => (
                                        <button key={i} onClick={() => { setQuery(dq.query); runQuery(dq.query); }} className="tp-button h-6 text-[9px]">
                                            {dq.query}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </Panel>

                    {/* Error */}
                    {error && (
                        <div className="border border-red-800 bg-red-950 p-2 text-[10px] text-red-300">{error}</div>
                    )}

                    {/* Interpretation */}
                    {result?.interpretation && <InterpretationView interpretation={result.interpretation} />}

                    {/* Results */}
                    {result && (
                        <Panel title={`RESULTS — ${result.result_count || 0} items`} icon={Search}>
                            {result.original_query && result.original_query !== query && (
                                <div className="mb-2 text-[9px] text-fg-faint">
                                    Original: "{result.original_query}" → Resolved: "{result.resolved_query}"
                                </div>
                            )}
                            <div className="space-y-1 max-h-[400px] overflow-y-auto">
                                {(result.results || []).map((item, i) => (
                                    <ResultItem key={item.id || item.evidence_id || i} item={item} index={i} />
                                ))}
                                {(!result.results || result.results.length === 0) && !loading && (
                                    <div className="text-[10px] text-fg-faint py-4 text-center">No results returned.</div>
                                )}
                            </div>
                            {result.limitations?.length > 0 && (
                                <div className="mt-3 text-[9px] text-fg-faint">
                                    {result.limitations.map((l, i) => <div key={i}>• {l}</div>)}
                                </div>
                            )}
                        </Panel>
                    )}
                </div>

                {/* Sidebar */}
                <div className="space-y-3">
                    <Panel title="QUERY HISTORY" icon={Clock3}>
                        <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
                            {history.map((entry, i) => (
                                <HistoryItem key={i} entry={entry} onRerun={(q) => { setQuery(q); runQuery(q); }} />
                            ))}
                            {!history.length && (
                                <div className="text-[10px] text-fg-faint py-4 text-center">No queries yet.</div>
                            )}
                        </div>
                    </Panel>

                    <Panel title="SUPPORTED INTENTS" icon={Search}>
                        <div className="space-y-1">
                            {[
                                { intent: 'entity_neighbors', label: 'Who is connected to X?' },
                                { intent: 'relationship_query', label: 'Show relationships of X' },
                                { intent: 'temporal_change', label: 'What changed after date?' },
                                { intent: 'evidence_for', label: 'What evidence supports X?' },
                                { intent: 'cross_case', label: 'Which cases contain X?' },
                                { intent: 'bridge_entities', label: 'Who connects communities?' },
                                { intent: 'financial_flow', label: 'Show money flows from A to B' },
                                { intent: 'contradiction', label: 'What contradicts this hypothesis?' },
                                { intent: 'motif_search', label: 'Find patterns involving X' },
                            ].map(({ intent, label }) => (
                                <div key={intent} className="flex items-center gap-2 text-[10px]">
                                    <span className="font-mono text-primary">{intent}</span>
                                    <span className="text-fg-faint">— {label}</span>
                                </div>
                            ))}
                        </div>
                    </Panel>
                </div>
            </div>
        </div>
    );
}
