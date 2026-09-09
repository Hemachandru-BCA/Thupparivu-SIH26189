import { useHealthCheck } from '@/api/graph';
import { Settings, CheckCircle, XCircle, Server, Monitor } from 'lucide-react';

export default function SettingsWorkspace() {
    const { data: health, isLoading } = useHealthCheck();

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <Settings size={13} className="text-fg-muted" />
                <span className="text-[11px] font-semibold text-fg-primary">SETTINGS</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 max-w-2xl space-y-4">
                {/* API Connection */}
                <div className="tp-panel">
                    <div className="tp-panel-header">
                        <span className="text-[11px] font-semibold text-fg-primary">API CONNECTION</span>
                    </div>
                    <div className="p-3 space-y-2">
                        <div className="flex items-center gap-2">
                            {health?.status === 'ok'
                                ? <CheckCircle size={12} className="text-green" />
                                : <XCircle size={12} className="text-red" />}
                            <span className="text-[11px] text-fg-secondary">
                                {health?.status === 'ok' ? 'Connected' : 'Unreachable'}
                            </span>
                        </div>
                        {health && (
                            <div className="text-[10px] font-mono text-fg-faint space-y-1">
                                <div>Status: {health.status}</div>
                                {health.version && <div>Version: {health.version}</div>}
                                {health.dataset && <div>Dataset: {health.dataset}</div>}
                            </div>
                        )}
                    </div>
                </div>

                {/* System Info */}
                <div className="tp-panel">
                    <div className="tp-panel-header">
                        <span className="text-[11px] font-semibold text-fg-primary">SYSTEM INFORMATION</span>
                    </div>
                    <div className="p-3 space-y-2 text-[11px]">
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Application</span>
                            <span className="text-fg-secondary font-mono">Thupparivu SIH-26189</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Version</span>
                            <span className="text-fg-secondary font-mono">1.0.0</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Frontend</span>
                            <span className="text-fg-secondary font-mono">React + Vite</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Backend</span>
                            <span className="text-fg-secondary font-mono">FastAPI + Python</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-fg-faint">Graph Engine</span>
                            <span className="text-fg-secondary font-mono">Cytoscape.js</span>
                        </div>
                    </div>
                </div>

                {/* Graph Preferences */}
                <div className="tp-panel">
                    <div className="tp-panel-header">
                        <span className="text-[11px] font-semibold text-fg-primary">WORKSPACE PREFERENCES</span>
                    </div>
                    <div className="p-3 space-y-3">
                        <div>
                            <label className="text-[10px] text-fg-faint font-mono uppercase block mb-1">DEFAULT EXPANSION DEPTH</label>
                            <select className="tp-select w-32">
                                <option value="1">1 hop</option>
                                <option value="2" selected>2 hops</option>
                                <option value="3">3 hops</option>
                                <option value="4">4 hops</option>
                                <option value="5">5 hops</option>
                            </select>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-[11px] text-fg-secondary">Show entity IDs in graph</span>
                            <input type="checkbox" defaultChecked className="accent-primary" />
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-[11px] text-fg-secondary">Animate graph layout</span>
                            <input type="checkbox" defaultChecked className="accent-primary" />
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-[11px] text-fg-secondary">Compact data tables</span>
                            <input type="checkbox" defaultChecked className="accent-primary" />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
