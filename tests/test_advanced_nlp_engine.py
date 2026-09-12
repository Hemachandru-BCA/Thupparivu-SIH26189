"""
tests/test_advanced_nlp_engine.py
---------------------------------
Unit and integration tests for the Advanced NLP & Intelligence Engine.
"""

import pytest
from src.nlp.document import Document, SourceSpan, ModalityType, PolarityType
from src.nlp.processor import DocumentProcessor
from src.analysis.behavioral_profiler import BehavioralProfile, BehaviorChangeReport
from src.analysis.modus_operandi import MOPattern
from src.analysis.knowledge_gaps import KnowledgeGap
from src.llm.guardrails import LLMGuardrails
from src.llm.tasks import ConstrainedSummarizer

def test_document_model_creation():
    doc = Document(
        document_id="DOC-001",
        source_id="FIR-101",
        raw_text="Ravi contacted Suresh yesterday regarding the transfer.",
    )
    assert doc.document_id == "DOC-001"
    assert doc.content_hash != ""
    assert doc.source_type == "REPORT"

def test_document_processor():
    processor = DocumentProcessor()
    doc = processor.process("Ravi transferred money in Chennai.", "TX-01", "DOC-02")
    assert doc.document_id == "DOC-02"
    assert doc.language in ["en", "ta", "hi", "unknown"]

def test_behavioral_profiler_models():
    base = BehavioralProfile(entity_id="E-101", total_calls=10, unique_contacts=3)
    recent = BehavioralProfile(entity_id="E-101", total_calls=45, unique_contacts=12)
    report = BehaviorChangeReport(
        entity_id="E-101",
        baseline=base,
        recent=recent,
        overall_change_score=0.75,
        explanation="Communication burst detected.",
    )
    d = report.to_dict()
    assert d["change_score"] == 0.75
    assert d["baseline"]["communications"]["total_calls"] == 10
    assert d["recent"]["communications"]["total_calls"] == 45

def test_modus_operandi_model():
    mo = MOPattern(
        pattern_id="MO-01",
        name="Night Vehicle Meeting",
        event_sequence=["VEHICLE_ARRIVAL", "PHONE_BURST", "MEETING", "TRANSACTION"],
        frequency=4,
    )
    d = mo.to_dict()
    assert len(d["event_sequence"]) == 4
    assert d["frequency"] == 4

def test_knowledge_gap_model():
    gap = KnowledgeGap(
        gap_id="GAP-01",
        gap_type="UNVERIFIED_IDENTIFIER",
        subject_id="E-202",
        description="Phone ownership uncorroborated.",
        severity="MEDIUM",
        recommended_action="Cross-verify subscriber registry.",
    )
    d = gap.to_dict()
    assert d["severity"] == "MEDIUM"
    assert d["gap_type"] == "UNVERIFIED_IDENTIFIER"

def test_llm_guardrails():
    valid_ids = {"EV-001", "EV-002", "EV-003"}
    ok, invalid = LLMGuardrails.validate_citations(["EV-001", "EV-002"], valid_ids)
    assert ok is True
    assert len(invalid) == 0

    ok, invalid = LLMGuardrails.validate_citations(["EV-001", "EV-999"], valid_ids)
    assert ok is False
    assert invalid == ["EV-999"]

def test_constrained_summarizer():
    ctx = {
        "canonical_name": "Ravi Kumar",
        "entity_id": "E-101",
        "relationships": [{"id": "R1"}],
        "evidence_ids": ["EV-01"],
        "observed_facts": ["Call recorded on 12 Jan"],
    }
    brief = ConstrainedSummarizer.generate_entity_brief(ctx)
    assert "Ravi Kumar" in brief["title"]
    assert brief["dossier_status"] == "DRAFT_FOR_HUMAN_REVIEW"
    assert brief["status"] == "OBSERVED"
