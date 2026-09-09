import { useState } from 'react';
import { useHealthCheck, useListJobs, useTriggerPipeline } from '@/api/graph';
import { Upload, Play, RotateCcw, CheckCircle, AlertTriangle, Clock, Database } from 'lucide-react';
import { formatTimestamp } from '@/components/app-shell';

const PIPELINE_STAGES = [
    { id: 'generate', label: 'GENERATE', description: 'Generate synthetic data' },
    { id: 'preprocess', label: 'PREPROCESS', description: 'Clean and normalize data' },
    { id: 'extract', label: 'EXTRACT', description: 'Extract entities and events' },
    { id: 'graph', label: 'BUILD GRAPH', description: 'Construct knowledge graph' },
    { id: 'ghosts', label: 'GHOST DETECTION', description: 'Run anomaly detection' },
];

export default function PipelineWorkspace() {
    const { data: health } = useHealthCheck();
    const { data: jobsData, refetch: refetchJobs } = useListJobs();
    const { trigger: triggerPipeline } = useTriggerPipeline();
    const [triggering, setTriggering] = useState(null);

    const jobs = jobsData?.results || jobsData?.items || jobsData || [];

    const handleTrigger = async (stage) => {
        setTriggering(stage);
        try {
            await triggerPipeline(stage);
            setTimeout(() => refetchJobs(), 1000);
        } catch (e) {
            console.error('Pipeline trigger failed:', e);
        } finally {
            setTriggering(null);
        }
    };

    return (
        <div className="h-full flex flex-col overflow-hidden animate-fade-in">
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border-subtle bg-bg-surface shrink-0">
                <Upload size={13} className="text-primary" />
                <span className="text-[11px] font-semibold text-fg-primary">DATA INGESTION</span>
                <div className="w-px h-4 bg-border-default" />
                <div className="flex items-center gap-1.5">
                    <div className={`tp-status-dot ${health?.status === 'ok' ? 'bg-green' : 'bg-red'}`} />
                    <span className="text-[10px] font-mono text-fg-faint">
                        API {health?.status === 'ok' ? 'HEALTHY' : 'UNREACHABLE'}
                    </span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Pipeline stages */}
                <div className="tp-panel">
                    <div className="tp-panel-header">
                        <span className="text-[11px] font-semibold text-fg-primary">PIPELINE STAGES</span>
                    </div>
                    <div className="p-3 grid grid-cols-5 gap-2">
                        {PIPELINE_STAGES.map(stage => (
                            <div key={stage.id} className="tp-panel p-3 text-center">
                                <div className="font-mono text-[10px] text-fg-muted mb-1">{stage.label}</div>
                                <div className="text-[9px] text-fg-faint mb-2">{stage.description}</div>
                                <button onClick={() => handleTrigger(stage.id)}
                                    disabled={triggering !== null}
                                    className="tp-btn tp-btn-primary text-[9px] h-6 w-full justify-center">
                                    {triggering === stage.id
                                        ? <RotateCcw size={10} className="animate-spin" />
                                        : <Play size={10} />}
                                    {triggering === stage.id ? 'Running...' : 'Run'}
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Job history */}
                <div className="tp-panel">
                    <div className="tp-panel-header">
                        <span className="text-[11px] font-semibold text-fg-primary">JOB HISTORY</span>
                        <span className="text-[10px] font-mono text-fg-faint">{jobs.length} jobs</span>
                    </div>
                    <div className="overflow-y-auto" style={{maxHeight: 400}}>
                        <table className="tp-table">
                            <thead>
                                <tr>
                                    <th>JOB ID</th>
                                    <th>STAGE</th>
                                    <th>STATUS</th>
                                    <th>CREATED</th>
                                    <th>STARTED</th>
                                    <th>FINISHED</th>
                                    <th>ERROR</th>
                                </tr>
                            </thead>
                            <tbody>
                                {jobs.map((job, i) => (
                                    <tr key={job.job_id || i}>
                                        <td className="font-mono text-fg-faint">{job.job_id || job.id}</td>
                                        <td>
                                            <span className="tp-badge tp-badge-blue">{job.kind || job.stage}</span>
                                        </td>
                                        <td>
                                            <div className="flex items-center gap-1.5">
                                                {job.status === 'completed' || job.status === 'success'
                                                    ? <CheckCircle size={10} className="text-green" />
                                                    : job.status === 'failed'
                                                        ? <AlertTriangle size={10} className="text-red" />
                                                        : <Clock size={10} className="text-amber" />}
                                                <span className={`text-[10px] font-mono ${
                                                    job.status === 'completed' || job.status === 'success' ? 'text-green' :
                                                    job.status === 'failed' ? 'text-red' : 'text-amber'
                                                }`}>
                                                    {(job.status || 'pending').toUpperCase()}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="font-mono text-fg-faint text-[10px]">{formatTimestamp(job.created_at)}</td>
                                        <td className="font-mono text-fg-faint text-[10px]">{formatTimestamp(job.started_at)}</td>
                                        <td className="font-mono text-fg-faint text-[10px]">{formatTimestamp(job.finished_at)}</td>
                                        <td className="text-[10px] text-red max-w-xs truncate">{job.error || ''}</td>
                                    </tr>
                                ))}
                                {jobs.length === 0 && (
                                    <tr><td colSpan={7} className="text-center py-4 text-fg-faint text-[10px]">No jobs recorded</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
