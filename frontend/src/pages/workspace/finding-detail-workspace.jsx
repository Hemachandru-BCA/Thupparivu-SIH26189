import { useState, useMemo } from "react";
import { useLocation } from "wouter";
import { useFindings } from "@/api/xai";
import { Brain, Search } from "lucide-react";
import { getConfidenceColor } from "@/components/app-shell";

export default function FindingDetailWorkspace() {
    // Actually this is the Findings List Workspace (formerly finding-detail-workspace.jsx which did both list & detail)
    const [, setLocation] = useLocation();
    const { data: findingsData, isLoading } = useFindings();
    const findings = findingsData?.results || findingsData?.items || findingsData || [];
    const [search, setSearch] = useState("");

    const filtered = useMemo(() => {
        if (!search) return findings;
        const q = search.toLowerCase();
        return findings.filter(f =>
            (f.finding_id || "").toLowerCase().includes(q) ||
            (f.subject_id || "").toLowerCase().includes(q) ||
            (f.finding_type || "").toLowerCase().includes(q) ||
            (f.method || "").toLowerCase().includes(q)
        );
    }, [findings, search]);

    if (isLoading) return (
        <div className="flex items-center justify-center h-full">
            <div className="tp-progress tp-progress-indeterminate" style={{width: 200}} />
        </div>
    );

    return (
        <div className="h-full flex overflow-hidden animate-fade-in">
            <div className="flex-1 flex flex-col min-w-0">
                <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                    <Brain size={13} className="text-purple" />
                    <span className="text-[11px] font-semibold text-fg-primary">FINDINGS</span>
                    <span className="tp-badge tp-badge-purple">{findings.length} total</span>
                    <div className="w-px h-4 bg-border-default" />
                    <div className="relative flex-1 max-w-sm">
                        <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-faint" />
                        <input value={search} onChange={e => setSearch(e.target.value)}
                            placeholder="Filter findings..."
                            className="tp-input pl-7 h-7 text-[11px]" />
                    </div>
                </div>

                <div className="flex-1 overflow-auto">
                    <table className="tp-table">
                        <thead>
                            <tr>
                                <th>FINDING ID</th>
                                <th>TYPE & METHOD</th>
                                <th>SUBJECT</th>
                                <th>CONFIDENCE</th>
                                <th>EVIDENCE COUNT</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((finding, i) => (
                                <tr key={finding.finding_id || i} className="cursor-pointer group hover:bg-bg-hover transition-colors"
                                    onClick={() => setLocation(`/findings/${finding.finding_id || finding.id}`)}>
                                    <td className="font-mono text-fg-faint" style={{maxWidth: 160}}>{finding.finding_id || finding.id}</td>
                                    <td>
                                        <div className="flex flex-col gap-0.5">
                                            <span className="tp-badge tp-badge-purple">{finding.finding_type || "FINDING"}</span>
                                            <span className="text-[10px] text-fg-muted truncate max-w-xs">{finding.method || "Analysis"}</span>
                                        </div>
                                    </td>
                                    <td className="font-medium text-fg-primary group-hover:text-primary transition-colors">{finding.subject_label || finding.subject_id}</td>
                                    <td>
                                        <span className="font-mono text-[10px]" style={{color: getConfidenceColor(finding.confidence || 0)}}>
                                            {((finding.confidence || 0) * 100).toFixed(1)}%
                                        </span>
                                    </td>
                                    <td className="font-mono text-fg-secondary">
                                        {(finding.supporting_evidence || []).length || 0}
                                    </td>
                                </tr>
                            ))}
                            {filtered.length === 0 && (
                                <tr>
                                    <td colSpan={5} className="text-center py-8 text-fg-faint text-[11px]">
                                        No findings match the current filters
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
