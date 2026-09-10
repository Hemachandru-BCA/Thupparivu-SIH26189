import React, { useState } from 'react';
import { MapPin, Layers, Users, Filter, Crosshair, Circle, Zap, Clock3 } from 'lucide-react';
import { useGeoObservations, useGeoClusters, useGeoProximity } from '@/api/intel';
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

function Stat({ label, value, accent }) {
    return (
        <div className="border border-border-subtle bg-bg-root px-2 py-2">
            <div className="text-[9px] uppercase tracking-wide text-fg-faint">{label}</div>
            <div className={`mt-1 text-[16px] font-mono ${accent || 'text-fg-primary'}`}>{value}</div>
        </div>
    );
}

function LocationRow({ obs, onHighlight }) {
    return (
        <div className="flex items-start gap-2 border-b border-border-subtle pb-1.5 hover:bg-bg-hover px-1" onMouseEnter={() => onHighlight(obs)}>
            <MapPin size={12} className="mt-0.5 shrink-0 text-amber-400" />
            <div className="flex-1 min-w-0">
                <div className="text-[10px] text-fg-secondary truncate">{obs.address_text || obs.location_id}</div>
                <div className="flex gap-2 mt-0.5">
                    <span className="tp-badge tp-badge-blue">{obs.entity_type || 'location'}</span>
                    {obs.entity_label && <span className="tp-badge tp-badge-neutral">{obs.entity_label}</span>}
                    <span className="text-[9px] text-fg-faint font-mono">{obs.timestamp?.slice(0, 10)}</span>
                </div>
            </div>
            <div className="text-right text-[9px] text-fg-faint font-mono shrink-0">
                <div>{obs.latitude?.toFixed(3)}</div>
                <div>{obs.longitude?.toFixed(3)}</div>
            </div>
        </div>
    );
}

