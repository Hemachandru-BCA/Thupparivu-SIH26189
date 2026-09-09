"""Tests for Phase-6 evaluation: synthetic generator, benchmark tasks,
red-team honesty checks."""
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.run_benchmark import (  # noqa: E402
    results_to_markdown,
    run_full_benchmark,
    run_task_a_entity_resolution,
    run_task_d_ghost_detection,
    run_task_g_temporal_prediction,
)
from src.evaluation.synthetic_generator import (  # noqa: E402
    SyntheticInvestigationGenerator,
)


# ------------------------------------------------------------------ #
# Synthetic generator
# ------------------------------------------------------------------ #

def test_generator_has_ground_truth():
    gen = SyntheticInvestigationGenerator(seed=42)
    inv = gen.generate(n_communities=2, members_per_community=4,
                       hidden_intermediaries=1, n_false_edges=2)
    truth = inv.ground_truth
    assert len(truth.hidden_intermediaries) == 1
    assert len(truth.hidden_relationships) >= 2
    assert len(truth.false_relationships) == 2
    assert truth.duplicate_of  # has duplicate identities
    assert inv.metadata["seed"] == 42


def test_generator_deterministic():
    gen1 = SyntheticInvestigationGenerator(seed=7)
    gen2 = SyntheticInvestigationGenerator(seed=7)
    inv1 = gen1.generate(n_communities=2, members_per_community=3,
                         hidden_intermediaries=1)
    inv2 = gen2.generate(n_communities=2, members_per_community=3,
                         hidden_intermediaries=1)
    assert sorted(inv1.graph.nodes()) == sorted(inv2.graph.nodes())
    assert len(inv1.ground_truth.hidden_intermediaries) == len(
        inv2.ground_truth.hidden_intermediaries)


def test_observed_graph_masks_hidden():
    gen = SyntheticInvestigationGenerator(seed=42)
    inv = gen.generate(n_communities=2, members_per_community=4,
                       hidden_intermediaries=1, n_false_edges=0)
    observed = inv.observed_graph
    # hidden intermediaries removed
    for hid in inv.ground_truth.hidden_intermediaries:
        assert hid not in observed
    # hidden relationships not visible
    for edge in inv.ground_truth.hidden_relationships:
        u, v = edge["source"], edge["target"]
        assert not observed.has_edge(u, v)


def test_false_edges_planted_in_observed():
    gen = SyntheticInvestigationGenerator(seed=42)
    inv = gen.generate(n_communities=2, members_per_community=4,
                       hidden_intermediaries=0, n_false_edges=2)
    observed = inv.observed_graph
    false_count = sum(
        1 for _, _, d in observed.edges(data=True)
        if (d.get("attributes") or {}).get("false_planted"))
    assert false_count == 2


# ------------------------------------------------------------------ #
# Benchmark tasks
# ------------------------------------------------------------------ #

def test_run_full_benchmark_completes():
    results = run_full_benchmark(seed=42, n_communities=2, members=4,
                                 hidden=1, n_false=2)
    for task in ("TASK_A_ER", "TASK_C_LINK", "TASK_D_GHOST",
                 "TASK_E_COMMUNITY", "TASK_F_ANOMALY",
                 "TASK_G_TEMPORAL", "TASK_H_COUNTERFACTUAL"):
        assert task in results, f"missing task {task}"
    assert "metadata" in results
    assert results["TASK_A_ER"]["f1"] >= 0.0
    assert results["TASK_D_GHOST"]["precision"] >= 0.0


def test_task_a_metrics_bounded():
    gen = SyntheticInvestigationGenerator(seed=5)
    inv = gen.generate(n_communities=2, members_per_community=4,
                       hidden_intermediaries=1, n_false_edges=2)
    metrics = run_task_a_entity_resolution(inv)
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    assert 0.0 <= metrics["f1"] <= 1.0


def test_task_g_temporal_no_leakage():
    gen = SyntheticInvestigationGenerator(seed=5)
    inv = gen.generate(n_communities=2, members_per_community=4,
                       hidden_intermediaries=1, n_false_edges=2)
    metrics = run_task_g_temporal_prediction(inv)
    assert metrics["leakage_free"] is True
    assert metrics["leaked_future_edges"] == 0


