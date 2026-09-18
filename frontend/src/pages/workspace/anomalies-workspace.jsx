import { useState, useMemo } from "react";
import { useGetGhosts } from "@/api/graph";
import { AlertTriangle, Search } from "lucide-react";
import { formatNumber } from "@/utils/format";
import { getConfidenceColor } from "@/components/app-shell";
import { useInvestigation } from "@/state/investigation-context";

export default function AnomaliesWorkspace() {
    const { data: ghostsData, isLoading } = useGetGhosts();
    const ghosts = ghostsData?.results || ghostsData?.items || ghostsData || [];
    const [search, setSearch] = useState("");
    const { setSelectedHypothesis, setInspectorOpen } = useInvestigation();

    const filtered = useMemo(() => {
        if (!search) return ghosts;
        const q = search.toLowerCase();
        return ghosts.filter(g =>
            (g.ghost_id || "").toLowerCase().includes(q) ||
            (g.label || "").toLowerCase().includes(q) ||
            (g.subtype || "").toLowerCase().includes(q)
        );
    }, [ghosts, search]);

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex overflow-hidden animate-fade-in">
            {/* List */}
            <div className="flex-1 flex flex-col min-w-0">
                <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                    <AlertTriangle size={13} className="text-amber" />
                    <span className="text-[11px] font-semibold text-fg-primary">ANOMALIES</span>
                    <span className="tp-badge tp-badge-amber">{ghosts.length} total</span>
                    <div className="w-px h-4 bg-border-default" />
                    <div className="relative flex-1 max-w-sm">
                        <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint" />
                        <input value={search} onChange={e => setSearch(e.target.value)}
                            placeholder="Filter anomalies..."
                            className="tp-input pl-7 h-7 text-[11px]" />
                    </div>
                </div>

                <div className="flex-1 overflow-auto">
                    <table className="tp-table">
                        <thead>
                            <tr>
                                <th>GHOST ID</th>
                                <th>LABEL / NAME</th>
                                <th>TYPE</th>
                                <th>CONFIDENCE</th>
                                <th>METRICS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((ghost, i) => (
                                <tr key={ghost.ghost_id || i} className="cursor-pointer group hover:bg-bg-hover transition-colors"
                                    onClick={() => { setSelectedHypothesis(ghost); setInspectorOpen(true); }}>
                                    <td className="font-mono text-fg-faint" style={{maxWidth: 160}}>{ghost.ghost_id}</td>
                                    <td className="font-medium text-fg-primary group-hover:text-primary transition-colors">{ghost.label}</td>
                                    <td>
                                        <span className="tp-badge tp-badge-amber">{ghost.subtype || "HIDDEN NODE"}</span>
                                    </td>
                                    <td>
                                        <div className="flex items-center gap-2">
                                            <span className="font-mono text-[10px]" style={{color: getConfidenceColor(ghost.confidence || 0)}}>
                                                {((ghost.confidence || 0) * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    </td>
                                    <td className="font-mono text-fg-secondary text-[10px]">
                                        Deg: {ghost.metrics?.proxy_degree || 0}
                                    </td>
                                </tr>
                            ))}
                            {filtered.length === 0 && (
                                <tr>
                                    <td colSpan={5} className="text-center py-8 text-fg-faint text-[11px]">
                                        No anomalies match the current filters
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
