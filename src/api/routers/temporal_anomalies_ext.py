"""Temporal Anomaly API endpoint extension.

Adds anomaly detection to existing temporal routes.
"""

from fastapi import Query
from src.api.routers import temporal
from src.analysis.temporal_anomalies import TemporalAnomalyDetector
from src.api import services

@temporal.router.get("/anomalies")
def get_temporal_anomalies(
    entity_id: str = Query(None, description="Filter by entity"),
):
    """Detect temporal anomalies in network activity."""
    graph = services.load_graph()
    detector = TemporalAnomalyDetector(graph=graph)
    
    if entity_id:
        anomalies = detector.get_anomalies_for_entity(entity_id)
    else:
        anomalies = detector.detect_all_anomalies()
    
    return {
        "anomalies": [a.model_dump() for a in anomalies],
        "count": len(anomalies),
    }

@temporal.router.get("/anomalies/summary")
def get_anomaly_summary():
    """Get temporal anomaly summary statistics."""
    graph = services.load_graph()
    detector = TemporalAnomalyDetector(graph=graph)
    return detector.summarize_anomalies()
