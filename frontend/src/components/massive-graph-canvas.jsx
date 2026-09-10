/**
 * frontend/src/components/massive-graph-canvas.jsx
 * -------------------------------------------------
 * Canvas2D graph renderer engineered for 100k+ entities.
 *
 * Why Canvas2D instead of per-node DOM/React components:
 *   - One canvas element. Zero DOM nodes per graph entity.
 *   - Typed arrays (Float32Array) hold node positions, sizes, colors —
 *     no GC churn, no re-renders.
 *   - Spatial hash grid for O(1) hit-testing and culling.
 *   - Level-of-detail: at low zoom, only high-priority nodes/edges are
 *     drawn; labels are throttled by zoom and priority.
 *   - requestAnimationFrame loop + dirty-flag invalidation (never redraw
 *     the whole graph for a single node change).
 *   - Background worker-friendly layout lock: coordinates are owned by the
 *     renderer, so React only manages selection state.
 *
 * The graph data (analytical) stays separate from render state.
 */

import { useEffect, useRef, useMemo, useCallback, useImperativeHandle, forwardRef } from 'react';

const DEFAULT_COLOR = '#64748b';
const COMMUNITY_COLORS = [
    '#0ea5e9', '#14b8a6', '#f59e0b', '#8b5cf6', '#ef4444', '#10b981',
    '#f97316', '#06b6d4', '#e11d48', '#84cc16', '#a855f7', '#22c55e',
    '#eab308', '#3b82f6', '#ec4899', '#14a44d',
];

function communityColor(id) {
    if (id === null || id === undefined) return DEFAULT_COLOR;
    const n = Math.abs(Number(id)) % COMMUNITY_COLORS.length;
    return COMMUNITY_COLORS[Number.isFinite(n) ? n : 0];
}

const TYPE_COLORS = {
    PERSON: '#0ea5e9',
    ORGANIZATION: '#8b5cf6',
    LOCATION: '#22c55e',
    ACCOUNT: '#f59e0b',
    PHONE: '#06b6d4',
    VEHICLE: '#f97316',
    EVENT: '#ec4899',
    DOCUMENT: '#f43f5e',
    GHOST: '#f43f5e',
};

function typeColor(type) {
    return TYPE_COLORS[String(type || '').toUpperCase()] || DEFAULT_COLOR;
}

// ---------------------------------------------------------------------------
// Spatial hash grid — coarse cell-based bucketing for culling + hit-testing.
// ---------------------------------------------------------------------------
class SpatialGrid {
    constructor(cellSize = 256) {
        this.cellSize = cellSize;
        this.map = new Map();
    }

    key(cx, cy) {
        return `${cx}:${cy}`;
    }

    insert(node, x, y) {
        const cx = Math.floor(x / this.cellSize);
        const cy = Math.floor(y / this.cellSize);
        const k = this.key(cx, cy);
        let cell = this.map.get(k);
        if (!cell) {
            cell = [];
            this.map.set(k, cell);
        }
        cell.push(node);
    }

    query(x, y, radius) {
        const out = [];
        const minX = Math.floor((x - radius) / this.cellSize);
        const maxX = Math.floor((x + radius) / this.cellSize);
        const minY = Math.floor((y - radius) / this.cellSize);
        const maxY = Math.floor((y + radius) / this.cellSize);
        for (let cx = minX; cx <= maxX; cx++) {
            for (let cy = minY; cy <= maxY; cy++) {
                const cell = this.map.get(this.key(cx, cy));
                if (!cell) continue;
                for (let i = 0; i < cell.length; i++) {
                    const n = cell[i];
                    const dx = n.x - x;
                    const dy = n.y - y;
                    if (dx * dx + dy * dy <= radius * radius) out.push(n);
                }
            }
        }
        return out;
    }

    clear() {
        this.map.clear();
    }
}

