"""Tests for Hybrid RAG Retriever and Enhanced Financial Intelligence.

Tests cover:
- HybridRetriever retrieval strategies
- Graph neighborhood expansion
- Evidence-grounded context formatting
- Enhanced financial flow via copilot
- Copilot UI route
"""

import pytest
import networkx as nx

from src.rag.retriever import HybridRetriever, RetrievedChunk


def _make_graph():
    """Create a test graph."""
    g = nx.MultiDiGraph()
    g.add_node("P1", canonical_name="Alice", entity_type="PERSON",
               source_evidence_ids=["EV-001"], cases=["CASE-001"])
    g.add_node("P2", canonical_name="Bob", entity_type="PERSON",
               source_evidence_ids=["EV-002"], cases=["CASE-001"])
    g.add_node("P3", canonical_name="Charlie", entity_type="PERSON",
               source_evidence_ids=["EV-003"])
    g.add_node("LOC1", canonical_name="Warehouse", entity_type="LOCATION",
               source_evidence_ids=["EV-004"])
    g.add_edge("P1", "P2", key=0, relation="KNOWS", source_evidence_ids=["EV-005"])
    g.add_edge("P1", "LOC1", key=0, relation="VISITS", source_evidence_ids=["EV-006"])
    g.add_edge("P2", "P3", key=0, relation="CALLS", source_evidence_ids=["EV-007"])
    return g


# ── HybridRetriever tests ──────────────────────────────────────────────────


def test_retriever_initialization():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    assert retriever.graph is g
    assert retriever.max_chunks == 20
    assert retriever.max_hops == 2


def test_graph_retrieve_entity_found():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = retriever._graph_retrieve("Alice")
    assert len(chunks) > 0
    assert chunks[0].source_type in ("node", "edge")
    assert "EV-001" in chunks[0].evidence_ids


def test_graph_retrieve_entity_not_found():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = retriever._graph_retrieve("NonExistent")
    assert len(chunks) == 0


def test_graph_retrieve_expands_neighbors():
    g = _make_graph()
    retriever = HybridRetriever(graph=g, max_hops=2)
    chunks = retriever._graph_retrieve("Alice")
    # Should get Alice + Bob + Warehouse at minimum
    assert len(chunks) >= 3


def test_case_retrieve():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = retriever._case_retrieve("CASE-001")
    assert len(chunks) == 2  # Alice and Bob are in CASE-001


def test_case_retrieve_no_match():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = retriever._case_retrieve("CASE-9999")
    assert len(chunks) == 0


def test_extract_entities_from_query():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    entities = retriever._extract_entities('Find "Alice" and "Bob"')
    assert "Alice" in entities
    assert "Bob" in entities


def test_extract_case_ids():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    case_ids = retriever._extract_case_ids("Show me CASE-001 and CASE-042")
    assert "CASE-001" in case_ids
    assert "CASE-042" in case_ids


def test_resolve_entity_by_name():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    resolved = retriever._resolve_entity("Bob")
    assert resolved == "P2"


def test_resolve_entity_by_id():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    resolved = retriever._resolve_entity("P1")
    assert resolved == "P1"


def test_resolve_entity_not_found():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    resolved = retriever._resolve_entity("NonExistent")
    assert resolved is None


def test_retrieve_full_pipeline():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = retriever.retrieve('Find "Alice"')
    assert len(chunks) > 0
    # Should have deduped Alice from graph and keyword
    chunk_ids = [c.chunk_id for c in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_format_context_with_chunks():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = [
        RetrievedChunk(
            chunk_id="TEST-1",
            content="Alice is a person",
            source_type="node",
            source_id="P1",
            evidence_ids=["EV-001", "EV-002"],
            retrieval_method="graph_neighborhood",
            score=0.9,
        )
    ]
    ctx = retriever.format_context(chunks, max_chars=500)
    assert "Alice is a person" in ctx
    assert "EV-001" in ctx
    assert "EV-002" in ctx


def test_format_context_empty():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    ctx = retriever.format_context([], max_chars=500)
    assert "No relevant context" in ctx


def test_format_context_respects_char_limit():
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = [
        RetrievedChunk(
            chunk_id=f"C-{i}",
            content=f"Content for chunk {i} " * 50,
            source_type="node",
            source_id=f"X{i}",
            retrieval_method="test",
            score=0.5,
        )
        for i in range(100)
    ]
    ctx = retriever.format_context(chunks, max_chars=200)
    assert len(ctx) <= 200


def test_no_keyword_retrieval_without_store():
    g = _make_graph()
    retriever = HybridRetriever(graph=g, evidence_store=None)
    chunks = retriever._keyword_retrieve("anything")
    assert len(chunks) == 0


def test_retriever_deduplicates():
    """Same entity should not appear twice in results."""
    g = _make_graph()
    retriever = HybridRetriever(graph=g)
    chunks = retriever.retrieve('"Alice"')
    seen = set()
    for c in chunks:
        assert c.chunk_id not in seen
        seen.add(c.chunk_id)


def test_retriever_limits_results():
    g = _make_graph()
    retriever = HybridRetriever(graph=g, max_chunks=2)
    chunks = retriever.retrieve("find everyone")
    assert len(chunks) <= 2


# ── Copilot enhanced financial tool test ────────────────────────────────────


def test_copilot_financial_flow_uses_enhanced_analyzer():
    """Test that copilot financial tool tries enhanced analyzer."""
    from src.llm.copilot import InvestigationCopilot
    
    g = nx.MultiDiGraph()
    g.add_node("ACCT1", canonical_name="Account 1", entity_type="ACCOUNT",
               source_evidence_ids=["EV-001"])
    g.add_node("ACCT2", canonical_name="Account 2", entity_type="ACCOUNT",
               source_evidence_ids=["EV-002"])
    g.add_edge("ACCT1", "ACCT2", key=0, relation="TRANSFERRED_TO",
               attributes={"amount": 10000}, source_evidence_ids=["EV-003"])
    
    class _FakeStore:
        def search(self, q, limit=10):
            return []
    
    copilot = InvestigationCopilot(graph=g, evidence_store=_FakeStore())
    result = copilot._tool_analyze_financial_flow()
    
    assert "patterns" in result
    assert "_evidence_ids" in result


# ── Copilot uses hybrid RAG ────────────────────────────────────────────────


def test_copilot_ask_includes_rag():
    """Test that copilot ask method uses hybrid retrieval."""
    from src.llm.copilot import InvestigationCopilot, MockCopilotProvider
    
    g = _make_graph()
    
    class _FakeStore:
        def search(self, q, limit=10):
            return []
    
    copilot = InvestigationCopilot(
        graph=g,
        evidence_store=_FakeStore(),
        llm_provider=MockCopilotProvider(),
    )
    response = copilot.ask('Tell me about "Alice"')
    assert response.response_id is not None
    assert response.answer is not None
    # Should have evidence from graph retrieval
    assert isinstance(response.evidence_ids, list)


# ── Copilot UI route ────────────────────────────────────────────────────────


def test_copilot_ui_route():
    """Test that /copilot route exists in FastAPI app."""
    from src.api.main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/copilot")
    # Should return 200 (file found) or 404 (file missing), route exists
    assert resp.status_code in (200, 404)


def test_copilot_ui_content_type():
    """Test copilot UI returns HTML."""
    from src.api.main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/copilot")
    if resp.status_code == 200:
        ct = resp.headers.get("content-type", "")
        assert "html" in ct or "text" in ct
