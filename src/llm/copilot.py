"""Tool-based Investigation Copilot.

This module provides the main copilot implementation with a tool-based
architecture that ensures:
1. LLM interprets natural language questions
2. Tools execute deterministically against real data
3. Results are evidence-grounded
4. All actions are auditable

The copilot NEVER directly mutates the graph. It provides intelligence
and recommendations through verified tool calls.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Type, Union
import uuid
from uuid import uuid5

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

COPILOT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "sentinelgraph/copilot")


class ToolName(str, Enum):
    """Available copilot tools."""
    SEARCH_ENTITIES = "search_entities"
    SEARCH_EVIDENCE = "search_evidence"
    GET_ENTITY = "get_entity"
    GET_NEIGHBORS = "get_neighbors"
    FIND_PATHS = "find_paths"
    GET_TIMELINE = "get_timeline"
    FIND_COMMUNITIES = "find_communities"
    CALCULATE_CENTRALITY = "calculate_centrality"
    DETECT_ANOMALIES = "detect_anomalies"
    ANALYZE_FINANCIAL_FLOW = "analyze_financial_flow"
    FIND_HIDDEN_CONNECTORS = "find_hidden_connectors"
    COMPARE_CASES = "compare_cases"
    RUN_COUNTERFACTUAL = "run_counterfactual"
    GET_SUPPORTING_EVIDENCE = "get_supporting_evidence"
    GET_COUNTER_EVIDENCE = "get_counter_evidence"
    GET_CROSS_CASE_LINKS = "get_cross_case_links"


class ToolResult(BaseModel):
    """Result from a tool execution."""
    model_config = ConfigDict(extra="forbid")
    
    tool_name: str = Field(..., description="Name of the tool that was executed")
    success: bool = Field(..., description="Whether the tool execution succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Tool output data")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: float = Field(0.0, description="Execution time in milliseconds")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs referenced")
    
    def to_context(self) -> Dict[str, Any]:
        """Convert to context for LLM."""
        return {
            "tool": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "evidence_ids": self.evidence_ids,
        }


class CopilotTool(BaseModel):
    """Definition of a copilot tool."""
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description for LLM")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for parameters")
    required_params: List[str] = Field(default_factory=list, description="Required parameter names")
    
    def to_openai_tool(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params,
                }
            }
        }


class ToolCall(BaseModel):
    """A tool call requested by the LLM."""
    model_config = ConfigDict(extra="forbid")
    
    call_id: str = Field(..., description="Unique call ID")
    tool_name: str = Field(..., description="Tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    reasoning: Optional[str] = Field(None, description="LLM's reasoning for this call")


class CopilotResponse(BaseModel):
    """Complete response from the copilot."""
    model_config = ConfigDict(extra="forbid")
    
    response_id: str = Field(..., description="Unique response ID")
    query: str = Field(..., description="Original user query")
    answer: str = Field(..., description="Final answer to the user")
    
    # Key findings
    key_findings: List[str] = Field(default_factory=list, description="Key findings from analysis")
    
    # Evidence grounding
    evidence_ids: List[str] = Field(default_factory=list, description="All evidence IDs referenced")
    supporting_evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    counter_evidence: List[str] = Field(default_factory=list, description="Counter evidence")
    unknown_information: List[str] = Field(default_factory=list, description="Unknown/missing information")
    
    # Graph relationships
    entities_mentioned: List[str] = Field(default_factory=list, description="Entities mentioned")
    relationships: List[Dict[str, str]] = Field(default_factory=list, description="Relationships found")
    
    # Confidence
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Overall confidence")
    confidence_factors: Dict[str, float] = Field(default_factory=dict, description="Confidence breakdown")
    
    # Status
    status: str = Field("INFERRED", description="Observation status (OBSERVED/INFERRED/UNKNOWN)")
    requires_human_review: bool = Field(True, description="Always requires human review")
    
    # Tools used
    tools_called: List[ToolResult] = Field(default_factory=list, description="Tools that were executed")
    
    # Timing
    response_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When response was generated"
    )
    processing_time_ms: float = Field(0.0, description="Total processing time")


class LLMProvider(Protocol):
    """Protocol for LLM providers."""
    
    name: str
    
    def generate(self, prompt: str, context: List[Dict[str, Any]]) -> str:
        """Generate response from prompt."""
        ...
    
    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        context: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate response with tool calling support."""
        ...


