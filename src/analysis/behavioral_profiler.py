"""
analysis/behavioral_profiler.py
-------------------------------
Behavioral Profiling and Change Detection Engine for Thupparivu.

Computes entity behavioral profiles across:
  - Communications (frequency, burst count, night activity, unique contacts)
  - Financials (volume, transaction count, velocity, cycles, layering)
  - Locations (unique locations, entropy, movement)
  - Network role (centrality, bridge score, community shifts)

Detects statistically significant changes between a baseline period
and an active/incident window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import networkx as nx

logger = logging.getLogger(__name__)

@dataclass
class BehavioralProfile:
    """Structured behavioral representation of an entity."""
    entity_id: str
    period_label: str = "all_time"
    
    # Communication metrics
    total_calls: int = 0
    unique_contacts: int = 0
    avg_call_duration_sec: float = 0.0
    night_call_ratio: float = 0.0
    burst_count: int = 0
    
    # Financial metrics
    total_inflow: float = 0.0
    total_outflow: float = 0.0
    transaction_count: int = 0
    rapid_transfer_count: int = 0
    
    # Spatial metrics
    unique_locations: int = 0
    
    # Graph / Network metrics
    degree: int = 0
    betweenness: float = 0.0
    bridge_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "period": self.period_label,
            "communications": {
                "total_calls": self.total_calls,
                "unique_contacts": self.unique_contacts,
                "night_ratio": round(self.night_call_ratio, 3),
                "burst_count": self.burst_count,
            },
            "financial": {
                "total_inflow": self.total_inflow,
                "total_outflow": self.total_outflow,
                "transaction_count": self.transaction_count,
            },
            "network": {
                "degree": self.degree,
                "betweenness": round(self.betweenness, 4),
                "bridge_score": round(self.bridge_score, 4),
            },
            "locations": {
                "unique_locations": self.unique_locations,
            }
        }

@dataclass
class BehaviorChangeReport:
    """Explains detected shift from baseline to active period."""
    entity_id: str
    baseline: BehavioralProfile
    recent: BehavioralProfile
    
    # Normalized deltas (0 to 1 scale)
    communication_change: float = 0.0
    financial_change: float = 0.0
    location_change: float = 0.0
    network_change: float = 0.0
    
    overall_change_score: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "change_score": round(self.overall_change_score, 4),
            "components": {
                "communication": round(self.communication_change, 3),
                "financial": round(self.financial_change, 3),
                "location": round(self.location_change, 3),
                "network": round(self.network_change, 3),
            },
            "baseline": self.baseline.to_dict(),
            "recent": self.recent.to_dict(),
            "explanation": self.explanation,
        }
