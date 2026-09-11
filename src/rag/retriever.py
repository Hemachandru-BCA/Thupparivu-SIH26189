"""Hybrid RAG Retriever.

Implements hybrid retrieval combining:
- Keyword retrieval (deterministic)
- Vector retrieval (if embeddings available)
- Graph neighborhood retrieval (NetworkX)
- Temporal filtering

This ensures the copilot retrieves evidence-grounded context
without depending on expensive external APIs.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    """A retrieved context chunk with grounding metadata."""
    model_config = ConfigDict(extra="forbid")
    
    chunk_id: str = Field(..., description="Unique chunk ID")
    content: str = Field(..., description="Chunk content")
    source_type: str = Field(..., description="Source: evidence, node, edge, document")
    source_id: str = Field(..., description="Source record ID")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs referenced")
    
    # Retrieval metadata
    retrieval_method: str = Field(..., description="How chunk was retrieved")
    score: float = Field(0.0, ge=0.0, le=1.0, description="Relevance score")
    entity_ids: List[str] = Field(default_factory=list, description="Entities involved")
    
    # Temporal
    timestamp: Optional[str] = Field(None, description="Event/record timestamp")


@dataclass
class HybridRetriever:
    """Hybrid retrieval engine combining multiple retrieval strategies.
    
    Retrieval pipeline:
    1. Intent parsing (extract entities/cases/dates from query)
    2. Keyword retrieval (evidence store search)
    3. Graph neighborhood retrieval (entity expansion)
    4. Temporal filtering
    5. Reranking (combine scores)
    6. Return bounded context
    """
    
    graph: nx.MultiDiGraph
    evidence_store: Any = None
    
    # Limits
    max_chunks: int = 20
    max_hops: int = 2
    max_neighbors: int = 15
    
    def retrieve(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[RetrievedChunk]:
        """Retrieve grounded context for a query.
        
        Args:
            query: User query
            context: Optional context (entity_id, case_ids, filters)
            
        Returns:
            Ranked list of retrieved chunks
        """
        if context is None:
            context = {}
        
        # 1. Parse intent: extract entity names, case IDs, dates
        entities = self._extract_entities(query)
        case_ids = self._extract_case_ids(query)
        
        # 2. Keyword retrieval from evidence store
        keyword_chunks = self._keyword_retrieve(query)
        
        # 3. Graph retrieval for each entity
        graph_chunks = []
        for entity in entities[:3]:
            graph_chunks.extend(self._graph_retrieve(entity))
        
        # 4. Case-based retrieval
        case_chunks = []
        for case_id in case_ids:
            case_chunks.extend(self._case_retrieve(case_id))
        
        # 5. Combine and deduplicate
        combined: Dict[str, RetrievedChunk] = {}
        for chunk in keyword_chunks + graph_chunks + case_chunks:
            if chunk.chunk_id not in combined:
                combined[chunk.chunk_id] = chunk
        
        # 6. Apply temporal filter if requested
        if context.get("start_date") or context.get("end_date"):
            combined = {
                cid: c for cid, c in combined.items()
                if self._in_time_window(c, context)
            }
        
        # 7. Sort by score and limit
        chunks = sorted(combined.values(), key=lambda c: c.score, reverse=True)
        return chunks[: self.max_chunks]
    
    def _keyword_retrieve(self, query: str) -> List[RetrievedChunk]:
        """Keyword-based retrieval from evidence store."""
        chunks = []
        
        if self.evidence_store is None:
            return chunks
        
        try:
            # Search evidence store for matching records
            results = self.evidence_store.search(query, limit=10)
            
            for record in results:
                content = getattr(record, "content", None) or getattr(record, "text", "")
                record_id = getattr(record, "id", None) or getattr(record, "evidence_id", "")
                if not record_id:
                    continue
                
                chunk_id = f"KW-{hashlib.md5(f'{record_id}:{query}'.encode()).hexdigest()[:12]}"
                chunks.append(RetrievedChunk(
                    chunk_id=chunk_id,
                    content=content if isinstance(content, str) else str(content),
                    source_type="evidence",
                    source_id=record_id,
                    evidence_ids=[record_id],
                    retrieval_method="keyword",
                    score=0.7,
                ))
        except Exception as e:
            logger.debug(f"Keyword retrieval failed: {e}")
        
        return chunks
    
    def _graph_retrieve(self, entity: str) -> List[RetrievedChunk]:
        """Retrieve graph context around an entity."""
        chunks = []
        entity_id = self._resolve_entity(entity)
        
        if not entity_id:
            return chunks
        
        # Get entity node
        node_data = self.graph.nodes.get(entity_id, {})
        label = node_data.get("canonical_name") or node_data.get("label", entity_id)
        
        # Entity chunk
        evidence_ids = node_data.get("source_evidence_ids", [])
        chunks.append(RetrievedChunk(
            chunk_id=f"GR-{entity_id}",
            content=(
                f"Entity: {label}\n"
                f"Type: {node_data.get('entity_type', 'UNKNOWN')}\n"
                f"Evidence: {', '.join(evidence_ids) if evidence_ids else 'None linked'}"
            ),
            source_type="node",
            source_id=entity_id,
            evidence_ids=evidence_ids if isinstance(evidence_ids, list) else [],
            retrieval_method="graph_neighborhood",
            score=0.9,
            entity_ids=[entity_id],
        ))
        
        # Neighbors within hops
        visited: Set[str] = {entity_id}
        frontier = [entity_id]
        
        for _ in range(self.max_hops):
            next_frontier = []
            for current in frontier:
                for neighbor in self.graph.neighbors(current):
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
                    
                    n_data = self.graph.nodes.get(neighbor, {})
                    n_label = n_data.get("canonical_name") or n_data.get("label", neighbor)
                    n_evidence = n_data.get("source_evidence_ids", [])
                    
                    # Relationship info
                    rels = []
                    if self.graph.has_edge(current, neighbor):
                        for k, ed in self.graph[current][neighbor].items():
                            rel = ed.get("relation", "UNKNOWN")
                            rels.append(rel)
                    
                    chunks.append(RetrievedChunk(
                        chunk_id=f"GR-{entity_id}-{neighbor}",
                        content=(
                            f"Connected entity: {n_label} "
                            f"({n_data.get('entity_type', 'UNKNOWN')})\n"
                            f"Relationship: {', '.join(rels[:3])}\n"
                            f"Linked to: {label}"
                        ),
                        source_type="edge",
                        source_id=f"{entity_id}-{neighbor}",
                        evidence_ids=n_evidence if isinstance(n_evidence, list) else [],
                        retrieval_method="graph_neighborhood",
                        score=0.85 / (visited.__len__() if hasattr(visited, "__len__") else 2),
                        entity_ids=[entity_id, neighbor],
                    ))
                    
                    if len(next_frontier) >= self.max_neighbors:
                        break
                if len(chunks) >= self.max_chunks:
                    break
            frontier = next_frontier[: self.max_neighbors]
            if not frontier:
                break
        
        return chunks[: self.max_chunks]
    
    def _case_retrieve(self, case_id: str) -> List[RetrievedChunk]:
        """Retrieve context for a case."""
        chunks = []
        
        for node_id, node_data in self.graph.nodes(data=True):
            cases = node_data.get("cases", [])
            if not isinstance(cases, list):
                cases = [cases]
            
            if case_id in cases:
                label = node_data.get("canonical_name") or node_data.get("label", node_id)
                evidence_ids = node_data.get("source_evidence_ids", [])
                
                chunks.append(RetrievedChunk(
                    chunk_id=f"CS-{case_id}-{node_id}",
                    content=f"Entity in {case_id}: {label} ({node_data.get('entity_type', 'UNKNOWN')})",
                    source_type="node",
                    source_id=node_id,
                    evidence_ids=evidence_ids if isinstance(evidence_ids, list) else [],
                    retrieval_method="case_context",
                    score=0.75,
                    entity_ids=[node_id],
                ))
        
        return chunks
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract entity names from query."""
        # Quoted names
        quoted = re.findall(r'"([^"]+)"', query)
        if quoted:
            return quoted[:3]
        
        # Capitalized names
        names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', query)
        common = {'Who', 'What', 'When', 'Where', 'Why', 'How', 'The', 'This',
                  'That', 'These', 'Those', 'Find', 'Show', 'Give', 'Tell', 'Is',
                  'Are', 'Was', 'Were', 'Has', 'Have', 'Had', 'Case', 'Case-',
                  'Between', 'And', 'Analyze', 'Analyse', 'List', 'Which'}
        return [n for n in names if n not in common][:3]
    
    def _extract_case_ids(self, query: str) -> List[str]:
        """Extract case IDs from query."""
        pattern = r'CASE[-\s]?(\d+)'
        matches = re.findall(pattern, query, re.IGNORECASE)
        return [f"CASE-{m}" for m in matches][:3]
    
    def _resolve_entity(self, name: str) -> Optional[str]:
        """Resolve entity name to graph node ID."""
        if name in self.graph:
            return name
        
        name_lower = name.lower()
        for node_id, node_data in self.graph.nodes(data=True):
            label = node_data.get("canonical_name") or node_data.get("label", "")
            if label and name_lower in str(label).lower():
                return node_id
        return None
    
    def _in_time_window(self, chunk: RetrievedChunk, context: Dict[str, Any]) -> bool:
        """Check if chunk falls in requested time window."""
        if not chunk.timestamp:
            return True
        
        try:
            ts = datetime.fromisoformat(chunk.timestamp)
            
            if start := context.get("start_date"):
                start_ts = datetime.fromisoformat(start)
                if ts < start_ts:
                    return False
            
            if end := context.get("end_date"):
                end_ts = datetime.fromisoformat(end)
                if ts > end_ts:
                    return False
        except Exception:
            return True
        
        return True
    
    def format_context(self, chunks: List[RetrievedChunk], max_chars: int = 4000) -> str:
        """Format retrieved chunks into a bounded context string.
        
        This is the bounded context that gets sent to the LLM/copilot.
        Never sends the entire graph - only the retrieved subgraph evidence.
        """
        parts = []
        char_count = 0
        
        for chunk in chunks:
            block = f"[{chunk.source_type}:{chunk.source_id}]\n{chunk.content}"
            if chunk.evidence_ids:
                block += f"\nEvidence: {', '.join(chunk.evidence_ids[:5])}"
            block += f"\n(score: {chunk.score:.2f}, method: {chunk.retrieval_method})"
            
            if char_count + len(block) > max_chars:
                break
            
            parts.append(block)
            char_count += len(block)
        
        return "\n\n".join(parts) if parts else "No relevant context found."