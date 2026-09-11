"""Tests for Investigation Copilot.

Tests cover:
- Tool registration and execution
- Query interpretation
- Evidence grounding
- Response formatting
"""

import pytest
import networkx as nx

from src.llm.copilot import (
    InvestigationCopilot,
    MockCopilotProvider,
    ToolResult,
    CopilotResponse,
    ToolName,
)


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    g = nx.MultiDiGraph()
    
    # Add nodes
    g.add_node("PERSON-001", canonical_name="John Doe", entity_type="PERSON", 
               source_evidence_ids=["EV-001"], metrics={"pagerank": 0.15})
    g.add_node("PERSON-002", canonical_name="Jane Smith", entity_type="PERSON",
               source_evidence_ids=["EV-002"], metrics={"pagerank": 0.12})
    g.add_node("LOCATION-001", canonical_name="Warehouse", entity_type="LOCATION",
               source_evidence_ids=["EV-003"])
    g.add_node("ACCOUNT-001", canonical_name="ACC-12345", entity_type="ACCOUNT",
               source_evidence_ids=["EV-004"])
    
    # Add edges
    g.add_edge("PERSON-001", "PERSON-002", key=0, relation="KNOWS",
               source_evidence_ids=["EV-005"])
    g.add_edge("PERSON-001", "LOCATION-001", key=0, relation="VISITS",
               source_evidence_ids=["EV-006"])
    g.add_edge("PERSON-001", "ACCOUNT-001", key=0, relation="USES_ACCOUNT",
               source_evidence_ids=["EV-007"])
    
    return g


@pytest.fixture
def mock_evidence_store():
    """Create a mock evidence store."""
    class MockStore:
        def get(self, evidence_id):
            return {"id": evidence_id, "content": f"Evidence {evidence_id}"}
    
    return MockStore()


def test_copilot_initialization(sample_graph, mock_evidence_store):
    """Test copilot initializes correctly."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
        llm_provider=MockCopilotProvider(),
    )
    
    assert copilot.graph is not None
    assert copilot.evidence_store is not None
    assert len(copilot._tools) > 0
    assert len(copilot._tool_definitions) > 0


def test_copilot_tool_registration(sample_graph, mock_evidence_store):
    """Test all tools are registered."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    tools = copilot.get_available_tools()
    tool_names = [t.name for t in tools]
    
    # Check key tools are registered
    assert ToolName.SEARCH_ENTITIES.value in tool_names
    assert ToolName.FIND_PATHS.value in tool_names
    assert ToolName.FIND_HIDDEN_CONNECTORS.value in tool_names
    assert ToolName.ANALYZE_FINANCIAL_FLOW.value in tool_names
    assert ToolName.RUN_COUNTERFACTUAL.value in tool_names


def test_copilot_search_entities(sample_graph, mock_evidence_store):
    """Test entity search tool."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    result = copilot._tool_search_entities(query="John", limit=5)
    
    assert "entities" in result
    assert len(result["entities"]) > 0
    assert any("John" in e["label"] for e in result["entities"])


def test_copilot_get_entity(sample_graph, mock_evidence_store):
    """Test get entity tool."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    result = copilot._tool_get_entity(entity_id="PERSON-001")
    
    assert result["id"] == "PERSON-001"
    assert result["label"] == "John Doe"
    assert result["type"] == "PERSON"
    assert "EV-001" in result["_evidence_ids"]


def test_copilot_get_neighbors(sample_graph, mock_evidence_store):
    """Test get neighbors tool."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    result = copilot._tool_get_neighbors(entity_id="PERSON-001", limit=10)
    
    assert "neighbors" in result
    # PERSON-001 has 3 connections
    assert len(result["neighbors"]) >= 3


def test_copilot_find_paths(sample_graph, mock_evidence_store):
    """Test path finding tool."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    result = copilot._tool_find_paths(source="PERSON-001", target="PERSON-002")
    
    assert "paths" in result
    assert len(result["paths"]) > 0
    # There's a direct edge, so path length should be 1
    assert result["paths"][0]["length"] == 1


