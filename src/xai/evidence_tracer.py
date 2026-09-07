"""
evidence_tracer.py
------------------
Evidence provenance layer + local retrieval index (Phase C / Phase D).

Every graph-derived conclusion in SentinelGraph AI must be traceable back to
source records.  This module provides:

* :class:`EvidenceRecord` - the normalized provenance unit (source type,
  source record id, uri, excerpt, structured fields, hash, confidence).
* :class:`EvidenceStore` - an in-memory/JSON index built from the pipeline
  artifacts (synthetic CSVs, cleaned records, graph triplets, ghost
  predictions) exposing:

      get_evidence(id)
      get_evidence_for_node(node_id)
      get_evidence_for_edge(edge_id)
      get_evidence_for_finding(finding_id)
      search_evidence(query)
      get_timeline(subject_id)

The store is deliberately backend-agnostic: :class:`EvidenceBackend` is the
interface a PostgreSQL/OpenSearch/vector backend would implement later (see
``src/adapters``).  The local demo requires none of those.

Integrity rules enforced here:

* evidence ids are deterministic (uuid5 of the source record + kind), so the
  same source record always yields the same evidence id;
* every record carries a sha256 ``hash`` of its canonical content;
* ``provenance`` distinguishes observed records from generated/synthetic ones;
* this layer NEVER invents evidence - it only indexes what exists.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import (Any, Dict, Iterable, List, Mapping, Optional, Protocol,
                    Sequence, Tuple)

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

EVIDENCE_NAMESPACE = uuid.UUID("6f1d2c34-9a2e-5b7c-8f41-3c9a5d1e7b10")

VALID_SOURCE_TYPES = {
    "CALL",
    "TRANSACTION",
    "MEETING",
    "FIR",
    "INTELLIGENCE_REPORT",
    "PERSON_PROFILE",
    "TRIPLET",
    "TIP",
    "API_RECORD",
    "DOCUMENT",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_evidence_id(source_type: str, source_record_id: str, kind: str = "record") -> str:
    """Deterministic evidence id for a given source record."""
    raw = f"{source_type}|{source_record_id}|{kind}"
    return "EV-" + str(uuid.uuid5(EVIDENCE_NAMESPACE, raw))


class EvidenceRecord(BaseModel):
    """A single provenance unit.  Everything the XAI layer cites resolves to
    one of these."""

    evidence_id: str
    source_type: str
    source_record_id: str
    source_uri: str = ""
    timestamp: Optional[str] = None
    ingested_at: str = Field(default_factory=_utcnow)
    text_excerpt: str = ""
    structured_fields: Dict[str, Any] = Field(default_factory=dict)
    hash: str = ""
    provenance: str = "observed_record"   # observed_record | generated_synthetic
    confidence: float = 1.0
    subject_ids: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.hash:
            canonical = json.dumps(
                {
                    "source_type": self.source_type,
                    "source_record_id": self.source_record_id,
                    "excerpt": self.text_excerpt,
                    "fields": self.structured_fields,
                },
                sort_keys=True,
                default=str,
            )
            self.hash = _sha256(canonical)


class EvidenceBackend(Protocol):
    """Interface a production backend (PostgreSQL / OpenSearch / vector DB)
    would implement.  The local demo satisfies this with dicts."""

    def upsert(self, record: EvidenceRecord) -> None: ...

    def get(self, evidence_id: str) -> Optional[EvidenceRecord]: ...

    def iter_all(self) -> Iterable[EvidenceRecord]: ...


class InMemoryEvidenceBackend:
    """Plain-dict backend (local/demo mode)."""

    def __init__(self) -> None:
        self._records: Dict[str, EvidenceRecord] = {}

    def upsert(self, record: EvidenceRecord) -> None:
        self._records[record.evidence_id] = record

    def get(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self._records.get(evidence_id)

    def iter_all(self) -> Iterable[EvidenceRecord]:
        return list(self._records.values())


class EvidenceStore:
    """Indexes evidence records and their links to graph nodes/edges/findings."""

    def __init__(self, backend: Optional[EvidenceBackend] = None) -> None:
        self.backend = backend or InMemoryEvidenceBackend()
        self._by_node: Dict[str, List[str]] = defaultdict(list)
        self._by_edge: Dict[str, List[str]] = defaultdict(list)
        self._by_finding: Dict[str, List[str]] = defaultdict(list)
        self._by_source_record: Dict[str, str] = {}
        self._token_index: Dict[str, List[str]] = defaultdict(list)

    # ------------------------------------------------------------- indexing
    def add(self, record: EvidenceRecord, *,
            node_ids: Optional[Sequence[str]] = None,
            edge_ids: Optional[Sequence[str]] = None,
            finding_ids: Optional[Sequence[str]] = None) -> EvidenceRecord:
        if record.source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"invalid source_type: {record.source_type}")
        self.backend.upsert(record)
        self._by_source_record.setdefault(record.source_record_id, record.evidence_id)
        for token in _tokens(record.text_excerpt):
            self._token_index[token].append(record.evidence_id)
        for nid in node_ids or []:
            if record.evidence_id not in self._by_node[nid]:
                self._by_node[nid].append(record.evidence_id)
            for token in _tokens(nid):
                if token and record.evidence_id not in self._by_node.get(f"name:{token}", []):
                    self._by_node[f"name:{token}"].append(record.evidence_id)
        for eid in edge_ids or []:
            if record.evidence_id not in self._by_edge[eid]:
                self._by_edge[eid].append(record.evidence_id)
        for fid in finding_ids or []:
            if record.evidence_id not in self._by_finding[fid]:
                self._by_finding[fid].append(record.evidence_id)
        return record

    # ------------------------------------------------------------ retrieval
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self.backend.get(evidence_id)

    def require_evidence(self, evidence_id: str) -> EvidenceRecord:
        record = self.get_evidence(evidence_id)
        if record is None:
            raise KeyError(f"unknown evidence id: {evidence_id}")
        return record

    def all_ids(self) -> List[str]:
        return [r.evidence_id for r in self.backend.iter_all()]

    def count(self) -> int:
        return len(self.all_ids())

    def get_evidence_for_node(self, node_id: str, limit: int = 200) -> List[EvidenceRecord]:
        """All evidence linked to a graph node (by guid, by known name token,
        or by structured person/account ids)."""
        ids: List[str] = list(self._by_node.get(node_id, []))
        for token in _tokens(node_id):
            ids.extend(self._by_node.get(f"name:{token}", []))
        seen, out = set(), []
        for eid in ids:
            rec = self.backend.get(eid)
            if rec is not None and eid not in seen:
                seen.add(eid)
                out.append(rec)
        out.sort(key=lambda r: (r.timestamp or "", r.evidence_id))
        return out[:limit]

    def get_evidence_for_edge(self, edge_id: str) -> List[EvidenceRecord]:
        return [r for r in (self.backend.get(eid) for eid in self._by_edge.get(edge_id, []))
                if r is not None]

    def get_evidence_for_finding(self, finding_id: str) -> List[EvidenceRecord]:
        return [r for r in (self.backend.get(eid) for eid in self._by_finding.get(finding_id, []))
                if r is not None]

    def link_finding(self, finding_id: str, evidence_ids: Sequence[str]) -> None:
        """Attach existing evidence ids to a finding."""
        for eid in evidence_ids:
            if self.backend.get(eid) is None:
                continue
            bucket = self._by_finding.setdefault(finding_id, [])
            if eid not in bucket:
                bucket.append(eid)

    def search_evidence(self, query: str, limit: int = 25,
                        source_type: Optional[str] = None) -> List[EvidenceRecord]:
        """Token-overlap ranked keyword search over excerpts + record ids."""
        q_tokens = [t for t in _tokens(query) if len(t) > 2]
        if not q_tokens:
            return []
        scores: Dict[str, int] = defaultdict(int)
        for token in q_tokens:
            for eid in self._token_index.get(token, []):
                scores[eid] += 1
            for eid in self._by_source_record.get(token.upper(), []):
                scores[eid] += 3
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        out: List[EvidenceRecord] = []
        for eid, _score in ranked:
            rec = self.backend.get(eid)
            if rec is None:
                continue
            if source_type and rec.source_type != source_type:
                continue
            out.append(rec)
            if len(out) >= limit:
                break
        return out

    def get_timeline(self, subject_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Chronological evidence for one subject (node guid or known name)."""
        records = self.get_evidence_for_node(subject_id, limit=limit)
        records.sort(key=lambda r: (r.timestamp or "9999", r.evidence_id))
        return [r.model_dump() for r in records]

    # ---------------------------------------------------------- persistence
    def to_json(self, path: str | Path) -> Path:
        payload = {
            "generated_at": _utcnow(),
            "records": [r.model_dump() for r in self.backend.iter_all()],
            "by_node": {k: v for k, v in self._by_node.items()},
            "by_edge": {k: v for k, v in self._by_edge.items()},
            "by_finding": {k: v for k, v in self._by_finding.items()},
        }
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, default=str))
        logger.info("Evidence index written to %s (%s records)", out, len(payload["records"]))
        return out

    @classmethod
    def from_json(cls, path: str | Path) -> "EvidenceStore":
        payload = json.loads(Path(path).read_text())
        store = cls()
        for rec in payload.get("records", []):
            store.backend.upsert(EvidenceRecord.model_validate(rec))
        for k, v in payload.get("by_node", {}).items():
            store._by_node[k] = list(v)
        for k, v in payload.get("by_edge", {}).items():
            store._by_edge[k] = list(v)
        for k, v in payload.get("by_finding", {}).items():
            store._by_finding[k] = list(v)
        for rec in store.backend.iter_all():
            store._by_source_record.setdefault(rec.source_record_id, rec.evidence_id)
            for token in _tokens(rec.text_excerpt):
                store._token_index[token].append(rec.evidence_id)
        return store


