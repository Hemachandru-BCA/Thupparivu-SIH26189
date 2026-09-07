"""
relation_extractor.py
---------------------
Converts entity-annotated SpaCy docs into knowledge-graph triplets.

Relations
---------
TRANSFERRED_FUNDS   "Ramesh transferred 5000 to Akash"
                    passive : "5,000 was transferred to Akash by Ramesh"
                    received: "Akash received 5000 from Ramesh"
CALLED              "Priya called Sunil from TWR-012 for 300 seconds"
                    ("Akash received a call from Ramesh")
MET                 "Deepak met Farhan at the Warehouse District"
MEMBER_OF / LEADS   "Vikram is a member of the Cobra Gang"
OWNS_VEHICLE        "Vikram drives a black Toyota Camry"
HAS_PHONE           "Vikram can be reached at +91-98765-43210"
LOCATED_AT          "Sunil lives in Mumbai"
ASSOCIATED_WITH     low-confidence fallback when >= 2 PERSONs co-occur

Every triplet carries provenance (record_id, evidence sentence, sentence
index) and a confidence score (1.0 explicit pattern, 0.4 fallback).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from spacy.tokens import Doc, Span, Token

__all__ = ["Triplet", "RelationExtractor", "parse_amount", "detect_currency",
           "detect_channel", "parse_duration", "detect_timestamp"]

# --------------------------------------------------------------------------- #
# Triplet model
# --------------------------------------------------------------------------- #


@dataclass
class Triplet:
    source: str
    source_type: str
    relation: str
    target: str
    target_type: str
    record_id: str = ""
    evidence: str = ""
    sentence_index: int = -1
    confidence: float = 1.0
    amount: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "source": self.source,
            "source_type": self.source_type,
            "relation": self.relation,
            "target": self.target,
            "target_type": self.target_type,
            "record_id": self.record_id,
            "evidence": self.evidence,
            "sentence_index": self.sentence_index,
            "confidence": self.confidence,
        }
        if self.amount is not None:
            payload["amount"] = self.amount
        if self.attributes:
            payload["attributes"] = self.attributes
        return payload


# --------------------------------------------------------------------------- #
# Pure helpers (unit-testable without spaCy)
# --------------------------------------------------------------------------- #

_AMOUNT_RE = re.compile(
    r"(?<![\w-])"                                   # not part of a longer token
    r"(?:₹|\$|€|£|rs\.?|inr|usd|eur|gbp)?\s*"
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
    r"\s*(k|m|cr|crore|crores|lakh|lakhs|lac)?"
    r"(?![\w-])",                                   # rejects ISO dates like 2025-02-11
    re.IGNORECASE,
)

_MULTIPLIERS = {
    "k": 1_000, "m": 1_000_000,
    "cr": 10_000_000, "crore": 10_000_000, "crores": 10_000_000,
    "lakh": 100_000, "lakhs": 100_000, "lac": 100_000,
}

_CURRENCY_SYMBOLS = (("₹", "INR"), ("$", "USD"), ("€", "EUR"), ("£", "GBP"))
_CURRENCY_WORDS = (
    (("rupees", "rupee", "inr"), "INR"),
    (("dollars", "dollar", "usd"), "USD"),
    (("euros", "euro", "eur"), "EUR"),
    (("pounds", "pound", "gbp"), "GBP"),
)

_CHANNEL_RE = re.compile(
    r"\b(?:via|using|through|over|in)\s+(?:an?\s+|the\s+)?"
    r"(bank\s+transfer|wire\s+transfer|wire|cash|crypto(?:currency)?|bitcoin|"
    r"mobile\s+wallet|upi|hawala)\b",
    re.IGNORECASE,
)

_DURATION_RE = re.compile(
    r"\b(?:for|lasting)\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)

_ACCOUNT_RE = re.compile(r"\b(?:account|acct)\s+([A-Z0-9][A-Z0-9_-]{2,})\b", re.IGNORECASE)

_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?Z?)?\b"
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\b"
)

_MONEY_CONTEXT_RE = re.compile(
    r"\b(?:money|funds|cash|payment|amount|sum|fee|rupees?|dollars?|euros?|paid)\b",
    re.IGNORECASE,
)


def parse_amount(text: str) -> Optional[float]:
    """'5000' -> 5000, '$5k' -> 5000, '2.5 lakh' -> 250000, ISO dates -> None."""
    if not text:
        return None
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    multiplier = (match.group(2) or "").lower()
    value *= _MULTIPLIERS.get(multiplier, 1)
    value = round(value, 2)
    return int(value) if value.is_integer() else value


def detect_currency(text: str) -> Optional[str]:
    for symbol, code in _CURRENCY_SYMBOLS:
        if symbol in text:
            return code
    lowered = text.lower()
    for words, code in _CURRENCY_WORDS:
        for word in words:
            if re.search(rf"\b{word}\b", lowered):
                return code
    return None


def detect_channel(text: str) -> Optional[str]:
    match = _CHANNEL_RE.search(text)
    return match.group(1).lower() if match else None


def parse_duration(text: str) -> Optional[int]:
    """Duration in seconds: 'for 5 minutes' -> 300."""
    match = _DURATION_RE.search(text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("sec"):
        return int(value)
    if unit.startswith("min"):
        return int(value * 60)
    return int(value * 3600)          # hours / hrs


def detect_timestamp(text: str) -> Optional[str]:
    match = _TIMESTAMP_RE.search(text)
    return match.group(0) if match else None


# --------------------------------------------------------------------------- #
# Triggers and cues
# --------------------------------------------------------------------------- #

_TRANSFER_TRIGGERS: Set[str] = {
    "transfer", "transferred", "transfers", "transferring",
    "send", "sent", "sends", "sending",
    "wire", "wired", "wiring",
    "pay", "paid", "pays", "paying",
    "remit", "remitted", "remittance",
    "give", "gave", "gives", "given",
    "donate", "donated",
}
_RECEIVE_TRIGGERS: Set[str] = {
    "receive", "received", "receives", "receiving",
    "collect", "collected", "collects",
}
_CALL_TRIGGERS: Set[str] = {
    "call", "called", "calls", "calling",
    "phone", "phoned", "phones",
    "ring", "rang", "rung",
    "dial", "dialed", "dialled", "dials",
    "contact", "contacted",
}
_MEET_TRIGGERS: Set[str] = {
    "meet", "meets", "met", "meeting", "gathered", "assemble", "assembled",
    "rendezvous", "conferred",
}

_MEMBER_CUE_RE = re.compile(
    r"\b(?:member\s+of|part\s+of|belongs\s+to|works?\s+for|worked\s+for|"
    r"affiliated\s+with|associated\s+with|boss\s+of|head(?:ed|s)?\s+of|"
    r"leader\s+of|leads|runs)\b",
    re.IGNORECASE,
)
_LEADER_CUE_RE = re.compile(r"\b(?:boss|head|heads|headed|leader|leads|runs|kingpin)\b",
                            re.IGNORECASE)
_LED_BY_RE = re.compile(r"\b(?:led\s+by|run\s+by|headed\s+by)\b", re.IGNORECASE)
_VEHICLE_CUE_RE = re.compile(
    r"\b(?:drives?|drove|driving|owns?|owned|rides?|rode|riding|"
    r"seen\s+(?:in|driving|riding)|spotted\s+(?:in|driving|riding)|"
    r"travel(?:l)?ed\s+in|arrived\s+in|left\s+in|registered\s+to)\b",
    re.IGNORECASE,
)
_LOCATED_CUE_RE = re.compile(
    r"\b(?:lives?|lived|resides?|resided|staying\s+(?:at|in)|based\s+in|"
    r"operates?\s+(?:from|in)|located\s+(?:at|in))\b",
    re.IGNORECASE,
)
_RECEIVED_CALL_RE = re.compile(r"\b(?:received|got)\s+(?:an?\s+)?call\s+from\b",
                               re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Small span helpers (all offsets are doc-level)
# --------------------------------------------------------------------------- #

def _lemma(token: Token) -> str:
    lemma = token.lemma_ or ""
    return lemma.lower() if lemma else token.lower_


def _trigger_tokens(sent: Span, triggers: Set[str]) -> List[Token]:
    return [t for t in sent if t.lower_ in triggers or _lemma(t) in triggers]


def _ents(sent: Span, label: str) -> List[Span]:
    return [e for e in sent.ents if e.label_ == label]


def _nearest_before(ents: Sequence[Span], char: int) -> Optional[Span]:
    before = [e for e in ents if e.end_char <= char]
    return before[-1] if before else None


def _nearest_after(ents: Sequence[Span], char: int) -> Optional[Span]:
    after = [e for e in ents if e.start_char >= char]
    return after[0] if after else None


def _findall_in_sent(sent: Span, pattern: re.Pattern) -> List[Tuple[re.Match, int, int]]:
    """Regex matches inside the sentence, returned with doc-level offsets."""
    return [
        (m, sent.start_char + m.start(), sent.start_char + m.end())
        for m in pattern.finditer(sent.text)
    ]


_MASK_LABELS = {"PERSON", "ORGANIZATION", "LOCATION", "VEHICLE", "PHONE", "DATE", "TIME"}


def _amount_search_text(sent: Span) -> str:
    """Blank out entity spans so phone/plate digits never look like amounts."""
    chars = list(sent.text)
    for ent in sent.ents:
        if ent.label_ in _MASK_LABELS:
            start = max(0, ent.start_char - sent.start_char)
            end = min(len(chars), ent.end_char - sent.start_char)
            for i in range(start, end):
                chars[i] = " "
    return "".join(chars)


# --------------------------------------------------------------------------- #
# Extractor
# --------------------------------------------------------------------------- #


class RelationExtractor:
    """
    Sentence-scoped, rule-based relation extraction over an annotated Doc.

    infer_co_occurrence:
        When True, sentences with >= 2 PERSONs and no explicit relation emit
        a low-confidence ASSOCIATED_WITH edge (useful for link analysis on
        noisy intel text).
    """

    def __init__(self, infer_co_occurrence: bool = True):
        self.infer_co_occurrence = infer_co_occurrence

    # -- public API -------------------------------------------------------- #

    def extract(self, doc: Doc, record_id: str = "") -> List[Triplet]:
        triplets: List[Triplet] = []
        for sent_idx, sent in enumerate(doc.sents):
            if not sent.text.strip():
                continue
            triplets.extend(self._extract_sentence(sent, sent_idx, record_id))
        return triplets

    # -- internals --------------------------------------------------------- #

    def _extract_sentence(self, sent: Span, sent_idx: int, record_id: str) -> List[Triplet]:
        text = sent.text
        triplets: List[Triplet] = []

        triplets += self._extract_transfers(sent, sent_idx, record_id)
        call_triplets = self._extract_calls(sent, sent_idx, record_id)
        triplets += call_triplets
        triplets += self._extract_meetings(sent, sent_idx, record_id)
        triplets += self._extract_memberships(sent, sent_idx, record_id)
        triplets += self._extract_vehicles(sent, sent_idx, record_id)

        call_context = (
            bool(call_triplets)
            or bool(_trigger_tokens(sent, _CALL_TRIGGERS))
            or bool(_RECEIVED_CALL_RE.search(text))
        )
        triplets += self._extract_phones(sent, sent_idx, record_id, call_context)
        triplets += self._extract_locations(sent, sent_idx, record_id)

        if self.infer_co_occurrence and not triplets:
            persons = _ents(sent, "PERSON")
            for left, right in zip(persons, persons[1:]):
                triplets.append(
                    Triplet(
                        source=left.text.strip(), source_type="PERSON",
                        relation="ASSOCIATED_WITH",
                        target=right.text.strip(), target_type="PERSON",
                        record_id=record_id, evidence=text.strip(),
                        sentence_index=sent_idx, confidence=0.4,
                        attributes={"method": "co_occurrence"},
                    )
                )
        return triplets

    def _make(self, source: Span, relation: str, target: Span, sent: Span,
              sent_idx: int, record_id: str, confidence: float = 1.0,
              amount: Optional[float] = None,
              attributes: Optional[Dict[str, Any]] = None) -> Triplet:
        return Triplet(
            source=source.text.strip(), source_type=source.label_,
            relation=relation,
            target=target.text.strip(), target_type=target.label_,
            record_id=record_id, evidence=sent.text.strip(),
            sentence_index=sent_idx, confidence=confidence,
            amount=amount, attributes=attributes or {},
        )

    # -- TRANSFERRED_FUNDS -------------------------------------------------- #

    def _extract_transfers(self, sent: Span, sent_idx: int, record_id: str) -> List[Triplet]:
        persons = _ents(sent, "PERSON")
        orgs = _ents(sent, "ORGANIZATION")
        candidate_targets = sorted(persons + orgs, key=lambda e: e.start_char)

        verbs = _trigger_tokens(sent, _TRANSFER_TRIGGERS) + \
                _trigger_tokens(sent, _RECEIVE_TRIGGERS)
        if not verbs:
            return []

        amount = self._sentence_amount(sent)
        if amount is None and not _MONEY_CONTEXT_RE.search(sent.text):
            return []        # "gave a speech" / "sent the documents" -> not a transaction

        attributes: Dict[str, Any] = {}
        currency = detect_currency(sent.text)
        if currency:
            attributes["currency"] = currency
        channel = detect_channel(sent.text)
        if channel:
            attributes["channel"] = channel
        timestamp = detect_timestamp(sent.text)
        if timestamp:
            attributes["timestamp"] = timestamp
        account_match = _ACCOUNT_RE.search(sent.text)
        if account_match:
            attributes["account_id"] = account_match.group(1).upper()

        triplets: List[Triplet] = []
        seen: Set[Tuple[str, str, Optional[float]]] = set()

        for verb in verbs:
            verb_end = verb.idx + len(verb.text)
            is_receive = verb.lower_ in _RECEIVE_TRIGGERS or _lemma(verb) in _RECEIVE_TRIGGERS
            passive = re.search(
                rf"\b(?:was|were|is|are|been|being)\s+{re.escape(verb.lower_)}\b",
                sent.text, re.IGNORECASE,
            )

            source = target = None

            if passive and not is_receive:
                after = [p for p in persons if p.start_char >= verb_end]
                if len(after) >= 2:          # "...was transferred to Akash by Ramesh"
                    target, source = after[0], after[1]
                elif len(after) == 1:
                    target = after[0]
                    source = _nearest_before(persons, verb.idx)
            elif is_receive:
                target = _nearest_before(persons, verb.idx)          # receiver
                anchor = None
                for token in sent:
                    if token.i > verb.i and token.lower_ in ("from", "by"):
                        anchor = token.idx + len(token.text)
                        break
                source = (_nearest_after(persons, anchor) if anchor is not None
                          else _nearest_after(persons, verb_end))    # sender
            else:
                source = _nearest_before(persons, verb.idx)
                to_anchor = None
                for token in sent:
                    if token.i > verb.i and token.lower_ == "to":
                        to_anchor = token.idx + len(token.text)
                        break
                if to_anchor is not None:
                    target = _nearest_after(candidate_targets, to_anchor)
                if target is None:                                    # "paid Akash 5000"
                    target = _nearest_after(candidate_targets, verb_end)
                if source is not None and target is not None and target.text == source.text:
                    target = None

            if source is None or target is None:
                continue
            key = (source.text.strip(), target.text.strip(), amount)
            if key in seen:
                continue
            seen.add(key)
            triplets.append(
                self._make(source, "TRANSFERRED_FUNDS", target, sent, sent_idx,
                           record_id, amount=amount, attributes=dict(attributes))
            )
            if attributes.get("account_id"):
                account_name = attributes["account_id"]
                triplets.append(Triplet(
                    source=source.text.strip(), source_type=source.label_,
                    relation="USES_ACCOUNT", target=account_name, target_type="ACCOUNT",
                    record_id=record_id, evidence=sent.text.strip(), sentence_index=sent_idx,
                    confidence=1.0, attributes={"account_id": account_name, "timestamp": attributes.get("timestamp")}
                ))
                if target.text.strip() != source.text.strip():
                    triplets.append(Triplet(
                        source=target.text.strip(), source_type=target.label_,
                        relation="USES_ACCOUNT", target=account_name, target_type="ACCOUNT",
                        record_id=record_id, evidence=sent.text.strip(), sentence_index=sent_idx,
                        confidence=1.0, attributes={"account_id": account_name, "timestamp": attributes.get("timestamp")}
                    ))
        return triplets

    @staticmethod
    def _sentence_amount(sent: Span) -> Optional[float]:
        for entity in (e for e in sent.ents if e.label_ in ("MONEY", "QUANTITY")):
            amount = parse_amount(entity.text)
            if amount is not None:
                return amount
        return parse_amount(_amount_search_text(sent))

    # -- CALLED -------------------------------------------------------------- #

    def _extract_calls(self, sent: Span, sent_idx: int, record_id: str) -> List[Triplet]:
        text = sent.text
        persons = _ents(sent, "PERSON")

        attributes: Dict[str, Any] = {}
        locations = _ents(sent, "LOCATION")
        phones = _ents(sent, "PHONE")
        if locations:
            attributes["location"] = locations[0].text.strip()
        if phones:
            attributes["phone"] = phones[0].text.strip()
        duration = parse_duration(text)
        if duration is not None:
            attributes["duration_sec"] = duration
        timestamp = detect_timestamp(text)
        if timestamp:
            attributes["timestamp"] = timestamp

        triplets: List[Triplet] = []
        received = _RECEIVED_CALL_RE.search(text)

        if received:
            # "Akash received a call from Ramesh."  ->  Ramesh called Akash
            call_start = sent.start_char + received.start()
            from_end = sent.start_char + received.end()
            target = _nearest_before(persons, call_start)
            source = _nearest_after(persons, from_end)
            if source and target and source.text != target.text:
                triplets.append(
                    self._make(source, "CALLED", target, sent, sent_idx,
                               record_id, attributes=dict(attributes)))
            return triplets

        for verb in _trigger_tokens(sent, _CALL_TRIGGERS):
            source = _nearest_before(persons, verb.idx)
            target = _nearest_after(persons, verb.idx + len(verb.text))
            if source and target and source.text != target.text:
                triplets.append(
                    self._make(source, "CALLED", target, sent, sent_idx,
                               record_id, attributes=dict(attributes)))
        return triplets

    # -- MET ----------------------------------------------------------------- #

    def _extract_meetings(self, sent: Span, sent_idx: int, record_id: str) -> List[Triplet]:
        text = sent.text
        persons = _ents(sent, "PERSON")
        triggered = bool(_trigger_tokens(sent, _MEET_TRIGGERS)) or \
                    bool(re.search(r"\bmeeting\b", text, re.IGNORECASE))
        if not triggered:
            return []

        attributes: Dict[str, Any] = {}
        locations = _ents(sent, "LOCATION")
        if locations:
            attributes["location"] = locations[0].text.strip()
        timestamp = detect_timestamp(text)
        if timestamp:
            attributes["timestamp"] = timestamp

        triplets: List[Triplet] = []
        if len(persons) >= 2:
            for i in range(len(persons)):
                for j in range(i + 1, len(persons)):
                    triplets.append(
                        self._make(persons[i], "MET", persons[j], sent, sent_idx,
                                   record_id, attributes=dict(attributes)))
        elif len(persons) == 1 and locations:
            triplets.append(
                self._make(persons[0], "ATTENDED_MEETING_AT", locations[0],
                           sent, sent_idx, record_id, attributes=dict(attributes)))
        return triplets

    # -- MEMBER_OF / LEADS --------------------------------------------------- #

    def _extract_memberships(self, sent: Span, sent_idx: int, record_id: str) -> List[Triplet]:
        persons = _ents(sent, "PERSON")
        orgs = _ents(sent, "ORGANIZATION")
        triplets: List[Triplet] = []

        for match, doc_start, doc_end in _findall_in_sent(sent, _MEMBER_CUE_RE):
            person = _nearest_before(persons, doc_start)
            org = _nearest_after(orgs, doc_end)
            if person and org:
                relation = "LEADS" if _LEADER_CUE_RE.search(match.group(0)) else "MEMBER_OF"
                triplets.append(self._make(person, relation, org, sent, sent_idx, record_id))

        for _match, doc_start, doc_end in _findall_in_sent(sent, _LED_BY_RE):
            org = _nearest_before(orgs, doc_start)
            person = _nearest_after(persons, doc_end)
            if org and person:
                triplets.append(self._make(person, "LEADS", org, sent, sent_idx, record_id))
        return triplets

    # -- OWNS_VEHICLE -------------------------------------------------------- #

    def _extract_vehicles(self, sent: Span, sent_idx: int, record_id: str) -> List[Triplet]:
        persons = _ents(sent, "PERSON")
        confidence = 1.0 if _VEHICLE_CUE_RE.search(sent.text) else 0.6
        triplets: List[Triplet] = []
        for vehicle in _ents(sent, "VEHICLE"):
            person = _nearest_before(persons, vehicle.start_char)
            if person:
                triplets.append(
                    self._make(person, "OWNS_VEHICLE", vehicle, sent, sent_idx,
                               record_id, confidence=confidence))
        return triplets

    # -- HAS_PHONE ------------------------------------------------------------- #

    def _extract_phones(self, sent: Span, sent_idx: int, record_id: str,
                        in_call_sentence: bool) -> List[Triplet]:
        if in_call_sentence:
            return []            # phone already consumed as an attribute of CALLED
        persons = _ents(sent, "PERSON")
        triplets: List[Triplet] = []
        for phone in _ents(sent, "PHONE"):
            person = _nearest_before(persons, phone.start_char)
            if person:
                triplets.append(self._make(person, "HAS_PHONE", phone, sent, sent_idx,
                                           record_id))
        return triplets

    # -- LOCATED_AT ------------------------------------------------------------ #

    def _extract_locations(self, sent: Span, sent_idx: int, record_id: str) -> List[Triplet]:
        persons = _ents(sent, "PERSON")
        locations = _ents(sent, "LOCATION")
        triplets: List[Triplet] = []
        for _match, doc_start, doc_end in _findall_in_sent(sent, _LOCATED_CUE_RE):
            person = _nearest_before(persons, doc_start)
            location = _nearest_after(locations, doc_end)
            if person and location:
                triplets.append(self._make(person, "LOCATED_AT", location, sent,
                                           sent_idx, record_id))
        return triplets
