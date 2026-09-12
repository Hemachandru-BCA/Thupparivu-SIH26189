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
import re
from typing import Optional, List, Tuple
from src.nlp.document import TemporalSpan, TemporalRelationType, SourceSpan

# Temporal regex patterns
_ABSOLUTE_DATE_RES = (
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),  # ISO format
    re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b"),  # DD-MM-YYYY
    re.compile(r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b", re.IGNORECASE),
)
_TIME_RES = (
    re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})\s*(am|pm)\b", re.IGNORECASE),
)
_RELATIVE_DATE_RES = re.compile(
    r"\b(yesterday|today|tomorrow|day before yesterday|day after tomorrow|"
    r"last (night|week|month|year)|next (week|month|year)|"
    r"this (week|month|year)|\d+\s+(days?|weeks?|months?|years?)\s+ago|"
    r"in\s+\d+\s+(days?|weeks?|months?|years?)|"
    r"the (previous|following|next)\s+(day|night|week|month))\b", 
    re.IGNORECASE
)
_RELATIVE_TIME_RES = re.compile(
    r"\b(early morning|morning|afternoon|evening|night|midnight|noon)\b", 
    re.IGNORECASE
)
_TEMPORAL_RELATION_RES = re.compile(
    r"\b(before|after|during|until|since|between)\s+", 
    re.IGNORECASE
)
_INTERVAL_RES = re.compile(
    r"\b(between)\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?\s+and\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?\b", 
    re.IGNORECASE
)

_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def parse_temporal_expression(text: str, span: SourceSpan, anchor_time: Optional[datetime] = None) -> TemporalSpan:
    """Extract and normalize a temporal expression relative to an optional anchor."""
    if not anchor_time:
        anchor_time = datetime.now()
    
    text_lower = text.lower().strip()
    
    # Try absolute date + time
    for pattern in _ABSOLUTE_DATE_RES:
        match = pattern.search(text)
        if match:
            iso_date = _parse_absolute_date(match, pattern)
            time_match = _extract_time(text)
            if iso_date and time_match:
                iso_date += "T" + time_match
            return TemporalSpan(
                id=f"TS-{hash(text) % 100000:05d}",
                surface_text=text,
                span=span,
                sentence_index=0,
                normalized_iso=iso_date,
                is_relative=False,
                temporal_relation=TemporalRelationType.SAME_TIME,
                confidence=0.95
            )
    
    # Try relative date
    rel_match = _RELATIVE_DATE_RES.search(text_lower)
    if rel_match:
        iso_date, delta = _parse_relative_date(rel_match.group(1), anchor_time)
        return TemporalSpan(
            id=f"TS-{hash(text) % 100000:05d}",
            surface_text=text,
            span=span,
            sentence_index=0,
            normalized_iso=iso_date,
            is_relative=True,
            temporal_relation=TemporalRelationType.APPROXIMATE,
            delta_minutes=delta,
            confidence=0.8
        )
    
    # Try time of day
    time_match = _extract_time(text)
    if time_match:
        iso_time = anchor_time.strftime("%Y-%m-%d") + "T" + time_match
        return TemporalSpan(
            id=f"TS-{hash(text) % 100000:05d}",
            surface_text=text,
            span=span,
            sentence_index=0,
            normalized_iso=iso_time,
            is_relative=False,
            temporal_relation=TemporalRelationType.SAME_TIME,
            confidence=0.9
        )
    
    return TemporalSpan(
        id=f"TS-{hash(text) % 100000:05d}",
        surface_text=text,
        span=span,
        sentence_index=0,
        is_relative=True,
        temporal_relation=TemporalRelationType.UNKNOWN,
        confidence=0.3
    )

def _parse_absolute_date(match: re.Match, pattern: re.Pattern) -> Optional[str]:
    """Parse absolute date from regex match."""
    groups = match.groups()
    try:
        if pattern.pattern.startswith(r"\b(\d{4})"):  # ISO
            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
        elif pattern.pattern.startswith(r"\b(\d{1,2})[-/]"):  # DD-MM-YYYY
            day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
        elif "jan|feb|mar" in pattern.pattern and pattern.pattern.startswith(r"\b(\d{1,2})\s+"):  # DD MON YYYY
            day, month_str, year = int(groups[0]), groups[1][:3].lower(), int(groups[2])
            month = _MONTH_MAP.get(month_str, 1)
        else:  # MON DD, YYYY
            month_str, day, year = groups[0][:3].lower(), int(groups[1]), int(groups[2])
            month = _MONTH_MAP.get(month_str, 1)
        
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        return None

def _extract_time(text: str) -> Optional[str]:
    """Extract time component from text."""
    for pattern in _TIME_RES:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            try:
                hour = int(groups[0])
                minute = int(groups[1]) if len(groups) > 1 and groups[1] else 0
                second = int(groups[2]) if len(groups) > 2 and groups[2] else 0
                ampm = groups[3].lower() if len(groups) > 3 and groups[3] else None
                
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                return f"{hour:02d}:{minute:02d}:{second:02d}"
            except (ValueError, IndexError):
                continue
    return None