# --------------------------------------------------------------------------- #
# Builders - construct the index from pipeline artifacts
# --------------------------------------------------------------------------- #

def _excerpt(text: str, cap: int = 400) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= cap else text[: cap - 1] + "…"


def build_store_from_artifacts(
    *,
    persons_csv: Path,
    calls_csv: Path,
    transactions_csv: Path,
    meetings_csv: Path,
    cleaned_records_path: Path,
    triplets_path: Path,
    graph_data_path: Optional[Path] = None,
    ghost_predictions_path: Optional[Path] = None,
) -> EvidenceStore:
    """Build the full evidence index from the pipeline artifacts.

    Evidence semantics: the index reflects what the *system observed*,
    not the simulator's ground-truth world state.  Primary sources:

      1. cleaned records (``data/processed/cleaned_records.json``) - the
         observed subset of calls/transactions/meetings plus FIRs,
         intelligence reports and person profiles, each with the original
         record id preserved;
      2. graph triplets - normalized, edge-level provenance with excerpts;
      3. graph node linkage (guid -> evidence via names + structured ids);
      4. ghost prediction anchor links.

    The raw synthetic CSVs (50k calls / 20k tx / 8k meetings) represent the
    full ground truth used for benchmarking and are deliberately NOT
    indexed as evidence: only the ingested/observed subset qualifies.
    They are still read for the person_id -> name mapping.
    """
    store = EvidenceStore()

    # -------------------------------------------------- id <-> name maps --
    person_names: Dict[str, str] = {}
    if persons_csv.exists():
        with persons_csv.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                person_names[row.get("person_id", "")] = row.get("full_name", "")

    # ------------------------------------------------------ 1: cleaned -- #
    type_map = {
        "fir": "FIR",
        "intelligence_report": "INTELLIGENCE_REPORT",
        "call_observation": "CALL",
        "transaction_observation": "TRANSACTION",
        "meeting_observation": "MEETING",
        "person": "PERSON_PROFILE",
        "document_page": "DOCUMENT",
    }
    if cleaned_records_path.exists():
        cleaned = json.loads(cleaned_records_path.read_text())
        for recj in cleaned:
            rid = str(recj.get("record_id") or "")
            rtype = type_map.get(str(recj.get("record_type", "")).lower())
            if not rid or rtype is None:
                continue
            meta = recj.get("metadata") or {}
            timestamp = (meta.get("timestamp") or meta.get("date_filed")
                         or meta.get("date_reported"))
            subjects: List[str] = []
            for key in ("source_person_id", "target_person_id", "person_id"):
                if meta.get(key):
                    subjects.append(str(meta[key]))
            for key in ("attendee_ids", "person_ids"):
                val = meta.get(key)
                if isinstance(val, list):
                    subjects.extend(str(v) for v in val)
            account = meta.get("account_id") or meta.get("account")
            if account:
                subjects.append(str(account))
            rec = EvidenceRecord(
                evidence_id=make_evidence_id(rtype, rid),
                source_type=rtype,
                source_record_id=rid,
                source_uri=f"data/processed/cleaned_records.json#{rid}",
                timestamp=timestamp,
                text_excerpt=_excerpt(str(recj.get("text") or "")),
                structured_fields={
                    "record_type": recj.get("record_type"),
                    "language": recj.get("language"),
                    "is_duplicate": recj.get("is_duplicate"),
                    "metadata": {k: v for k, v in meta.items()
                                 if k in ("source_person_id", "target_person_id",
                                          "attendee_ids", "person_id", "gang_id",
                                          "role", "location", "account_id",
                                          "timestamp", "date_filed", "tower_location")},
                },
                provenance="generated_synthetic",
                confidence=round(float(recj.get("language_confidence") or 0.9), 3),
                subject_ids=sorted(set(subjects)),
            )
            store.add(rec, node_ids=sorted(set(subjects)))

    # ------------------------------------------------------ 2: triplets - #
    if triplets_path.exists():
        triplets = json.loads(triplets_path.read_text())
        for idx, trip in enumerate(triplets.get("triplets", [])):
            rid = str(trip.get("record_id") or f"triplet-{idx}")
            eid = make_evidence_id("TRIPLET", rid, kind=f"edge-{idx}")
            attrs = trip.get("attributes") or {}
            subjects = [
                str(v) for v in (attrs.get("source_person_id"), attrs.get("target_person_id"))
                if v
            ]
            rec = EvidenceRecord(
                evidence_id=eid,
                source_type="TRIPLET",
                source_record_id=rid,
                source_uri=f"data/processed/graph_triplets.json#triplets[{idx}]",
                timestamp=attrs.get("timestamp"),
                text_excerpt=_excerpt(str(trip.get("evidence") or "")),
                structured_fields={
                    "source": trip.get("source"),
                    "source_type": trip.get("source_type"),
                    "relation": trip.get("relation"),
                    "target": trip.get("target"),
                    "target_type": trip.get("target_type"),
                    "confidence": trip.get("confidence"),
                    "attributes": attrs,
                },
                provenance="generated_synthetic",
                confidence=round(float(trip.get("confidence") or 0.8), 3),
                subject_ids=subjects,
            )
            store.add(rec, node_ids=subjects)

    # --------------------------------------------- 3: graph node linkage - #
    if graph_data_path is not None and graph_data_path.exists():
        _link_graph_nodes(store, graph_data_path, person_names)

    # ------------------------------------------------ 4: ghost anchors --- #
    if ghost_predictions_path is not None and ghost_predictions_path.exists():
        _link_ghost_anchors(store, ghost_predictions_path)

    logger.info("Evidence index built: %s records", store.count())
    return store


