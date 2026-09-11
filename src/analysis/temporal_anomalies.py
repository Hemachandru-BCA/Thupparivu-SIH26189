"""Temporal Anomaly Detection.

Identifies anomalous temporal patterns that may indicate:
- Coordination before events
- Sudden changes in network behavior
- Dormant actors becoming active
- Synchronized suspicious activity
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of temporal anomalies."""
    COMMUNICATION_BURST = "COMMUNICATION_BURST"
    DORMANT_ACTIVATION = "DORMANT_ACTIVATION"
    SYNCHRONIZED_ACTIVITY = "SYNCHRONIZED_ACTIVITY"
    NEW_RELATIONSHIP_CLUSTER = "NEW_RELATIONSHIP_CLUSTER"
    TEMPORAL_ISOLATION = "TEMPORAL_ISOLATION"


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TemporalAnomaly(BaseModel):
    """A detected temporal anomaly."""
    model_config = ConfigDict(extra="forbid")
    
    anomaly_id: str = Field(..., description="Unique anomaly ID")
    anomaly_type: AnomalyType = Field(..., description="Type of anomaly")
    severity: AnomalySeverity = Field(..., description="Anomaly severity")
    
    # Involved entities
    entity_ids: List[str] = Field(default_factory=list)
    
    # Temporal context
    start_time: Optional[datetime] = Field(None)
    end_time: Optional[datetime] = Field(None)
    baseline_rate: float = Field(0.0, description="Normal activity rate")
    observed_rate: float = Field(0.0, description="Observed activity rate")
    
    # Details
    description: str = Field(...)
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)


