"""Tests for LLM-assisted extraction module.

Tests cover:
- Schema validation
- Evidence grounding requirements
- LLM extraction pipeline
- Mock provider behavior
"""

import pytest
from datetime import datetime

from src.extraction.llm.schemas import (
    EntityMention,
    EntityType,
    RelationshipCandidate,
    RelationshipType,
    EventCandidate,
    EventType,
    EvidenceClaim,
    ExtractionMethod,
    ObservationStatus,
    SourceSpan,
    ConfidenceComponents,
)
from src.extraction.llm.extractor import (
    LLMExtractor,
    MockExtractionProvider,
    ExtractionConfig,
)


def test_entity_mention_requires_evidence_for_observed():
    """OBSERVED entities must have evidence IDs."""
    with pytest.raises(ValueError, match="OBSERVED entities must have"):
        EntityMention(
            mention_id="EM-001",
            entity_text="John Doe",
            entity_type=EntityType.PERSON,
            extraction_method=ExtractionMethod.LLM_ASSISTED,
            status=ObservationStatus.OBSERVED,
            source_evidence_ids=[],  # Empty - should fail
        )


def test_entity_mention_inferred_no_evidence_ok():
    """INFERRED entities can have no evidence."""
    entity = EntityMention(
        mention_id="EM-002",
        entity_text="Potential Contact",
        entity_type=EntityType.PERSON,
        extraction_method=ExtractionMethod.LLM_ASSISTED,
        status=ObservationStatus.INFERRED,
        source_evidence_ids=[],
    )
    assert entity.status == ObservationStatus.INFERRED


def test_relationship_requires_evidence_for_observed():
    """OBSERVED relationships must have evidence IDs."""
    with pytest.raises(ValueError, match="OBSERVED relationships must have"):
        RelationshipCandidate(
            candidate_id="RC-001",
            subject="Person A",
            subject_text="Person A",
            predicate=RelationshipType.KNOWS,
            object="Person B",
            object_text="Person B",
            extraction_method=ExtractionMethod.LLM_ASSISTED,
            status=ObservationStatus.OBSERVED,
            source_evidence_ids=[],
        )


def test_evidence_claim_always_requires_evidence():
    """All claims must have evidence IDs."""
    with pytest.raises(ValueError, match="Claims must have at least one"):
        EvidenceClaim(
            claim_id="CL-001",
            subject="Person A",
            predicate="knows",
            object="Person B",
            extraction_method=ExtractionMethod.LLM_ASSISTED,
            status=ObservationStatus.OBSERVED,
            source_evidence_ids=[],
        )


def test_confidence_components_overall_calculation():
    """Test confidence score calculation."""
    conf = ConfidenceComponents(
        evidence_quality=0.9,
        extraction_confidence=0.8,
        entity_resolution=0.7,
        temporal_consistency=0.6,
        graph_support=0.8,
        counter_evidence_penalty=0.1,
    )
    
    overall = conf.overall()
    assert 0.0 <= overall <= 1.0
    # With counter-evidence penalty, should be reduced
    assert overall < 0.9


def test_source_span_validation():
    """Source span end must be >= start."""
    with pytest.raises(ValueError):
        SourceSpan(
            start_offset=100,
            end_offset=50,  # End before start - should fail
            text="invalid",
        )


def test_mock_extraction_provider():
    """Test mock provider returns structured output."""
    provider = MockExtractionProvider()
    
    context = [
        {
            "kind": "document",
            "text": "John Doe met Jane Smith at the warehouse. John called +1234567890.",
            "evidence_id": "EV-001",
        }
    ]
    
    result = provider.generate("Extract entities", context)
    import json
    data = json.loads(result)
    
    assert "entities" in data
    assert "relationships" in data
    assert data["provider"] == "mock-extraction"
    assert data["deterministic"] is True