def _link_graph_nodes(store: EvidenceStore, graph_data_path: Path,
                      person_names: Mapping[str, str]) -> None:
    """Link graph node guids to evidence ids via names / structured ids."""
    graph_doc = json.loads(graph_data_path.read_text())
    person_id_to_node: Dict[str, str] = {}
    name_to_node: Dict[str, str] = {}
    for node in graph_doc.get("nodes", []):
        nid = node.get("id")
        if not nid:
            continue
        attrs = node.get("attributes") or {}
        label = (node.get("label") or "").lower()
        if label:
            name_to_node[label] = nid
        for alias in node.get("aliases") or []:
            name_to_node[str(alias).lower()] = nid
        for key in ("person_id",):
            if attrs.get(key):
                person_id_to_node[str(attrs[key])] = nid
        if str(node.get("type", "")).upper() == "PERSON" and label:
            for pid, pname in person_names.items():
                if pname.lower() == label:
                    person_id_to_node[pid] = nid
                    break
    # person-id linkage: attach call/tx/meeting/profile evidence to endpoints
    for pid, nid in person_id_to_node.items():
        for rec in store.get_evidence_for_node(pid, limit=2000):
            bucket = store._by_node.setdefault(nid, [])
            if rec.evidence_id not in bucket:
                bucket.append(rec.evidence_id)
    # name-token linkage for non-person nodes (locations, orgs, gangs...)
    for label, nid in name_to_node.items():
        for rec in store.get_evidence_for_node(f"name:{label}", limit=200):
            bucket = store._by_node.setdefault(nid, [])
            if rec.evidence_id not in bucket:
                bucket.append(rec.evidence_id)
    # edge linkage: edge id -> its triplet record evidence
    for edge in graph_doc.get("edges", []):
        eid_edge = edge.get("id")
        attrs = edge.get("attributes") or {}
        rid = str(attrs.get("record_id") or "")
        rec_id = store._by_source_record.get(rid)
        if eid_edge and rec_id:
            bucket = store._by_edge.setdefault(eid_edge, [])
            if rec_id not in bucket:
                bucket.append(rec_id)


