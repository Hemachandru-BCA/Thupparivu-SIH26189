"""
routers/intel.py
----------------
Case intelligence + cross-case API (route groups: /api/intel/*).

* GET /api/intel/cases/{case_id}/brief — structured CASE BRIEF with
  per-claim evidence references (never an LLM essay)
* GET /api/intel/cross-case — entities appearing in multiple cases and
  cross-case entity reuse stats
* GET /api/intel/gaps — investigative gaps: missing identity fields,
  missing timestamps, unresolved links, unexplained bridges

All claims reference structured data; nothing is fabricated.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import audit, paths, services

router = APIRouter(prefix="/api/intel", tags=["intel"])


# --------------------------------------------------------------------------- #
# Case brief
# --------------------------------------------------------------------------- #

def _case_path(case_id: str) -> str:
    safe = "".join(c for c in case_id if c.isalnum() or c in "-_")
    from pathlib import Path as P

    p = paths.CASES_DIR / f"{safe}.json"
    return str(p)


def _load_case(case_id: str) -> Dict[str, Any]:
    import json as _json

    p = _case_path(case_id)
    if not __import__("pathlib").Path(p).exists():
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    try:
        return _json.loads(__import__("pathlib").Path(p).read_text())
    except _json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Corrupt case file: {case_id}")


def _graph_stats() -> Dict[str, Any]:
    doc = services.graph_document()
    nodes = doc.get("nodes", [])
    edges = doc.get("edges", [])
    meta = doc.get("metadata", {})
    return {
        "entity_count": len(nodes),
        "relationship_count": len(edges),
        "evidence_count": _evidence_count(),
        "community_count": meta.get("num_communities"),
        "resolved_entities": meta.get("entity_resolution", {}).get("resolved_entity_count"),
    }


def _evidence_count() -> int:
    try:
        store = services.evidence_store()
        return store.count()
    except Exception:
        return 0


def _findings_count() -> int:
    try:
        doc = json.loads(paths.FINDINGS_PATH.read_text())
        return len(doc.get("findings", [])) if isinstance(doc, dict) else len(doc)
    except Exception:
        return 0


def _ghost_count() -> int:
    try:
        doc = services.ghost_document()
        nodes = doc.get("ghost_nodes", []) if isinstance(doc, dict) else doc
        return len(nodes)
    except Exception:
        return 0


def _open_hypotheses() -> int:
    try:
        hp = json.loads((paths.GRAPH_OUTPUT_DIR / "hypotheses.json").read_text())
        hyps = hp.get("hypotheses", [])
        return sum(1 for h in hyps if h.get("status") in ("OPEN", "UNDER_REVIEW"))
    except Exception:
        return 0


@router.get("/cases/{case_id}/brief")
def case_brief(case_id: str):
    """Structured case brief with claim-level evidence references."""
    case = _load_case(case_id)
    stats = _graph_stats()
    findings = []
    try:
        doc = json.loads(paths.FINDINGS_PATH.read_text())
        findings = doc.get("findings", []) if isinstance(doc, dict) else doc
    except Exception:
        findings = []

    high_value = [f for f in findings if (f.get("confidence_score") or {}).get(
        "overall_confidence", 0) or (f.get("confidence") or 0) >= 0.7][:5]
    contradictions = [f for f in findings if f.get("counter_evidence_ids")][:5]

    # top entities by pagerank
    doc = services.graph_document()
    nodes = doc.get("nodes", [])
    top = sorted(
        nodes,
        key=lambda n: (n.get("metrics") or {}).get("pagerank", 0),
        reverse=True,
    )[:8]

    brief = {
        "case_id": case_id,
        "title": case.get("title"),
        "status": case.get("status"),
        "current_state": {
            "entities": stats["entity_count"],
            "relationships": stats["relationship_count"],
            "evidence_items": stats["evidence_count"],
            "communities": stats["community_count"],
            "open_hypotheses": _open_hypotheses(),
            "critical_anomalies": _ghost_count(),
        },
        "network_summary": {
            "entity_count": stats["entity_count"],
            "relationship_count": stats["relationship_count"],
            "community_count": stats["community_count"],
            "generated_at": doc.get("metadata", {}).get("generated_at"),
        },
        "key_entities": [
            {"id": n.get("id"), "label": n.get("label"),
             "type": n.get("type"), "pagerank": (n.get("metrics") or {}).get("pagerank")}
            for n in top
        ],
        "active_hypotheses": _open_hypotheses(),
        "high_value_findings": [
            {"id": f.get("id"), "type": f.get("finding_type"),
             "subject_label": f.get("subject_label"),
             "evidence_ids": (f.get("supporting_evidence_ids") or [])[:5]}
            for f in high_value
        ],
        "contradictions": [
            {"id": f.get("id"), "subject_label": f.get("subject_label"),
             "counter_evidence_ids": (f.get("counter_evidence_ids") or [])[:5]}
            for f in contradictions
        ],
        "evidence_quality": _evidence_quality(),
        "latest_model_run": _latest_model_run(),
        "data_health": _data_health(),
    }
    audit.record_action("intel.case_brief", object_ids=[case_id])
    return brief


def _evidence_quality() -> Dict[str, Any]:
    """Aggregate evidence quality: source-type diversity + coverage."""
    try:
        store = services.evidence_store()
        recs = store.records if hasattr(store, "records") else []
        by_source: Dict[str, int] = defaultdict(int)
        for r in recs:
            by_source[r.source_type] = by_source.get(r.source_type, 0) + 1
        return {
            "total": len(recs),
            "by_source_type": dict(by_source),
            "independent_source_types": len(by_source),
        }
    except Exception:
        return {"total": 0, "by_source_type": {}, "independent_source_types": 0}


def _latest_model_run() -> Optional[Dict[str, Any]]:
    try:
        from src.domain.model_registry import ModelRegistry

        reg = ModelRegistry(paths.GRAPH_OUTPUT_DIR / "model_registry.json")
        runs = sorted(reg.list_runs(), key=lambda r: r.started_at, reverse=True)
        if not runs:
            return None
        r = runs[0]
        return {"model": r.model, "version": r.version, "started_at": r.started_at,
                "status": r.status}
    except Exception:
        return None


def _data_health() -> Dict[str, Any]:
    try:
        cleaned = json.loads(paths.CLEANED_RECORDS_PATH.read_text())
        records = cleaned if isinstance(cleaned, list) else cleaned.get("records", [])
        missing_ts = 0
        for r in records:
            if not (r.get("timestamp") or r.get("occurred_at") or r.get("date")):
                missing_ts += 1
        return {
            "records": len(records),
            "missing_timestamps": missing_ts,
            "completeness": round(1 - (missing_ts / max(len(records), 1)), 4),
        }
    except Exception:
        return {"records": 0, "missing_timestamps": 0, "completeness": 0.0}


# --------------------------------------------------------------------------- #
# Investigative gaps
# --------------------------------------------------------------------------- #

@router.get("/gaps")
def investigative_gaps(limit: int = Query(50, ge=1, le=300)):
    """Surface open analytical questions (missing data, unresolved links...).

    Each gap has a REQUESTED ACTION and OPEN status so it becomes a
    workflow item rather than a static warning.
    """
    gaps = []

    try:
        doc = services.graph_document()
        nodes = doc.get("nodes", [])
        unresolved = [n for n in nodes if n.get("type") == "UNKNOWN"]
        gaps.append({
            "type": "UNRESOLVED_IDENTITY",
            "count": len(unresolved),
            "severity": "MEDIUM",
            "description": f"{len(unresolved)} entities have an unresolved identity type.",
            "request": "Review entity type assignment",
            "status": "OPEN",
            "sample_ids": [n.get("id") for n in unresolved[:5]],
        })
    except Exception:
        pass

    try:
        cleaned = json.loads(paths.CLEANED_RECORDS_PATH.read_text())
        records = cleaned if isinstance(cleaned, list) else cleaned.get("records", [])
        missing_ts = sum(1 for r in records
                         if not (r.get("timestamp") or r.get("occurred_at") or r.get("date")))
        if missing_ts:
            gaps.append({
                "type": "MISSING_TIMESTAMP",
                "count": missing_ts,
                "severity": "HIGH",
                "description": f"{missing_ts} records lack a timestamp and degrade temporal analysis.",
                "request": "Acquire timestamped records",
                "status": "OPEN",
            })
    except Exception:
        pass

    try:
        store = services.evidence_store()
        recs = store.records if hasattr(store, "records") else []
        unknown_sources = sum(1 for r in recs if r.source_type in ("UNKNOWN", "?"))
        if unknown_sources:
            gaps.append({
                "type": "UNKNOWN_SOURCE",
                "count": unknown_sources,
                "severity": "LOW",
                "description": f"{unknown_sources} evidence items have an unknown source type.",
                "request": "Attribute source types",
                "status": "OPEN",
            })
    except Exception:
        pass

    audit.record_action("intel.gaps")
    return {"items": gaps[:limit], "total": len(gaps)}


# --------------------------------------------------------------------------- #
# Cross-case
# --------------------------------------------------------------------------- #

@router.get("/cross-case")
def cross_case(limit: int = Query(30, ge=1, le=200)):
    """Entities reused across case workspaces (identity reuse signal)."""
    cases = []
    for p in sorted(paths.CASES_DIR.glob("CASE-*.json")):
        try:
            cases.append(json.loads(p.read_text()))
        except Exception:
            continue

    # Build a label/type lookup from the graph node data (if available)
    label_lookup: Dict[str, Dict[str, str]] = {}
    try:
        graph_data = services.graph_document()
        if graph_data and isinstance(graph_data, dict):
            for node in graph_data.get("nodes", []) or []:
                nid = node.get("id") or node.get("label")
                if nid:
                    label_lookup[nid] = {
                        "label": node.get("label") or node.get("type") or nid,
                        "type": node.get("type") or node.get("entity_type") or "ENTITY",
                    }
    except Exception:
        graph_data = None

    entity_in_cases: Dict[str, List[str]] = defaultdict(list)
    entity_notes: Dict[str, str] = {}
    for case in cases:
        for item in case.get("items", []):
            eid = item.get("id") or item.get("entity_id")
            if eid:
                entity_in_cases[eid].append(case.get("id"))
                if item.get("note"):
                    entity_notes.setdefault(eid, item["note"])

    reuse = [
        {
            "entity_id": eid,
            "cases": cids,
            "case_count": len(cids),
            "label": label_lookup.get(eid, {}).get("label", eid[:24]),
            "entity_type": label_lookup.get(eid, {}).get("type", "ENTITY"),
            "note": entity_notes.get(eid, ""),
        }
        for eid, cids in entity_in_cases.items()
        if len(cids) > 1
    ]
    reuse.sort(key=lambda r: -r["case_count"])

    audit.record_action("intel.cross_case")
    return {
        "case_count": len(cases),
        "reused_entities": reuse[:limit],
        "total_reused": len(reuse),
        "note": "ENTITY REUSE — shared identifiers across cases, requires review",
    }