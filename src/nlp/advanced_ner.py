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
    # extended common Indian given names (short transactional records)
    "sudhir", "manish", "kavitha", "mohan", "mukesh", "vinod", "karthik",
    "mahesh", "prakash", "sandeep", "nilesh", "chetan", "sameer",
    "imran", "faisal", "abdul", "kavita", "gayatri", "divya", "swati",
    "sumit", "rajiv", "ankit", "sonal", "rekha", "manju", "shruti",
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
    "hotel saravana bhavan", "saravana bhavan",
)

# Vehicle brands/models
_VEHICLE_BRANDS = r"(?:toyota|honda|hero|ford|suzuki|bmw|mercedes|hyundai|tata|chevrolet|nissan|audi|kia|volkswagen|vw|jeep|mahindra|yamaha|bajaj|royal|skoda|volvo|mitsubishi|fiat|renault|lexus|subaru|mazda|dodge|tesla)"
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
_VEHICLE_MODEL_RE = re.compile(
    rf"\b(?:(?i:{_COLORS})\s+)?(?i:{_VEHICLE_MODELS})\b",
    re.IGNORECASE,
)
_UPI_APP_RES = re.compile(
    r"\b(?:gpay|google\s*pay|phonepe|paytm|bhimpay)\b",
    re.IGNORECASE,
)
_KNOWN_BANKS: frozenset = frozenset([
    "sbi bank", "hdfc", "state bank of india", "reserve bank of india",
    "icici", "icici bank", "axis bank", "kotak mahindra bank", "pnb",
    "bank of india", "bank of baroda", "canara bank", "union bank",
    "yes bank", "indian overseas bank", "federal bank", "idfc",
])  # type: ignore[assignment]
_PLATE_RES = (
    # Indian RTO plates: XX-NN-XX-NNNN or XX NN XX NNNN
    re.compile(r"\b[A-Z]{2}[-.\s]?\d{1,2}[-.\s]?[A-Z]{1,3}[-.\s]?\d{4}\b"),
    # Generic short plates — but NOT FIR/case/reference IDs (those contain
    # a 4-digit year like FIR-2024-9912 and would partially match)
    re.compile(r"\b(?!TWR-)(?!FIR-|CASE-|REF-|TXN-|ID-|DOC-)[A-Z]{3,4}-\d{3,4}\b"),
)
_DATE_RES = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
)
_TIME_RES = (
    # pattern 1: HH:MM[:SS] with optional am/pm — do NOT consume the trailing
    # whitespace (the \b after \s* was eating the space after the time)
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?=\s*(?:am|pm)?\b)", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s*(?:am|pm)\b", re.IGNORECASE),
)
_MONEY_RES = re.compile(
    r"(?P<cur>₹|\$|€|£|rs\.?|inr|usd|eur|gbp)\s*(?P<amt>\d[\d,]*\.?\d*)\s*"
    r"(?P<unit>(?:crore|lakh|k|million|thousand)?)"
    r"|(?P<amt2>\d[\d,]*\.?\d*)\s*(?P<unit2>(?:crore|lakh|lakhs|million|thousand|rupees|bucks|grand))",
    re.IGNORECASE,
)
_CRIME_RES = re.compile(r"\b(?:murder|theft|robbery|burglary|assault|fraud|kidnapping|extortion|arson|smuggling|trafficking|bribery|corruption|embezzlement|money laundering)\b", re.IGNORECASE)
_WEAPON_RES = re.compile(r"\b(?:gun|pistol|revolver|rifle|knife|knives|dagger|sword|bomb|explosive|grenade|shotgun)\b", re.IGNORECASE)
_IP_RES = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RES = re.compile(r"\b[a-z0-9-]+\.[a-z]{2,}\b")
_ACCOUNT_RES = re.compile(
    r"\b(?:account|acct)\s+(?:number|no\.?)?\s*"
    r"([A-Z0-9][A-Z0-9_-]*\d[A-Z0-9_-]*)\b",
    re.IGNORECASE,
)
_POLICE_STATION_RES = re.compile(
    r"\b(?:police\s+station|ps)\s+([A-Z][A-Za-z\s]{1,40}?)\b",
    re.IGNORECASE,
)
# FIR / case references.  The capture group *must* contain a digit — this
# excludes English function words that otherwise satisfy the bare alnum class
# (e.g. "no FIR regarding the fraud" used to extract "regarding" as the ID).
# Two forms:
#   1. trigger + separator:  "case no. CASE-2024-556", "FIR no. FIR-2024-8890"
#   2. dash-attached:        "filed FIR-2024-9912" (FIR doubles as ID prefix)
_FIR_RES = (
    re.compile(
        r"\b(?:fir|case)\s*(?:no\.?|number)?\s*[#:]?\s*"
        r"([A-Z0-9][A-Z0-9/_-]*\d[A-Z0-9/_-]*)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b((?:fir|case)-[A-Z0-9][A-Z0-9/_-]*\d[A-Z0-9/_-]*)\b",
        re.IGNORECASE,
    ),
)
_ID_RES = re.compile(
    r"\b(?:reference|ref|transaction\s*(?:id|no)|txn\s*(?:id|no))\s*[#:]?\s*"
    r"([A-Z0-9][A-Z0-9/_-]*\d[A-Z0-9/_-]*)\b",
    re.IGNORECASE,
)
# Document IDs (passport / license / aadhaar style: prefix + digits).
# The capture group must contain a digit — "aadhaar reference" must not
# swallow the bare English word "reference" as the ID.
_DOCUMENT_RES = re.compile(
    r"\b(?:document\s*(?:id|no\.?|number)?|passport|aadhaar|license|licence|"
    r"driving\s*licence|voter\s*id|pan)\s*[#:]?\s*"
    r"([A-Z0-9][A-Z0-9-]*\d[A-Z0-9-]*)\b",
    re.IGNORECASE,
)
_COURT_RES = re.compile(r"\b(?:court|high\s*court|district\s*court|sessions\s*court)\b", re.IGNORECASE)
_SOCIAL_HANDLE_RES = re.compile(r"\B@[A-Za-z0-9_]{2,30}\b")

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

