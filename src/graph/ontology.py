"""Canonical graph relation ontology and legacy aliases."""

RELATION_ALIASES = {
    "TRANSFERRED_FUNDS": "TRANSFERRED_TO",
    "TRANSFER": "TRANSFERRED_TO",
    "TRANSFERRED": "TRANSFERRED_TO",
    "LOCATED_AT": "LOCATED_IN",
    "ATTENDED_MEETING_AT": "ATTENDED_MEETING_AT",
    "CALLED": "CALLED",
    "MET": "MET",
    "MEMBER_OF": "MEMBER_OF",
    "LEADS": "LEADS",
    "USES_ACCOUNT": "USES_ACCOUNT",
}

CANONICAL_RELATIONS = frozenset(RELATION_ALIASES.values())


def normalize_relation(relation: str) -> str:
    raw = str(relation or "").strip().upper()
    return RELATION_ALIASES.get(raw, raw or "RELATED_TO")
