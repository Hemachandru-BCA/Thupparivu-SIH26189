// src/components/cytoscape-graph.jsx
// Interactive WebGL-capable graph explorer (Cytoscape.js) — Phase H.
//
// Features: pan / zoom / fit, node & edge selection, community coloring,
// PageRank-based node sizing, edge-type styling, ghost nodes as first-class
// translucent dashed objects, inferred-edge dashes, evidence & path
// highlighting, and counterfactual simulation overlays (removed node,
// affected nodes, new brokers, disconnected nodes).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const COMMUNITY_COLORS = [
    '#14b8a6', '#f59e0b', '#3b82f6', '#ef4444', '#8b5cf6',
    '#10b981', '#f97316', '#06b6d4', '#e11d48', '#84cc16',
    '#a855f7', '#0ea5e9', '#d946ef', '#22c55e', '#eab308',
];

function communityColor(id) {
    if (id === null || id === undefined) return '#94a3b8';
    return COMMUNITY_COLORS[Math.abs(Number(id)) % COMMUNITY_COLORS.length];
}

const NODE_TYPE_LABELS = {
    PERSON: 'PERSON',
    LOCATION: 'LOC',
    ORGANIZATION: 'ORG',
    ACCOUNT: 'ACC',
    PHONE: 'PHONE',
    VEHICLE: 'VEH',
    EVENT: 'EVENT',
    DOCUMENT: 'DOC',
    GHOST: 'HYP',
};

function buildElements(nodes, edges, options = {}) {
    const { affectedIds = [], brokerIds = [], removedId = null, dimOthers = false } = options;
    const affected = new Set(affectedIds.map(String));
    const brokers = new Set(brokerIds.map(String));

    const nodeEls = nodes.map((n) => {
        const id = String(n.id);
        const metrics = n.metrics || {};
        const isGhost = String(n.type || '').toUpperCase() === 'GHOST' || Boolean(n.is_ghost);
        const isRemoved = removedId && id === String(removedId);
        const isAffected = affected.has(id);
        const isBroker = brokers.has(id);
        const pagerank = Number(metrics.pagerank || 0);
        const size = isGhost
            ? 34
            : Math.min(46, 14 + Math.sqrt(Math.max(pagerank, 0) * 4000) * 6 + Math.min(10, (n.mention_count || 0) / 8));
        const dim = dimOthers && !isRemoved && !isAffected && !isBroker && id !== String(removedId);
        return {
            group: 'nodes',
            data: {
                id,
                label: n.label || id,
                nodeType: String(n.type || 'UNKNOWN').toUpperCase(),
                community: n.community_id ?? n.community ?? null,
                pagerank,
                isGhost,
                isRemoved,
                isAffected,
                isBroker,
                degree: n.degree || 0,
            },
            classes: [
                isGhost ? 'ghost' : '',
                isRemoved ? 'removed' : '',
                isAffected ? 'affected' : '',
                isBroker ? 'broker' : '',
                dim ? 'dimmed' : '',
            ].filter(Boolean).join(' '),
            style: {
                width: size,
                height: size,
                'background-color': isRemoved ? '#ef4444' : communityColor(n.community_id ?? n.community),
            },
        };
    });

    const present = new Set(nodeEls.map((e) => e.data.id));
    const edgeEls = edges
        .filter((e) => present.has(String(e.source)) && present.has(String(e.target)))
        .map((e, idx) => {
            const inferred = Boolean(e.inferred || (e.attributes || {}).inferred);
            return {
                group: 'edges',
                data: {
                    id: String(e.id ?? `e${idx}`),
                    source: String(e.source),
                    target: String(e.target),
                    relation: e.type || e.label || 'RELATED_TO',
                    evidenceIds: (e.evidence_ids ?? []).map(String),
                },
                classes: [inferred ? 'inferred' : 'observed', (e.evidence_ids ?? []).length ? 'has-evidence' : '']
                    .filter(Boolean)
                    .join(' '),
            };
        });
    return { nodeEls, edgeEls };
}