_MODEL_PREFERENCE: Tuple[str, ...] = ("en_core_web_trf", "en_core_web_sm")

# Optional override: SENTINELGRAPH_NER_MODEL=disabled  -> regex-only
#                     SENTINELGRAPH_NER_MODEL=en_core_web_sm -> force a model
_MODEL_OVERRIDE = "SENTINELGRAPH_NER_MODEL"


def _load_spacy_model() -> Optional[Language]:
    """Try to load the best available spaCy NER model.

    Preference (in order):
      1. ``SENTINELGRAPH_NER_MODEL`` env var (explicit user choice; the
         sentinel value ``"disabled"`` forces the regex-only fallback).
      2. ``en_core_web_trf`` (transformer)
      3. ``en_core_web_sm`` (statistical)
      4. ``None`` → regex-only extraction.
    """
    import os

    override = os.environ.get(_MODEL_OVERRIDE, "").strip().lower()
    if override == "disabled":
        warnings.warn(
            "SENTINELGRAPH_NER_MODEL=disabled set; using regex-only extraction."
        )
        return None

    candidates: List[str] = []
    if override:
        candidates.append(override)
    candidates.extend(_MODEL_PREFERENCE)

    tried: List[str] = []
    for name in candidates:
        tried.append(name)
        try:
            return spacy.load(name)
        except OSError:
            continue
    warnings.warn(
        "No spaCy statistical NER model installed "
        f"(tried {' / '.join(tried)}). Using regex-only extraction."
    )
    return None


def extract_investigative_entities(text: str, document_id: str) -> List[EntitySpan]:
    """Extract investigative entities with source spans using spaCy + regex + gazetteer fusion."""
    if not text.strip():
        return []
    
    entities: List[EntitySpan] = []
    entity_id_counter = 0
    
    nlp = _load_spacy_model()
    
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

# Person names (fused: single token OR <KNOWN_FIRST> <CapitalizedSurname>)
_Known_SURNAMES: Tuple[str, ...] = (
    "kumar", "sharma", "verma", "singh", "patel", "reddy", "iyer",
    "nair", "gowda", "gupta", "jain", "mehta", "shah", "das",
    "yadav", "banerjee", "chatterjee", "mukherjee", "bose", "rao",
    "murthy", "kulkarni", "deshmukh", "joshi", "khan", "kapoor",
    "malhotra", "chopra", "khanna", "saxena", "tiwari", "pandey",
)
# common English words that often follow a first name but are NOT surnames
_NAME_STOPWORDS = frozenset(
    "called calls call calling met meets meeting met with and or but however "
    "reportedly allegedly reportedly visited visited went came said says told "
    "wired transferred sent paid received exchanged discussed seized without "
    "on in at near from to was were is are has have had been being will would "
    "could should must may might did does do done not no never allegedly "
    "supposedly reportedly claimed denied admits confirmed as owned using used "
    "held took taken seen spotted found purchased bought sold gave give taken "
    "collected collected collects collecting drove driving parked parked "
    "walked walking travelled traveled ran run left leaves leaving arrived "
    "reached contacted contacted dialled dialed messaged messaged texted "
    "knows knew asked asking answered replied mentioned mentioned stated "
    "reported claimed admitted denied confirmed accused suspected arrested "
    "detained released questioned interrogated charged indicted convicted "
    "pleaded deposited withdrew withdrew cashed cashed deposited own owns "
    "registered travelled stays stayed lived lives resides works worked "
    "joined operates operated ran runs involved linked connected associated "
    "attended attended appeared appeared departed departed boarded checked "
    "booked rented hired borrowed returned kept stored hid hid buried dumped "
    "discarded destroyed erased deleted recorded documented photographed "
    "filmed watched observed intercepted monitored tracked followed tailed "
    "shadowed surveilled searched raided investigated probed queried searched "
    "contained contains containing contains held carrying carried stored "
    "kept possessed possessing".split()
)

