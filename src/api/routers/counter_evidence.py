"""
routers/counter_evidence.py
---------------------------
Counter-evidence analysis API (route group: /api/counter-evidence/*).

Ensures investigators can see what contradicts their hypotheses, not just
what supports them.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Query

from src.api import audit, services

router = APIRouter(prefix="/api/counter-evidence", tags=["counter-evidence"])


def _get_analyzer():
    from src.analysis.counter_evidence import CounterEvidenceAnalyzer
    evidence = services.evidence_store()
    return CounterEvidenceAnalyzer(evidence)


def _load_findings():
    try:
        from src.api.paths import FINDINGS_PATH
        if FINDINGS_PATH.exists():
            data = json.loads(FINDINGS_PATH.read_text())
            return data.get("findings", [])
    except Exception:
        pass
    return []


@router.get("/")
def all_counter_evidence():
    """Counter-evidence analysis for all findings."""
    analyzer = _get_analyzer()
    findings = _load_findings()
    panels = analyzer.analyze_all_findings(findings)
    audit.record_action("counter-evidence.all", detail={"count": len(panels)})
    return {
        "panels": [p.model_dump() for p in panels],
        "total": len(panels),
    }


@router.get("/finding/{finding_id}")
def finding_counter_evidence(finding_id: str):
    """Counter-evidence analysis for a specific finding."""
    analyzer = _get_analyzer()
    findings = _load_findings()
    finding = next((f for f in findings if f.get("id") == finding_id), None)
    if not finding:
        return {"error": "Finding not found", "finding_id": finding_id}
    panel = analyzer.analyze_finding(finding)
    audit.record_action("counter-evidence.finding", object_ids=[finding_id])
    return panel.model_dump()