const STYLESHEET = [
    {
        selector: 'node',
        style: {
            label: 'data(label)',
            'font-size': 7,
            color: '#e2e8f0',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'text-background-color': '#0a101b',
            'text-background-opacity': 0.75,
            'text-background-padding': 2,
            'text-background-shape': 'roundrectangle',
            'border-width': 1.5,
            'border-color': '#34465d',
            'min-zoomed-font-size': 5,
        },
    },
    {
        selector: 'edge',
        style: {
            width: 1.2,
            'line-color': '#405268',
            'curve-style': 'haystack',
            'haystack-radius': 0.4,
            opacity: 0.55,
        },
    },
    {
        selector: 'edge.observed',
        style: { 'line-style': 'solid' },
    },
    {
        selector: 'edge.inferred',
        style: { 'line-style': 'dashed', 'line-color': '#f59e0b', opacity: 0.72 },
    },
    {
        selector: 'edge.has-evidence',
        style: { 'line-color': '#14b8a6' },
    },
    {
        selector: 'node.ghost',
        style: {
            'border-style': 'dashed',
            'border-width': 3,
            'border-color': '#f59e0b',
            'background-opacity': 0.28,
            'background-color': '#f59e0b',
            shape: 'round-hexagon',
            label: 'data(label)',
            'font-size': 9,
            'font-weight': 'bold',
            color: '#fde68a',
        },
    },
    {
        selector: 'node.removed',
        style: {
            'background-color': '#ef4444',
            'border-color': '#fca5a5',
            'border-width': 3,
            'background-opacity': 0.9,
        },
    },
    {
        selector: 'node.affected',
        style: {
            'border-color': '#f59e0b',
            'border-width': 2.5,
        },
    },
    {
        selector: 'node.broker',
        style: {
            'border-color': '#22d3ee',
            'border-width': 3,
            'border-style': 'double',
        },
    },
    {
        selector: 'node.dimmed',
        style: { opacity: 0.18 },
    },
    {
        selector: 'edge.dimmed',
        style: { opacity: 0.06 },
    },
    {
        selector: 'node.selected',
        style: { 'border-width': 4, 'border-color': '#f8fafc' },
    },
    {
        selector: 'edge.highlighted',
        style: { width: 3, 'line-color': '#f8fafc', opacity: 1, 'curve-style': 'bezier' },
    },
];

