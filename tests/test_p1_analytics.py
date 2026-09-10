from datetime import datetime, timedelta

import networkx as nx

from src.analysis.counter_evidence import CounterEvidenceAnalyzer
from src.analysis.data_quality import DataQualityAssessor
from src.analysis.financial_analysis import FinancialAnalyzer
from src.analysis.method_agreement import MethodAgreementAnalyzer
from src.analysis.motif_detector import MotifDetector
from src.analysis.network_replay import NetworkReplayEngine
from src.xai.evidence_tracer import EvidenceRecord, EvidenceStore


def _edge(timestamp, relation="ASSOCIATED_WITH", amount=None, record_id="R1"):
    attributes = {"timestamp": timestamp, "record_id": record_id, "confidence": 0.9}
    if amount is not None:
        attributes["amount"] = amount
    return {"relation": relation, "attributes": attributes}


def _graph():
    graph = nx.MultiDiGraph()
    for node in "ABCDE":
        graph.add_node(node, canonical_name=f"Entity {node}", entity_type="PERSON", mention_count=3)
    graph.add_edge("A", "B", key="ab", **_edge("2025-01-01T00:00:00", "CALLED", record_id="C1"))
    graph.add_edge("B", "C", key="bc", **_edge("2025-01-02T00:00:00", "TRANSFERRED_TO", 1000, "T1"))
    graph.add_edge("C", "D", key="cd", **_edge("2025-01-03T00:00:00", "TRANSFERRED_TO", 800, "T2"))
    graph.add_edge("D", "E", key="de", **_edge("2025-01-04T00:00:00", "TRANSFERRED_TO", 600, "T3"))
    graph.add_edge("E", "B", key="eb", **_edge("2025-01-05T00:00:00", "TRANSFERRED_TO", 500, "T4"))
    graph.add_edge("A", "C", key="ac", **_edge("2025-01-06T00:00:00", "CALLED", record_id="C2"))
    graph.add_edge("A", "D", key="ad", **_edge("2025-01-07T00:00:00", "CALLED", record_id="C3"))
    graph.add_edge("A", "E", key="ae", **_edge("2025-01-08T00:00:00", "CALLED", record_id="C4"))
    return graph


def test_replay_cumulative_and_diff_are_deterministic():
    graph = _graph()
    engine = NetworkReplayEngine(graph)
    first = engine.snapshot_at("2025-01-02T00:00:00", "cumulative")
    second = engine.snapshot_at("2025-01-04T00:00:00", "cumulative")
    assert first.edge_count == 2
    assert second.edge_count == 4
    delta = engine.compute_delta("2025-01-02T00:00:00", "2025-01-04T00:00:00")
    assert delta.edges_added == 2
    assert engine.snapshot_at("2025-01-04T00:00:00", "cumulative") == second


def test_motifs_detect_chain_fanout_and_ring():
    report = MotifDetector(_graph()).detect_all(top_n=20)
    types = {motif.motif_type for motif in report.motifs}
    assert "CHAIN" in types
    assert "FAN_OUT" in types
    assert "RING" in types


def test_financial_aggregation_and_paths():
    graph = _graph()
    # Account-only edges are required by the financial analyzer.
    for node in "BCDE":
        graph.nodes[node]["entity_type"] = "ACCOUNT"
    analyzer = FinancialAnalyzer(graph)
    flows = analyzer.aggregated_flows(min_amount=500)
    assert any(flow.source == "B" and flow.target == "C" for flow in flows)
    paths = analyzer.find_paths("B", max_hops=3, min_amount=500)
    assert paths
    assert paths[0].hop_count >= 1


def test_quality_and_method_agreement_return_explainable_results():
    graph = _graph()
    quality = DataQualityAssessor(graph).assess(entity_ids=["B"])
    assert 0 <= quality.overall_readiness <= 1
    assert quality.entity_quality[0].entity_id == "B"
    agreement = MethodAgreementAnalyzer(graph).analyze(entity_ids=["B"])
    assert agreement.entities[0].entity_id == "B"
    assert "Degree" in agreement.methods_compared


def test_counter_evidence_preserves_polarity():
    store = EvidenceStore()
    for evidence_id, record_id in [("EV-S", "S1"), ("EV-C", "C1")]:
        store.add(EvidenceRecord(
            evidence_id=evidence_id,
            source_type="CALL",
            source_record_id=record_id,
            text_excerpt=record_id,
            confidence=0.9,
        ))
    finding = {
        "id": "F1",
        "subject_label": "Entity B",
        "supporting_evidence_ids": ["EV-S"],
        "counter_evidence_ids": ["EV-C"],
    }
    panel = CounterEvidenceAnalyzer(store).analyze_finding(finding)
    assert panel.support_count == 1
    assert panel.contradiction_count == 1
    assert panel.supporting[0].polarity == "SUPPORTING"
    assert panel.contradictory[0].polarity == "CONTRADICTORY"
