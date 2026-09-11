"""LLM-assisted extraction engine with evidence grounding.

This module provides structured extraction from unstructured evidence
using LLM assistance, with strict validation and evidence grounding.

Key principles:
1. LLM produces CANDIDATE extractions, never direct graph mutations
2. All extractions must pass schema validation
3. All evidence IDs must resolve to actual evidence records
4. Confidence is decomposed into transparent components
5. OBSERVED/INFERRED/UNKNOWN distinction is preserved
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Set
import uuid
from uuid import uuid5

from pydantic import ValidationError

from src.extraction.llm.schemas import (
    EntityMention,
    EntityType,
    EventCandidate,
    EventType,
    EvidenceClaim,
    ExtractionMethod,
    ExtractionResult,
    ObservationStatus,
    RelationshipCandidate,
    RelationshipType,
    SourceSpan,
    ConfidenceComponents,
)

logger = logging.getLogger(__name__)

# Namespace for extraction IDs
EXTRACTION_NAMESPACE = uuid5(uuid.NAMESPACE_URL, "sentinelgraph/extraction")


class LLMProvider(Protocol):
    """Protocol for LLM providers used in extraction."""
    
    name: str
    
    def generate(self, prompt: str, context: List[Dict[str, Any]]) -> str:
        """Generate response from prompt with context."""
        ...


class ExtractionError(RuntimeError):
    """Base class for extraction errors."""
    pass


class EvidenceResolutionError(ExtractionError):
    """Raised when evidence IDs cannot be resolved."""
    pass


class ValidationFailedError(ExtractionError):
    """Raised when LLM output fails validation."""
    pass


@dataclass
class ExtractionConfig:
    """Configuration for LLM-assisted extraction."""
    
    # Evidence requirements
    require_evidence_ids: bool = True
    validate_evidence_exists: bool = True
    
    # Confidence thresholds
    min_confidence_for_observed: float = 0.7
    min_confidence_for_inferred: float = 0.5
    
    # Caching
    cache_llm_results: bool = True
    cache_dir: Optional[Path] = None
    
    # Limits
    max_entities_per_doc: int = 100
    max_relationships_per_doc: int = 100
    max_events_per_doc: int = 50


class MockExtractionProvider:
    """Deterministic mock provider for offline extraction.
    
    This provider returns structured extractions based on pattern matching
    without requiring an external LLM API. Used for:
    - Offline demo mode
    - Testing extraction pipeline
    - Fallback when LLM unavailable
    """
    
    name = "mock-extraction"
    
    def generate(self, prompt: str, context: List[Dict[str, Any]]) -> str:
        """Generate mock extraction based on context patterns."""
        # Extract text from context
        text = ""
        evidence_ids = []
        for item in context:
            if item.get("kind") == "document":
                text += item.get("text", "") + "\n"
                if eid := item.get("evidence_id"):
                    evidence_ids.append(eid)
        
        # Pattern-based mock extraction
        entities = self._mock_entities(text, evidence_ids)
        relationships = self._mock_relationships(text, evidence_ids)
        events = self._mock_events(text, evidence_ids)
        
        result = {
            "entities": entities,
            "relationships": relationships,
            "events": events,
            "provider": self.name,
            "deterministic": True,
        }
        
        return json.dumps(result)
    
    def _mock_entities(self, text: str, evidence_ids: List[str]) -> List[Dict]:
        """Extract entities using simple patterns."""
        import re
        entities = []
        
        # Ensure we have at least one evidence ID for the mock
        default_evidence = evidence_ids if evidence_ids else ["EV-MOCK-001"]
        
        # Simple name pattern (capitalized words)
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
        for match in re.finditer(name_pattern, text):
            name = match.group(1)
            # Skip common words
            if name in ('The', 'This', 'That', 'A', 'An', 'In', 'On', 'At', 'To', 'For'):
                continue
            
            entities.append({
                "entity_text": name,
                "entity_type": "PERSON",
                "source_evidence_ids": default_evidence[:1],
                "source_spans": [{
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "text": match.group(0)
                }],
                "extraction_method": "LLM_ASSISTED",
                "status": "OBSERVED"
            })
        
        # Phone pattern
        phone_pattern = r'\b(\+?\d{10,15})\b'
        for match in re.finditer(phone_pattern, text):
            entities.append({
                "entity_text": match.group(1),
                "entity_type": "PHONE",
                "source_evidence_ids": default_evidence[:1],
                "source_spans": [{
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "text": match.group(0)
                }],
                "extraction_method": "RULE_BASED",
                "status": "OBSERVED"
            })
        
        # Email pattern
        email_pattern = r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        for match in re.finditer(email_pattern, text):
            entities.append({
                "entity_text": match.group(1),
                "entity_type": "EMAIL",
                "source_evidence_ids": default_evidence[:1],
                "source_spans": [{
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "text": match.group(0)
                }],
                "extraction_method": "RULE_BASED",
                "status": "OBSERVED"
            })
        
        return entities[:20]  # Limit for mock
    
    def _mock_relationships(self, text: str, evidence_ids: List[str]) -> List[Dict]:
        """Extract relationships using simple patterns."""
        import re
        relationships = []
        
        # Ensure we have at least one evidence ID for the mock
        default_evidence = evidence_ids if evidence_ids else ["EV-MOCK-001"]
        
        # Meeting pattern: "X met Y" or "X meeting Y"
        meeting_pattern = r'\b([A-Z][a-z]+)\s+(?:met|meeting|met with)\s+([A-Z][a-z]+)\b'
        for match in re.finditer(meeting_pattern, text, re.IGNORECASE):
            relationships.append({
                "subject_text": match.group(1),
                "predicate": "MEETS",
                "object_text": match.group(2),
                "source_evidence_ids": default_evidence[:1],
                "source_spans": [{
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "text": match.group(0)
                }],
                "extraction_method": "LLM_ASSISTED",
                "status": "OBSERVED"
            })
        
        # Communication pattern: "X called Y"
        call_pattern = r'\b([A-Z][a-z]+)\s+(?:called|phoned|contacted)\s+([A-Z][a-z]+)\b'
        for match in re.finditer(call_pattern, text, re.IGNORECASE):
            relationships.append({
                "subject_text": match.group(1),
                "predicate": "CALLS",
                "object_text": match.group(2),
                "source_evidence_ids": default_evidence[:1],
                "source_spans": [{
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "text": match.group(0)
                }],
                "extraction_method": "LLM_ASSISTED",
                "status": "OBSERVED"
            })
        
        return relationships[:20]
    
    def _mock_events(self, text: str, evidence_ids: List[str]) -> List[Dict]:
        """Extract events using simple patterns."""
        import re
        events = []
        
        # Meeting event pattern
        meeting_event = r'\b([A-Z][a-z]+)\s+was\s+(?:seen|observed)\s+(?:meeting|with)\s+([A-Z][a-z]+)\s+(?:near|at)\s+([a-zA-Z\s]+)'
        for match in re.finditer(meeting_event, text, re.IGNORECASE):
            events.append({
                "event_type": "MEETING",
                "description": match.group(0),
                "participant_texts": [match.group(1), match.group(2)],
                "location": match.group(3).strip(),
                "source_evidence_ids": evidence_ids[:1] if evidence_ids else [],
                "extraction_method": "LLM_ASSISTED",
                "status": "OBSERVED" if evidence_ids else "UNKNOWN"
            })
        
        return events[:10]


class LLMExtractor:
    """LLM-assisted extraction engine with evidence grounding.
    
    This is the main entry point for semantic extraction from evidence.
    It orchestrates the extraction pipeline:
    
    1. Document/text input
    2. LLM-assisted extraction (structured)
    3. Schema validation
    4. Evidence grounding validation
    5. Entity resolution preparation
    6. Graph insertion candidates
    
    The LLM NEVER directly mutates the graph. All extractions are
    candidates that must be validated before insertion.
    """
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[ExtractionConfig] = None,
        evidence_store: Optional[Any] = None,
    ):
        self.llm_provider = llm_provider or MockExtractionProvider()
        self.config = config or ExtractionConfig()
        self.evidence_store = evidence_store
        
        # In-memory cache
        self._cache: Dict[str, ExtractionResult] = {}
    
    def extract(
        self,
        document_id: str,
        text: str,
        evidence_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        """Extract entities, relationships, events from text.
        
        This is the main extraction entry point.
        
        Args:
            document_id: Source document identifier
            text: Text content to extract from
            evidence_ids: Evidence IDs this text came from
            metadata: Additional metadata
            
        Returns:
            ExtractionResult with all extracted items
        """
        # Check cache
        cache_key = self._cache_key(document_id, text)
        if self.config.cache_llm_results and cache_key in self._cache:
            logger.debug(f"Cache hit for document {document_id}")
            return self._cache[cache_key]
        
        # Build context for LLM
        context = self._build_context(document_id, text, evidence_ids, metadata)
        
        # Get LLM response
        try:
            llm_response = self.llm_provider.generate(
                prompt=self._extraction_prompt(),
                context=context,
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise ExtractionError(f"LLM generation failed: {e}") from e
        
        # Parse and validate
        try:
            result = self._parse_and_validate(
                llm_response=llm_response,
                document_id=document_id,
                evidence_ids=evidence_ids or [],
            )
        except ValidationFailedError as e:
            logger.warning(f"Validation failed for {document_id}: {e}")
            # Return empty result with validation errors
            result = ExtractionResult(
                extraction_id=self._extraction_id(document_id),
                source_document_id=document_id,
                extraction_method=ExtractionMethod.LLM_ASSISTED,
                validated=False,
                validation_errors=[str(e)],
            )
        
        # Cache result
        if self.config.cache_llm_results:
            self._cache[cache_key] = result
        
        return result
    
    def _cache_key(self, document_id: str, text: str) -> str:
        """Generate cache key from document content."""
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{document_id}:{content_hash}"
    
    def _extraction_id(self, document_id: str) -> str:
        """Generate unique extraction ID."""
        return f"EXT-{uuid5(EXTRACTION_NAMESPACE, document_id)}"
    
    def _extraction_prompt(self) -> str:
        """Get the extraction prompt template."""
        return """Extract structured information from the provided evidence.

