"""Tests for Phase-5 investigative reasoning: hypothesis engine, evidence
contradiction detection, counterfactual engine, dossier generation."""
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.domain.models import Hypothesis, Observation  # noqa: E402
from src.investigation.contradiction import (  # noqa: E402
    CONTRADICTS,
    SUPPORTS,
    UNKNOWN,
    EvidenceContradictionDetector,
    analyse_evidence,
)
from src.investigation.counterfactual_engine import (  # noqa: E402
    CounterfactualEngine,
    compute_baseline,
)
from src.investigation.dossier import (  # noqa: E402
    DossierGenerator,
    validate_dossier,
)
from src.investigation.hypothesis_engine import (  # noqa: E402
    HypothesisEngine,
)


# ------------------------------------------------------------------ #
# Graph helpers
# ------------------------------------------------------------------ #

def _barbell_graph():
    g = nx.MultiDiGraph()
    comm_a = ["A0", "A1", "A2", "A3", "A4"]
    comm_b = ["B0", "B1", "B2", "B3", "B4"]
    bridge = "BRIDGE"
    for i in range(len(comm_a)):
        for j in range(i + 1, len(comm_a)):
            g.add_edge(comm_a[i], comm_a[j], key=f"{comm_a[i]}-{comm_a[j]}", relation="CALLED")
    for i in range(len(comm_b)):
        for j in range(i + 1, len(comm_b)):
            g.add_edge(comm_b[i], comm_b[j], key=f"{comm_b[i]}-{comm_b[j]}", relation="CALLED")
    g.add_edge(comm_a[0], bridge, key="a0-bridge", relation="CALLED",
               attributes={"timestamp": "2025-01-01T08:00:00Z"})
    g.add_edge(bridge, comm_b[0], key="bridge-b0", relation="CALLED",
               attributes={"timestamp": "2025-01-02T08:00:00Z"})
    for n in comm_a + comm_b + [bridge]:
        g.nodes[n].setdefault("entity_type", "PERSON")
        g.nodes[n].setdefault("canonical_name", n)
    g.nodes["A0"].setdefault("aliases", ["A0", "A-zero", "A0-alpha"])
    g.nodes["A0"].setdefault("mention_count", 8)
    return g


# ------------------------------------------------------------------ #
# Contradiction
# ------------------------------------------------------------------ #

def test_analyse_evidence_supports():
    polarity, strength = analyse_evidence(
        "Ravi confirmed he called Kumar on Monday",
        "Ravi called Kumar")
    assert polarity == SUPPORTS
    assert strength > 0


def test_analyse_evidence_contradicts():
    polarity, strength = analyse_evidence(
        "Ravi denied any call with Kumar",
        "Ravi called Kumar")
    assert polarity == CONTRADICTS
    assert strength > 0


def test_analyse_evidence_unknown():
    polarity, strength = analyse_evidence(
        "The weather was fine that day",
        "Ravi called Kumar")
    assert polarity == UNKNOWN


def test_contradiction_detector_conflict():
    detector = EvidenceContradictionDetector()
    report = detector.analyse(
        hypothesis_id="H-1",
        claim_text="Ravi called Kumar",
        evidence_ids=["EV-1", "EV-2"],
        excerpt_overrides={
            "EV-1": "Ravi confirmed the call to Kumar",
            "EV-2": "Kumar denied any call from Ravi",
        },
    )
    assert report.has_conflict
    assert len(report.supporting) == 1
    assert len(report.contradicting) == 1
    assert report.to_dict()["verdict"] == "CONTRADICTED"


def test_contradiction_no_fabrication_unknown():
    detector = EvidenceContradictionDetector()
    report = detector.analyse(
        hypothesis_id="H-1",
        claim_text="Ravi called Kumar",
        evidence_ids=["EV-1"],
        excerpt_overrides={"EV-1": "transactions were processed at noon"},
    )
    assert report.to_dict()["verdict"] == "UNKNOWN"


# ------------------------------------------------------------------ #
# Hypothesis engine
# ------------------------------------------------------------------ #

def test_hypothesis_from_ghost():
    g = _barbell_graph()
    engine = HypothesisEngine(g)

    class FakeGhost:
        ghost_id = "GH-1"
        ghost_score = 0.7
        signals = {"structural": 0.8, "temporal": 0.5}
        shared_infrastructure = ["ACC-1"]
        explanation = "hidden intermediary hypothesis"
        def get(self, k, default=None):
            return getattr(self, k, default)

    hyps = engine.from_ghosts([FakeGhost()])
    assert len(hyps) == 1
    h = hyps[0]
    assert h.hypothesis_type == "POTENTIAL_HIDDEN_INTERMEDIARY"
    assert h.status == "OPEN"
    assert h.confidence > 0


def test_hypothesis_from_predicted_link():
    g = _barbell_graph()
    engine = HypothesisEngine(g)

    class FakeLink:
        candidate_source = "A0"
        candidate_target = "B1"
        probability = 0.8
        status = "PREDICTED_FUTURE_LINK"
        supporting_evidence = ["EV-1"]
        counter_evidence = []
        explanation = "predicted link"

    hyps = engine.from_predicted_links([FakeLink()])
    assert len(hyps) == 1
    assert hyps[0].hypothesis_type == "POTENTIAL_MISSING_LINK"


