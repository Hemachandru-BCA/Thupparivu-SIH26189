"""
guid_generator.py
-----------------
Stable GUID generation for resolved entities and records.

Entity GUIDs must be *deterministic*: the same canonical entity (or the
same source record) must always produce the same id, so that artifacts
produced by different pipeline runs can be diffed, rejoined and audited.

Two id flavours are provided:

* :func:`entity_guid`      - keyed by entity type + canonical name
  (normalized), stable across runs;
* :func:`record_guid`      - keyed by source system + source record id, used
  when a record must be addressable even if it never becomes an entity;
* :func:`evidence_guid`    - keyed by (record, kind) for provenance refs.

The underlying scheme is UUIDv5 over a project-fixed namespace, so ids are
verifiable without any central registry.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.resolution.transliteration import to_latin_fold

SENTINELGRAPH_NAMESPACE = uuid.UUID("e3f1a7b2-6c4d-4e89-9a50-2b7f6d8c5a41")


def _guid_strategy() -> str:
    """Read GUID_STRATEGY lazily so tests can change it at runtime."""
    return os.environ.get("GUID_STRATEGY", "stable").lower()


def _uuid5(name: str) -> str:
    return str(uuid.uuid5(SENTINELGRAPH_NAMESPACE, name))


def _normalize(text: Optional[str]) -> str:
    return " ".join((text or "").strip().lower().split())


def _normalize_phone(phone: Optional[str]) -> str:
    """Strip non-digits, keep last 10 digits if present."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) >= 10:
        digits = digits[-10:]
    return digits


def _normalize_dob(dob: Optional[str]) -> str:
    """Parse DOB to YYYY-MM-DD; on failure return empty string."""
    if not dob:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(str(dob).strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        from dateutil import parser as _dp
        dt = _dp.parse(str(dob))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def make_stable_guid(
    name: str,
    dob: Optional[str] = None,
    phone: Optional[str] = None,
    entity_type: str = "PERSON",
) -> str:
    """
    Content-addressable GUID based on SHA-256 of canonical entity fields.
    """
    norm_name = to_latin_fold(name)
    norm_phone = _normalize_phone(phone)
    norm_dob = _normalize_dob(dob)
    canonical = f"{entity_type.upper()}|{norm_name}|{norm_dob}|{norm_phone}"
    hash_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"E-{hash_digest}"


def generate_legacy_guid(
    entity_type: str, canonical_name: str, dob: Optional[str] = None,
    phone: Optional[str] = None,
) -> str:
    """Legacy UUIDv5-based GUID (kept for backward compatibility)."""
    name_part = _normalize(canonical_name)
    dob_part = _normalize(dob) if dob else ""
    phone_part = _normalize_phone(phone) if phone else ""
    return _uuid5(f"entity|{entity_type.upper()}|{name_part}|{dob_part}|{phone_part}")


def entity_guid(entity_type: str, canonical_name: str) -> str:
    """Dispatcher: selects strategy via GUID_STRATEGY env var."""
    if _guid_strategy() == "legacy":
        return generate_legacy_guid(entity_type, canonical_name)
    return make_stable_guid(canonical_name)


def migrate_guid_map(old_graph, new_graph) -> dict:
    """Compute old->new GUID mappings for entities in both graphs."""
    def _extract_persons(graph):
        persons = {}
        for node, data in graph.nodes(data=True):
            if data.get("entity_type", "").upper() == "PERSON":
                name = data.get("name", "")
                dob = data.get("dob", "")
                phone = data.get("phone", "")
                if name:
                    guid = make_stable_guid(name, dob, phone)
                    persons[(name, dob, phone)] = (node, guid)
        return persons
    old_entities = _extract_persons(old_graph)
    new_entities = _extract_persons(new_graph)
    mapping = {}
    for key, (old_node, old_guid) in old_entities.items():
        if key in new_entities:
            _, new_guid = new_entities[key]
            if old_guid != new_guid:
                mapping[old_guid] = new_guid
    out_path = Path("data/exports/guid_migration.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mapping, indent=2))
    return mapping


def record_guid(source_system: str, source_record_id: str) -> str:
    """Deterministic GUID for a source record (call / tx / FIR / ...)."""
    return _uuid5(f"record|{source_system.lower()}|{str(source_record_id).strip()}")


def evidence_guid(source_record_id: str, kind: str = "record") -> str:
    """Deterministic GUID for an evidence reference."""
    return _uuid5(f"evidence|{str(source_record_id).strip()}|{kind}")


def ghost_guid(community_a: int, community_b: int, anchors: str = "") -> str:
    """Deterministic GUID for a ghost candidate (matches the detector)."""
    key = f"{min(community_a, community_b)}|{max(community_a, community_b)}"
    if anchors:
        key += f"|{anchors}"
    return _uuid5(f"ghost|{key}")
