"""
nlp/advanced_ner.py
-------------------
Advanced investigative NER engine for the Document Understanding pipeline.

Extends the basic spaCy-based extraction into a rich investigative taxonomy
(25+ types) with strict character span tracking and confidence decomposition.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set

import spacy
from spacy.language import Language
from spacy.tokens import Doc, Span

from src.nlp.document import EntitySpan, SourceSpan

# Expanded investigative taxonomy
TARGET_LABELS: Tuple[str, ...] = (
    "PERSON", "ALIAS", "PHONE", "EMAIL", "ADDRESS", "LOCATION", 
    "VEHICLE", "VEHICLE_NUMBER", "ORGANIZATION", "ACCOUNT", 
    "BANK", "UPI", "TRANSACTION", "CASE", "FIR", "INCIDENT", 
    "DATE", "TIME", "MONEY", "CRIME", "WEAPON", "DEVICE", 
    "SOCIAL_HANDLE", "DOCUMENT", "IDENTIFIER", "POLICE_STATION", 
    "COURT", "IP_ADDRESS", "DOMAIN"
)

# Common Indian given names for gazetteer
KNOWN_PERSONS: Tuple[str, ...] = (
    "ramesh", "akash", "vikram", "suresh", "arjun", "rohit", "priya",
    "meera", "kiran", "rahul", "amit", "sanjay", "vijay", "deepak",
    "manoj", "pooja", "neha", "anil", "rajesh", "sunil", "vikas",
    "ashok", "naveen", "varun", "aditya", "harish", "mohit", "rakesh",
    "ajay", "gaurav", "vishal", "pradeep",
)

# Common locations
KNOWN_LOCATIONS: Tuple[str, ...] = (
    "warehouse district", "riverside docks", "downtown cafe",
    "abandoned factory", "private villa", "parking garage b",
    "storage facility 12", "old harbour pier", "chennai", "mumbai",
    "delhi", "bangalore", "hyderabad", "pune", "kolkata", "coimbatore",
)

# Common organizations
KNOWN_ORGANIZATIONS: Tuple[str, ...] = (
    "lucky star bar", "sentinel logistics", "blue horizon trading",
    "cobra gang", "red viper syndicate", "shadow crew", "black cartel",
)

# Vehicle brands/models
_VEHICLE_BRANDS = r"(?:toyota|honda|ford|suzuki|bmw|mercedes|hyundai|tata|chevrolet|nissan|audi|kia|volkswagen|vw|jeep|mahindra|yamaha|bajaj|royal|skoda|volvo|mitsubishi|fiat|renault|lexus|subaru|mazda|dodge|tesla)"
_VEHICLE_MODELS = r"(?:camry|corolla|civic|accord|swift|baleno|i20|creta|scorpio|fortuner|innova|amaze|thar|bolero|ertiga|wagonr|alto|pulsar|activa|splendor|enfield|benz)"
_VEHICLE_TYPES = r"(?:car|sedan|suv|van|hatchback|truck|pickup|motorcycle|motorbike|bike|scooter|minivan|lorry|rickshaw)"
_COLORS = r"(?:black|white|red|blue|silver|gray|grey|green|yellow|orange|brown|beige|maroon)"

# Pre-compiled regex patterns
_TOWER_RE = re.compile(r"\bTWR-\d{2,4}\b")
_PHONE_RES = (
    re.compile(r"\+\d{1,3}[-.\s]?\(?\d{2,5}\)?(?:[-.\s]?\d{2,6}){1,3}"),
    re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
    re.compile(r"\b\d{5}\s\d{5}\b"),
    re.compile(r"\b\d{10,12}\b"),
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_UPI_RE = re.compile(r"\b[A-Za-z0-9._-]+@[A-Za-z]{2,}\b")
_VEHICLE_BRAND_RE = re.compile(
    rf"\b(?:(?i:{_COLORS})\s+)?(?i:{_VEHICLE_BRANDS})"
    rf"(?:\s+(?:(?i:{_VEHICLE_MODELS})|[A-Z][A-Za-z0-9-]+)){{0,2}}\b"
)
_VEHICLE_TYPE_RE = re.compile(rf"\b(?:(?i:{_COLORS})\s+)?(?i:{_VEHICLE_TYPES})\b")
_PLATE_RES = (
    re.compile(r"\b[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4}\b"),
    re.compile(r"\b(?!TWR-)[A-Z]{3}-\d{3,4}\b"),
)
_DATE_RES = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
)
_TIME_RES = (
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s*(?:am|pm)\b", re.IGNORECASE),
)
_MONEY_RES = re.compile(
    r"(?P<cur>₹|\$|€|£|rs\.?|inr|usd|eur|gbp)?\s*(?P<amt>\d[\d,]*\.?\d*)\s*"
    r"(?P<unit>(?:crore|lakh|k|million|thousand)?)",
    re.IGNORECASE,
)
_CRIME_RES = re.compile(r"\b(?:murder|theft|robbery|burglary|assault|fraud|kidnapping|extortion|arson|smuggling|trafficking|bribery|corruption|embezzlement|money laundering)\b", re.IGNORECASE)
_WEAPON_RES = re.compile(r"\b(?:gun|pistol|revolver|rifle|knife|dagger|sword|bomb|explosive|grenade|rifle|shotgun)\b", re.IGNORECASE)
_IP_RES = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RES = re.compile(r"\b[a-z0-9-]+\.[a-z]{2,}\b")
_ACCOUNT_RES = re.compile(r"\b(?:account|acct)\s+([A-Z0-9][A-Z0-9_-]{2,})\b", re.IGNORECASE)

# Gazetteer patterns (lowercase for matching)
PERSON_GAZETTEER: Set[str] = set(KNOWN_PERSONS)
LOCATION_GAZETTEER: Set[str] = set(KNOWN_LOCATIONS)
ORG_GAZETTEER: Set[str] = set(KNOWN_ORGANIZATIONS)

# Stopwords for vehicle disambiguation
_VEHICLE_STOPWORDS = frozenset(
    "group inc ltd llc company corp corporation gang crew syndicate cartel district "
    "police department motors industries bank trust rally club hotel restaurant bar "
    "cafe office".split()
)

def _contains_stopword(text: str) -> bool:
    return any(word.lower() in _VEHICLE_STOPWORDS for word in text.split())

def extract_investigative_entities(text: str, document_id: str) -> List[EntitySpan]:
    """Extract investigative entities with source spans using spaCy + regex + gazetteer fusion."""
    if not text.strip():
        return []
    
    entities: List[EntitySpan] = []
    entity_id_counter = 0
    
    # Try to load spaCy model
    nlp = None
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        warnings.warn("spaCy model 'en_core_web_sm' not found. Using regex-only extraction.")
        nlp = None
    
    doc = nlp(text) if nlp else None
    
    # 1. spaCy statistical NER (if available)
    if doc:
        for ent in doc.ents:
            label = _map_spacy_label(ent.label_)
            if label:
                entity_id_counter += 1
                entities.append(EntitySpan(
                    id=f"ENT-{document_id}-{entity_id_counter:04d}",
                    entity_type=label,
                    surface_text=ent.text,
                    normalized_text=ent.text.lower().strip(),
                    span=SourceSpan(start_char=ent.start_char, end_char=ent.end_char, text=ent.text),
                    sentence_index=_get_sentence_index(doc, ent.start_char),
                    confidence=0.85,
                    extractor="spacy_ner",
                    document_id=document_id,
                    attributes={"spacy_label": ent.label_}
                ))
    
    # 2. Gazetteer-based matching (persons, locations, organizations)
    entities.extend(_gazetteer_matches(text, document_id, entity_id_counter))
    entity_id_counter += len([e for e in entities if e.id.startswith(f"ENT-{document_id}")])
    
    # 3. Regex-based extraction for structured entities
    entities.extend(_regex_matches(text, document_id, entity_id_counter))
    
    # 4. Resolve overlaps (priority: structured > gazetteer > statistical)
    entities = _resolve_overlaps(entities)
    
    return entities

def _map_spacy_label(label: str) -> Optional[str]:
    """Map spaCy labels to investigative taxonomy."""
    mapping = {
        "PERSON": "PERSON",
        "GPE": "LOCATION",
        "LOC": "LOCATION",
        "FAC": "LOCATION",
        "ORG": "ORGANIZATION",
        "NORP": "ORGANIZATION",
        "DATE": "DATE",
        "TIME": "TIME",
        "MONEY": "MONEY",
        "CARDINAL": None,
        "ORDINAL": None,
        "PERCENT": None,
        "QUANTITY": None,
    }
    return mapping.get(label)

def _get_sentence_index(doc: Doc, char_pos: int) -> int:
    """Find which sentence index a character position falls in."""
    for i, sent in enumerate(doc.sents):
        if sent.start_char <= char_pos < sent.end_char:
            return i
    return 0

def _gazetteer_matches(text: str, document_id: str, start_counter: int) -> List[EntitySpan]:
    """Extract entities using gazetteer matching."""
    entities = []
    counter = start_counter
    text_lower = text.lower()
    
    # Person names
    for name in PERSON_GAZETTEER:
        for match in re.finditer(rf"\b{re.escape(name)}\b", text_lower):
            counter += 1
            start, end = match.start(), match.end()
            entities.append(EntitySpan(
                id=f"ENT-{document_id}-{counter:04d}",
                entity_type="PERSON",
                surface_text=text[start:end],
                normalized_text=name,
                span=SourceSpan(start_char=start, end_char=end, text=text[start:end]),
                sentence_index=0,
                confidence=0.8,
                extractor="gazetteer",
                document_id=document_id,
                attributes={"gazetteer": "KNOWN_PERSONS"}
            ))
    
    # Locations
    for loc in LOCATION_GAZETTEER:
        for match in re.finditer(rf"\b{re.escape(loc)}\b", text_lower):
            counter += 1
            start, end = match.start(), match.end()
            entities.append(EntitySpan(
                id=f"ENT-{document_id}-{counter:04d}",
                entity_type="LOCATION",
                surface_text=text[start:end],
                normalized_text=loc,
                span=SourceSpan(start_char=start, end_char=end, text=text[start:end]),
                sentence_index=0,
                confidence=0.8,
                extractor="gazetteer",
                document_id=document_id,
                attributes={"gazetteer": "KNOWN_LOCATIONS"}
            ))
    
    # Organizations
    for org in ORG_GAZETTEER:
        for match in re.finditer(rf"\b{re.escape(org)}\b", text_lower):
            counter += 1
            start, end = match.start(), match.end()
            entities.append(EntitySpan(
                id=f"ENT-{document_id}-{counter:04d}",
                entity_type="ORGANIZATION",
                surface_text=text[start:end],
                normalized_text=org,
                span=SourceSpan(start_char=start, end_char=end, text=text[start:end]),
                sentence_index=0,
                confidence=0.8,
                extractor="gazetteer",
                document_id=document_id,
                attributes={"gazetteer": "KNOWN_ORGANIZATIONS"}
            ))
    
    return entities

def _regex_matches(text: str, document_id: str, start_counter: int) -> List[EntitySpan]:
    """Extract entities using regex patterns for structured data."""
    entities = []
    counter = start_counter
    
    patterns = [
        (_PHONE_RES, "PHONE", "regex_phone", 0.95),
        ((_EMAIL_RE,), "EMAIL", "regex_email", 0.95),
        ((_UPI_RE,), "UPI", "regex_upi", 0.9),
        ((_ACCOUNT_RES,), "ACCOUNT", "regex_account", 0.85),
        (_DATE_RES, "DATE", "regex_date", 0.9),
        (_TIME_RES, "TIME", "regex_time", 0.9),
        ((_MONEY_RES,), "MONEY", "regex_money", 0.9),
        ((_CRIME_RES,), "CRIME", "regex_crime", 0.85),
        ((_WEAPON_RES,), "WEAPON", "regex_weapon", 0.85),
        ((_IP_RES,), "IP_ADDRESS", "regex_ip", 0.9),
        ((_DOMAIN_RES,), "DOMAIN", "regex_domain", 0.9),
        ((_VEHICLE_BRAND_RE,), "VEHICLE", "regex_vehicle_brand", 0.85),
        ((_VEHICLE_TYPE_RE,), "VEHICLE", "regex_vehicle_type", 0.75),
        (_PLATE_RES, "VEHICLE_NUMBER", "regex_plate", 0.95),
        ((_TOWER_RE,), "LOCATION", "regex_tower", 0.9),
    ]
    for pattern_group, label, extractor, confidence in patterns:
        patterns_list = pattern_group if isinstance(pattern_group, tuple) else [pattern_group]
        for pattern in patterns_list:
            for match in pattern.finditer(text):
                counter += 1
                start, end = match.start(), match.end()
                # For MONEY, extract amount
                attrs = {}
                if label == "MONEY" and match.groupdict():
                    attrs = {"amount": match.group("amt"), "currency": match.group("cur")}
                
                # Skip vehicle matches with stopwords
                if label == "VEHICLE" and _contains_stopword(text[start:end]):
                    continue
                
                entities.append(EntitySpan(
                    id=f"ENT-{document_id}-{counter:04d}",
                    entity_type=label,
                    surface_text=text[start:end],
                    normalized_text=text[start:end].lower().strip(),
                    span=SourceSpan(start_char=start, end_char=end, text=text[start:end]),
                    sentence_index=0,
                    confidence=confidence,
                    extractor=extractor,
                    document_id=document_id,
                    attributes=attrs
                ))
    
    return entities

def _resolve_overlaps(entities: List[EntitySpan]) -> List[EntitySpan]:
    """Resolve overlapping entity spans using priority: structured > gazetteer > statistical."""
    if not entities:
        return []
    
    # Priority: regex (structured) > gazetteer > spacy
    priority = {"regex_phone": 0, "regex_email": 0, "regex_upi": 0, "regex_account": 0,
                "regex_date": 0, "regex_time": 0, "regex_money": 0, "regex_crime": 0,
                "regex_weapon": 0, "regex_ip": 0, "regex_domain": 0, 
                "regex_vehicle_brand": 0, "regex_vehicle_type": 0, "regex_plate": 0,
                "regex_tower": 0,
                "gazetteer": 1, "spacy_ner": 2}
    
    # Sort by start position, then by priority
    entities.sort(key=lambda e: (e.span.start_char, priority.get(e.extractor, 99)))
    
    resolved = []
    for ent in entities:
        # Check for overlap with already accepted entities
        overlap = False
        for accepted in resolved:
            if (ent.span.start_char < accepted.span.end_char and 
                ent.span.end_char > accepted.span.start_char):
                overlap = True
                break
        if not overlap:
            resolved.append(ent)
    
    return resolved