export function CytoscapeGraph({
    nodes,
    edges,
    onNodeSelect,
    onEdgeSelect,
    focusNodeId,
    highlightPathIds,
    simulation,
    height = 560,
    layoutName = 'cose',
}) {
    const containerRef = useRef(null);
    const cyRef = useRef(null);
    const [ready, setReady] = useState(false);
    const [expanded, setExpanded] = useState(false);

    const { nodeEls, edgeEls } = useMemo(
        () => buildElements(nodes, edges, {
            affectedIds: simulation?.affected_nodes ?? [],
            brokerIds: (simulation?.new_brokers ?? []).map((b) => b.guid),
            removedId: simulation?.removed ? String(simulation.removed) : (simulation?.target_node_id ?? null),
            dimOthers: Boolean(simulation),
        }),
        [nodes, edges, simulation],
    );

    useEffect(() => {
        let cancelled = false;
        let cy;
        (async () => {
            const cytoscape = (await import('cytoscape')).default;
            if (cancelled || !containerRef.current) return;
            cy = cytoscape({
                container: containerRef.current,
                elements: [...nodeEls, ...edgeEls],
                style: STYLESHEET,
                layout: { name: layoutName, animate: false, randomize: true, nodeOverlap: 12, idealEdgeLength: 60 },
                wheelSensitivity: 0.25,
            });
            cyRef.current = cy;
            cy.on('tap', 'node', (evt) => onNodeSelect?.(evt.target.data()));
            cy.on('tap', 'edge', (evt) => onEdgeSelect?.(evt.target.data()));
            cy.on('tap', (evt) => {
                if (evt.target === cy) onNodeSelect?.(null);
            });
            setReady(true);
        })();
        return () => {
            cancelled = true;
            setReady(false);
            if (cy) cy.destroy();
            cyRef.current = null;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // data updates
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy || !ready) return;
        cy.elements().remove();
        cy.add([...nodeEls, ...edgeEls]);
        cy.layout({ name: layoutName, animate: false, randomize: true, nodeOverlap: 12, idealEdgeLength: 60 }).run();
        cy.fit(undefined, 40);
    }, [nodeEls, edgeEls, layoutName, ready]);

    // focus node
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy || !ready || !focusNodeId) return;
        const target = cy.getElementById(String(focusNodeId));
        if (target.nonempty()) {
            cy.elements().removeClass('selected highlighted');
            target.addClass('selected');
            target.connectedEdges().addClass('highlighted');
            cy.animate({ center: { eles: target }, zoom: 1.6 }, { duration: 350 });
        }
    }, [focusNodeId, ready]);

    // path highlight
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy || !ready) return;
        cy.edges().removeClass('highlighted');
        cy.nodes().removeClass('selected');
        if (highlightPathIds?.length) {
            const ids = highlightPathIds.map(String);
            for (let i = 0; i < ids.length - 1; i++) {
                cy.getElementById(`${ids[i]}`).connectedEdges().forEach((edge) => {
                    const s = edge.data('source');
                    const t = edge.data('target');
                    if ((s === ids[i] && t === ids[i + 1]) || (s === ids[i + 1] && t === ids[i])) {
                        edge.addClass('highlighted');
                    }
                });
            }
            ids.forEach((id) => cy.getElementById(id).addClass('selected'));
        }
    }, [highlightPathIds, ready]);

    const fit = useCallback(() => cyRef.current?.fit(undefined, 40), []);
    const zoom = useCallback((factor) => {
        const cy = cyRef.current;
        if (!cy) return;
        cy.animate({ zoom: Math.max(0.3, Math.min(3, cy.zoom() * factor)), center: cy.center() }, { duration: 180 });
    }, []);
    const relayout = useCallback(() => {
        cyRef.current?.layout({ name: layoutName, animate: true, nodeOverlap: 12, idealEdgeLength: 60 }).run();
    }, [layoutName]);

    const ghostCount = useMemo(() => nodeEls.filter((n) => n.data.isGhost).length, [nodeEls]);

    return (
        <div className="relative overflow-hidden rounded-md border border-card-border bg-[#0a101b] shadow-[inset_0_0_80px_rgba(20,184,166,.04)]" style={{ height }}>
            <div ref={containerRef} style={{ height: '100%', width: '100%' }} data-testid="cytoscape-container" />
            <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-1.5">
                <span className="rounded bg-background/80 px-2 py-1 font-mono-ui text-[9px] uppercase tracking-wide text-foreground/80 backdrop-blur">
                    {nodes.length} nodes · {edges.length} edges
                </span>
                {ghostCount > 0 && (
                    <span className="rounded bg-primary/20 px-2 py-1 font-mono-ui text-[9px] uppercase tracking-wide text-primary backdrop-blur">
                        {ghostCount} ghost hypotheses
                    </span>
                )}
                {simulation && (
                    <span className="rounded bg-chart-4/20 px-2 py-1 font-mono-ui text-[9px] uppercase tracking-wide text-chart-4 backdrop-blur">
                        counterfactual overlay
                    </span>
                )}
            </div>
            <div className="absolute right-3 top-3 flex gap-1.5">
                <button aria-label="Fit graph" onClick={fit} className="rounded border border-border bg-background/85 px-2.5 py-1.5 font-mono-ui text-[10px] uppercase text-foreground/80 backdrop-blur hover:text-foreground" title="Fit to screen">
                    Fit
                </button>
                <button aria-label="Zoom out" onClick={() => zoom(0.8)} className="rounded border border-border bg-background/85 px-2.5 py-1.5 font-mono-ui text-[10px] uppercase text-foreground/80 backdrop-blur hover:text-foreground" title="Zoom out">
                    −
                </button>
                <button aria-label="Zoom in" onClick={() => zoom(1.25)} className="rounded border border-border bg-background/85 px-2.5 py-1.5 font-mono-ui text-[10px] uppercase text-foreground/80 backdrop-blur hover:text-foreground" title="Zoom in">
                    +
                </button>
                <button aria-label="Re-run graph layout" onClick={relayout} className="rounded border border-border bg-background/85 px-2.5 py-1.5 font-mono-ui text-[10px] uppercase text-foreground/80 backdrop-blur hover:text-foreground" title="Re-run layout">
                    Layout
                </button>
            </div>
            <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-2 rounded-md bg-background/85 px-3 py-2 backdrop-blur">
                <LegendSwatch color="#14b8a6" label="observed edge" />
                <LegendSwatch color="#f59e0b" label="inferred / ghost" dashed />
                <LegendSwatch color="#ef4444" label="removed (sim)" />
                <LegendSwatch color="#f59e0b" label="affected" />
                <LegendSwatch color="#22d3ee" label="new broker" />
            </div>
            {!ready && (
                <div className="absolute inset-0 grid place-items-center bg-background/70">
                    <div className="font-mono-ui text-[10px] uppercase tracking-[0.2em] text-muted-foreground">loading graph engine…</div>
                </div>
            )}
        </div>
    );
}

function LegendSwatch({ color, label, dashed = false }) {
    return (
        <span className="flex items-center gap-1.5 font-mono-ui text-[9px] uppercase text-foreground/70">
            <span
                className="inline-block h-2.5 w-4 rounded-sm border"
                style={{ borderColor: color, background: dashed ? 'transparent' : color, borderStyle: dashed ? 'dashed' : 'solid' }}
            />
            {label}
        </span>
    );
}

export { communityColor, NODE_TYPE_LABELS };