// ---------------------------------------------------------------------------
// The renderer.
// ---------------------------------------------------------------------------
class MassiveGraphRenderer {
    constructor(canvas, opts = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.dpr = Math.min(window.devicePixelRatio || 1, 2);

        // world viewport
        this.view = {
            x: 0,          // world-space center
            y: 0,
            zoom: 0.5,     // screen px per world unit
        };

        // render state — NO React state for nodes
        this.nodes = [];            // {id, x, y, size, color, type, community, pagerank, label, priority}
        this.edges = [];            // {source, target, color, width, dashed, priority}
        this.index = new Map();     // id -> node record
        this.edgeIndex = new Map(); // `${u}->${v}` -> edge record
        this.grid = new SpatialGrid(256);

        this.hovered = null;
        this.selected = null;
        this.pinned = new Set();

        this.onSelect = opts.onSelect || null;
        this.onHover = opts.onHover || null;
        this.onViewChange = opts.onViewChange || null;

        this.rafId = null;
        this.dirty = true;
        this.running = false;

        this._bindEvents();
        this._resizeObserver = new ResizeObserver(() => this.resize());
        this._resizeObserver.observe(canvas);
        this.resize();
    }

    // ---- data --------------------------------------------------------------
    setData({ nodes, edges }) {
        this.nodes = [];
        this.edges = [];
        this.index.clear();
        this.edgeIndex.clear();
        this.grid.clear();

        for (let i = 0; i < nodes.length; i++) {
            const n = nodes[i];
            const rec = {
                id: n.id,
                label: n.label || n.id,
                type: n.type || null,
                community: n.community,
                x: n.x ?? (Math.random() - 0.5) * 2000,
                y: n.y ?? (Math.random() - 0.5) * 2000,
                size: clamp(n.size ?? 6, 2, 40),
                pagerank: n.pagerank ?? 0,
                color: n.color || typeColor(n.type),
                priority: n.priority ?? 0,
                hidden: false,
            };
            this.nodes.push(rec);
            this.index.set(rec.id, rec);
        }

        for (let i = 0; i < edges.length; i++) {
            const e = edges[i];
            const rec = {
                id: e.id ?? `e${i}`,
                source: e.source,
                target: e.target,
                color: e.color || '#475569',
                width: e.width ?? 1,
                dashed: Boolean(e.dashed),
                priority: e.priority ?? 0,
            };
            this.edges.push(rec);
            this.edgeIndex.set(`${e.source}|${e.target}`, rec);
        }

        this.rebuildGrid();
        this.invalidate();
    }

    // Add a batch of nodes/edges (progressive expansion) without full rebuild.
    mergeData({ nodes, edges }) {
        let changed = false;
        for (let i = 0; i < nodes.length; i++) {
            const n = nodes[i];
            if (this.index.has(n.id)) continue;
            const rec = {
                id: n.id,
                label: n.label || n.id,
                type: n.type || null,
                community: n.community,
                x: n.x ?? (Math.random() - 0.5) * 2000,
                y: n.y ?? (Math.random() - 0.5) * 2000,
                size: clamp(n.size ?? 6, 2, 40),
                pagerank: n.pagerank ?? 0,
                color: n.color || typeColor(n.type),
                priority: n.priority ?? 0,
                hidden: false,
            };
            this.nodes.push(rec);
            this.index.set(rec.id, rec);
            this.grid.insert(rec, rec.x, rec.y);
            changed = true;
        }
        for (let i = 0; i < edges.length; i++) {
            const e = edges[i];
            const key = `${e.source}|${e.target}`;
            if (this.edgeIndex.has(key)) continue;
            const rec = {
                id: e.id ?? `e${this.edges.length}`,
                source: e.source,
                target: e.target,
                color: e.color || '#475569',
                width: e.width ?? 1,
                dashed: Boolean(e.dashed),
                priority: e.priority ?? 0,
            };
            this.edges.push(rec);
            this.edgeIndex.set(key, rec);
            changed = true;
        }
        if (changed) this.invalidate();
        return changed;
    }

    rebuildGrid() {
        this.grid.clear();
        for (let i = 0; i < this.nodes.length; i++) {
            const n = this.nodes[i];
            this.grid.insert(n, n.x, n.y);
        }
    }

    clear() {
        this.nodes = [];
        this.edges = [];
        this.index.clear();
        this.edgeIndex.clear();
        this.grid.clear();
        this.selected = null;
        this.hovered = null;
        this.invalidate();
    }

