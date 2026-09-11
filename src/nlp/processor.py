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

from typing import Dict, Any
from src.nlp.document import Document
from src.nlp.language_layer import detect_language
from src.nlp.advanced_ner import extract_investigative_entities

class DocumentProcessor:
    """Orchestrates the entire document understanding pipeline."""

    def process(self, text: str, source_id: str, document_id: str) -> Document:
        doc = Document(
            document_id=document_id,
            source_id=source_id,
            raw_text=text,
        )
        # Apply language detection
        lang = detect_language(text)
        doc.language = lang.language
        doc.language_confidence = lang.confidence

        # Apply NER
        doc.entities = extract_investigative_entities(text, document_id)

        # Apply other stages...

        return doc