def test_llm_extractor_basic():
    """Test basic extraction with mock provider."""
    extractor = LLMExtractor()
    
    result = extractor.extract(
        document_id="DOC-001",
        text="Ravi met Kumar near the old warehouse. Ravi called +919876543210.",
        evidence_ids=["EV-001"],
    )
    
    assert result.extraction_id is not None
    assert result.source_document_id == "DOC-001"
    assert result.extraction_method == ExtractionMethod.LLM_ASSISTED
    # Mock provider should extract some entities
    assert len(result.entities) > 0


def test_llm_extractor_caching():
    """Test extraction result caching."""
    extractor = LLMExtractor(config=ExtractionConfig(cache_llm_results=True))
    
    text = "Test entity extraction for caching."
    
    # First call
    result1 = extractor.extract("DOC-CACHE-001", text, evidence_ids=["EV-001"])
    
    # Second call with same document - should hit cache
    result2 = extractor.extract("DOC-CACHE-001", text, evidence_ids=["EV-001"])
    
    assert result1.extraction_id == result2.extraction_id
    assert result1.entity_count() == result2.entity_count()


def test_llm_extractor_validation_errors():
    """Test that invalid LLM output is caught."""
    # This would be tested with a provider that returns malformed JSON
    # For now, we test that the extractor handles validation gracefully
    extractor = LLMExtractor()
    
    result = extractor.extract(
        document_id="DOC-INVALID",
        text="",
        evidence_ids=[],
    )
    
    # Should return a result even if empty
    assert result.extraction_id is not None


def test_extraction_result_evidence_id_collection():
    """Test that all evidence IDs are collected."""
    from src.extraction.llm.schemas import ExtractionResult
    
    result = ExtractionResult(
        extraction_id="EXT-001",
        source_document_id="DOC-001",
        extraction_method=ExtractionMethod.LLM_ASSISTED,
        entities=[
            EntityMention(
                mention_id="EM-001",
                entity_text="Person A",
                entity_type=EntityType.PERSON,
                extraction_method=ExtractionMethod.LLM_ASSISTED,
                status=ObservationStatus.OBSERVED,
                source_evidence_ids=["EV-001", "EV-002"],
            )
        ],
        relationships=[
            RelationshipCandidate(
                candidate_id="RC-001",
                subject="Person A",
                subject_text="Person A",
                predicate=RelationshipType.KNOWS,
                object="Person B",
                object_text="Person B",
                extraction_method=ExtractionMethod.LLM_ASSISTED,
                status=ObservationStatus.OBSERVED,
                source_evidence_ids=["EV-003"],
            )
        ],
    )
    
    all_ids = result.all_evidence_ids()
    assert "EV-001" in all_ids
    assert "EV-002" in all_ids
    assert "EV-003" in all_ids
    assert len(all_ids) == 3


def test_batch_extraction():
    """Test batch extraction of multiple documents."""
    extractor = LLMExtractor()
    
    documents = [
        {
            "document_id": "DOC-BATCH-001",
            "text": "Person A met Person B.",
            "evidence_ids": ["EV-001"],
        },
        {
            "document_id": "DOC-BATCH-002",
            "text": "Person C called Person D.",
            "evidence_ids": ["EV-002"],
        },
    ]
    
    results = extractor.batch_extract(documents)
    
    assert len(results) == 2
    assert all(r.extraction_id is not None for r in results)


def test_entity_type_enum():
    """Test entity type enumeration."""
    assert EntityType.PERSON.value == "PERSON"
    assert EntityType.ORGANIZATION.value == "ORGANIZATION"
    assert EntityType.FINANCIAL_INSTRUMENT.value == "FINANCIAL_INSTRUMENT"


def test_observation_status_enum():
    """Test observation status values."""
    assert ObservationStatus.OBSERVED.value == "OBSERVED"
    assert ObservationStatus.INFERRED.value == "INFERRED"
    assert ObservationStatus.UNKNOWN.value == "UNKNOWN"
    assert ObservationStatus.CONTRADICTED.value == "CONTRADICTED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
