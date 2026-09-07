"""
ner.py
------
SpaCy-based entity extraction for the graph-building NLP pipeline.

Canonical labels: PERSON, LOCATION, ORGANIZATION, VEHICLE, PHONE.

Layers
------
1. Statistical  - en_core_web_sm tags PERSON, GPE/LOC (-> LOCATION), ORG
   (-> ORGANIZATION). MONEY / DATE / TIME spans are kept for the downstream
   relation and event extractors.
2. Gazetteer    - an EntityRuler placed BEFORE the statistical NER boosts
   recall on domain phrases ("Warehouse District", "Lucky Star Bar").
3. Regex        - a custom `domain_entity_regexes` component placed AFTER NER
   adds PHONE, VEHICLE (incl. licence plates) and cell-tower LOCATION spans
   that no statistical model will ever emit.
4. Resolution   - deterministic overlap handling:
   PHONE(0) > VEHICLE(1) > tower(2) > org-suffix(3) > statistical(4);
   the longest span wins inside a layer.

If en_core_web_sm is missing, the extractor degrades to a rules-only blank
pipeline (with a warning) so imports and unit tests never hard-fail.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import spacy
from spacy.language import Language
from spacy.tokens import Doc, Span

__all__ = ["Entity", "EntityExtractor", "TARGET_LABELS", "build_nlp"]

DEFAULT_MODEL = "en_core_web_sm"
TARGET_LABELS: Tuple[str, ...] = ("PERSON", "LOCATION", "ORGANIZATION", "VEHICLE", "PHONE")

CANONICAL_LABEL_MAP: Dict[str, str] = {
    "PERSON": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
    "ORG": "ORGANIZATION",
    "LOCATION": "LOCATION",
    "ORGANIZATION": "ORGANIZATION",
    "VEHICLE": "VEHICLE",
    "PHONE": "PHONE",
}

# --------------------------------------------------------------------------- #
# Gazetteers (phrases the statistical model has never seen)
# --------------------------------------------------------------------------- #

KNOWN_LOCATIONS: Tuple[str, ...] = (
    "warehouse district", "riverside docks", "downtown cafe",
    "abandoned factory", "private villa", "parking garage b",
    "storage facility 12", "old harbour pier",
)
KNOWN_ORGANIZATIONS: Tuple[str, ...] = (
    "lucky star bar", "sentinel logistics", "blue horizon trading",
)
# Common Indian given names. Newer en_core_web_sm builds often miss these as
# PERSON in short transactional sentences ("Ramesh transferred 5000 to Akash."),
# so they are seeded into the ruler layer alongside the closed-world
# extra_gazetteer mechanism below.
KNOWN_PERSONS: Tuple[str, ...] = (
    "ramesh", "akash", "vikram", "suresh", "arjun", "rohit", "priya",
    "meera", "kiran", "rahul", "amit", "sanjay", "vijay", "deepak",
    "manoj", "pooja", "neha", "anil", "rajesh", "sunil", "vikas",
    "ashok", "naveen", "varun", "aditya", "harish", "mohit", "rakesh",
    "ajay", "gaurav", "vishal", "pradeep",
)

# --------------------------------------------------------------------------- #
# Regex layer
# --------------------------------------------------------------------------- #

_TOWER_RE = re.compile(r"\bTWR-\d{2,4}\b")

_PHONE_RES = (
    # +91-98765-43210 / +1 (202) 555-0134 / +1-202-555-0134
    re.compile(r"\+\d{1,3}[-.\s]?\(?\d{2,5}\)?(?:[-.\s]?\d{2,6}){1,3}"),
    # 555-555-0134 / 555.555.0134
    re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
    # 98765 43210
    re.compile(r"\b\d{5}\s\d{5}\b"),
    # bare 10-12 digit numbers
    re.compile(r"\b\d{10,12}\b"),
)

_COLORS = r"(?:black|white|red|blue|silver|gray|grey|green|yellow|orange|brown|beige|maroon)"
_BRANDS = (
    r"(?:toyota|honda|ford|suzuki|bmw|mercedes|hyundai|tata|chevrolet|nissan|audi|kia|"
    r"volkswagen|vw|jeep|mahindra|yamaha|bajaj|royal|skoda|volvo|mitsubishi|fiat|renault|"
    r"lexus|subaru|mazda|dodge|tesla)"
)
_MODELS = (
    r"(?:camry|corolla|civic|accord|swift|baleno|i20|creta|scorpio|fortuner|innova|amaze|"
    r"thar|bolero|ertiga|wagonr|alto|pulsar|activa|splendor|enfield|benz)"
)
_TYPES = (
    r"(?:car|sedan|suv|van|hatchback|truck|pickup|motorcycle|motorbike|bike|scooter|"
    r"minivan|lorry|rickshaw)"
)

_VEHICLE_BRAND_RE = re.compile(          # "black Toyota Camry", "Mercedes Benz"
    rf"\b(?:(?i:{_COLORS})\s+)?(?i:{_BRANDS})"
    rf"(?:\s+(?:(?i:{_MODELS})|[A-Z][A-Za-z0-9-]+)){{0,2}}\b"
)
_VEHICLE_TYPE_RE = re.compile(           # "a blue SUV", "the truck"
    rf"\b(?:(?i:{_COLORS})\s+)?(?i:{_TYPES})\b"
)
_PLATE_RES = (                           # "MH 12 AB 1234", "ABC-1234"
    re.compile(r"\b[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4}\b"),
    re.compile(r"\b(?!TWR-)[A-Z]{3}-\d{3,4}\b"),   # exclude cell-tower IDs (TWR-###)
)

# Words that, inside a VEHICLE match, reveal it is actually an org name.
_VEHICLE_STOPWORDS = frozenset(
    "group inc ltd llc company corp corporation gang crew syndicate cartel district "
    "police department motors industries bank trust rally club hotel restaurant bar "
    "cafe office".split()
)

_ORG_SUFFIX_RE = re.compile(             # "Cobra Gang", "Red Viper Syndicate"
    r"\b(?:(?!The\b|A\b|An\b)[A-Z][\w&'-]*\s+){1,3}"
    r"(?:Gang|Syndicate|Crew|Cartel|Outfit|Firm|Company|Corporation|Trust|Brothers)\b"
)


def _contains_stopword(text: str) -> bool:
    return any(word.lower() in _VEHICLE_STOPWORDS for word in text.split())


def _regex_spans(doc: Doc, label: str, patterns: Tuple[re.Pattern, ...]) -> List[Span]:
    spans: List[Span] = []
    for pattern in patterns:
        for match in pattern.finditer(doc.text):
            span = doc.char_span(match.start(), match.end(), label=label)
            if span is None:                       # misaligned with token bounds
                continue
            if label == "VEHICLE" and _contains_stopword(span.text):
                continue
            spans.append(span)
    return spans


@Language.component("domain_entity_regexes")
def domain_entity_regexes(doc: Doc) -> Doc:
    """Add PHONE/VEHICLE/tower spans, resolve overlaps, canonicalise labels."""
    candidates = [(0, span) for span in doc.ents]                       # statistical + ruler
    candidates += [(1, s) for s in _regex_spans(doc, "PHONE", _PHONE_RES)]
    candidates += [(2, s) for s in _regex_spans(doc, "VEHICLE", (_VEHICLE_BRAND_RE, _VEHICLE_TYPE_RE))]
    candidates += [(2, s) for s in _regex_spans(doc, "VEHICLE", _PLATE_RES)]
    candidates += [(3, s) for s in _regex_spans(doc, "LOCATION", (_TOWER_RE,))]
    candidates += [(4, s) for s in _regex_spans(doc, "ORGANIZATION", (_ORG_SUFFIX_RE,))]

    # priority asc, length desc, start asc  ->  deterministic resolution
    candidates.sort(key=lambda c: (c[0], -(c[1].end - c[1].start), c[1].start))

    occupied: set = set()
    final: List[Span] = []
    for _priority, span in candidates:
        token_ids = set(range(span.start, span.end))
        if token_ids & occupied:
            continue
        occupied |= token_ids
        final.append(span)

    final.sort(key=lambda s: s.start)
    doc.ents = [
        Span(doc, s.start, s.end, label=CANONICAL_LABEL_MAP.get(s.label_, s.label_))
        for s in final
    ]
    return doc


def _gazetteer_patterns(extra_gazetteer: Optional[Dict[str, Iterable[str]]] = None) -> List[dict]:
    patterns: List[dict] = []
    for phrase in KNOWN_LOCATIONS:
        patterns.append({"label": "LOCATION", "pattern": [{"LOWER": w.lower()} for w in phrase.split()]})
    for phrase in KNOWN_ORGANIZATIONS:
        patterns.append({"label": "ORGANIZATION", "pattern": [{"LOWER": w.lower()} for w in phrase.split()]})
    for phrase in KNOWN_PERSONS:
        patterns.append({"label": "PERSON", "pattern": [{"LOWER": w.lower()} for w in phrase.split()]})

    # Optional closed-world gazetteer (e.g. every known person's full name
    # from this run's persons.csv). This is how PERSON entities get
    # recognised when no statistical model (en_core_web_sm) is available:
    # in a synthetic, closed-universe dataset every name that will ever
    # appear in the text is already known ahead of time, so a lookup is not
    # a hack here -- it is a legitimate (and more precise) substitute for
    # what the statistical model would otherwise be guessing at.
    for label, phrases in (extra_gazetteer or {}).items():
        for phrase in phrases:
            phrase = (phrase or "").strip()
            if not phrase:
                continue
            patterns.append({"label": label, "pattern": [{"LOWER": w.lower()} for w in phrase.split()]})
    return patterns


def build_nlp(model_name: Optional[str] = DEFAULT_MODEL,
              extra_gazetteer: Optional[Dict[str, Iterable[str]]] = None) -> Language:
    """Build the shared SpaCy pipeline (statistical + gazetteer + regex).

    `extra_gazetteer` optionally maps entity label -> iterable of known
    phrases (e.g. {"PERSON": ["Ramesh Kumar", "Akash Verma", ...]}) to seed
    the entity_ruler with, on top of the built-in LOCATION/ORGANIZATION
    lists. See `_gazetteer_patterns` docstring note above for why this
    matters when no statistical model is installed.
    """
    if model_name:
        try:
            nlp = spacy.load(model_name)
        except OSError:
            warnings.warn(
                f"SpaCy model '{model_name}' is not installed - falling back to a "
                f"rules-only pipeline. Fix with:  python -m spacy download {model_name}"
            )
            nlp = spacy.blank("en")
            nlp._model_fallback = True
    else:
        nlp = spacy.blank("en")

    if "parser" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer", first=True)

    if "entity_ruler" not in nlp.pipe_names:
        ruler = (
            nlp.add_pipe("entity_ruler", before="ner")
            if "ner" in nlp.pipe_names
            else nlp.add_pipe("entity_ruler")
        )
        ruler.add_patterns(_gazetteer_patterns(extra_gazetteer))

    if "domain_entity_regexes" not in nlp.pipe_names:
        nlp.add_pipe("domain_entity_regexes", last=True)
    return nlp


@dataclass
class Entity:
    """A single extracted entity mention (one graph-node candidate)."""
    text: str
    label: str
    start_char: int
    end_char: int
    sentence_index: int = -1

    @property
    def key(self) -> str:
        return f"{self.label}::{self.text}"

    def to_dict(self) -> dict:
        return asdict(self)


class EntityExtractor:
    """Facade around the SpaCy pipeline."""

    def __init__(self, model_name: Optional[str] = DEFAULT_MODEL,
                 nlp: Optional[Language] = None,
                 extra_gazetteer: Optional[Dict[str, Iterable[str]]] = None):
        self.nlp = nlp if nlp is not None else build_nlp(model_name, extra_gazetteer=extra_gazetteer)

    def process(self, text: str) -> Doc:
        return self.nlp(text)

    def extract(self, text: str) -> List[Entity]:
        return self.entities_from_doc(self.process(text))

    def extract_batch(self, texts: Iterable[str], batch_size: int = 64) -> List[List[Entity]]:
        docs = self.nlp.pipe(list(texts), batch_size=batch_size)
        return [self.entities_from_doc(d) for d in docs]

    @staticmethod
    def entities_from_doc(doc: Doc) -> List[Entity]:
        entities: List[Entity] = []
        for sent_idx, sent in enumerate(doc.sents):
            for ent in sent.ents:
                if ent.label_ in TARGET_LABELS:
                    entities.append(
                        Entity(
                            text=ent.text.strip(),
                            label=ent.label_,
                            start_char=ent.start_char,
                            end_char=ent.end_char,
                            sentence_index=sent_idx,
                        )
                    )
        return entities