function ClusterRow({ cluster }) {
    const COLORS = ['bg-rose-400', 'bg-amber-400', 'bg-emerald-400', 'bg-blue-400', 'bg-purple-400'];
    return (
        <div className="border border-border-subtle bg-bg-root px-2 py-2">
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${COLORS[cluster.cluster_id % COLORS.length]}`} />
                    <span className="text-[10px] font-mono text-fg-secondary">Cluster {cluster.cluster_id + 1}</span>
                </div>
                <span className="text-[9px] font-mono text-fg-faint">{cluster.entity_count} entities · {cluster.observation_count} obs</span>
            </div>
            <div className="mt-1 text-[9px] text-fg-faint">
                {cluster.avg_latitude?.toFixed(4)}°N, {cluster.avg_longitude?.toFixed(4)}°E · radius {cluster.radius_km?.toFixed(2)} km
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
                {(cluster.entity_types || []).map((t) => <span key={t} className="tp-badge tp-badge-neutral">{t}</span>)}
            </div>
        </div>
    );
}

export default function GeospatialWorkspace() {
    const { selectedEntity, selectedLocation, setSelectedLocation } = useInvestigation();
    const [entityFilter, setEntityFilter] = useState('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [viewMode, setViewMode] = useState('observations'); // observations | clusters | proximity
    const [highlighted, setHighlighted] = useState(null);

    const params = {};
    if (entityFilter) params.entity_type = entityFilter;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;

    const { data: obsData, isLoading: obsLoading } = useGeoObservations({ ...params, limit: 100 });
    const { data: clusterData } = useGeoClusters(5);
    const { data: proxData } = useGeoProximity(5);

    const observations = obsData?.observations || [];
    const clusters = clusterData?.clusters || [];
    const proxPairs = proxData?.proximity_pairs || [];

    return (
        <div className="h-full overflow-y-auto animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-bg-surface px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <MapPin size={15} className="text-primary" />
                        <h1 className="text-[13px] font-semibold tracking-wide text-fg-primary">GEOSPATIAL INTELLIGENCE</h1>
                    </div>
                    <p className="mt-1 text-[10px] text-fg-faint">Where the network operates — locations, co-occurrence, and spatial patterns.</p>
                </div>
                <div className="flex items-center gap-2">
                    <select value={viewMode} onChange={(e) => setViewMode(e.target.value)} className="tp-input h-7 text-[10px]">
                        <option value="observations">Entity Map</option>
                        <option value="clusters">Activity Clusters</option>
                        <option value="proximity">Spatial Proximity</option>
                    </select>
                </div>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2 border-b border-border-subtle bg-bg-root px-4 py-2">
                <Filter size={11} className="text-fg-faint" />
                <select value={entityFilter} onChange={(e) => setEntityFilter(e.target.value)} className="tp-input h-6 text-[10px]">
                    <option value="">All entity types</option>
                    <option value="PERSON">Person</option>
                    <option value="LOCATION">Location</option>
                    <option value="PHONE">Phone</option>
                    <option value="VEHICLE">Vehicle</option>
                    <option value="ACCOUNT">Account</option>
                </select>
                <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="tp-input h-6 text-[10px]" />
                <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="tp-input h-6 text-[10px]" />
                {selectedEntity?.id && (
                    <span className="tp-badge tp-badge-blue">FOCUSED: {selectedEntity.label || selectedEntity.id}</span>
                )}
            </div>

            <div className="grid gap-3 p-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
                {/* Main Map Area */}
                <Panel title={viewMode === 'clusters' ? 'ACTIVITY CLUSTERS' : viewMode === 'proximity' ? 'SPATIAL PROXIMITY' : 'ENTITY MAP'} icon={MapPin} className="min-h-[400px]">
                    {viewMode === 'observations' && (
                        <div className="space-y-1 max-h-[500px] overflow-y-auto">
                            {observations.map((obs, i) => (
                                <LocationRow key={obs.observation_id || i} obs={obs} onHighlight={setHighlighted} />
                            ))}
                            {!observations.length && !obsLoading && (
                                <div className="text-[10px] text-fg-faint py-6 text-center">
                                    No geographic observations found.
                                    <div className="mt-2">The current dataset may not contain lat/lon data.</div>
                                </div>
                            )}
                        </div>
                    )}

                    {viewMode === 'clusters' && (
                        <div className="space-y-1.5 max-h-[500px] overflow-y-auto">
                            {clusters.map((cluster) => (
                                <ClusterRow key={cluster.cluster_id} cluster={cluster} />
                            ))}
                            {!clusters.length && (
                                <div className="text-[10px] text-fg-faint py-6 text-center">No geographic clusters identified.</div>
                            )}
                        </div>
                    )}

                    {viewMode === 'proximity' && (
                        <div className="space-y-1.5 max-h-[500px] overflow-y-auto">
                            {proxPairs.map((pair, i) => (
                                <div key={i} className="flex items-start gap-2 border-b border-border-subtle pb-1.5 px-1">
                                    <Crosshair size={12} className="mt-0.5 shrink-0 text-emerald-400" />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-[10px] text-fg-secondary">
                                            {pair.entity_a_label} ↔ {pair.entity_b_label}
                                        </div>
                                        <div className="flex gap-2 mt-0.5">
                                            <span className="tp-badge tp-badge-blue">{pair.distance_km?.toFixed(2)} km</span>
                                            <span className="text-[9px] text-fg-faint">{pair.co_occurrence_count} co-occurrences</span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {!proxPairs.length && (
                                <div className="text-[10px] text-fg-faint py-6 text-center">No spatial proximity pairs identified.</div>
                            )}
                        </div>
                    )}
                </Panel>

                {/* Sidebar */}
                <div className="space-y-3">
                    <Panel title="GEO INVENTORY" icon={Layers}>
                        <div className="grid grid-cols-2 gap-1.5">
                            <Stat label="Observations" value={obsData?.total ?? observations.length} />
                            <Stat label="Locations" value={obsData?.locations_count ?? '—'} />
                            <Stat label="Clusters" value={clusters.length} />
                            <Stat label="Proximity Pairs" value={proxPairs.length} />
                        </div>
                        {obsData?.limitations?.[0] && (
                            <div className="mt-2 text-[9px] text-fg-faint">{obsData.limitations[0]}</div>
                        )}
                    </Panel>

                    <Panel title="ENTITY TYPE BREAKDOWN" icon={Users}>
                        <div className="space-y-1">
                            {obsData?.by_entity_type && Object.entries(obsData.by_entity_type).map(([type, count]) => (
                                <div key={type} className="flex items-center justify-between text-[10px] text-fg-secondary">
                                    <span>{type}</span>
                                    <span className="font-mono">{count}</span>
                                </div>
                            ))}
                        </div>
                    </Panel>

                    <Panel title="HIGHLIGHTED" icon={Zap}>
                        {highlighted ? (
                            <div className="space-y-1">
                                <div className="text-[10px] text-fg-secondary">{highlighted.address_text || highlighted.location_id}</div>
                                <div className="text-[9px] text-fg-faint">{highlighted.entity_type} · {highlighted.entity_label}</div>
                                <div className="text-[9px] text-fg-faint font-mono">{highlighted.latitude?.toFixed(6)}, {highlighted.longitude?.toFixed(6)}</div>
                                <div className="text-[9px] text-fg-faint font-mono">{highlighted.timestamp}</div>
                                {highlighted.evidence_ids?.length > 0 && (
                                    <div className="mt-1 flex flex-wrap gap-1">
                                        {highlighted.evidence_ids.map((eid) => <span key={eid} className="tp-badge tp-badge-green">{eid}</span>)}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-[10px] text-fg-faint">Hover over a location to inspect details.</div>
                        )}
                    </Panel>
                </div>
            </div>
        </div>
    );
}
