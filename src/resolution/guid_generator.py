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

import uuid
from typing import Optional

SENTINELGRAPH_NAMESPACE = uuid.UUID("e3f1a7b2-6c4d-4e89-9a50-2b7f6d8c5a41")


def _uuid5(name: str) -> str:
    return str(uuid.uuid5(SENTINELGRAPH_NAMESPACE, name))


def _normalize(text: Optional[str]) -> str:
    return " ".join((text or "").strip().lower().split())


def entity_guid(entity_type: str, canonical_name: str) -> str:
    """Deterministic GUID for a resolved entity.

    ``entity_guid("PERSON", "Ramesh Kumar")`` is stable across runs and
    across machines.
    """
    return _uuid5(f"entity|{entity_type.upper()}|{_normalize(canonical_name)}")


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
