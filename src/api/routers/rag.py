"""Hybrid RAG API routes.

Endpoints:
- POST /api/rag/retrieve - Retrieve grounded context for a query
- GET /api/rag/status - RAG system status

This integrates keyword + graph + case retrieval for
evidence-grounded answers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException

from src.api import audit, services

router = APIRouter(prefix="/api/rag", tags=["rag"])
logger = logging.getLogger(__name__)


def _get_retriever():
    """Get or create hybrid retriever."""
    from src.rag.retriever import HybridRetriever
    
    graph = services.load_graph()
    evidence_store = services.evidence_store()
    
    return HybridRetriever(
        graph=graph,
        evidence_store=evidence_store,
    )


@router.post("/retrieve")
def retrieve_context(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Retrieve evidence-grounded context for a query.
    
    Combines keyword, graph neighborhood, and case-based retrieval
    to return a bounded, evidence-grounded context.
    
    The context is capped and never includes the entire graph.
    """
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    context = body.get("context") or {}
    max_chunks = body.get("max_chunks", 20)
    max_chars = body.get("max_chars", 4000)
    
    retriever = _get_retriever()
    retriever.max_chunks = max_chunks
    
    chunks = retriever.retrieve(query, context=context)
    context_text = retriever.format_context(chunks, max_chars=max_chars)
    
    audit.record_action("rag.retrieve", detail={
        "query": query[:100],
        "chunks_retrieved": len(chunks),
        "context_chars": len(context_text),
    })
    
    return {
        "query": query,
        "chunks": [c.model_dump() for c in chunks],
        "context": context_text,
        "chunk_count": len(chunks),
        "evidence_ids": list({
            eid for c in chunks for eid in c.evidence_ids
        }),
    }


@router.get("/status")
def rag_status() -> Dict[str, Any]:
    """Get RAG system status."""
    retriever = _get_retriever()
    
    return {
        "status": "available",
        "strategies": [
            {"name": "keyword", "description": "Evidence store keyword search", "enabled": retriever.evidence_store is not None},
            {"name": "graph_neighborhood", "description": "Graph entity expansion", "enabled": True},
            {"name": "case_context", "description": "Case-based entity retrieval", "enabled": True},
            {"name": "temporal_filter", "description": "Time-window filtering", "enabled": True},
        ],
        "max_chunks": retriever.max_chunks,
        "max_hops": retriever.max_hops,
        "graph_nodes": retriever.graph.number_of_nodes(),
        "graph_edges": retriever.graph.number_of_edges(),
    }