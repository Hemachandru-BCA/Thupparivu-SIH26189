"""Tests for the Phase-1 domain layer: typed models, provenance,
scoring abstraction and model-run tracking."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.domain import (  # noqa: E402
    ConfidenceScore,
    Entity,
    FactStatus,
    Hypothesis,
    ModelRun,
    Prediction,
    Provenance,
    Relationship,
    RelationshipStatus,
)
from src.domain.model_registry import ModelRegistry  # noqa: E402
from src.domain.scoring import Signal, SignalBundle  # noqa: E402


def test_confidence_score_defaults_and_blend():
    score = ConfidenceScore()
    assert score.value == 0.0
    blended = ConfidenceScore(
        structural_score=0.8,
        temporal_score=0.6,
        evidence_score=0.9,
        counter_evidence_penalty=0.1,
    )
    v = blended.value
    assert 0.0 <= v <= 1.0
    # default: equal weight across ALL 6 families (semantic/behavioral are 0.0)
    # mean = (0.8+0.6+0+0+0.9+0)/6 ≈ 0.3833, minus 0.1 penalty ≈ 0.2833
    expected = round((0.8 + 0.6 + 0.0 + 0.0 + 0.9 + 0.0) / 6 - 0.1, 4)
    assert v == expected


def test_confidence_score_custom_weights():
    score = ConfidenceScore(structural_score=1.0, evidence_score=0.5)
    v = score.blended({"structural": 1.0, "evidence": 0.0})
    assert v == 1.0


def test_fact_status_semantics():
    assert FactStatus.OBSERVED.value == "OBSERVED"
    assert FactStatus.CONTRADICTED.value == "CONTRADICTED"


def test_relationship_status_default_observed():
    rel = Relationship(
        id="R1", source_entity="A", target_entity="B", relationship_type="CALLED"
    )
    assert rel.status == RelationshipStatus.OBSERVED
    pred = Prediction(
        id="P1", candidate_source="A", candidate_target="B", probability=0.7
    )
    assert pred.status == RelationshipStatus.PREDICTED_FUTURE


def test_provenance_chain():
    prov = Provenance(
        source={"source": "CALL", "record_id": "call-1"},
        extraction_model="relation_extractor",
        model_version="1.0.0",
        confidence=0.9,
    )
    assert prov.source.source == "CALL"
    assert prov.confidence == 0.9


def test_hypothesis_lifecycle():
    h = Hypothesis(
        id="H1",
        hypothesis_type="POTENTIAL_HIDDEN_INTERMEDIARY",
        subject="E-42",
        confidence=0.55,
        status="OPEN",
    )
    assert h.status == "OPEN"
    h2 = h.model_copy(update={"status": "SUPPORTED"})
    assert h2.status == "SUPPORTED"


def test_signal_bundle_to_confidence():
    b = SignalBundle()
    b.add(Signal("cn", "structural", 0.9, 0.5, "common neighbors"))
    b.add(Signal("temporal", "temporal", 0.6, 0.5, "temporal overlap"))
    b.counter_evidence_penalty = 0.1
    c = b.to_confidence()
    assert abs(c.structural_score - 0.9) < 1e-6
    assert abs(c.temporal_score - 0.6) < 1e-6
    assert len(c.explanations) == 2
    assert "structural" in b.explain()


def test_signal_percentile_clamp():
    sig = Signal("x", "structural", 1.7)
    assert sig.value <= 1.0


def test_model_run_tracking():
    run = ModelRun(
        model_name="link_predictor",
        model_version="1.0.0",
        configuration={"max_depth": 3},
        input_dataset_version="synth-2025-01-01",
        random_seed=42,
        metrics={"roc_auc": 0.81},
    )
    assert run.run_id.startswith("0" * 0) or isinstance(run.run_id, str)
    assert len(run.run_id) == 36  # uuid5 hex


def test_model_registry_roundtrip(tmp_path):
    registry = ModelRegistry(tmp_path / "registry.json")
    run = registry.start_run(
        "temporal_predictor", "0.1.0",
        config={"window": 30},
        dataset_version="synth-1",
        seed=7,
        tags=["phase2"],
    )
    registry.finish_run(run.run_id, {"mae": 1.2}, outputs=["P-1"])
    loaded = ModelRegistry(tmp_path / "registry.json")
    assert loaded.get_run(run.run_id) is not None
    got = loaded.get_run(run.run_id)
    assert got.metrics["mae"] == 1.2
    assert got.outputs == ["P-1"]
    assert got.status == "COMPLETED"


def test_entity_and_alias_shape():
    e = Entity(
        id="E-1",
        entity_type="PERSON",
        canonical_name="Ravi Kumar",
        aliases=["R. Kumar", "Ravi K"],
        first_seen="2025-01-01T00:00:00Z",
        source="CALL",
    )
    assert e.status == "ACTIVE"
    assert e.first_seen == "2025-01-01T00:00:00Z"


def test_domain_ids_deterministic():
    from src.domain.models import domain_uuid5

    assert domain_uuid5("entity", "Ravi") == domain_uuid5("entity", "Ravi")
    assert domain_uuid5("entity", "Ravi") != domain_uuid5("entity", "Sita")