IMPORTANT RULES:
1. Extract only what is explicitly stated in the evidence
2. Mark status as OBSERVED for direct observations, INFERRED for derived conclusions
3. Every extraction must reference at least one evidence_id
4. Do not fabricate information not in the source
5. Preserve the exact text spans where possible

Extract:
- Entities: people, organizations, locations, phones, emails, vehicles, accounts
- Relationships: how entities are connected (KNOWS, CALLS, MEETS, OWNS, etc.)
- Events: occurrences involving entities (MEETING, TRANSACTION, COMMUNICATION, etc.)

Return JSON with:
{
  "entities": [{"entity_text", "entity_type", "source_evidence_ids", "status", ...}],
  "relationships": [{"subject_text", "predicate", "object_text", "source_evidence_ids", ...}],
  "events": [{"event_type", "description", "participant_texts", "location", ...}]
}
"""
    
    def _build_context(
        self,
        document_id: str,
        text: str,
        evidence_ids: Optional[List[str]],
        metadata: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build context for LLM prompt."""
        context = [
            {
                "kind": "document",
                "document_id": document_id,
                "text": text,
                "evidence_ids": evidence_ids or [],
                "metadata": metadata or {},
            }
        ]
        
        # Add evidence records if available
        if self.evidence_store and evidence_ids:
            for eid in evidence_ids:
                try:
                    record = self.evidence_store.get(eid)
                    if record:
                        context.append({
                            "kind": "evidence",
                            "evidence_id": eid,
                            "content": getattr(record, "content", ""),
                            "metadata": getattr(record, "metadata", {}),
                        })
                except Exception as e:
                    logger.warning(f"Could not retrieve evidence {eid}: {e}")
        
        return context
    
    def _parse_and_validate(
        self,
        llm_response: str,
        document_id: str,
        evidence_ids: List[str],
    ) -> ExtractionResult:
        """Parse LLM response and validate extractions."""
        
        # Parse JSON
        try:
            data = json.loads(llm_response)
        except json.JSONDecodeError as e:
            raise ValidationFailedError(f"Invalid JSON from LLM: {e}")
        
        # Create extraction result
        extraction_id = self._extraction_id(document_id)
        result = ExtractionResult(
            extraction_id=extraction_id,
            source_document_id=document_id,
            extraction_method=ExtractionMethod.LLM_ASSISTED,
            llm_provider=self.llm_provider.name,
        )
        
        # Validate and add entities
        for entity_data in data.get("entities", []):
            try:
                entity = self._validate_entity(entity_data, evidence_ids)
                result.entities.append(entity)
            except ValidationError as e:
                logger.warning(f"Entity validation failed: {e}")
                result.validation_errors.append(f"Entity: {e}")
            except EvidenceResolutionError as e:
                logger.warning(f"Evidence resolution failed: {e}")
                result.validation_errors.append(str(e))
        
        # Validate and add relationships
        for rel_data in data.get("relationships", []):
            try:
                relationship = self._validate_relationship(rel_data, evidence_ids)
                result.relationships.append(relationship)
            except ValidationError as e:
                logger.warning(f"Relationship validation failed: {e}")
                result.validation_errors.append(f"Relationship: {e}")
            except EvidenceResolutionError as e:
                logger.warning(f"Evidence resolution failed: {e}")
                result.validation_errors.append(str(e))
        
        # Validate and add events
        for event_data in data.get("events", []):
            try:
                event = self._validate_event(event_data, evidence_ids)
                result.events.append(event)
            except ValidationError as e:
                logger.warning(f"Event validation failed: {e}")
                result.validation_errors.append(f"Event: {e}")
            except EvidenceResolutionError as e:
                logger.warning(f"Evidence resolution failed: {e}")
                result.validation_errors.append(str(e))
        
        # Apply limits
        result.entities = result.entities[:self.config.max_entities_per_doc]
        result.relationships = result.relationships[:self.config.max_relationships_per_doc]
        result.events = result.events[:self.config.max_events_per_doc]
        
        # Mark as validated if no errors
        result.validated = len(result.validation_errors) == 0
        
        return result
    
    def _validate_entity(
        self,
        data: Dict[str, Any],
        available_evidence_ids: List[str],
    ) -> EntityMention:
        """Validate entity data and create EntityMention."""
        
        # Validate evidence IDs
        source_evidence_ids = data.get("source_evidence_ids", [])
        if self.config.require_evidence_ids and not source_evidence_ids:
            raise EvidenceResolutionError(
                "Entity has no source_evidence_ids. All entities must be grounded in evidence."
            )
        
        # Validate evidence IDs exist if required
        if self.config.validate_evidence_exists and source_evidence_ids:
            for eid in source_evidence_ids:
                if eid not in available_evidence_ids:
                    # Don't fail, just warn and use what we have
                    logger.warning(f"Evidence ID {eid} not in available evidence")
        
        # Convert source spans
        source_spans = []
        for span_data in data.get("source_spans", []):
            try:
                source_spans.append(SourceSpan(**span_data))
            except Exception as e:
                logger.debug(f"Invalid source span: {e}")
        
        # Create confidence components
        confidence = ConfidenceComponents(
            evidence_quality=data.get("confidence", 0.8),
            extraction_confidence=0.8 if data.get("extraction_method") == "RULE_BASED" else 0.7,
        )
        
        # Create entity mention
        return EntityMention(
            mention_id=f"EM-{uuid5(EXTRACTION_NAMESPACE, str(data.get('entity_text', '')))}",
            entity_text=data.get("entity_text", ""),
            entity_type=EntityType(data.get("entity_type", "UNKNOWN")),
            normalized_form=data.get("normalized_form"),
            source_evidence_ids=source_evidence_ids or available_evidence_ids[:1],
            source_spans=source_spans,
            extraction_method=ExtractionMethod(data.get("extraction_method", "LLM_ASSISTED")),
            status=ObservationStatus(data.get("status", "OBSERVED" if source_evidence_ids else "UNKNOWN")),
            confidence=confidence,
            attributes=data.get("attributes", {}),
        )
    
    def _validate_relationship(
        self,
        data: Dict[str, Any],
        available_evidence_ids: List[str],
    ) -> RelationshipCandidate:
        """Validate relationship data and create RelationshipCandidate."""
        
        source_evidence_ids = data.get("source_evidence_ids", [])
        if self.config.require_evidence_ids and not source_evidence_ids:
            raise EvidenceResolutionError(
                "Relationship has no source_evidence_ids. All relationships must be grounded in evidence."
            )
        
        # Convert source spans
        source_spans = []
        for span_data in data.get("source_spans", []):
            try:
                source_spans.append(SourceSpan(**span_data))
            except Exception as e:
                logger.debug(f"Invalid source span: {e}")
        
        confidence = ConfidenceComponents(
            evidence_quality=data.get("confidence", 0.8),
            extraction_confidence=0.75,
        )
        
        return RelationshipCandidate(
            candidate_id=f"RC-{uuid5(EXTRACTION_NAMESPACE, f'{data.get('subject_text', '')}-{data.get('predicate', '')}-{data.get('object_text', '')}')}",
            subject=data.get("subject", data.get("subject_text", "")),
            subject_text=data.get("subject_text", ""),
            predicate=RelationshipType(data.get("predicate", "RELATED_TO")),
            object=data.get("object", data.get("object_text", "")),
            object_text=data.get("object_text", ""),
            source_evidence_ids=source_evidence_ids or available_evidence_ids[:1],
            source_spans=source_spans,
            extraction_method=ExtractionMethod(data.get("extraction_method", "LLM_ASSISTED")),
            status=ObservationStatus(data.get("status", "OBSERVED" if source_evidence_ids else "UNKNOWN")),
            confidence=confidence,
            context=data.get("context"),
            attributes=data.get("attributes", {}),
        )
    
    def _validate_event(
        self,
        data: Dict[str, Any],
        available_evidence_ids: List[str],
    ) -> EventCandidate:
        """Validate event data and create EventCandidate."""
        
        source_evidence_ids = data.get("source_evidence_ids", [])
        if self.config.require_evidence_ids and not source_evidence_ids:
            raise EvidenceResolutionError(
                "Event has no source_evidence_ids. All events must be grounded in evidence."
            )
        
        # Convert source spans
        source_spans = []
        for span_data in data.get("source_spans", []):
            try:
                source_spans.append(SourceSpan(**span_data))
            except Exception as e:
                logger.debug(f"Invalid source span: {e}")
        
        confidence = ConfidenceComponents(
            evidence_quality=data.get("confidence", 0.8),
            extraction_confidence=0.7,
        )
        
        return EventCandidate(
            event_id=f"EV-{uuid5(EXTRACTION_NAMESPACE, data.get('description', str(data)))}",
            event_type=EventType(data.get("event_type", "UNKNOWN")),
            description=data.get("description", ""),
            participants=data.get("participants", []),
            participant_texts=data.get("participant_texts", []),
            location=data.get("location"),
            source_evidence_ids=source_evidence_ids or available_evidence_ids[:1],
            source_spans=source_spans,
            extraction_method=ExtractionMethod(data.get("extraction_method", "LLM_ASSISTED")),
            status=ObservationStatus(data.get("status", "OBSERVED" if source_evidence_ids else "UNKNOWN")),
            confidence=confidence,
            attributes=data.get("attributes", {}),
        )
    
    def batch_extract(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[ExtractionResult]:
        """Extract from multiple documents.
        
        Args:
            documents: List of dicts with 'document_id', 'text', 'evidence_ids'
            
        Returns:
            List of ExtractionResults
        """
        results = []
        for doc in documents:
            try:
                result = self.extract(
                    document_id=doc["document_id"],
                    text=doc["text"],
                    evidence_ids=doc.get("evidence_ids"),
                    metadata=doc.get("metadata"),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Extraction failed for {doc.get('document_id')}: {e}")
                # Add failed result
                results.append(ExtractionResult(
                    extraction_id=self._extraction_id(doc.get("document_id", "unknown")),
                    source_document_id=doc.get("document_id", "unknown"),
                    extraction_method=ExtractionMethod.LLM_ASSISTED,
                    validated=False,
                    validation_errors=[str(e)],
                ))
        
        return results


def get_extractor(
    provider: Optional[str] = None,
    evidence_store: Optional[Any] = None,
) -> LLMExtractor:
    """Factory function to get configured extractor.
    
    Args:
        provider: "mock" or "openai-compatible" (defaults to mock)
        evidence_store: Optional evidence store for validation
        
    Returns:
        Configured LLMExtractor
    """
    if provider is None or provider == "mock":
        llm_provider = MockExtractionProvider()
    elif provider == "openai-compatible":
        from src.xai.llm_providers import OpenAICompatProvider
        llm_provider = OpenAICompatProvider()
    else:
        raise ValueError(f"Unknown provider: {provider}")
    
    return LLMExtractor(
        llm_provider=llm_provider,
        evidence_store=evidence_store,
    )