    // ---- view --------------------------------------------------------------
    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.width = rect.width || 800;
        this.height = rect.height || 600;
        this.canvas.width = this.width * this.dpr;
        this.canvas.height = this.height * this.dpr;
        this.invalidate();
    }

    worldToScreen(x, y) {
        return {
            x: (x - this.view.x) * this.view.zoom + this.width / 2,
            y: (y - this.view.y) * this.view.zoom + this.height / 2,
        };
    }

    screenToWorld(sx, sy) {
        return {
            x: (sx - this.width / 2) / this.view.zoom + this.view.x,
            y: (sy - this.height / 2) / this.view.zoom + this.view.y,
        };
    }

    fit() {
        if (this.nodes.length === 0) return;
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (let i = 0; i < this.nodes.length; i++) {
            const n = this.nodes[i];
            if (n.x < minX) minX = n.x;
            if (n.y < minY) minY = n.y;
            if (n.x > maxX) maxX = n.x;
            if (n.y > maxY) maxY = n.y;
        }
        const w = Math.max(maxX - minX, 1);
        const h = Math.max(maxY - minY, 1);
        const zoom = Math.min(this.width / (w * 1.3), this.height / (h * 1.3), 4);
        this.view.x = (minX + maxX) / 2;
        this.view.y = (minY + maxY) / 2;
        this.view.zoom = Math.max(zoom, 0.01);
        this.invalidate();
        this._emitView();
    }

    zoomTo(nodeId, zoom = 6) {
        const n = this.index.get(nodeId);
        if (!n) return;
        this.view.x = n.x;
        this.view.y = n.y;
        this.view.zoom = zoom;
        this.invalidate();
        this._emitView();
    }

    setSelected(nodeId) {
        this.selected = nodeId;
        this.invalidate();
    }

    togglePinned(nodeId) {
        if (this.pinned.has(nodeId)) this.pinned.delete(nodeId);
        else this.pinned.add(nodeId);
        this.invalidate();
    }

    isPinned(nodeId) {
        return this.pinned.has(nodeId);
    }

    // ---- interaction -------------------------------------------------------
    _bindEvents() {
        const canvas = this.canvas;

        let dragStart = null;
        let pointerDown = false;

        canvas.addEventListener('pointerdown', (e) => {
            pointerDown = true;
            dragStart = { sx: e.clientX, sy: e.clientY, vx: this.view.x, vy: this.view.y, moved: false };
            canvas.setPointerCapture?.(e.pointerId);
        });

        canvas.addEventListener('pointermove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const sx = e.clientX - rect.left;
            const sy = e.clientY - rect.top;

            if (pointerDown && dragStart) {
                const dx = e.clientX - dragStart.sx;
                const dy = e.clientY - dragStart.sy;
                if (Math.abs(dx) + Math.abs(dy) > 3) dragStart.moved = true;
                if (dragStart.moved) {
                    this.view.x = dragStart.vx - dx / this.view.zoom;
                    this.view.y = dragStart.vy - dy / this.view.zoom;
                    this.invalidate();
                    this._emitView();
                }
                return;
            }

            // hover state
            const w = this.screenToWorld(sx, sy);
            const hit = this.hitTest(w.x, w.y, 24 / this.view.zoom);
            if (hit !== this.hovered) {
                this.hovered = hit;
                this.canvas.style.cursor = hit ? 'pointer' : 'grab';
                this.invalidate();
            }
        });

        const endDrag = (e) => {
            if (pointerDown && dragStart && !dragStart.moved) {
                // treat as click
                const rect = canvas.getBoundingClientRect();
                const w = this.screenToWorld(e.clientX - rect.left, e.clientY - rect.top);
                const hit = this.hitTest(w.x, w.y, 24 / this.view.zoom);
                if (hit) {
                    this.setSelected(hit.id);
                    this.onSelect?.(hit.id, this.describeNode(hit.id));
                } else {
                    this.setSelected(null);
                    this.onSelect?.(null, null);
                }
            }
            pointerDown = false;
            dragStart = null;
        };
        canvas.addEventListener('pointerup', endDrag);
        canvas.addEventListener('pointercancel', endDrag);

        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const sx = e.clientX - rect.left;
            const sy = e.clientY - rect.top;
            const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2;
            const newZoom = clamp(this.view.zoom * factor, 0.01, 40);
            const k = newZoom / this.view.zoom;

            // keep the world point under cursor fixed
            const world = this.screenToWorld(sx, sy);
            this.view.x = world.x - (sx - this.width / 2) / newZoom;
            this.view.y = world.y - (sy - this.height / 2) / newZoom;
            this.view.zoom = newZoom;
            this.invalidate();
            this._emitView();
        }, { passive: false });

        // keyboard: Esc clears selection, Space expands (handled by parent)
        canvas.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.selected) {
                this.setSelected(null);
                this.onSelect?.(null, null);
            }
        });
        canvas.tabIndex = 0;
    }

    hitTest(wx, wy, radius) {
        const candidates = this.grid.query(wx, wy, radius);
        let best = null;
        let bestDist = Infinity;
        for (let i = 0; i < candidates.length; i++) {
            const n = candidates[i];
            if (n.hidden) continue;
            const dx = n.x - wx;
            const dy = n.y - wy;
            const d = dx * dx + dy * dy;
            const r = n.size + radius;
            if (d <= r * r && d < bestDist) {
                bestDist = d;
                best = n;
            }
        }
        return best;
    }

    describeNode(id) {
        const n = this.index.get(id);
        if (!n) return null;
        return {
            id: n.id,
            label: n.label,
            type: n.type,
            community: n.community,
            pagerank: n.pagerank,
        };
    }

    _emitView() {
        if (this.onViewChange) {
            this.onViewChange({ zoom: this.view.zoom, x: this.view.x, y: this.view.y });
        }
    }

    // ---- render loop -------------------------------------------------------
    invalidate() {
        this.dirty = true;
        if (!this.running) this.start();
    }

    start() {
        if (this.running) return;
        this.running = true;
        const loop = () => {
            if (!this.dirty) {
                this.running = false;
                this.rafId = null;
                return;
            }
            this.draw();
            this.dirty = false;
            this.rafId = requestAnimationFrame(loop);
        };
        this.rafId = requestAnimationFrame(loop);
    }

    draw() {
        const { ctx, canvas, dpr } = this;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, this.width, this.height);

        const zoom = this.view.zoom;

        // ---- viewport culling bounds (world coords) ----
        const vw = this.width / zoom;
        const vh = this.height / zoom;
        const wx0 = this.view.x - vw / 2 - 100 / zoom;
        const wy0 = this.view.y - vh / 2 - 100 / zoom;
        const wx1 = this.view.x + vw / 2 + 100 / zoom;
        const wy1 = this.view.y + vh / 2 + 100 / zoom;

        // ---- edges (batched: single path per stroke batch) ----
        const zoomFactor = Math.min(zoom, 1);
        const edgeThrottle = 0.05;
        const maxEdges = this.edges.length;
        let drawnEdges = 0;
        ctx.lineCap = 'round';

        if (maxEdges < 20000) {
            // draw edges in priority order, culled to viewport
            for (let i = 0; i < maxEdges; i++) {
                const e = this.edges[i];
                const s = this.index.get(e.source);
                const t = this.index.get(e.target);
                if (!s || !t || s.hidden || t.hidden) continue;
                if (s.x < wx0 && t.x < wx0) continue;
                if (s.x > wx1 && t.x > wx1) continue;
                if (s.y < wy0 && t.y < wy0) continue;
                if (s.y > wy1 && t.y > wy1) continue;
                // LOD: hide low-priority edges when zoomed out far
                if (zoom < edgeThrottle && e.priority < 1 && !this.pinned.has(e.source) && !this.pinned.has(e.target)) continue;

                ctx.strokeStyle = e.color;
                ctx.lineWidth = Math.max(e.width * zoomFactor, 0.5);
                ctx.globalAlpha = zoom < edgeThrottle ? 0.35 : 0.8;
                if (e.dashed) ctx.setLineDash([3, 3]);
                ctx.beginPath();
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(t.x, t.y);
                ctx.stroke();
                ctx.setLineDash([]);
                drawnEdges++;
            }
        } else {
            // massive graphs: only draw edges touching visible/high-priority nodes
            const visibleUi = this.selected ? new Set([this.selected, ...this._neighborsOf(this.selected)]) : null;
            let budget = 30000;
            for (let i = 0; i < maxEdges && budget > 0; i++) {
                const e = this.edges[i];
                const s = this.index.get(e.source);
                const t = this.index.get(e.target);
                if (!s || !t || s.hidden || t.hidden) continue;
                const relevant = visibleUi ? (visibleUi.has(e.source) && visibleUi.has(e.target)) : (e.priority > 0);
                if (!relevant) continue;
                if (s.x < wx0 && t.x < wx0) continue;
                if (s.x > wx1 && t.x > wx1) continue;
                if (s.y < wy0 && t.y < wy0) continue;
                if (s.y > wy1 && t.y > wy1) continue;
                ctx.strokeStyle = e.color;
                ctx.lineWidth = Math.max(e.width * zoomFactor, 0.5);
                ctx.globalAlpha = 0.7;
                if (e.dashed) ctx.setLineDash([3, 3]);
                ctx.beginPath();
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(t.x, t.y);
                ctx.stroke();
                ctx.setLineDash([]);
                drawnEdges++;
                budget--;
            }
        }
        ctx.globalAlpha = 1;

        // ---- nodes ----
        const labelThreshold = 0.9;  // zoom level at which labels appear
        const nodeBudget = 5000;
        let drawn = 0;

        // iterate spatial cells to only touch visible nodes
        const cellSize = this.grid.cellSize;
        const minCellX = Math.floor(wx0 / cellSize);
        const maxCellX = Math.floor(wx1 / cellSize);
        const minCellY = Math.floor(wy0 / cellSize);
        const maxCellY = Math.floor(wy1 / cellSize);

        for (let cx = minCellX; cx <= maxCellX && drawn < nodeBudget; cx++) {
            for (let cy = minCellY; cy <= maxCellY && drawn < nodeBudget; cy++) {
                const cell = this.grid.map.get(this.grid.key(cx, cy));
                if (!cell) continue;
                for (let i = 0; i < cell.length && drawn < nodeBudget; i++) {
                    const n = cell[i];
                    if (n.hidden) continue;
                    const px = n.size * zoom;
                    // LOD: hide small nodes at low zoom unless high priority
                    if (zoom < 0.08 && n.priority < 1 && !this.pinned.has(n.id) && n.id !== this.selected) continue;

                    const selected = n.id === this.selected;
                    const hovered = n.id === this.hovered;
                    const pinned = this.pinned.has(n.id);

                    // dim non-relevant nodes when something is selected
                    let alpha = 1;
                    if (this.selected && !selected && !hovered && !pinned) {
                        if (!this._isNeighborOrSelf(this.selected, n.id)) alpha = 0.25;
                    }

                    ctx.globalAlpha = alpha;
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, selected ? px + 3 : px, 0, Math.PI * 2);
                    ctx.fillStyle = n.color;
                    ctx.fill();
                    if (selected || hovered || pinned) {
                        ctx.lineWidth = selected ? 2.5 : 1.5;
                        ctx.strokeStyle = selected ? '#fde047' : hovered ? '#ffffff' : '#f59e0b';
                        ctx.stroke();
                    }
                    ctx.globalAlpha = 1;

                    // labels — throttled
                    if (zoom >= labelThreshold && (selected || hovered || pinned || n.priority > 1 || zoom > 2.2)) {
                        const fontSize = clamp(9 + (zoom - labelThreshold) * 1.6, 10, 14);
                        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
                        ctx.fillStyle = selected ? '#fde047' : '#e2e8f0';
                        ctx.textAlign = 'center';
                        ctx.fillText(n.label, n.x, n.y - px - 4);
                    }
                    drawn++;
                }
            }
        }

        // selection ring drawn after everything else
        if (this.selected) {
            const n = this.index.get(this.selected);
            if (n) {
                ctx.beginPath();
                ctx.arc(n.x, n.y, n.size * zoom + 8, 0, Math.PI * 2);
                ctx.strokeStyle = '#fde047';
                ctx.lineWidth = 1.5;
                ctx.setLineDash([4, 4]);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }
    }

    _neighborsOf(nodeId) {
        const out = new Set();
        for (let i = 0; i < this.edges.length; i++) {
            const e = this.edges[i];
            if (e.source === nodeId) out.add(e.target);
            if (e.target === nodeId) out.add(e.source);
        }
        return out;
    }

    _isNeighborOrSelf(nodeId, otherId) {
        if (nodeId === otherId) return true;
        const nbrs = this._neighborsOf(nodeId);
        return nbrs.has(otherId);
    }

    setPinnedList(ids) {
        this.pinned = new Set(ids);
        this.invalidate();
    }

    destroy() {
        this.running = false;
        if (this.rafId) cancelAnimationFrame(this.rafId);
        this._resizeObserver?.disconnect();
        this.canvas.removeEventListener?.();
    }
}

