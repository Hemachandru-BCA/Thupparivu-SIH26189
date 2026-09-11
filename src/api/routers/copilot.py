"""Investigation Copilot API routes.

Exposes the tool-based copilot for natural language investigation queries.

Endpoints:
- POST /api/copilot/ask - Ask a question
- GET /api/copilot/tools - List available tools
- GET /api/copilot/demo-queries - Get demo queries
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from src.api import audit, services

router = APIRouter(prefix="/api/copilot", tags=["copilot"])
logger = logging.getLogger(__name__)


def _get_copilot():
    """Get or create copilot instance."""
    from src.llm.copilot import InvestigationCopilot, MockCopilotProvider
    
    graph = services.load_graph()
    evidence_store = services.evidence_store()
    
    return InvestigationCopilot(
        graph=graph,
        evidence_store=evidence_store,
        llm_provider=MockCopilotProvider(),
    )


@router.post("/ask")
def ask_question(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Ask the investigation copilot a question.
    
    The copilot will:
    1. Interpret the natural language query
    2. Select appropriate analytical tools
    3. Execute tools against the graph/evidence
    4. Return an evidence-grounded response
    
    All responses are DRAFT FOR HUMAN REVIEW.
    """
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    context = body.get("context")
    
    copilot = _get_copilot()
    response = copilot.ask(query, context=context)
    
    audit.record_action("copilot.ask", detail={
        "query": query[:100],
        "tools_used": len(response.tools_called),
        "evidence_count": len(response.evidence_ids),
    })
    
    return response.model_dump()


@router.get("/tools")
def list_tools() -> Dict[str, Any]:
    """List available copilot tools.
    
    Returns tool definitions in OpenAI function calling format.
    """
    copilot = _get_copilot()
    tools = copilot.get_available_tools()
    
    return {
        "tools": [t.model_dump() for t in tools],
        "count": len(tools),
    }


@router.get("/demo-queries")
def demo_queries() -> Dict[str, Any]:
    """Get example queries for demo mode.
    
    These queries demonstrate copilot capabilities without
    requiring external LLM API access.
    """
    queries = [
        {
            "query": "Who connects Case-0198 and Case-0421?",
            "description": "Find cross-case connections",
            "tools": ["get_cross_case_links"],
        },
        {
            "query": "Find hidden connectors in this network",
            "description": "Identify potential hidden coordinators",
            "tools": ["find_hidden_connectors"],
        },
        {
            "query": "What is the path between Ravi and the warehouse incident?",
            "description": "Find relationship paths between entities",
            "tools": ["find_paths", "search_entities"],
        },
        {
            "query": "Show me the timeline for this entity",
            "description": "Get temporal events for an entity",
            "tools": ["get_timeline", "search_entities"],
        },
        {
            "query": "What happens if we remove this node?",
            "description": "Run counterfactual simulation",
            "tools": ["run_counterfactual", "search_entities"],
        },
        {
            "query": "What unusual financial patterns exist?",
            "description": "Detect financial anomalies",
            "tools": ["analyze_financial_flow"],
        },
        {
            "query": "Who are the most central entities?",
            "description": "Calculate network centrality",
            "tools": ["calculate_centrality"],
        },
        {
            "query": "What evidence supports this finding?",
            "description": "Get supporting evidence for a finding",
            "tools": ["get_supporting_evidence"],
        },
        {
            "query": "Show me counter-evidence for this hypothesis",
            "description": "Get contradicting evidence",
            "tools": ["get_counter_evidence"],
        },
        {
            "query": "What anomalies exist in this network?",
            "description": "Detect structural anomalies",
            "tools": ["detect_anomalies"],
        },
    ]
    
    return {"queries": queries, "count": len(queries)}


@router.get("/status")
def copilot_status() -> Dict[str, Any]:
    """Get copilot status and configuration."""
    return {
        "status": "available",
        "provider": "mock",  # Would be dynamic based on config
        "offline_capable": True,
        "tools_available": len(_get_copilot().get_available_tools()),
        "message": "Copilot is operating in offline mode with deterministic responses",
    }
