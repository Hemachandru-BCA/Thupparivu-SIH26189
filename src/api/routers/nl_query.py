"""
routers/nl_query.py
-------------------
Natural Language Analyst Query API (route group: /api/nl-query/*).

Converts natural-language questions into structured queries, then executes
them deterministically against the graph/evidence/index.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from src.api import audit, services

router = APIRouter(prefix="/api/nl-query", tags=["nl-query"])


def _get_engine():
    from src.analysis.nl_query import NLQueryEngine
    graph = services.load_graph()
    evidence = services.evidence_store()
    return NLQueryEngine(graph, evidence)


@router.post("/ask")
def ask_query(body: Dict[str, Any] = Body(...)):
    """Parse and execute a natural-language analytical query."""
    query = body.get("query", "").strip()
    if not query:
        return {"error": "Empty query", "query": ""}
    engine = _get_engine()
    interpretation = engine.parse(query)
    result = engine.execute(interpretation)
    audit.record_action("nl-query.ask", detail={"query": query[:100], "intent": interpretation.structured.intent, "results": result.total})
    return result.model_dump()


@router.get("/parse")
def parse_only(q: str = Query(..., description="Natural language query")):
    """Parse a query without executing (preview interpretation)."""
    engine = _get_engine()
    interpretation = engine.parse(q)
    audit.record_action("nl-query.parse", detail={"query": q[:100]})
    return interpretation.model_dump()


@router.get("/demo-queries")
def demo_queries():
    """List predefined demo queries for offline/deterministic mode."""
    from src.analysis.nl_query import MockAnalystQueryProvider
    return {"queries": MockAnalystQueryProvider.available_queries()}