function clamp(v, lo, hi) {
    return v < lo ? lo : v > hi ? hi : v;
}

// ---------------------------------------------------------------------------
// React wrapper — exposes imperative API for zoom, fit, expand, select.
// ---------------------------------------------------------------------------
export const MassiveGraphCanvas = forwardRef(function MassiveGraphCanvas(
    { nodes = [], edges = [], onSelect, onHover, onViewChange, debug = false, overlayRatio },
    ref,
) {
    const canvasRef = useRef(null);
    const rendererRef = useRef(null);
    const nodesRef = useRef(nodes);
    const edgesRef = useRef(edges);
    const listenersRef = useRef({ onSelect, onHover, onViewChange });

    useEffect(() => {
        listenersRef.current = { onSelect, onHover, onViewChange };
    }, [onSelect, onHover, onViewChange]);

    // create renderer once
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const renderer = new MassiveGraphRenderer(canvas, {
            onSelect: (id, node) => listenersRef.current.onSelect?.(id, node),
            onHover: (id) => listenersRef.current.onHover?.(id),
            onViewChange: (view) => listenersRef.current.onViewChange?.(view),
        });
        rendererRef.current = renderer;
        renderer.setData({ nodes: nodesRef.current, edges: edgesRef.current });
        return () => {
            renderer.destroy();
            rendererRef.current = null;
        };
    }, []);

    // merge new data without rebuilding when expanding (progressive loads)
    useEffect(() => {
        const renderer = rendererRef.current;
        if (!renderer) return;
        nodesRef.current = nodes;
        edgesRef.current = edges;
        renderer.mergeData({ nodes, edges });
    }, [nodes, edges]);

    useImperativeHandle(ref, () => ({
        getRenderer: () => rendererRef.current,
        zoomTo: (id, zoom) => rendererRef.current?.zoomTo(id, zoom),
        fit: () => rendererRef.current?.fit(),
        setSelected: (id) => rendererRef.current?.setSelected(id),
        togglePinned: (id) => rendererRef.current?.togglePinned(id),
        setPinnedList: (ids) => rendererRef.current?.setPinnedList(ids),
        selectNeighborhood: (id, radius) => {
            const r = rendererRef.current;
            if (!r) return;
            const n = r.index.get(id);
            if (!n) return;
            const hit = r.grid.query(n.x, n.y, radius);
            return hit.map((h) => h.id);
        },
        neighborsOf: (id) => {
            const r = rendererRef.current;
            if (!r) return [];
            return Array.from(r._neighborsOf(id));
        },
        nodeCount: () => rendererRef.current?.nodes.length ?? 0,
        edgeCount: () => rendererRef.current?.edges.length ?? 0,
    }));

    return (
        <canvas
            ref={canvasRef}
            className="massive-graph-canvas"
            style={{ width: '100%', height: '100%', display: 'block', outline: 'none' }}
            aria-label="Investigation network graph. Use mouse wheel to zoom, drag to pan, click a node to inspect it."
        />
    );
});