def _link_ghost_anchors(store: EvidenceStore, ghost_predictions_path: Path) -> None:
    """Ghost predicted structure -> evidence links (anchors are real records)."""
    ghost_doc = json.loads(ghost_predictions_path.read_text())
    ghosts: List[Dict[str, Any]] = []
    if isinstance(ghost_doc, list):
        ghosts = [g for g in ghost_doc if isinstance(g, dict)]
    elif isinstance(ghost_doc, dict):
        for key in ("ghost_nodes", "ghosts", "predictions", "nodes", "items"):
            val = ghost_doc.get(key)
            if isinstance(val, list):
                ghosts = [g for g in val if isinstance(g, dict)]
                break
    for ghost in ghosts:
        gid = ghost.get("ghost_id")
        if not gid:
            continue
        for anchor in ghost.get("evidence", []) or []:
            anchor_guid = anchor.get("anchor_guid")
            if not anchor_guid:
                continue
            for rec in store.get_evidence_for_node(str(anchor_guid), limit=50):
                bucket = store._by_node.setdefault(str(gid), [])
                if rec.evidence_id not in bucket:
                    bucket.append(rec.evidence_id)


def _tokens(text: str) -> List[str]:
    """Lowercased word tokens >= 3 chars, plus digits-only runs."""
    text = (text or "").lower()
    return re.findall(r"[a-z0-9_]{3,}", text)
