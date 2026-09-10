"""
routers/enhanced_financial.py
-----------------------------
Enhanced Financial Flow Analysis API (route group: /api/financial-enhanced/*).

Extends the basic financial router with advanced analytical signals:
aggregated flows, layering detection, circular flows, burst detection,
and path finding with upstream/downstream expansion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query

from src.api import audit, services

router = APIRouter(prefix="/api/financial-enhanced", tags=["financial-enhanced"])


def _get_analyzer():
    from src.analysis.financial_analysis import FinancialAnalyzer
    graph = services.load_graph()
    return FinancialAnalyzer(graph)


@router.get("/aggregated")
def aggregated_flows(
    min_amount: float = Query(0, ge=0),
    date_start: Optional[str] = Query(None),
    date_end: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Aggregated transaction flows between entity pairs."""
    analyzer = _get_analyzer()
    date_range = (date_start, date_end) if date_start and date_end else None
    flows = analyzer.aggregated_flows(min_amount=min_amount, date_range=date_range)
    audit.record_action("financial-enhanced.aggregated", detail={"min_amount": min_amount, "count": len(flows)})
    return {"flows": [f.model_dump() for f in flows[:limit]], "total": len(flows)}


@router.get("/paths")
def find_paths(
    source: str = Query(..., description="Source account/entity ID"),
    max_hops: int = Query(4, ge=1, le=6),
    min_amount: float = Query(0, ge=0),
    destination: Optional[str] = Query(None),
):
    """Find financial flow paths from a source."""
    analyzer = _get_analyzer()
    paths = analyzer.find_paths(source, max_hops=max_hops, min_amount=min_amount, destination=destination)
    audit.record_action("financial-enhanced.paths", object_ids=[source], detail={"max_hops": max_hops})
    return {"paths": [p.model_dump() for p in paths], "total": len(paths), "source": source}


@router.get("/signals")
def financial_signals():
    """All detected financial analytical signals."""
    analyzer = _get_analyzer()
    report = analyzer.analyze()
    audit.record_action("financial-enhanced.signals", detail={"count": len(report.signals)})
    return {
        "signals": [s.model_dump() for s in report.signals],
        "total": len(report.signals),
        "summary": report.summary,
        "limitations": report.limitations,
    }


@router.post("/analyze")
def full_analysis(body: Dict[str, Any] = Body(...)):
    """Full financial analysis with optional source entity focus."""
    analyzer = _get_analyzer()
    source = body.get("source")
    max_hops = int(body.get("max_hops", 4))
    min_amount = float(body.get("min_amount", 0))
    report = analyzer.analyze(source=source, max_hops=max_hops, min_amount=min_amount)
    audit.record_action("financial-enhanced.analyze", object_ids=[source] if source else [])
    return report.model_dump()