@dataclass
class TemporalAnomalyDetector:
    """Detects temporal anomalies in network activity."""
    
    graph: nx.MultiDiGraph
    
    # Detection thresholds
    burst_threshold: float = 3.0  # Activity rate multiplier
    dormancy_days: int = 30  # Days of inactivity
    sync_window_hours: int = 2  # Time window for synchronization
    
    def detect_all_anomalies(self) -> List[TemporalAnomaly]:
        """Detect all temporal anomalies."""
        anomalies = []
        
        anomalies.extend(self.detect_communication_bursts())
        anomalies.extend(self.detect_dormant_activations())
        anomalies.extend(self.detect_synchronized_activity())
        anomalies.extend(self.detect_new_relationship_clusters())
        
        return anomalies
    
    def detect_communication_bursts(self) -> List[TemporalAnomaly]:
        """Detect sudden increases in communication activity."""
        anomalies = []
        
        # Group edges by entity and time window
        entity_activity: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        
        for src, tgt, key, data in self.graph.edges(keys=True, data=True):
            attrs = data.get("attributes", {})
            ts_str = attrs.get("timestamp") or attrs.get("observed_at")
            
            if ts_str:
                try:
                    ts = self._parse_timestamp(ts_str)
                    ev_ids = data.get("source_evidence_ids", [])
                    ev_id = ev_ids[0] if ev_ids else f"EDGE-{key}"
                    
                    entity_activity[src].append((ts, ev_id))
                    entity_activity[tgt].append((ts, ev_id))
                except:
                    pass
        
        # Analyze activity patterns
        for entity_id, activities in entity_activity.items():
            if len(activities) < 5:  # Need minimum data
                continue
            
            sorted_acts = sorted(activities, key=lambda x: x[0])
            
            # Calculate baseline rate (events per day)
            if len(sorted_acts) < 2:
                continue
            
            total_span = (sorted_acts[-1][0] - sorted_acts[0][0]).days or 1
            baseline_rate = len(sorted_acts) / total_span
            
            # Check for bursts (high activity in short window)
            for i in range(len(sorted_acts) - 3):
                window = sorted_acts[i:i+4]
                window_span = (window[-1][0] - window[0][0]).days or 0.1
                window_rate = 4 / window_span
                
                if window_rate > baseline_rate * self.burst_threshold:
                    evidence_ids = [ev for _, ev in window]
                    anomalies.append(TemporalAnomaly(
                        anomaly_id=f"ANOM-BURST-{entity_id}-{i}",
                        anomaly_type=AnomalyType.COMMUNICATION_BURST,
                        severity=AnomalySeverity.MEDIUM,
                        entity_ids=[entity_id],
                        start_time=window[0][0],
                        end_time=window[-1][0],
                        baseline_rate=baseline_rate,
                        observed_rate=window_rate,
                        description=f"Communication burst: {window_rate:.1f}x normal rate",
                        evidence_ids=evidence_ids,
                        confidence=min(0.9, window_rate / baseline_rate / 5),
                    ))
        
        return anomalies[:20]  # Limit results
    
    def detect_dormant_activations(self) -> List[TemporalAnomaly]:
        """Detect entities going from dormant to active."""
        anomalies = []
        
        # Track entity activity over time
        entity_timeline: Dict[str, List[datetime]] = defaultdict(list)
        
        for src, tgt, key, data in self.graph.edges(keys=True, data=True):
            attrs = data.get("attributes", {})
            ts_str = attrs.get("timestamp")
            
            if ts_str:
                try:
                    ts = self._parse_timestamp(ts_str)
                    entity_timeline[src].append(ts)
                    entity_timeline[tgt].append(ts)
                except:
                    pass
        
        # Find dormant → active transitions
        for entity_id, timestamps in entity_timeline.items():
            if len(timestamps) < 3:
                continue
            
            sorted_ts = sorted(timestamps)
            
            # Look for gaps followed by activity
            for i in range(len(sorted_ts) - 1):
                gap = (sorted_ts[i+1] - sorted_ts[i]).days
                
                if gap >= self.dormancy_days:
                    # Count activity after reactivation
                    post_activity = sum(
                        1 for t in sorted_ts[i+1:]
                        if (t - sorted_ts[i+1]).days < 7
                    )
                    
                    if post_activity >= 3:
                        anomalies.append(TemporalAnomaly(
                            anomaly_id=f"ANOM-DORMANT-{entity_id}-{i}",
                            anomaly_type=AnomalyType.DORMANT_ACTIVATION,
                            severity=AnomalySeverity.HIGH,
                            entity_ids=[entity_id],
                            start_time=sorted_ts[i+1],
                            baseline_rate=0.0,
                            observed_rate=post_activity / 7,
                            description=f"Dormant for {gap} days, then {post_activity} activities in 7 days",
                            confidence=min(0.9, gap / 90),
                        ))
        
        return anomalies[:10]
    
    def detect_synchronized_activity(self) -> List[TemporalAnomaly]:
        """Detect multiple entities acting synchronously."""
        anomalies = []
        
        # Group activities by time windows
        time_windows: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        
        for src, tgt, key, data in self.graph.edges(keys=True, data=True):
            attrs = data.get("attributes", {})
            ts_str = attrs.get("timestamp")
            
            if ts_str:
                try:
                    ts = self._parse_timestamp(ts_str)
                    # Round to 2-hour window
                    window_key = ts.strftime("%Y-%m-%d-%H")
                    ev_ids = data.get("source_evidence_ids", [])
                    ev_id = ev_ids[0] if ev_ids else f"EDGE-{key}"
                    time_windows[window_key].append((src, ev_id))
                except:
                    pass
        
        # Find windows with unusual number of distinct entities
        for window_key, activities in time_windows.items():
            entities = set(e for e, _ in activities)
            
            if len(entities) >= 5:  # Multiple entities active
                evidence_ids = [ev for _, ev in activities]
                anomalies.append(TemporalAnomaly(
                    anomaly_id=f"ANOM-SYNC-{window_key}",
                    anomaly_type=AnomalyType.SYNCHRONIZED_ACTIVITY,
                    severity=AnomalySeverity.MEDIUM,
                    entity_ids=list(entities),
                    description=f"{len(entities)} entities active in {self.sync_window_hours}h window",
                    evidence_ids=evidence_ids[:10],
                    confidence=min(0.8, len(entities) / 10),
                ))
        
        return anomalies[:10]
    
    def detect_new_relationship_clusters(self) -> List[TemporalAnomaly]:
        """Detect sudden formation of new relationship clusters."""
        anomalies = []
        
        # Group new relationships by time
        relationships_by_time: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
        
        for src, tgt, key, data in self.graph.edges(keys=True, data=True):
            attrs = data.get("attributes", {})
            ts_str = attrs.get("timestamp")
            
            if ts_str:
                try:
                    ts = self._parse_timestamp(ts_str)
                    week_key = ts.strftime("%Y-W%W")
                    ev_ids = data.get("source_evidence_ids", [])
                    ev_id = ev_ids[0] if ev_ids else f"EDGE-{key}"
                    relationships_by_time[week_key].append((src, tgt, ev_id))
                except:
                    pass
        
        # Find weeks with unusual relationship formation
        baseline = len(self.graph.edges()) / max(1, len(relationships_by_time))
        
        for week_key, rels in relationships_by_time.items():
            if len(rels) > baseline * 2.5:  # 2.5x normal
                entities = set()
                evidence_ids = []
                for src, tgt, ev in rels:
                    entities.add(src)
                    entities.add(tgt)
                    evidence_ids.append(ev)
                
                anomalies.append(TemporalAnomaly(
                    anomaly_id=f"ANOM-CLUSTER-{week_key}",
                    anomaly_type=AnomalyType.NEW_RELATIONSHIP_CLUSTER,
                    severity=AnomalySeverity.MEDIUM,
                    entity_ids=list(entities)[:20],
                    description=f"{len(rels)} new relationships formed (baseline: {baseline:.1f})",
                    evidence_ids=evidence_ids[:10],
                    baseline_rate=baseline,
                    observed_rate=float(len(rels)),
                    confidence=min(0.85, len(rels) / baseline / 4),
                ))
        
        return anomalies[:10]
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse timestamp string."""
        if isinstance(ts_str, datetime):
            return ts_str
        
        try:
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        except:
            from dateutil import parser
            return parser.parse(ts_str)
    
    def get_anomalies_for_entity(self, entity_id: str) -> List[TemporalAnomaly]:
        """Get anomalies involving specific entity."""
        all_anomalies = self.detect_all_anomalies()
        return [a for a in all_anomalies if entity_id in a.entity_ids]
    
    def summarize_anomalies(self) -> Dict[str, Any]:
        """Get anomaly summary statistics."""
        all_anomalies = self.detect_all_anomalies()
        
        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        
        for anomaly in all_anomalies:
            by_type[anomaly.anomaly_type.value] += 1
            by_severity[anomaly.severity.value] += 1
        
        return {
            "total_anomalies": len(all_anomalies),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
            "high_severity_count": by_severity.get("HIGH", 0),
        }