def test_markdown_report_generation():
    results = run_full_benchmark(seed=42, n_communities=2, members=4,
                                 hidden=1, n_false=1)
    md = results_to_markdown(results)
    assert "Thupparivu Backend Benchmark Report" in md
    assert "TASK A" in md
    assert "TASK D" in md
    assert "No manufactured metrics" in md


# ------------------------------------------------------------------ #
# Red-team: honest "I don't know" cases
# ------------------------------------------------------------------ #

def test_red_team_no_hidden_actor():
    """When no hidden intermediary is planted, detection should NOT fabricate
    high-confidence findings.  Either low recall or explicitly weak signals
    are acceptable — never a confident claim with no evidence."""
    gen = SyntheticInvestigationGenerator(seed=42)
    inv = gen.generate(n_communities=2, members_per_community=5,
                       hidden_intermediaries=0, n_false_edges=0)
    # the baseline graph is two communities with no bridge
    observed = inv.observed_graph
    from src.ml.hidden_intermediary import HiddenIntermediaryDetector
    detector = HiddenIntermediaryDetector(use_embeddings=False)
    detector.fit(observed)
    candidates = detector.detect(min_score=0.5, top_n=10)
    # with a 0.5 threshold there should be NO confident ghost claims
    # if any exist, they must be low-confidence (system says "not sure")
    for c in candidates:
        assert c.ghost_score < 0.8, (
            "fabricated confident ghost detection where none exists")


def test_red_team_contradictory_evidence():
    """Evidence that contradicts itself should produce a CONTRADICTED verdict
    rather than silently choosing a side."""
    from src.investigation.contradiction import EvidenceContradictionDetector
    detector = EvidenceContradictionDetector()
    report = detector.analyse(
        hypothesis_id="H-X",
        claim_text="Ravi called Kumar",
        evidence_ids=["E1", "E2"],
        excerpt_overrides={
            "E1": "Ravi confirmed calling Kumar",
            "E2": "Kumar denied receiving any call",
        },
    )
    assert report.has_conflict
    assert report.to_dict()["verdict"] == "CONTRADICTED"


def test_red_team_no_strong_hypothesis():
    """An isolated single node with no evidence should produce NO strong
    hypothesis in the dossier, and the dossier says I DON'T KNOW."""
    from src.investigation.dossier import DossierGenerator
    from src.investigation.hypothesis_engine import HypothesisEngine

    g = nx.MultiDiGraph()
    g.add_node("SOLO", entity_type="PERSON", canonical_name="Solo Person",
               aliases=[], mention_count=1)
    engine = HypothesisEngine(g)
    hyps = engine.generate_all()
    # no communities → no hypotheses
    assert len(hyps) == 0

    gen = DossierGenerator()
    dossier = gen.generate(subject_id="SOLO", subject_label="Solo Person")
    assert "I DON'T KNOW" in dossier.executive_summary


def test_red_team_highly_connected_innocent():
    """A hub that is merely a service provider must not be automatically
    flagged as wrongdoing — the hypothesis engine only produces structural
    observations with disclaimers."""
    from src.investigation.hypothesis_engine import HypothesisEngine

    g = nx.MultiDiGraph()
    provider = "PROVIDER"
    g.add_node(provider, entity_type="ORGANIZATION", canonical_name="ISP",
               aliases=[], mention_count=5)
    for i in range(20):
        node = f"CLIENT{i}"
        g.add_node(node, entity_type="PERSON", canonical_name=node,
                   aliases=[], mention_count=1)
        g.add_edge(provider, node, key=f"p-{node}", relation="REGISTERED_TO")
    engine = HypothesisEngine(g)
    hyps = engine.generate_all()
    for h in hyps:
        # every hypothesis is a structural observation with a disclaimer,
        # never a guilt determination
        assert "not an accusation" in h.explanation.lower() or "structural" in h.explanation.lower()
        for forbidden in ("caught", "arrest", "guilty of", "convicted"):
            assert forbidden not in h.explanation.lower()