class MockCopilotProvider:
    """Deterministic mock provider for offline copilot.
    
    Provides structured responses based on pattern matching without
    requiring an external LLM API. Used for:
    - Offline demo mode
    - Testing tool execution
    - Fallback when LLM unavailable
    """
    
    name = "mock-copilot"
    
    def generate(self, prompt: str, context: List[Dict[str, Any]]) -> str:
        """Generate mock response."""
        return json.dumps({
            "answer": "Based on the available data, I can provide an analysis.",
            "provider": self.name,
            "deterministic": True,
        })
    
    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        context: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate response with tool selection based on prompt patterns."""
        
        query = prompt.lower()
        
        # Pattern-based tool selection
        tool_calls = []
        
        # Cross-case connections
        if "connect" in query and ("case" in query or "cases" in query):
            case_ids = self._extract_case_ids(query)
            if len(case_ids) >= 2:
                tool_calls.append({
                    "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'cross-case')}",
                    "tool_name": ToolName.GET_CROSS_CASE_LINKS.value,
                    "arguments": {"case_ids": case_ids},
                })
        
        # Hidden connectors / ghost nodes
        if "hidden" in query or "ghost" in query or "connector" in query:
            tool_calls.append({
                "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'hidden-connectors')}",
                "tool_name": ToolName.FIND_HIDDEN_CONNECTORS.value,
                "arguments": {},
            })
        
        # Entity search
        if "who is" in query or "find" in query or "search" in query:
            entity_name = self._extract_entity_name(query)
            if entity_name:
                tool_calls.append({
                    "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'search-entities')}",
                    "tool_name": ToolName.SEARCH_ENTITIES.value,
                    "arguments": {"query": entity_name},
                })
        
        # Path finding
        if "path" in query or "connected" in query or "link" in query:
            entities = self._extract_two_entities(query)
            if len(entities) == 2:
                tool_calls.append({
                    "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'find-paths')}",
                    "tool_name": ToolName.FIND_PATHS.value,
                    "arguments": {"source": entities[0], "target": entities[1]},
                })
        
        # Timeline
        if "when" in query or "timeline" in query or "time" in query:
            entity = self._extract_entity_name(query)
            if entity:
                tool_calls.append({
                    "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'timeline')}",
                    "tool_name": ToolName.GET_TIMELINE.value,
                    "arguments": {"entity_id": entity},
                })
        
        # Financial analysis
        if "money" in query or "financial" in query or "transfer" in query or "transaction" in query:
            entity = self._extract_entity_name(query)
            tool_calls.append({
                "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'financial')}",
                "tool_name": ToolName.ANALYZE_FINANCIAL_FLOW.value,
                "arguments": {"entity_id": entity} if entity else {},
            })
        
        # Counterfactual
        if "remove" in query or "what if" in query or "without" in query:
            entity = self._extract_entity_name(query)
            if entity:
                tool_calls.append({
                    "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'counterfactual')}",
                    "tool_name": ToolName.RUN_COUNTERFACTUAL.value,
                    "arguments": {"entity_id": entity},
                })
        
        # Anomalies
        if "anomal" in query or "unusual" in query or "suspicious" in query:
            tool_calls.append({
                "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'anomalies')}",
                "tool_name": ToolName.DETECT_ANOMALIES.value,
                "arguments": {},
            })
        
        # Evidence
        if "evidence" in query:
            entity = self._extract_entity_name(query)
            tool_calls.append({
                "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'evidence')}",
                "tool_name": ToolName.GET_SUPPORTING_EVIDENCE.value,
                "arguments": {"entity_id": entity} if entity else {},
            })
        
        # Centrality / importance
        if "important" in query or "central" in query or "key" in query:
            tool_calls.append({
                "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'centrality')}",
                "tool_name": ToolName.CALCULATE_CENTRALITY.value,
                "arguments": {},
            })
        
        # Default: search entities
        if not tool_calls:
            entity = self._extract_entity_name(query)
            if entity:
                tool_calls.append({
                    "call_id": f"call-{uuid5(COPILOT_NAMESPACE, 'default-search')}",
                    "tool_name": ToolName.SEARCH_ENTITIES.value,
                    "arguments": {"query": entity},
                })
        
        return {
            "tool_calls": tool_calls,
            "reasoning": f"Selected {len(tool_calls)} tool(s) based on query patterns",
            "provider": self.name,
        }
    
    def _extract_case_ids(self, query: str) -> List[str]:
        """Extract case IDs from query."""
        import re
        pattern = r'CASE[-\s]?(\d+)'
        matches = re.findall(pattern, query, re.IGNORECASE)
        return [f"CASE-{m}" for m in matches]
    
    def _extract_entity_name(self, query: str) -> Optional[str]:
        """Extract entity name from query."""
        import re
        # Look for quoted names
        quoted = re.search(r'"([^"]+)"', query)
        if quoted:
            return quoted.group(1)
        # Look for capitalized names
        names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', query)
        # Filter common words
        common = {'Who', 'What', 'When', 'Where', 'Why', 'How', 'The', 'This', 'That', 'Is', 'Are', 'Was', 'Were'}
        for name in names:
            if name not in common:
                return name
        return None
    
    def _extract_two_entities(self, query: str) -> List[str]:
        """Extract two entity names from query."""
        import re
        names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', query)
        common = {'Who', 'What', 'When', 'Where', 'Why', 'How', 'The', 'This', 'That', 'Is', 'Are', 'Was', 'Were', 'And', 'Or', 'Between'}
        filtered = [n for n in names if n not in common]
        return filtered[:2]


@dataclass
class InvestigationCopilot:
    """Tool-based investigation copilot.
    
    This is the main entry point for investigator questions. It provides:
    1. Natural language understanding
    2. Tool selection and execution
    3. Evidence-grounded responses
    4. Transparent reasoning
    
    The copilot NEVER makes enforcement recommendations.
    All outputs are DRAFT_FOR_HUMAN_REVIEW.
    """
    
    graph: nx.MultiDiGraph
    evidence_store: Any
    llm_provider: Optional[LLMProvider] = None
    
    # Tool registry
    _tools: Dict[str, Callable] = field(default_factory=dict)
    _tool_definitions: Dict[str, CopilotTool] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize tools."""
        self._register_tools()
        if self.llm_provider is None:
            self.llm_provider = MockCopilotProvider()
    
    def _register_tools(self):
        """Register all available tools."""
        
        # Entity tools
        self._register_tool(
            ToolName.SEARCH_ENTITIES,
            self._tool_search_entities,
            CopilotTool(
                name=ToolName.SEARCH_ENTITIES.value,
                description="Search for entities by name, type, or attributes",
                parameters={
                    "query": {"type": "string", "description": "Search query"},
                    "entity_type": {"type": "string", "description": "Optional entity type filter"},
                    "limit": {"type": "integer", "description": "Max results (default 10)"},
                },
                required_params=["query"],
            )
        )
        
        self._register_tool(
            ToolName.GET_ENTITY,
            self._tool_get_entity,
            CopilotTool(
                name=ToolName.GET_ENTITY.value,
                description="Get detailed information about a specific entity",
                parameters={
                    "entity_id": {"type": "string", "description": "Entity ID"},
                },
                required_params=["entity_id"],
            )
        )
        
        self._register_tool(
            ToolName.GET_NEIGHBORS,
            self._tool_get_neighbors,
            CopilotTool(
                name=ToolName.GET_NEIGHBORS.value,
                description="Get entities connected to a specific entity",
                parameters={
                    "entity_id": {"type": "string", "description": "Entity ID"},
                    "relationship_types": {"type": "array", "description": "Filter by relationship types"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                required_params=["entity_id"],
            )
        )
        
        # Path tools
        self._register_tool(
            ToolName.FIND_PATHS,
            self._tool_find_paths,
            CopilotTool(
                name=ToolName.FIND_PATHS.value,
                description="Find paths between two entities in the network",
                parameters={
                    "source": {"type": "string", "description": "Source entity ID or name"},
                    "target": {"type": "string", "description": "Target entity ID or name"},
                    "max_hops": {"type": "integer", "description": "Maximum path length"},
                },
                required_params=["source", "target"],
            )
        )
        
        # Analytics tools
        self._register_tool(
            ToolName.CALCULATE_CENTRALITY,
            self._tool_calculate_centrality,
            CopilotTool(
                name=ToolName.CALCULATE_CENTRALITY.value,
                description="Calculate centrality metrics for entities",
                parameters={
                    "entity_id": {"type": "string", "description": "Optional specific entity"},
                    "metric": {"type": "string", "description": "Metric type: pagerank, betweenness, degree"},
                },
                required_params=[],
            )
        )
        
        self._register_tool(
            ToolName.FIND_COMMUNITIES,
            self._tool_find_communities,
            CopilotTool(
                name=ToolName.FIND_COMMUNITIES.value,
                description="Detect communities in the network",
                parameters={
                    "algorithm": {"type": "string", "description": "Algorithm: louvain, label_propagation"},
                },
                required_params=[],
            )
        )
        
        self._register_tool(
            ToolName.DETECT_ANOMALIES,
            self._tool_detect_anomalies,
            CopilotTool(
                name=ToolName.DETECT_ANOMALIES.value,
                description="Detect anomalous patterns in the network",
                parameters={
                    "anomaly_type": {"type": "string", "description": "Type: structural, temporal, financial"},
                },
                required_params=[],
            )
        )
        
        # Intelligence tools
        self._register_tool(
            ToolName.FIND_HIDDEN_CONNECTORS,
            self._tool_find_hidden_connectors,
            CopilotTool(
                name=ToolName.FIND_HIDDEN_CONNECTORS.value,
                description="Identify potential hidden coordinators using structural analysis",
                parameters={
                    "min_score": {"type": "number", "description": "Minimum ghost score threshold"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                required_params=[],
            )
        )
        
        self._register_tool(
            ToolName.ANALYZE_FINANCIAL_FLOW,
            self._tool_analyze_financial_flow,
            CopilotTool(
                name=ToolName.ANALYZE_FINANCIAL_FLOW.value,
                description="Analyze financial transaction patterns",
                parameters={
                    "entity_id": {"type": "string", "description": "Optional entity to focus on"},
                    "pattern_type": {"type": "string", "description": "Pattern: fan_in, fan_out, layering, circular"},
                },
                required_params=[],
            )
        )
        
        # Evidence tools
        self._register_tool(
            ToolName.GET_SUPPORTING_EVIDENCE,
            self._tool_get_supporting_evidence,
            CopilotTool(
                name=ToolName.GET_SUPPORTING_EVIDENCE.value,
                description="Get evidence supporting a finding or entity",
                parameters={
                    "entity_id": {"type": "string", "description": "Entity ID"},
                    "finding_id": {"type": "string", "description": "Finding ID"},
                },
                required_params=[],
            )
        )
        
        self._register_tool(
            ToolName.GET_COUNTER_EVIDENCE,
            self._tool_get_counter_evidence,
            CopilotTool(
                name=ToolName.GET_COUNTER_EVIDENCE.value,
                description="Get evidence that contradicts a finding",
                parameters={
                    "entity_id": {"type": "string", "description": "Entity ID"},
                    "finding_id": {"type": "string", "description": "Finding ID"},
                },
                required_params=[],
            )
        )
        
        # Simulation tools
        self._register_tool(
            ToolName.RUN_COUNTERFACTUAL,
            self._tool_run_counterfactual,
            CopilotTool(
                name=ToolName.RUN_COUNTERFACTUAL.value,
                description="Simulate network changes if an entity is removed",
                parameters={
                    "entity_id": {"type": "string", "description": "Entity to remove"},
                },
                required_params=["entity_id"],
            )
        )
        
        # Timeline tools
        self._register_tool(
            ToolName.GET_TIMELINE,
            self._tool_get_timeline,
            CopilotTool(
                name=ToolName.GET_TIMELINE.value,
                description="Get timeline of events for an entity",
                parameters={
                    "entity_id": {"type": "string", "description": "Entity ID"},
                    "start_date": {"type": "string", "description": "Start date (ISO)"},
                    "end_date": {"type": "string", "description": "End date (ISO)"},
                },
                required_params=["entity_id"],
            )
        )
        
        # Cross-case tools
        self._register_tool(
            ToolName.GET_CROSS_CASE_LINKS,
            self._tool_get_cross_case_links,
            CopilotTool(
                name=ToolName.GET_CROSS_CASE_LINKS.value,
                description="Find connections between multiple cases",
                parameters={
                    "case_ids": {"type": "array", "description": "List of case IDs to compare"},
                },
                required_params=["case_ids"],
            )
        )
    
    def _register_tool(self, name: ToolName, func: Callable, definition: CopilotTool):
        """Register a tool."""
        self._tools[name.value] = func
        self._tool_definitions[name.value] = definition
    
    def ask(self, query: str, context: Optional[Dict[str, Any]] = None) -> CopilotResponse:
        """Process an investigator question.
        
        This is the main entry point. It:
        1. Interprets the query
        2. Selects and executes tools
        3. Synthesizes evidence-grounded response
        
        Args:
            query: Natural language question
            context: Optional additional context
            
        Returns:
            CopilotResponse with evidence-grounded answer
        """
        start_time = datetime.now(timezone.utc)
        response_id = f"RESP-{uuid5(COPILOT_NAMESPACE, query)}"
        
        # Retrieve grounded context using hybrid RAG
        try:
            from src.rag.retriever import HybridRetriever
            retriever = HybridRetriever(
                graph=self.graph,
                evidence_store=self.evidence_store,
            )
            retrieved_chunks = retriever.retrieve(query, context=context or {})
            rag_context = retriever.format_context(retrieved_chunks, max_chars=3000)
            rag_evidence_ids = list({
                eid for c in retrieved_chunks for eid in c.evidence_ids
            })
        except Exception as e:
            logger.debug(f"RAG retrieval failed: {e}")
            rag_context = ""
            rag_evidence_ids = []
        
        # Get tool definitions for LLM
        tools = [t.to_openai_tool() for t in self._tool_definitions.values()]
        
        # Let LLM select tools
        try:
            llm_response = self.llm_provider.generate_with_tools(
                prompt=query,
                tools=tools,
                context=[
                    {"kind": "query", "text": query},
                    {"kind": "retrieved_context", "text": rag_context},
                ] + ([context] if context else []),
            )
        except Exception as e:
            logger.error(f"LLM tool selection failed: {e}")
            return self._error_response(response_id, query, str(e), start_time)
        
        # Execute tools
        tool_results = []
        evidence_ids = set(rag_evidence_ids)
        
        for call in llm_response.get("tool_calls", []):
            tool_name = call.get("tool_name")
            arguments = call.get("arguments", {})
            
            result = self._execute_tool(tool_name, arguments)
            tool_results.append(result)
            evidence_ids.update(result.evidence_ids)
        
        # Synthesize response
        answer = self._synthesize_response(query, tool_results)
        
        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds() * 1000
        
        return CopilotResponse(
            response_id=response_id,
            query=query,
            answer=answer,
            evidence_ids=list(evidence_ids),
            tools_called=tool_results,
            processing_time_ms=processing_time,
            requires_human_review=True,  # Always require human review
        )
    
    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result."""
        import time
        start = time.time()
        
        if tool_name not in self._tools:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
            )
        
        try:
            result_data = self._tools[tool_name](**arguments)
            evidence_ids = result_data.pop("_evidence_ids", [])
            
            return ToolResult(
                tool_name=tool_name,
                success=True,
                data=result_data,
                evidence_ids=evidence_ids,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
            )
    
    def _synthesize_response(self, query: str, tool_results: List[ToolResult]) -> str:
        """Synthesize final response from tool results."""
        
        if not tool_results:
            return "I was unable to retrieve relevant information. Please try rephrasing your question."
        
        # Build response based on successful tools
        parts = []
        evidence_ids = set()
        entities = set()
        
        for result in tool_results:
            if not result.success:
                parts.append(f"- {result.tool_name}: {result.error}")
                continue
            
            evidence_ids.update(result.evidence_ids)
            
            # Format based on tool type
            if result.tool_name == ToolName.SEARCH_ENTITIES.value:
                entities_found = result.data.get("entities", [])
                if entities_found:
                    parts.append(f"Found {len(entities_found)} entities:")
                    for e in entities_found[:5]:
                        entities.add(e.get("label", e.get("id")))
                        parts.append(f"  - {e.get('label', e.get('id'))} ({e.get('type', 'unknown')})")
            
            elif result.tool_name == ToolName.FIND_PATHS.value:
                paths = result.data.get("paths", [])
                if paths:
                    parts.append(f"Found {len(paths)} path(s):")
                    for p in paths[:3]:
                        path_str = " → ".join(p.get("nodes", []))
                        parts.append(f"  - {path_str}")
            
            elif result.tool_name == ToolName.FIND_HIDDEN_CONNECTORS.value:
                ghosts = result.data.get("ghosts", [])
                if ghosts:
                    parts.append(f"Identified {len(ghosts)} potential hidden connector(s):")
                    for g in ghosts[:3]:
                        parts.append(f"  - Score: {g.get('score', 0):.2f}")
                        parts.append(f"    Type: {g.get('subtype', 'unknown')}")
                        parts.append(f"    Communities connected: {g.get('communities_connected', 0)}")
            
            elif result.tool_name == ToolName.CALCULATE_CENTRALITY.value:
                top_entities = result.data.get("top_entities", [])
                if top_entities:
                    parts.append("Top entities by centrality:")
                    for e in top_entities[:5]:
                        parts.append(f"  - {e.get('label')}: {e.get('metric'):.3f}")
            
            elif result.tool_name == ToolName.ANALYZE_FINANCIAL_FLOW.value:
                patterns = result.data.get("patterns", [])
                if patterns:
                    parts.append("Financial patterns detected:")
                    for p in patterns[:5]:
                        parts.append(f"  - {p.get('type')}: {p.get('description')}")
            
            elif result.tool_name == ToolName.GET_TIMELINE.value:
                events = result.data.get("events", [])
                if events:
                    parts.append(f"Timeline ({len(events)} events):")
                    for ev in events[:10]:
                        parts.append(f"  - {ev.get('timestamp')}: {ev.get('type')} - {ev.get('summary', '')}")
            
            elif result.tool_name == ToolName.RUN_COUNTERFACTUAL.value:
                impact = result.data.get("impact", {})
                parts.append("Counterfactual simulation results:")
                parts.append(f"  - Network fragmentation: {impact.get('fragmentation_change', 0):.1%}")
                parts.append(f"  - Communities affected: {impact.get('communities_affected', 0)}")
                parts.append(f"  - Shortest paths changed: {impact.get('paths_affected', 0)}")
            
            elif result.tool_name == ToolName.GET_CROSS_CASE_LINKS.value:
                links = result.data.get("links", [])
                if links:
                    parts.append(f"Found {len(links)} cross-case connection(s):")
                    for link in links[:5]:
                        parts.append(f"  - Shared entity: {link.get('entity')}")
                        parts.append(f"    Cases: {', '.join(link.get('cases', []))}")
            
            else:
                # Generic data display
                data_str = json.dumps(result.data, indent=2)[:500]
                parts.append(f"{result.tool_name}:\n{data_str}")
        
        # Build final answer
        answer = "\n".join(parts)
        
        # Add evidence citation
        if evidence_ids:
            answer += f"\n\n**Evidence referenced:** {len(evidence_ids)} record(s)"
        
        # Add human review reminder
        answer += "\n\n*Status: DRAFT FOR HUMAN REVIEW*"
        
        return answer
    
    def _error_response(
        self,
        response_id: str,
        query: str,
        error: str,
        start_time: datetime,
    ) -> CopilotResponse:
        """Create an error response."""
        return CopilotResponse(
            response_id=response_id,
            query=query,
            answer=f"I encountered an error while processing your question: {error}",
            status="UNKNOWN",
            processing_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000,
        )
    
    # ================== TOOL IMPLEMENTATIONS ==================
    
    def _tool_search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Search for entities in the graph."""
        results = []
        evidence_ids = []
        
        query_lower = query.lower()
        
        for node_id, node_data in self.graph.nodes(data=True):
            label = node_data.get("canonical_name") or node_data.get("label") or str(node_id)
            node_type = node_data.get("entity_type", "UNKNOWN")
            
            # Filter by type if specified
            if entity_type and node_type != entity_type:
                continue
            
            # Match by name
            if query_lower in label.lower():
                results.append({
                    "id": node_id,
                    "label": label,
                    "type": node_type,
                    "metrics": node_data.get("metrics", {}),
                })
                
                # Collect evidence
                if ev_ids := node_data.get("source_evidence_ids"):
                    evidence_ids.extend(ev_ids if isinstance(ev_ids, list) else [ev_ids])
            
            if len(results) >= limit:
                break
        
        return {"entities": results, "_evidence_ids": evidence_ids}
    
    def _tool_get_entity(self, entity_id: str) -> Dict[str, Any]:
        """Get detailed entity information."""
        if entity_id not in self.graph:
            return {"error": f"Entity {entity_id} not found", "_evidence_ids": []}
        
        node_data = dict(self.graph.nodes[entity_id])
        evidence_ids = node_data.get("source_evidence_ids", [])
        
        return {
            "id": entity_id,
            "label": node_data.get("canonical_name") or node_data.get("label", entity_id),
            "type": node_data.get("entity_type", "UNKNOWN"),
            "aliases": node_data.get("aliases", []),
            "metrics": node_data.get("metrics", {}),
            "attributes": {k: v for k, v in node_data.items() if k not in ["metrics", "aliases"]},
            "_evidence_ids": evidence_ids if isinstance(evidence_ids, list) else [evidence_ids],
        }
    
    def _tool_get_neighbors(
        self,
        entity_id: str,
        relationship_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Get neighbors of an entity."""
        if entity_id not in self.graph:
            return {"neighbors": [], "_evidence_ids": []}
        
        neighbors = []
        evidence_ids = []
        
        for _, tgt, key, data in self.graph.out_edges(entity_id, keys=True, data=True):
            rel_type = data.get("relation", "UNKNOWN")
            if relationship_types and rel_type not in relationship_types:
                continue
            
            neighbor_data = self.graph.nodes.get(tgt, {})
            neighbors.append({
                "id": tgt,
                "label": neighbor_data.get("canonical_name") or neighbor_data.get("label", tgt),
                "type": neighbor_data.get("entity_type", "UNKNOWN"),
                "relationship": rel_type,
            })
            
            if ev_ids := data.get("source_evidence_ids"):
                evidence_ids.extend(ev_ids if isinstance(ev_ids, list) else [ev_ids])
        
        for src, _, key, data in self.graph.in_edges(entity_id, keys=True, data=True):
            rel_type = data.get("relation", "UNKNOWN")
            if relationship_types and rel_type not in relationship_types:
                continue
            
            neighbor_data = self.graph.nodes.get(src, {})
            neighbors.append({
                "id": src,
                "label": neighbor_data.get("canonical_name") or neighbor_data.get("label", src),
                "type": neighbor_data.get("entity_type", "UNKNOWN"),
                "relationship": rel_type,
                "direction": "incoming",
            })
        
        return {"neighbors": neighbors[:limit], "_evidence_ids": evidence_ids}
    
    def _tool_find_paths(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> Dict[str, Any]:
        """Find paths between two entities."""
        # Resolve names to IDs
        source_id = self._resolve_entity_id(source)
        target_id = self._resolve_entity_id(target)
        
        if not source_id or not target_id:
            return {"paths": [], "_evidence_ids": [], "error": "Could not resolve entity names"}
        
        try:
            paths = list(nx.all_shortest_paths(self.graph, source_id, target_id))[:5]
        except nx.NetworkXNoPath:
            return {"paths": [], "_evidence_ids": []}
        
        formatted_paths = []
        for path in paths:
            nodes = []
            for n in path:
                node_data = self.graph.nodes.get(n, {})
                nodes.append(node_data.get("canonical_name") or node_data.get("label", n))
            formatted_paths.append({"nodes": nodes, "length": len(path) - 1})
        
        return {"paths": formatted_paths, "_evidence_ids": []}
    
    def _resolve_entity_id(self, name_or_id: str) -> Optional[str]:
        """Resolve entity name or ID to graph node ID."""
        if name_or_id in self.graph:
            return name_or_id
        
        # Search by name
        name_lower = name_or_id.lower()
        for node_id, node_data in self.graph.nodes(data=True):
            label = node_data.get("canonical_name") or node_data.get("label", "")
            if name_lower in label.lower():
                return node_id
        
        return None
    
    def _tool_calculate_centrality(
        self,
        entity_id: Optional[str] = None,
        metric: str = "pagerank",
    ) -> Dict[str, Any]:
        """Calculate centrality metrics."""
        # Use NetworkX centrality functions with fallback
        try:
            if metric == "pagerank":
                centrality = nx.pagerank(self.graph)
            elif metric == "betweenness":
                centrality = nx.betweenness_centrality(self.graph)
            else:
                centrality = nx.degree_centrality(self.graph)
        except (ImportError, Exception) as e:
            logger.warning(f"Centrality calculation failed, using degree centrality: {e}")
            # Fallback to degree centrality which doesn't need scipy
            centrality = nx.degree_centrality(self.graph)
            metric = "degree"
        
        # Sort by centrality
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        top_entities = []
        for node_id, score in sorted_nodes[:10]:
            node_data = self.graph.nodes.get(node_id, {})
            top_entities.append({
                "id": node_id,
                "label": node_data.get("canonical_name") or node_data.get("label", node_id),
                "metric": score,
            })
        
        if entity_id:
            entity_score = centrality.get(entity_id, 0)
            return {
                "entity_id": entity_id,
                "metric": metric,
                "score": entity_score,
                "top_entities": top_entities,
                "_evidence_ids": [],
            }
        
        return {"top_entities": top_entities, "metric": metric, "_evidence_ids": []}
    
    def _tool_find_communities(self, algorithm: str = "louvain") -> Dict[str, Any]:
        """Detect communities in the network."""
        from src.graph.analytics import detect_communities
        
        communities = detect_communities(self.graph, algorithm=algorithm)
        
        formatted = []
        for i, community in enumerate(communities[:10]):
            members = []
            for node_id in list(community)[:5]:
                node_data = self.graph.nodes.get(node_id, {})
                members.append(node_data.get("canonical_name") or node_data.get("label", node_id))
            formatted.append({
                "id": i,
                "size": len(community),
                "sample_members": members,
            })
        
        return {"communities": formatted, "algorithm": algorithm, "_evidence_ids": []}
    
    def _tool_detect_anomalies(
        self,
        anomaly_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Detect anomalous patterns."""
        # Use ghost nodes as structural anomalies
        anomalies = []
        evidence_ids = []
        
        # Check for ghost predictions
        try:
            from src.graph.ghost_nodes import get_ghost_nodes
            ghosts = get_ghost_nodes()
            
            for ghost in ghosts[:10]:
                anomalies.append({
                    "type": "structural_hidden_connector",
                    "entity": ghost.get("ghost_id"),
                    "score": ghost.get("confidence", 0),
                    "description": f"Potential hidden connector with score {ghost.get('confidence', 0):.2f}",
                })
                evidence_ids.extend(ghost.get("evidence_ids", []))
        except Exception as e:
            logger.debug(f"Could not load ghost nodes: {e}")
        
        return {"anomalies": anomalies, "_evidence_ids": evidence_ids}
    
    def _tool_find_hidden_connectors(
        self,
        min_score: float = 0.5,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Find potential hidden connectors using ghost analysis."""
        ghosts = []
        evidence_ids = []
        
        try:
            from src.graph.ghost_nodes import get_ghost_nodes
            all_ghosts = get_ghost_nodes()
            
            for ghost in all_ghosts:
                score = ghost.get("confidence", 0)
                if score >= min_score:
                    ghosts.append({
                        "ghost_id": ghost.get("ghost_id"),
                        "score": score,
                        "subtype": ghost.get("subtype", "unknown"),
                        "communities_connected": ghost.get("communities_connected", 0),
                        "evidence_ids": ghost.get("evidence_ids", []),
                    })
                    evidence_ids.extend(ghost.get("evidence_ids", []))
        except Exception as e:
            logger.error(f"Ghost node retrieval failed: {e}")
        
        ghosts = sorted(ghosts, key=lambda x: x["score"], reverse=True)[:limit]
        
        return {"ghosts": ghosts, "_evidence_ids": evidence_ids}
    
    def _tool_analyze_financial_flow(
        self,
        entity_id: Optional[str] = None,
        pattern_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze financial transaction patterns using enhanced analyzer.
        
        Detects: fan-in, fan-out, layering, circular flow,
        rapid pass-through, dormant activation, transaction bursts.
        """
        from src.analysis.financial_analysis import FinancialAnalyzer
        
        try:
            analyzer = FinancialAnalyzer(graph=self.graph)
            report = analyzer.analyze(
                source=entity_id,
                max_hops=6,
            )
            
            # Convert signals to copilot format
            patterns = []
            evidence_ids = []
            
            for signal in report.signals:
                patterns.append({
                    "type": signal.signal_type,
                    "description": signal.description,
                    "entities": signal.entities,
                    "confidence": signal.confidence,
                    "transactions": signal.transactions_involved,
                })
                evidence_ids.extend(signal.evidence_ids)
            
            # Add aggregated flows as context
            top_flows = []
            for flow in report.aggregated_flows[:10]:
                top_flows.append({
                    "from": flow.source_label or flow.source,
                    "to": flow.target_label or flow.target,
                    "amount": flow.total_amount,
                    "count": flow.transaction_count,
                })
                evidence_ids.extend(flow.evidence_ids)
            
            # Add path information
            paths = []
            for path in report.paths[:5]:
                hops = [h.get("label", h.get("node", "")) for h in path.hops]
                paths.append({
                    "route": " → ".join(hops),
                    "amount": path.total_amount,
                    "hops": path.hop_count,
                })
                evidence_ids.extend(path.evidence_ids)
            
            return {
                "patterns": patterns,
                "top_flows": top_flows,
                "paths": paths,
                "summary": report.summary,
                "_evidence_ids": list(set(evidence_ids)),
            }
        except Exception as e:
            logger.warning(f"Enhanced financial analysis failed: {e}")
            # Fallback to basic analysis
            return self._tool_analyze_financial_flow_basic(entity_id)

    def _tool_get_supporting_evidence(
        self,
        entity_id: Optional[str] = None,
        finding_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get supporting evidence."""
        evidence = []
        evidence_ids = []
        
        if entity_id and entity_id in self.graph:
            node_data = self.graph.nodes[entity_id]
            ev_ids = node_data.get("source_evidence_ids", [])
            evidence_ids.extend(ev_ids if isinstance(ev_ids, list) else [ev_ids])
            
            for ev_id in evidence_ids[:10]:
                evidence.append({
                    "id": ev_id,
                    "type": "entity_evidence",
                    "entity": entity_id,
                })
        
        return {"evidence": evidence, "_evidence_ids": evidence_ids}
    
    def _tool_get_counter_evidence(
        self,
        entity_id: Optional[str] = None,
        finding_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get counter-evidence."""
        # This would integrate with the counter-evidence engine
        # For now, return empty
        return {"counter_evidence": [], "_evidence_ids": []}
    
    def _tool_run_counterfactual(self, entity_id: str) -> Dict[str, Any]:
        """Run counterfactual simulation."""
        from src.graph.simulation import simulate_node_removal
        
        try:
            result = simulate_node_removal(self.graph, entity_id)
            
            return {
                "impact": {
                    "fragmentation_change": result.get("fragmentation_change", 0),
                    "communities_affected": result.get("communities_affected", 0),
                    "paths_affected": result.get("paths_affected", 0),
                },
                "_evidence_ids": [],
            }
        except Exception as e:
            logger.error(f"Counterfactual simulation failed: {e}")
            return {"error": str(e), "_evidence_ids": []}
    
    def _tool_get_timeline(
        self,
        entity_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get timeline of events for an entity."""
        events = []
        evidence_ids = []
        
        # Get edges involving this entity
        for src, tgt, key, data in self.graph.out_edges(entity_id, keys=True, data=True):
            attrs = data.get("attributes", {})
            timestamp = attrs.get("timestamp") or attrs.get("observed_at")
            
            if timestamp:
                events.append({
                    "timestamp": timestamp,
                    "type": data.get("relation", "UNKNOWN"),
                    "summary": f"{src} → {tgt}",
                    "edge_id": key,
                })
            
            if ev_ids := data.get("source_evidence_ids"):
                evidence_ids.extend(ev_ids if isinstance(ev_ids, list) else [ev_ids])
        
        # Sort by timestamp
        events.sort(key=lambda x: x.get("timestamp", ""))
        
        return {"events": events[:50], "_evidence_ids": evidence_ids}
    
    def _tool_get_cross_case_links(self, case_ids: List[str]) -> Dict[str, Any]:
        """Find connections between cases."""
        links = []
        evidence_ids = []
        
        # Find entities that appear in multiple cases
        entity_cases = {}
        
        for case_id in case_ids:
            # Find entities in this case
            case_entities = set()
            for node_id, node_data in self.graph.nodes(data=True):
                cases = node_data.get("cases", [])
                if case_id in cases:
                    case_entities.add(node_id)
            
            for entity_id in case_entities:
                if entity_id not in entity_cases:
                    entity_cases[entity_id] = []
                entity_cases[entity_id].append(case_id)
        
        # Find shared entities
        for entity_id, cases in entity_cases.items():
            if len(cases) > 1:
                node_data = self.graph.nodes.get(entity_id, {})
                links.append({
                    "entity": node_data.get("canonical_name") or node_data.get("label", entity_id),
                    "entity_id": entity_id,
                    "cases": cases,
                })
                
                if ev_ids := node_data.get("source_evidence_ids"):
                    evidence_ids.extend(ev_ids if isinstance(ev_ids, list) else [ev_ids])
        
        return {"links": links, "_evidence_ids": evidence_ids}
    
    def get_available_tools(self) -> List[CopilotTool]:
        """Get list of available tools."""
        return list(self._tool_definitions.values())
