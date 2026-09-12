"""
nlp/processor.py
----------------
Multi-stage Document Processing Engine for Thupparivu.

Pipeline:
  Raw Document
    → Language Detection
    → Text Normalization
    → Sentence Segmentation
    → Advanced NER
    → Temporal Parsing
    → Negation & Modality Analysis
    → Coreference Resolution
    → Claim & Event Extraction
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Tuple
from src.nlp.document import Document, SourceSpan, ModalityType, PolarityType
from src.nlp.language_layer import detect_language
from src.nlp.advanced_ner import extract_investigative_entities
from src.nlp.temporal_parser import extract_all_temporal_expressions
from src.nlp.negation_modality import detect_negations, detect_modality, analyze_sentence_claims
from src.nlp.coreference import resolve_coreferences, extract_nominal_coreferences

class DocumentProcessor:
    """Orchestrates the entire document understanding pipeline."""

    def process(self, text: str, source_id: str, document_id: str) -> Document:
        """Process a raw document through the complete NLP pipeline."""
        doc = Document(
            document_id=document_id,
            source_id=source_id,
            raw_text=text,
        )
        
        # Stage 1: Language Detection
        lang = detect_language(text)
        doc.language = lang.language
        doc.language_confidence = lang.confidence
        
        # Stage 2: Text Normalization & Sentence Segmentation
        doc.normalized_text = self._normalize_text(text)
        doc.sentences = self._segment_sentences(text)
        
        # Stage 3: Advanced NER
        doc.entities = extract_investigative_entities(text, document_id)
        
        # Stage 4: Temporal Parsing
        sentence_spans = [(s.start_char, s.end_char) for s in doc.sentences]
        sentence_texts = [s.text for s in doc.sentences]
        doc.temporal_spans = extract_all_temporal_expressions(text, sentence_spans)
        
        # Stage 5: Negation & Modality Analysis
        doc.negations = []
        for i, sent in enumerate(doc.sentences):
            sent_negations = detect_negations(sent.text, i)
            doc.negations.extend(sent_negations)
        
        # Stage 6: Coreference Resolution
        doc.coreferences = resolve_coreferences(
            text, doc.entities, sentence_spans, sentence_texts
        )
        
        # Stage 7: Claim & Event Extraction (simplified for now)
        doc.claims = self._extract_claims(doc)
        doc.events = self._extract_events(doc)
        
        # Update metadata
        doc.metadata.update({
            "pipeline_version": "1.0",
            "stages_completed": [
                "language_detection",
                "normalization",
                "sentence_segmentation", 
                "ner",
                "temporal_parsing",
                "negation_modality",
                "coreference",
                "claim_extraction"
            ],
            "entity_count": len(doc.entities),
            "temporal_count": len(doc.temporal_spans),
            "negation_count": len(doc.negations),
            "coreference_count": len(doc.coreferences),
            "claim_count": len(doc.claims),
            "event_count": len(doc.events),
        })
        
        return doc
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text while preserving original."""
        # Unicode normalization
        import unicodedata
        text = unicodedata.normalize("NFKC", text)
        # Standardize whitespace
        text = re.sub(r"\s+", " ", text)
        # Standardize quotes
        text = text.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
        return text.strip()
    
    def _segment_sentences(self, text: str) -> List:
        """Segment text into sentences with character offsets."""
        from src.nlp.document import SentenceUnit
        sentences = []
        
        # Simple sentence segmentation (can be improved with spaCy)
        # Split on sentence boundaries
        sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
        spans = []
        last_end = 0
        
        for match in sentence_pattern.finditer(text):
            start = last_end
            end = match.start() + 1  # Include the punctuation
            spans.append((start, end))
            last_end = match.end()
        
        # Add final segment if any
        if last_end < len(text):
            spans.append((last_end, len(text)))
        
        # Create SentenceUnit objects
        for idx, (start, end) in enumerate(spans):
            sent_text = text[start:end].strip()
            if sent_text:
                sentences.append(SentenceUnit(
                    index=idx,
                    text=sent_text,
                    start_char=start,
                    end_char=end,
                    tokens=[],  # Tokens would be populated by tokenizer
                ))
        
        return sentences
    
    def _extract_claims(self, doc: Document) -> List:
        """Extract structured claims from processed document."""
        from src.nlp.document import ClaimUnit
        claims = []
        
        # Use negation/modality analysis on sentences
        for sent in doc.sentences:
            if not sent.text.strip():
                continue
            
            analysis = analyze_sentence_claims(sent.text, sent.index)
            
            # Create claim if we have entities in this sentence
            sent_entities = [e for e in doc.entities if e.sentence_index == sent.index]
            if sent_entities:
                # Create subject-predicate-object claims from entities and relations
                # This is simplified - real implementation would use relation extraction
                for ent in sent_entities:
                    claim_id = f"CL-{doc.document_id}-{sent.index}-{ent.id[-4:]}"
                    claims.append(ClaimUnit(
                        claim_id=claim_id,
                        subject=ent.surface_text,
                        predicate="MENTIONED_IN",
                        object=f"Sentence {sent.index}",
                        polarity=analysis["polarity"],
                        modality=analysis["modality"],
                        confidence=0.7,
                        source_span=SourceSpan(start_char=sent.start_char, end_char=sent.end_char, text=sent.text),
                        evidence_id=doc.source_id,
                        timestamp=None,
                        location=None,
                        sentence_index=sent.index,
                        is_negated=analysis["has_negation"],
                        attributes={"modality": analysis["modality"], "attributed": analysis["attributed"]}
                    ))
        
        return claims
    
    def _extract_events(self, doc: Document) -> List:
        """Extract events from temporal and entity information."""
        from src.nlp.document import EventUnit
        events = []
        
        # Combine temporal spans with entities to form events
        for temp in doc.temporal_spans:
            if temp.normalized_iso:
                sent_entities = [e for e in doc.entities if e.sentence_index == temp.sentence_index]
                if sent_entities:
                    participants = [{"id": e.id, "role": "participant", "text": e.surface_text} for e in sent_entities[:3]]
                    event_id = f"EVT-{doc.document_id}-{temp.sentence_index}-{temp.id[-4:]}"
                    events.append(EventUnit(
                        event_id=event_id,
                        event_type="TEMPORAL_MENTION",
                        participants=participants,
                        location=None,
                        timestamp=temp.normalized_iso,
                        source_span=temp.span,
                        evidence_id=doc.source_id,
                        sentence_index=temp.sentence_index,
                        modality=ModalityType.FACTUAL,
                        polarity=PolarityType.POSITIVE,
                        attributes={"temporal_text": temp.surface_text}
                    ))
        
        return events

def analyze_sentence_claims(text: str, sentence_index: int = 0) -> dict:
    """Analyze a sentence for negation, modality, and attribution."""
    from src.nlp.negation_modality import analyze_sentence_claims as _analyze
    return _analyze(text, sentence_index)