def test_copilot_calculate_centrality(sample_graph, mock_evidence_store):
    """Test centrality calculation tool."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    result = copilot._tool_calculate_centrality(metric="pagerank")
    
    assert "top_entities" in result
    assert len(result["top_entities"]) > 0
    assert all("metric" in e for e in result["top_entities"])


def test_copilot_analyze_financial_flow(sample_graph, mock_evidence_store):
    """Test financial flow analysis tool."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    result = copilot._tool_analyze_financial_flow()
    
    assert "patterns" in result
    # May have patterns depending on graph structure


def test_copilot_get_timeline(sample_graph, mock_evidence_store):
    """Test timeline tool."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    result = copilot._tool_get_timeline(entity_id="PERSON-001")
    
    assert "events" in result
    # Should have events from edges involving PERSON-001


def test_copilot_ask_query(sample_graph, mock_evidence_store):
    """Test full copilot query flow."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
        llm_provider=MockCopilotProvider(),
    )
    
    response = copilot.ask("Who is John Doe?")
    
    assert isinstance(response, CopilotResponse)
    assert response.query == "Who is John Doe?"
    assert response.answer is not None
    assert response.requires_human_review is True
    assert response.status == "INFERRED"


def test_copilot_ask_with_entity_search(sample_graph, mock_evidence_store):
    """Test copilot processes entity search queries."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
        llm_provider=MockCopilotProvider(),
    )
    
    # Query with clear entity name pattern
    response = copilot.ask("search for John Doe")
    
    assert isinstance(response, CopilotResponse)
    assert response.query == "search for John Doe"
    assert response.answer is not None
    # Mock provider should have attempted tool selection
    assert response.processing_time_ms >= 0


def test_copilot_ask_hidden_connectors(sample_graph, mock_evidence_store):
    """Test copilot triggers ghost detection."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
        llm_provider=MockCopilotProvider(),
    )
    
    response = copilot.ask("Find hidden connectors")
    
    assert isinstance(response, CopilotResponse)
    # Should have called find_hidden_connectors tool
    tool_names = [t.tool_name for t in response.tools_called]
    assert ToolName.FIND_HIDDEN_CONNECTORS.value in tool_names


def test_copilot_tool_execution_failure_handling(sample_graph, mock_evidence_store):
    """Test copilot handles tool failures gracefully."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
    )
    
    # Execute tool with invalid arguments
    result = copilot._execute_tool(
        tool_name=ToolName.GET_ENTITY.value,
        arguments={"entity_id": "NONEXISTENT"},
    )
    
    assert isinstance(result, ToolResult)
    # Tool should succeed but return no data for nonexistent entity


def test_copilot_response_evidence_collection(sample_graph, mock_evidence_store):
    """Test that evidence IDs are collected from tool results."""
    copilot = InvestigationCopilot(
        graph=sample_graph,
        evidence_store=mock_evidence_store,
        llm_provider=MockCopilotProvider(),
    )
    
    response = copilot.ask("Who is John Doe?")
    
    # Should have collected evidence IDs from graph nodes
    assert isinstance(response.evidence_ids, list)


def test_mock_copilot_provider_tool_selection():
    """Test mock provider selects tools based on query patterns."""
    provider = MockCopilotProvider()
    
    # Test cross-case detection
    result = provider.generate_with_tools(
        prompt="Who connects Case-0198 and Case-0421?",
        tools=[],
        context=[],
    )
    
    assert "tool_calls" in result
    tool_calls = result["tool_calls"]
    tool_names = [tc["tool_name"] for tc in tool_calls]
    
    # Should select cross-case tool
    assert ToolName.GET_CROSS_CASE_LINKS.value in tool_names


def test_mock_provider_extracts_entity_names():
    """Test mock provider can extract entity names from queries."""
    provider = MockCopilotProvider()
    
    name = provider._extract_entity_name("Who is Ravi Kumar?")
    assert name in ["Ravi", "Ravi Kumar", "Kumar"]


def test_copilot_response_requires_human_review():
    """Test all copilot responses require human review."""
    from src.llm.copilot import CopilotResponse
    
    response = CopilotResponse(
        response_id="RESP-001",
        query="Test query",
        answer="Test answer",
    )
    
    assert response.requires_human_review is True


def test_tool_result_to_context():
    """Test tool result converts to context format."""
    result = ToolResult(
        tool_name="test_tool",
        success=True,
        data={"key": "value"},
        evidence_ids=["EV-001"],
    )
    
    context = result.to_context()
    assert context["tool"] == "test_tool"
    assert context["success"] is True
    assert context["data"]["key"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
