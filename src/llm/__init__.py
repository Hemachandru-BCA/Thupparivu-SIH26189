"""Investigation Copilot - Tool-based LLM assistant for investigators.

This module implements a tool-based architecture where:
1. Investigator asks natural language questions
2. LLM interprets and selects appropriate tools
3. Tools execute deterministically against graph/evidence
4. LLM summarizes verified results with evidence citations

CRITICAL: The LLM never directly accesses or mutates the graph.
All data access goes through deterministic, auditable tools.
"""

from src.llm.copilot import (
    InvestigationCopilot,
    CopilotTool,
    CopilotResponse,
    ToolResult,
)

__all__ = [
    "InvestigationCopilot",
    "CopilotTool",
    "CopilotResponse",
    "ToolResult",
]