_PAT_CACHE: List[re.Pattern] = []
if not _PAT_CACHE:
    _names = "|".join(re.escape(n) for n in PERSON_GAZETTEER)
    _surnames = "|".join(re.escape(s) for s in _Known_SURNAMES)
    _stop = "|".join(re.escape(w) for w in sorted(_NAME_STOPWORDS, key=len, reverse=True))
    _titles = "|".join(re.escape(t) for t in (
        "inspector", "sub-inspector", "si", "asi", "constable", "head constable",
        "dsp", "sp", "commissioner", "deputy commissioner", "acp", "dgp",
        "dr", "mr", "mrs", "ms", "smt", "shri", "prof", "captain", "colonel",
        "major", "advocate", "judge", "magi",
    ))
    _PAT_CACHE = [
        re.compile(rf"\b({_names})\b", re.IGNORECASE),
        # known first name + (known surname OR capitalized token not a common
        # English verb/preposition/stopword)
        re.compile(
            rf"\b({_names})\s+((?i:{_surnames})|\b(?!{_stop}\b)[A-Z][a-z]{{1,20}})\b",
            re.IGNORECASE,
        ),
        # title + capitalized surname (Indian reporting style: "Inspector
        # Joshi", "Dr Sharma", "SI Kumar")
        re.compile(
            rf"\b(?<![A-Za-z])(?i:{_titles})\s+([A-Z][a-z]+)\b",
            re.IGNORECASE,
        ),
    ]


def _gazetteer_matches(text: str, document_id: str, start_counter: int) -> List[EntitySpan]:
    """Extract entities using gazetteer matching (single + fused name patterns)."""
    entities = []
    counter = start_counter

    for pat in _PAT_CACHE:
        for match in pat.finditer(text):
            counter += 1
            start, end = match.start(), match.end()
            surface = text[start:end]
            entities.append(EntitySpan(
                id=f"ENT-{document_id}-{counter:04d}",
                entity_type="PERSON",
                surface_text=surface,
                normalized_text=surface.lower().strip(),
                span=SourceSpan(start_char=start, end_char=end, text=surface),
                sentence_index=0,
                confidence=0.8,
                extractor="gazetteer",
                document_id=document_id,
                attributes={"gazetteer": "KNOWN_PERSONS"}
            ))
    
    # Locations
    text_lower = text.lower()
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


def _safe_match_span(match: "re.Match[str]") -> Tuple[int, int]:
    """Return the "content-only" span for a regex match.

    Prefers group(1) when it exists and participated in the match (so a
    trigger word like ``account `` / ``fir no.`` is excluded).  Falls back to
    the full match span when group 1 is absent *or* did not participate
    (e.g. the optional alternation in the MONEY pattern, where group 1 may
    be ``(-1, -1)`` → slice becomes ``""``).
    """
    if match.lastindex and match.lastindex >= 1:
        s, e = match.span(1)
        if s >= 0 and e >= s:
            return s, e
    return match.start(), match.end()