def _parse_relative_date(rel_text: str, anchor: datetime) -> Tuple[str, float]:
    """Parse relative date expression and return ISO date + delta in minutes."""
    rel_text = rel_text.lower()
    delta_minutes = 0.0
    
    if rel_text in ('yesterday', 'day before yesterday'):
        days = 1 if rel_text == 'yesterday' else 2
        result = anchor - timedelta(days=days)
        delta_minutes = -days * 24 * 60
    elif rel_text == 'tomorrow':
        result = anchor + timedelta(days=1)
        delta_minutes = 24 * 60
    elif rel_text == 'day after tomorrow':
        result = anchor + timedelta(days=2)
        delta_minutes = 2 * 24 * 60
    elif 'last night' in rel_text:
        result = anchor - timedelta(days=1)
        result = result.replace(hour=20, minute=0)
        delta_minutes = -24 * 60
    elif 'last week' in rel_text:
        result = anchor - timedelta(weeks=1)
        delta_minutes = -7 * 24 * 60
    elif 'last month' in rel_text:
        # Approximate month
        result = anchor - timedelta(days=30)
        delta_minutes = -30 * 24 * 60
    elif 'last year' in rel_text:
        result = anchor - timedelta(days=365)
        delta_minutes = -365 * 24 * 60
    elif 'next week' in rel_text:
        result = anchor + timedelta(weeks=1)
        delta_minutes = 7 * 24 * 60
    elif 'next month' in rel_text:
        result = anchor + timedelta(days=30)
        delta_minutes = 30 * 24 * 60
    elif 'next year' in rel_text:
        result = anchor + timedelta(days=365)
        delta_minutes = 365 * 24 * 60
    elif 'this week' in rel_text:
        # Start of week
        result = anchor - timedelta(days=anchor.weekday())
        delta_minutes = -anchor.weekday() * 24 * 60
    elif 'this month' in rel_text:
        result = anchor.replace(day=1)
        delta_minutes = -(anchor.day - 1) * 24 * 60
    elif 'this year' in rel_text:
        result = anchor.replace(month=1, day=1)
        delta_minutes = -(anchor.month - 1) * 30 * 24 * 60  # Approximate
    elif 'ago' in rel_text:
        # "X days/weeks/months/years ago"
        match = re.search(r'(\d+)\s+(days?|weeks?|months?|years?)\s+ago', rel_text)
        if match:
            num, unit = int(match.group(1)), match.group(2)
            if 'day' in unit:
                result = anchor - timedelta(days=num)
                delta_minutes = -num * 24 * 60
            elif 'week' in unit:
                result = anchor - timedelta(weeks=num)
                delta_minutes = -num * 7 * 24 * 60
            elif 'month' in unit:
                result = anchor - timedelta(days=num * 30)
                delta_minutes = -num * 30 * 24 * 60
            elif 'year' in unit:
                result = anchor - timedelta(days=num * 365)
                delta_minutes = -num * 365 * 24 * 60
        else:
            result = anchor
    elif 'in ' in rel_text and ('day' in rel_text or 'week' in rel_text or 'month' in rel_text or 'year' in rel_text):
        # "in X days/weeks/months/years"
        match = re.search(r'in\s+(\d+)\s+(days?|weeks?|months?|years?)', rel_text)
        if match:
            num, unit = int(match.group(1)), match.group(2)
            if 'day' in unit:
                result = anchor + timedelta(days=num)
                delta_minutes = num * 24 * 60
            elif 'week' in unit:
                result = anchor + timedelta(weeks=num)
                delta_minutes = num * 7 * 24 * 60
            elif 'month' in unit:
                result = anchor + timedelta(days=num * 30)
                delta_minutes = num * 30 * 24 * 60
            elif 'year' in unit:
                result = anchor + timedelta(days=num * 365)
                delta_minutes = num * 365 * 24 * 60
        else:
            result = anchor
    elif 'the previous day' in rel_text:
        result = anchor - timedelta(days=1)
        delta_minutes = -24 * 60
    elif 'the following day' in rel_text:
        result = anchor + timedelta(days=1)
        delta_minutes = 24 * 60
    elif 'the next day' in rel_text:
        result = anchor + timedelta(days=1)
        delta_minutes = 24 * 60
    else:
        result = anchor
    
    return result.strftime("%Y-%m-%d"), delta_minutes

def extract_all_temporal_expressions(text: str, sentence_spans: List[Tuple[int, int]]) -> List[TemporalSpan]:
    """Extract all temporal expressions from text with sentence context."""
    temporal_spans = []
    
    # Combined pattern for all temporal expressions
    combined_pattern = re.compile(
        r"("
        r"\b\d{4}-\d{2}-\d{2}\b|"
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b|"
        r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b|"
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b|"
        r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b|"
        r"\b\d{1,2}\s*(?:am|pm)\b|"
        r"\b(?:yesterday|today|tomorrow|day before yesterday|day after tomorrow|"
        r"last (?:night|week|month|year)|next (?:week|month|year)|"
        r"this (?:week|month|year)|\d+\s+(?:days?|weeks?|months?|years?)\s+ago|"
        r"in\s+\d+\s+(?:days?|weeks?|months?|years?)|"
        r"the (?:previous|following|next)\s+(?:day|night|week|month))"
        r")", 
        re.IGNORECASE
    )
    
    for match in combined_pattern.finditer(text):
        start, end = match.start(), match.end()
        
        # Find sentence index
        sentence_idx = 0
        for i, (s_start, s_end) in enumerate(sentence_spans):
            if start >= s_start and end <= s_end:
                sentence_idx = i
                break
        
        span = SourceSpan(start_char=start, end_char=end, text=match.group(0))
        temporal = parse_temporal_expression(match.group(0), span)
        temporal.sentence_index = sentence_idx
        temporal_spans.append(temporal)
    
    return temporal_spans
