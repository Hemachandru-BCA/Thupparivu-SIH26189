"""Evidence Conflict Detection Engine.

Detects and scores contradictions in evidence, including:
- Temporal conflicts (incompatible timestamps)
- Spatial conflicts (impossible locations)
- Identity conflicts (contradictory identity claims)
- Relationship conflicts (contradictory assertions)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

CONFLICT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "sentinelgraph/conflict")


class ConflictType(str, Enum):
    """Types of evidence conflicts."""
    TEMPORAL = "TEMPORAL"  # Incompatible timestamps
    SPATIAL = "SPATIAL"  # Impossible locations
    IDENTITY = "IDENTITY"  # Contradictory identity claims
    RELATIONSHIP = "RELATIONSHIP"  # Contradictory relationships
    ATTRIBUTE = "ATTRIBUTE"  # Conflicting attributes


class ConflictSeverity(str, Enum):
    """Severity of conflict."""
    LOW = "LOW"  # Minor inconsistency
    MEDIUM = "MEDIUM"  # Clear contradiction
    HIGH = "HIGH"  # Critical conflict requiring resolution
    CRITICAL = "CRITICAL"  # Severe conflict invalidating findings


class EvidenceConflict(BaseModel):
    """A detected conflict between evidence records."""
    model_config = ConfigDict(extra="forbid")
    
    conflict_id: str = Field(..., description="Unique conflict ID")
    conflict_type: ConflictType = Field(..., description="Type of conflict")
    severity: ConflictSeverity = Field(..., description="Conflict severity")
    
    # Conflicting evidence
    evidence_id_1: str = Field(..., description="First evidence ID")
    evidence_id_2: str = Field(..., description="Second evidence ID")
    
    # Conflict details
    description: str = Field(..., description="Human-readable description")
    field_name: Optional[str] = Field(None, description="Conflicting field")
    value_1: Optional[str] = Field(None, description="Value from evidence 1")
    value_2: Optional[str] = Field(None, description="Value from evidence 2")
    
    # Context
    entity_ids: List[str] = Field(default_factory=list, description="Affected entities")
    finding_ids: List[str] = Field(default_factory=list, description="Affected findings")
    
    # Resolution
    resolved: bool = Field(False, description="Whether conflict is resolved")
    resolution_note: Optional[str] = Field(None, description="Resolution explanation")
    
    # Metadata
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When conflict was detected"
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Detection confidence")


@dataclass
class ConflictDetector:
    """Detects conflicts in evidence and graph data.
    
    This detector analyzes evidence records, graph relationships, and temporal
    data to identify contradictions that investigators should be aware of.
    """
    
    graph: nx.MultiDiGraph
    evidence_store: Any
    
    # Thresholds
    temporal_threshold_hours: float = 1.0  # Can't be in 2 places within 1 hour
    spatial_distance_threshold_km: float = 100.0  # Unrealistic travel distance
    
    def detect_all_conflicts(self) -> List[EvidenceConflict]:
        """Detect all types of conflicts in the system."""
        conflicts = []
        
        conflicts.extend(self.detect_temporal_conflicts())
        conflicts.extend(self.detect_spatial_conflicts())
        conflicts.extend(self.detect_identity_conflicts())
        conflicts.extend(self.detect_relationship_conflicts())
        conflicts.extend(self.detect_attribute_conflicts())
        
        return conflicts
    
    def detect_temporal_conflicts(self) -> List[EvidenceConflict]:
        """Detect temporal contradictions.
        
        Examples:
        - Person reported at location A at 10:00 and location B at 10:05
          when travel time is physically impossible
        - Event dated before prerequisite event
        - Contradictory timestamps for same event
        """
        conflicts = []
        
        # Group events by entity
        entity_events: Dict[str, List[Tuple[str, datetime, str]]] = {}
        
        for src, tgt, key, data in self.graph.edges(keys=True, data=True):
            attrs = data.get("attributes", {})
            timestamp_str = attrs.get("timestamp") or attrs.get("observed_at")
            
            if timestamp_str:
                try:
                    timestamp = self._parse_timestamp(timestamp_str)
                    location = tgt if self._is_location(tgt) else None
                    
                    if location:
                        if src not in entity_events:
                            entity_events[src] = []
                        evidence_ids = data.get("source_evidence_ids", [])
                        ev_id = evidence_ids[0] if evidence_ids else f"EDGE-{key}"
                        entity_events[src].append((ev_id, timestamp, location))
                except Exception as e:
                    logger.debug(f"Could not parse timestamp {timestamp_str}: {e}")
        
        # Check for temporal conflicts
        for entity_id, events in entity_events.items():
            sorted_events = sorted(events, key=lambda x: x[1])
            
            for i in range(len(sorted_events) - 1):
                ev1_id, time1, loc1 = sorted_events[i]
                ev2_id, time2, loc2 = sorted_events[i + 1]
                
                time_diff = (time2 - time1).total_seconds() / 3600  # hours
                
                if time_diff < self.temporal_threshold_hours and loc1 != loc2:
                    conflicts.append(EvidenceConflict(
                        conflict_id=f"CONF-{uuid.uuid5(CONFLICT_NAMESPACE, f'{ev1_id}-{ev2_id}')}",
                        conflict_type=ConflictType.TEMPORAL,
                        severity=ConflictSeverity.MEDIUM,
                        evidence_id_1=ev1_id,
                        evidence_id_2=ev2_id,
                        description=f"Entity reported at {loc1} and {loc2} within {time_diff:.1f} hours",
                        field_name="location",
                        value_1=loc1,
                        value_2=loc2,
                        entity_ids=[entity_id],
                        confidence=0.8,
                    ))
        
        return conflicts
    
    def detect_spatial_conflicts(self) -> List[EvidenceConflict]:
        """Detect spatial impossibilities.
        
        Examples:
        - Person reported in two distant locations simultaneously
        - Location data contradicting known geography
        """
        conflicts = []
        
        # Find simultaneous location claims
        time_location_map: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
        
        for src, tgt, key, data in self.graph.edges(keys=True, data=True):
            if not self._is_location(tgt):
                continue
            
            attrs = data.get("attributes", {})
            timestamp_str = attrs.get("timestamp")
            
            if timestamp_str:
                time_key = (src, timestamp_str)
                evidence_ids = data.get("source_evidence_ids", [])
                ev_id = evidence_ids[0] if evidence_ids else f"EDGE-{key}"
                
                if time_key not in time_location_map:
                    time_location_map[time_key] = []
                time_location_map[time_key].append((ev_id, tgt))
        
        # Check for conflicts
        for (entity_id, timestamp), locations in time_location_map.items():
            if len(locations) > 1:
                for i in range(len(locations)):
                    for j in range(i + 1, len(locations)):
                        ev1_id, loc1 = locations[i]
                        ev2_id, loc2 = locations[j]
                        
                        if loc1 != loc2:
                            conflicts.append(EvidenceConflict(
                                conflict_id=f"CONF-{uuid.uuid5(CONFLICT_NAMESPACE, f'{ev1_id}-{ev2_id}')}",
                                conflict_type=ConflictType.SPATIAL,
                                severity=ConflictSeverity.HIGH,
                                evidence_id_1=ev1_id,
                                evidence_id_2=ev2_id,
                                description=f"Entity reported at multiple locations simultaneously",
                                field_name="location",
                                value_1=loc1,
                                value_2=loc2,
                                entity_ids=[entity_id],
                                confidence=0.9,
                            ))
        
        return conflicts
    
    def detect_identity_conflicts(self) -> List[EvidenceConflict]:
        """Detect contradictory identity claims.
        
        Examples:
        - Different names for same phone number
        - Different birth dates for same person
        - Contradictory identity attributes
        """
        conflicts = []
        
        # Check for conflicting canonical names from entity resolution
        phone_names: Dict[str, Set[Tuple[str, str]]] = {}  # phone -> {(name, evidence_id)}
        
        for node_id, node_data in self.graph.nodes(data=True):
            entity_type = node_data.get("entity_type", "")
            
            # Check for phone numbers with multiple associated names
            if entity_type == "PHONE":
                canonical = node_data.get("canonical_name", "")
                aliases = node_data.get("aliases", [])
                evidence_ids = node_data.get("source_evidence_ids", [])
                ev_id = evidence_ids[0] if evidence_ids else node_id
                
                all_names = [canonical] + aliases
                for name in all_names:
                    if name and name != node_id:
                        if node_id not in phone_names:
                            phone_names[node_id] = set()
                        phone_names[node_id].add((name, ev_id))
        
        # Find conflicts
        for phone_id, names_set in phone_names.items():
            if len(names_set) > 1:
                names_list = list(names_set)
                for i in range(len(names_list)):
                    for j in range(i + 1, len(names_list)):
                        name1, ev1 = names_list[i]
                        name2, ev2 = names_list[j]
                        
                        if name1.lower() != name2.lower():  # Not just case difference
                            conflicts.append(EvidenceConflict(
                                conflict_id=f"CONF-{uuid.uuid5(CONFLICT_NAMESPACE, f'{ev1}-{ev2}')}",
                                conflict_type=ConflictType.IDENTITY,
                                severity=ConflictSeverity.MEDIUM,
                                evidence_id_1=ev1,
                                evidence_id_2=ev2,
                                description=f"Phone {phone_id} associated with different names",
                                field_name="name",
                                value_1=name1,
                                value_2=name2,
                                entity_ids=[phone_id],
                                confidence=0.7,
                            ))
        
        return conflicts
    
    def detect_relationship_conflicts(self) -> List[EvidenceConflict]:
        """Detect contradictory relationship claims.
        
        Examples:
        - A knows B vs A doesn't know B
        - Mutually exclusive relationships
        """
        conflicts = []
        
        # Track relationship claims
        relationship_claims: Dict[Tuple[str, str], List[Tuple[str, str, str]]] = {}
        
        for src, tgt, key, data in self.graph.edges(keys=True, data=True):
            relation = data.get("relation", "UNKNOWN")
            evidence_ids = data.get("source_evidence_ids", [])
            ev_id = evidence_ids[0] if evidence_ids else f"EDGE-{key}"
            
            # Normalize direction for undirected relationships
            edge_key = tuple(sorted([src, tgt]))
            
            if edge_key not in relationship_claims:
                relationship_claims[edge_key] = []
            relationship_claims[edge_key].append((relation, ev_id, key))
        
        # Check for conflicting relationship types
        for (entity1, entity2), claims in relationship_claims.items():
            unique_relations = {}
            for relation, ev_id, key in claims:
                if relation not in unique_relations:
                    unique_relations[relation] = []
                unique_relations[relation].append((ev_id, key))
            
            # If same relationship type appears multiple times, no conflict
            # If different types, potential conflict
            if len(unique_relations) > 1:
                relation_types = list(unique_relations.keys())
                for i in range(len(relation_types)):
                    for j in range(i + 1, len(relation_types)):
                        rel1 = relation_types[i]
                        rel2 = relation_types[j]
                        
                        # Check if relationships are contradictory
                        if self._are_contradictory_relationships(rel1, rel2):
                            ev1 = unique_relations[rel1][0][0]
                            ev2 = unique_relations[rel2][0][0]
                            
                            conflicts.append(EvidenceConflict(
                                conflict_id=f"CONF-{uuid.uuid5(CONFLICT_NAMESPACE, f'{ev1}-{ev2}')}",
                                conflict_type=ConflictType.RELATIONSHIP,
                                severity=ConflictSeverity.LOW,
                                evidence_id_1=ev1,
                                evidence_id_2=ev2,
                                description=f"Contradictory relationships: {rel1} vs {rel2}",
                                field_name="relationship_type",
                                value_1=rel1,
                                value_2=rel2,
                                entity_ids=[entity1, entity2],
                                confidence=0.6,
                            ))
        
        return conflicts
    
    def detect_attribute_conflicts(self) -> List[EvidenceConflict]:
        """Detect conflicting attribute values.
        
        Examples:
        - Different ages for same person
        - Conflicting account balances
        - Contradictory status information
        """
        conflicts = []
        
        # Check node attributes for conflicts
        for node_id, node_data in self.graph.nodes(data=True):
            # If node has conflicting information in its attributes dict
            # (This would require multiple evidence sources contributing to same node)
            
            # For now, we focus on explicit contradictions in the evidence store
            evidence_ids = node_data.get("source_evidence_ids", [])
            if len(evidence_ids) > 1 and self.evidence_store:
                # Compare attributes from different evidence sources
                # This is a placeholder for more sophisticated attribute comparison
                pass
        
        return conflicts
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse timestamp string."""
        if isinstance(ts_str, datetime):
            return ts_str
        
        # Try ISO format
        try:
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        except:
            pass
        
        # Try common formats
        from dateutil import parser
        return parser.parse(ts_str)
    
    def _is_location(self, node_id: str) -> bool:
        """Check if node is a location."""
        if node_id not in self.graph:
            return False
        return self.graph.nodes[node_id].get("entity_type") == "LOCATION"
    
    def _are_contradictory_relationships(self, rel1: str, rel2: str) -> bool:
        """Check if two relationship types are contradictory."""
        # Define contradictory pairs
        contradictory = {
            ("KNOWS", "UNKNOWN_TO"),
            ("TRUSTS", "DISTRUSTS"),
            ("ALLY", "ENEMY"),
        }
        
        pair = tuple(sorted([rel1, rel2]))
        return pair in contradictory
    
    def get_conflicts_for_entity(self, entity_id: str) -> List[EvidenceConflict]:
        """Get all conflicts involving a specific entity."""
        all_conflicts = self.detect_all_conflicts()
        return [c for c in all_conflicts if entity_id in c.entity_ids]
    
    def get_conflicts_for_evidence(self, evidence_id: str) -> List[EvidenceConflict]:
        """Get all conflicts involving specific evidence."""
        all_conflicts = self.detect_all_conflicts()
        return [
            c for c in all_conflicts
            if evidence_id in [c.evidence_id_1, c.evidence_id_2]
        ]
    
    def get_conflicts_by_severity(
        self,
        min_severity: ConflictSeverity = ConflictSeverity.LOW
    ) -> List[EvidenceConflict]:
        """Get conflicts above a severity threshold."""
        severity_order = {
            ConflictSeverity.LOW: 1,
            ConflictSeverity.MEDIUM: 2,
            ConflictSeverity.HIGH: 3,
            ConflictSeverity.CRITICAL: 4,
        }
        
        threshold = severity_order[min_severity]
        all_conflicts = self.detect_all_conflicts()
        
        return [
            c for c in all_conflicts
            if severity_order[c.severity] >= threshold
        ]
    
    def summarize_conflicts(self) -> Dict[str, Any]:
        """Generate summary statistics of conflicts."""
        all_conflicts = self.detect_all_conflicts()
        
        by_type = {}
        by_severity = {}
        
        for conflict in all_conflicts:
            # Count by type
            if conflict.conflict_type not in by_type:
                by_type[conflict.conflict_type] = 0
            by_type[conflict.conflict_type] += 1
            
            # Count by severity
            if conflict.severity not in by_severity:
                by_severity[conflict.severity] = 0
            by_severity[conflict.severity] += 1
        
        return {
            "total_conflicts": len(all_conflicts),
            "by_type": {k.value: v for k, v in by_type.items()},
            "by_severity": {k.value: v for k, v in by_severity.items()},
            "unresolved": sum(1 for c in all_conflicts if not c.resolved),
            "high_severity_count": sum(
                1 for c in all_conflicts
                if c.severity in [ConflictSeverity.HIGH, ConflictSeverity.CRITICAL]
            ),
        }