def _regex_matches(text: str, document_id: str, start_counter: int) -> List[EntitySpan]:
    """Extract entities using regex patterns for structured data."""
    entities = []
    counter = start_counter
    
    patterns = [
        (_PHONE_RES, "PHONE", "regex_phone", 0.95),
        ((_EMAIL_RE,), "EMAIL", "regex_email", 0.95),
        ((_UPI_RE,), "UPI", "regex_upi", 0.9),
        ((_ACCOUNT_RES,), "ACCOUNT", "regex_account", 0.85),
        ((_POLICE_STATION_RES,), "POLICE_STATION", "regex_police_station", 0.9),
        (_FIR_RES, "FIR", "regex_fir", 0.9),
        ((_ID_RES,), "TRANSACTION", "regex_transaction_ref", 0.9),
        ((_DOCUMENT_RES,), "DOCUMENT", "regex_document", 0.9),
        ((_COURT_RES,), "COURT", "regex_court", 0.9),
        (_DATE_RES, "DATE", "regex_date", 0.9),
        (_TIME_RES, "TIME", "regex_time", 0.9),
        ((_MONEY_RES,), "MONEY", "regex_money", 0.9),
        ((_CRIME_RES,), "CRIME", "regex_crime", 0.85),
        ((_WEAPON_RES,), "WEAPON", "regex_weapon", 0.85),
        ((_IP_RES,), "IP_ADDRESS", "regex_ip", 0.9),
        ((_DOMAIN_RES,), "DOMAIN", "regex_domain", 0.9),
        ((_VEHICLE_BRAND_RE,), "VEHICLE", "regex_vehicle_brand", 0.85),
        ((_VEHICLE_MODEL_RE,), "VEHICLE", "regex_vehicle_model", 0.8),
        ((_VEHICLE_TYPE_RE,), "VEHICLE", "regex_vehicle_type", 0.75),
        ((_UPI_APP_RES,), "UPI", "regex_upi_app", 0.9),
        ((_SOCIAL_HANDLE_RES,), "SOCIAL_HANDLE", "regex_social", 0.85),
        (_PLATE_RES, "VEHICLE_NUMBER", "regex_plate", 0.95),
        ((_TOWER_RE,), "LOCATION", "regex_tower", 0.9),
    ]
    # Banks via known-name gazetteer (exact phrases — avoids "of SBI" slack)
    for bank in _KNOWN_BANKS:
        for match in re.finditer(rf"\b{re.escape(bank)}\b", text, re.IGNORECASE):
            counter += 1
            entities.append(EntitySpan(
                id=f"ENT-{document_id}-{counter:04d}",
                entity_type="BANK",
                surface_text=text[match.start():match.end()],
                normalized_text=bank,
                span=SourceSpan(start_char=match.start(), end_char=match.end(), text=text[match.start():match.end()]),
                sentence_index=0,
                confidence=0.85,
                extractor="regex_bank",
                document_id=document_id,
                attributes={"gazetteer": "KNOWN_BANKS"}
            ))

    for pattern_group, label, extractor, confidence in patterns:
        patterns_list = pattern_group if isinstance(pattern_group, tuple) else [pattern_group]
        for pattern in patterns_list:
            for match in pattern.finditer(text):
                counter += 1
                # Prefer group(1) span when a capture group exists (content
                # only, no trigger word like "account ", "reference ", "case ")
                start, end = _safe_match_span(match)
                # For MONEY, extract amount/currency
                attrs = {}
                if label == "MONEY" and match.groupdict():
                    gd = match.groupdict()
                    attrs = {
                        "amount": gd.get("amt") or gd.get("amt2") or "",
                        "currency": gd.get("cur") or "",
                    }
                
                # Skip vehicle matches with stopwords
                if label == "VEHICLE" and _contains_stopword(text[start:end]):
                    continue
                # Skip a bare vehicle *type* (sedan / truck / motorcycle)
                # directly preceded by a brand match — the brand ("Audi
                # sedan", "Tata truck") already produced a VEHICLE entity and
                # the type alone would double-count.
                if extractor == "regex_vehicle_type":
                    prev = text[:start].rstrip()
                    if re.search(rf"\b(?:{_VEHICLE_BRANDS})\s*$", prev, re.IGNORECASE):
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
    """Resolve overlapping entity spans.

    Priority: structured regex > gazetteer > statistical.  Within the same
    extractor tier, the *longest* span wins (a full "Ramesh Kumar" name beats
    the bare "Ramesh" first-name match).
    """
    if not entities:
        return []

    # Priority: context-qualified regex > bare regex/gazetteer > spacy. Lower number
    # wins; equal numbers are broken by longest-span-first then list order.
    priority = {
        # context-qualified structured extractions (win over bare numbers/names)
        "regex_account": 0, "regex_fir": 0, "regex_transaction_ref": 0,
        "regex_police_station": 0, "regex_bank": 0, "regex_plate": 0,
        "regex_upi_app": 0, "regex_upi": 0, "regex_email": 0,
        "regex_document": 0,
        # bare numeric/pattern extractions
        "regex_phone": 1, "regex_date": 1, "regex_time": 1, "regex_money": 1,
        "regex_crime": 1, "regex_weapon": 1, "regex_ip": 1, "regex_domain": 1,
        "regex_vehicle_brand": 1, "regex_vehicle_model": 1,
        "regex_vehicle_type": 1, "regex_tower": 1, "regex_court": 1,
        "regex_social": 1,
        # gazetteer / statistical
        "gazetteer": 2, "spacy_ner": 3,
    }

    # Sort by (start, priority asc, LENGTH DESC) so that when two same-priority
    # spans overlap, the longer one is processed first and wins.
    entities.sort(key=lambda e: (e.span.start_char,
                                 priority.get(e.extractor, 99),
                                 -(e.span.end_char - e.span.start_char)))

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
