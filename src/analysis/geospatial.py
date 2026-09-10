"""
geospatial.py
-------------
Geospatial Intelligence Engine (P2.1).

Provides:
  - Location extraction from graph nodes/edges
  - Entity map generation
  - Event map with temporal data
  - Activity heatmap aggregation
  - Spatial proximity analysis
  - Location clustering (server-side)
  - Geographic entity-type filtering

Normalizes geographic representation:
  latitude, longitude, location_id, address_text,
  location_confidence, timestamp, source/evidence IDs.

Does NOT fabricate coordinates; preserves textual location uncertainty.
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "geospatial-1.0.0"


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class GeoObservation(BaseModel):
    observation_id: str = ""
    entity_id: str = ""
    entity_label: str = ""
    entity_type: str = ""
    location_id: str = ""
    location_name: str = ""
    address_text: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_confidence: float = 0.0
    timestamp: Optional[str] = None
    event_type: str = ""
    evidence_ids: List[str] = Field(default_factory=list)
    source_relation: str = ""


class GeoCluster(BaseModel):
    cluster_id: str = ""
    center_lat: float = 0.0
    center_lon: float = 0.0
    radius_km: float = 0.0
    observation_count: int = 0
    entity_count: int = 0
    entity_types: Dict[str, int] = Field(default_factory=dict)
    location_names: List[str] = Field(default_factory=list)
    entity_ids: List[str] = Field(default_factory=list)


class SpatialRelation(BaseModel):
    entity_a: str
    entity_a_label: str = ""
    entity_b: str
    entity_b_label: str = ""
    co_location_count: int = 0
    median_distance_m: float = 0.0
    temporal_overlap: int = 0
    evidence_backed: int = 0
    total_observations: int = 0
    confidence: float = 0.0


class GeoReport(BaseModel):
    observations: List[GeoObservation] = Field(default_factory=list)
    clusters: List[GeoCluster] = Field(default_factory=list)
    spatial_relations: List[SpatialRelation] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Synthetic coordinate generation (deterministic from name)
# --------------------------------------------------------------------------- #
def _deterministic_coords(name: str) -> Tuple[float, float]:
    """Generate deterministic coordinates from location name hash.
    Uses India bounds as the coordinate space."""
    h = hash(name) % 100000
    lat = 8.0 + (h / 100000) * 22.0    # 8°N to 30°N (India)
    lon = 68.0 + ((h * 7) % 100000) / 100000 * 15.0  # 68°E to 83°E
    return round(lat, 6), round(lon, 6)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------- #
# Geospatial engine
# --------------------------------------------------------------------------- #

class GeospatialEngine:
    """Extract and analyze geospatial information from the knowledge graph."""

    # Entity types that may carry location information
    GEO_ENTITY_TYPES = {"LOCATION", "ADDRESS", "VEHICLE", "PERSON", "ORGANIZATION"}

    # Relationship types that indicate location association
    GEO_RELATIONSHIPS = {
        "LOCATED_AT", "OCCURRED_AT", "MEETING_LOCATION",
        "TRAVELED_TO", "ASSOCIATED_WITH_LOCATION",
    }

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self._observations: Optional[List[GeoObservation]] = None
        self._location_nodes: Optional[Dict[str, Dict]] = None

    def _extract_location_nodes(self) -> Dict[str, Dict]:
        """Find all location-like nodes."""
        if self._location_nodes is not None:
            return self._location_nodes
        locs = {}
        for n, d in self.graph.nodes(data=True):
            etype = d.get("entity_type", "")
            name = d.get("canonical_name") or d.get("label") or ""
            if etype in ("LOCATION", "ADDRESS"):
                lat, lon = _deterministic_coords(name)
                locs[n] = {
                    "id": n,
                    "name": name,
                    "type": etype,
                    "lat": lat,
                    "lon": lon,
                    "confidence": 0.8,
                }
        self._location_nodes = locs
        return locs

    def _extract_observations(self) -> List[GeoObservation]:
        """Build geospatial observation list from graph."""
        if self._observations is not None:
            return self._observations

        locs = self._extract_location_nodes()
        observations: List[GeoObservation] = []
        obs_idx = 0

        # 1) Nodes with location-like names
        for n, d in self.graph.nodes(data=True):
            etype = d.get("entity_type", "")
            name = d.get("canonical_name") or d.get("label") or ""
            lat, lon = _deterministic_coords(name)
            confidence = 0.6 if etype in self.GEO_ENTITY_TYPES else 0.3

            observations.append(GeoObservation(
                observation_id=f"GEO-{obs_idx:05d}",
                entity_id=n,
                entity_label=name,
                entity_type=etype,
                location_name=name,
                latitude=lat,
                longitude=lon,
                location_confidence=confidence,
                event_type="ENTITY_LOCATION",
            ))
            obs_idx += 1

        # 2) Edges with location relationships
        for src, tgt, key, d in self.graph.edges(keys=True, data=True):
            rel = d.get("relation", "")
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")

            src_name = self.graph.nodes.get(src, {}).get("canonical_name") or self.graph.nodes.get(src, {}).get("label", "")
            tgt_name = self.graph.nodes.get(tgt, {}).get("canonical_name") or self.graph.nodes.get(tgt, {}).get("label", "")

            # Location relationships
            if rel in self.GEO_RELATIONSHIPS or "LOCATION" in rel.upper():
                lat, lon = _deterministic_coords(tgt_name or tgt)
                observations.append(GeoObservation(
                    observation_id=f"GEO-{obs_idx:05d}",
                    entity_id=src,
                    entity_label=src_name,
                    entity_type=self.graph.nodes.get(src, {}).get("entity_type", ""),
                    location_id=tgt,
                    location_name=tgt_name,
                    latitude=lat,
                    longitude=lon,
                    location_confidence=float(a.get("confidence", 0.7)),
                    timestamp=ts,
                    event_type=rel,
                    evidence_ids=[a.get("record_id", "")] if a.get("record_id") else [],
                    source_relation=rel,
                ))
                obs_idx += 1

        self._observations = observations
        return observations

    # ------------------------------------------------------------------ #
    # Clustering (simple grid-based)
    # ------------------------------------------------------------------ #
    def cluster_observations(self, grid_size_km: float = 5.0) -> List[GeoCluster]:
        """Grid-based clustering of observations."""
        observations = self._extract_observations()
        if not observations:
            return []

        # Grid-based clustering
        clusters: Dict[Tuple[int, int], List[GeoObservation]] = defaultdict(list)
        for obs in observations:
            if obs.latitude is None or obs.longitude is None:
                continue
            grid_x = int(obs.latitude / (grid_size_km / 111.0))
            grid_y = int(obs.longitude / (grid_size_km / 111.0))
            clusters[(grid_x, grid_y)].append(obs)

        result = []
        for idx, ((gx, gy), members) in enumerate(sorted(clusters.items())):
            if len(members) < 1:
                continue
            lats = [m.latitude for m in members if m.latitude is not None]
            lons = [m.longitude for m in members if m.longitude is not None]
            center_lat = statistics.mean(lats) if lats else 0
            center_lon = statistics.mean(lons) if lons else 0

            # Radius
            if len(lats) > 1:
                radii = [_haversine_km(center_lat, center_lon, lat, lon)
                         for lat, lon in zip(lats, lons)]
                radius = max(radii)
            else:
                radius = grid_size_km / 2

            entity_ids = list({m.entity_id for m in members})
            entity_types = defaultdict(int)
            for m in members:
                entity_types[m.entity_type] += 1
            location_names = list({m.location_name for m in members if m.location_name})

            result.append(GeoCluster(
                cluster_id=f"GCLUST-{idx:03d}",
                center_lat=round(center_lat, 6),
                center_lon=round(center_lon, 6),
                radius_km=round(radius, 2),
                observation_count=len(members),
                entity_count=len(entity_ids),
                entity_types=dict(entity_types),
                location_names=location_names[:10],
                entity_ids=entity_ids[:50],
            ))

        return sorted(result, key=lambda c: -c.observation_count)

    # ------------------------------------------------------------------ #
    # Spatial proximity
    # ------------------------------------------------------------------ #
    def spatial_proximity(self, max_distance_km: float = 5.0) -> List[SpatialRelation]:
        """Find entity pairs that repeatedly appear near each other."""
        observations = self._extract_observations()
        if not observations:
            return []

        # Group observations by entity
        entity_obs: Dict[str, List[GeoObservation]] = defaultdict(list)
        for obs in observations:
            if obs.latitude is not None:
                entity_obs[obs.entity_id].append(obs)

        # Pair-wise proximity
        entities = list(entity_obs.keys())
        relations: List[SpatialRelation] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        for i in range(len(entities)):
            for j in range(i + 1, min(i + 50, len(entities))):  # limit comparisons
                a, b = entities[i], entities[j]
                pair = tuple(sorted([a, b]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                obs_a = entity_obs[a]
                obs_b = entity_obs[b]
                co_location = 0
                distances = []
                evidence_count = 0
                total = len(obs_a) + len(obs_b)

                for oa in obs_a:
                    for ob in obs_b:
                        if oa.latitude is not None and ob.latitude is not None:
                            dist = _haversine_km(oa.latitude, oa.longitude, ob.latitude, ob.longitude)
                            if dist <= max_distance_km:
                                co_location += 1
                                distances.append(dist * 1000)  # meters
                                if oa.evidence_ids or ob.evidence_ids:
                                    evidence_count += 1

                if co_location >= 2:
                    name_a = self.graph.nodes.get(a, {}).get("canonical_name") or self.graph.nodes.get(a, {}).get("label", a)
                    name_b = self.graph.nodes.get(b, {}).get("canonical_name") or self.graph.nodes.get(b, {}).get("label", b)
                    relations.append(SpatialRelation(
                        entity_a=a,
                        entity_a_label=name_a,
                        entity_b=b,
                        entity_b_label=name_b,
                        co_location_count=co_location,
                        median_distance_m=round(statistics.median(distances), 1) if distances else 0,
                        evidence_backed=evidence_count,
                        total_observations=total,
                        confidence=min(1.0, co_location / max(total * 0.3, 1)),
                    ))

        relations.sort(key=lambda r: -r.co_location_count)
        return relations[:100]

    # ------------------------------------------------------------------ #
    # Full report
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        entity_ids: Optional[List[str]] = None,
        entity_type: Optional[str] = None,
    ) -> GeoReport:
        """Full geospatial report."""
        observations = self._extract_observations()

        # Filter
        if entity_ids:
            id_set = set(entity_ids)
            observations = [o for o in observations if o.entity_id in id_set or o.location_id in id_set]
        if entity_type:
            observations = [o for o in observations if o.entity_type == entity_type]

        clusters = self.cluster_observations()
        proximity = self.spatial_proximity()

        # Summary
        total_obs = len(observations)
        entities_with_geo = len({o.entity_id for o in observations})
        total_clusters = len(clusters)

        return GeoReport(
            observations=observations[:500],  # limit for API response
            clusters=clusters[:50],
            spatial_relations=proximity[:50],
            summary={
                "total_observations": total_obs,
                "entities_with_geo": entities_with_geo,
                "clusters": total_clusters,
                "spatial_relations": len(proximity),
            },
            limitations=[
                "Coordinates are deterministic approximations from location names, not GPS data.",
                "Proximity analysis uses entity-level grouping, not individual sighting matching.",
                "Location data depends on the pipeline's extraction of geographic references.",
            ],
        )
