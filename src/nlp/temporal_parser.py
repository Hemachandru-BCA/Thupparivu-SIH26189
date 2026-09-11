"""
nlp/temporal_parser.py
----------------------
Temporal NLP engine — extracting and normalizing investigative time expressions.

Supports:
 - Absolute expressions: "12 January 2026", "2026-08-21"
 - Relative expressions: "yesterday", "last night", "two days ago", "before the incident"
 - Time of day: "around 8 PM", "18:30"
 - Intervals: "between 7 and 9 PM", "shortly after"
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, Tuple
from src.nlp.document import TemporalSpan, TemporalRelationType, SourceSpan

def parse_temporal_expression(text: str, span: SourceSpan, anchor_time: Optional[datetime] = None) -> TemporalSpan:
    """Extract and normalize a temporal expression relative to an optional anchor."""
    # Placeholder: logic for temporal parsing using regex/grammar
    return TemporalSpan(
        id="TS-" + span.text[:5],
        surface_text=span.text,
        span=span,
        sentence_index=0,
    )