def test_community_bridges_hypothesis():
    g = _barbell_graph()
    engine = HypothesisEngine(g)
    hyps = engine.community_bridges()
    # BRIDGE node is an articulation point
    bridge_hyps = [h for h in hyps if h.subject == "BRIDGE"]
    assert len(bridge_hyps) == 1
    assert "structural observation" in bridge_hyps[0].explanation.lower()


def test_unusual_coordinators():
    g = _barbell_graph()
    engine = HypothesisEngine(g)
    hyps = engine.unusual_coordinators()
    # the bridge has high betweenness vs degree
    bridge = [h for h in hyps if h.subject == "BRIDGE"]
    assert len(bridge) == 1


def test_entity_collision_hypothesis():
    g = _barbell_graph()
    engine = HypothesisEngine(g)
    hyps = engine.entity_collisions()
    assert len(hyps) >= 1  # A0 has 3+ aliases


def test_hypothesis_lifecycle_statuses():
    g = _barbell_graph()
    engine = HypothesisEngine(g)
    hyps = engine.generate_all()
    assert len(hyps) > 0
    for h in hyps:
        assert h.status in (
            "OPEN", "SUPPORTED", "WEAKENED", "CONTRADICTED",
            "RESOLVED", "REQUIRES_REVIEW",
        )


# ------------------------------------------------------------------ #
# Counterfactual engine
# ------------------------------------------------------------------ #

def test_counterfactual_remove_node():
    g = _barbell_graph()
    engine = CounterfactualEngine(g)
    result = engine.run("remove_node", "BRIDGE")
    assert result.status == "HYPOTHETICAL"
    # removing the bridge splits the graph
    assert result.deltas["component_delta"] >= 1
    assert "HYPOTHETICAL" in result.explanation


def test_counterfactual_remove_edge():
    g = _barbell_graph()
    engine = CounterfactualEngine(g)
    result = engine.run("remove_edge", ("A0", "BRIDGE"))
    assert result.deltas["component_delta"] >= 1


def test_counterfactual_restore_hidden_edge():
    g = _barbell_graph()
    engine = CounterfactualEngine(g)
    result = engine.run("restore_hidden_edge", ("A1", "B1"),
                        relation="ASSOCIATED_WITH")
    assert result.status == "HYPOTHETICAL"


def test_counterfactual_merge_entities():
    g = _barbell_graph()
    engine = CounterfactualEngine(g)
    result = engine.run("merge_entities", ("A0", "A1"))
    assert result.deltas["component_delta"] <= 0  # merging can't split


def test_counterfactual_split_entities():
    g = _barbell_graph()
    engine = CounterfactualEngine(g)
    result = engine.run("split_entities", "A0")
    assert result.deltas["component_delta"] >= 0


def test_counterfactual_baseline():
    g = _barbell_graph()
    b = compute_baseline(g)
    assert b.components == 1
    assert b.giant_component_fraction == 1.0
    assert b.communities >= 2


# ------------------------------------------------------------------ #
# Dossier
# ------------------------------------------------------------------ #

def test_dossier_generation_traceable():
    gen = DossierGenerator()
    hypothesis = Hypothesis(
        id="H-1", hypothesis_type="POTENTIAL_MISSING_LINK",
        subject="A0→B1", confidence=0.7,
        supporting_evidence_ids=["EV-1"], counter_evidence_ids=[],
        explanation="predicted link",
    )
    obs = Observation(
        id="O-1",
        text="A0 transferred funds to ACC-1",
        evidence_ids=["EV-2"],
        timestamp="2025-01-01T00:00:00Z",
    )
    dossier = gen.generate(
        subject_id="E-42",
        subject_label="Candidate X",
        hypotheses=[hypothesis],
        observations=[obs],
    )
    assert dossier.status == "DRAFT_FOR_HUMAN_REVIEW"
    assert "EV-2" in dossier.supporting_evidence
    sections = [s.title for s in dossier.sections]
    assert "Observed facts" in sections
    assert "Inferred hypotheses" in sections
    assert "Unknowns / gaps" in sections
    assert "disclaimer" in dossier.to_dict()


def test_dossier_honest_when_no_evidence():
    gen = DossierGenerator()
    dossier = gen.generate(subject_id="E-99", subject_label="Unknown person")
    assert "I DON'T KNOW" in dossier.executive_summary


def test_dossier_validation():
    gen = DossierGenerator()
    hypothesis = Hypothesis(id="H-1", hypothesis_type="POTENTIAL_MISSING_LINK",
                            subject="A→B", confidence=0.5,
                            supporting_evidence_ids=["EV-EXISTS"])
    dossier = gen.generate(subject_id="E-1", hypotheses=[hypothesis])
    report = validate_dossier(dossier, evidence_ids=["EV-EXISTS"])
    assert report["valid"]
    report2 = validate_dossier(dossier, evidence_ids=[])
    assert not report2["valid"]
    assert "EV-EXISTS" in report2["missing_evidence"]