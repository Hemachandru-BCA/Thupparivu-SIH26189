"""
nl_query.py
-----------
Natural Language Analyst Query Engine (P2.2).

Converts natural language questions into structured analytical queries,
then executes them deterministically against the graph/evidence/index.

This is NOT a chatbot.  It is:
  NL → Structured Query → Deterministic Execution

Supported query categories:
  - Entity queries (who is connected to X?)
  - Relationship queries (show financial relationships involving X)
  - Temporal queries (what changed after date Y?)
  - Evidence queries (what evidence supports connection X1↔X2?)
  - Cross-case queries (which cases contain this phone number?)
  - Network queries (who connects communities C1 and C4?)
  - Financial queries (show money flows from A to B)
  - Motif queries (find fan-out patterns involving X)
  - Contradiction queries (what evidence contradicts this hypothesis?)
  - Geographic queries (which entities near location X?)

Includes MockAnalystQueryProvider for deterministic offline demos.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "nl-query-1.0.0"


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class StructuredQuery(BaseModel):
    intent: str = ""
    entities: List[str] = Field(default_factory=list)
    entity_labels: List[str] = Field(default_factory=list)
    relationship_types: List[str] = Field(default_factory=list)
    time_range: Optional[Dict[str, str]] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    case_scope: Optional[str] = None
    evidence_required: bool = False
    max_results: int = 25
    original_query: str = ""


class QueryInterpretation(BaseModel):
    original_query: str
    structured: StructuredQuery
    confidence: float = 0.0
    ambiguity_notes: List[str] = Field(default_factory=list)
    alternatives: List[Dict[str, str]] = Field(default_factory=list)


class QueryResultItem(BaseModel):
    item_id: str = ""
    item_type: str = ""    # ENTITY | RELATIONSHIP | EVIDENCE | MOTIF | CASE | LOCATION
    label: str = ""
    detail: str = ""
    evidence_ids: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResult(BaseModel):
    query: QueryInterpretation
    results: List[QueryResultItem] = Field(default_factory=list)
    total: int = 0
    execution_time_ms: float = 0.0
    limitations: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Pattern-based intent parser (deterministic, no LLM)
# --------------------------------------------------------------------------- #

_INTENT_PATTERNS = [
    # Entity connections
    (r"(?:who|what).*(?:connected|connect|link|relate).*(?:to|with)\s+(\S+)", "entity_neighbors"),
    (r"(?:show|find|list).*(?:connected|connections|neighbors).*(?:of|to|around)\s+(\S+)", "entity_neighbors"),

    # Financial
    (r"(?:financial|money|fund|transfer|transaction).*(?:from|of|involving)\s+(\S+)", "financial_flow"),
    (r"(?:show|trace|follow).*(?:money|fund|financial|transaction).*(?:from|of)\s+(\S+)", "financial_flow"),

    # Temporal
    (r"(?:what|which).*(?:changed|change|happen|happened).*(?:after|since|before|during)\s+(.+)", "temporal_change"),
    (r"(?:replay|timeline|evolution).*(?:after|since|before|around)\s+(.+)", "temporal_replay"),

    # Evidence
    (r"(?:evidence|record|support|back).*(?:for|of|between)\s+(.+)", "evidence_lookup"),
    (r"(?:contradict|counter|weaken).*(?:evidence|proof|claim)\s+(.+)", "contradiction_lookup"),

    # Community / bridge
    (r"(?:who|which).*(?:bridge|connect|link).*(?:communities|groups|clusters)\s+(.+)", "community_bridge"),

    # Cross-case
    (r"(?:which|what).*(?:case|cases).*(?:contain|include|have)\s+(.+)", "cross_case_search"),

    # Motif
    (r"(?:find|show|detect).*(?:fan-in|fan-out|hub|broker|chain|ring|cycle|motif).*" + r"(?:for|of|involving|around)\s+(\S+)", "motif_search"),

    # Geographic
    (r"(?:where|location|place|area|map).*(?:of|for|near|around)\s+(.+)", "geo_lookup"),

    # General entity lookup
    (r"(?:who|what)\s+is\s+(\S+)", "entity_lookup"),
    (r"(?:tell|show|find)\s+(?:me\s+)?(?:about)\s+(\S+)", "entity_lookup"),
]


def _extract_entity_refs(query_lower: str) -> List[str]:
    """Extract entity references like P-0172, CASE-0421, etc."""
    patterns = [
        r'(P-\d{4})',
        r'(CASE-\d{4})',
        r'(C\d+)',
        r'([A-Z]{2,3}-\d{3,6})',
    ]
    refs = []
    for p in patterns:
        refs.extend(re.findall(p, query_lower, re.IGNORECASE))
    return refs


def _extract_time_range(query_lower: str) -> Optional[Dict[str, str]]:
    """Extract time references."""
    # Simple date patterns
    year_match = re.search(r'(20\d{2})', query_lower)
    month_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s*(20\d{2})?', query_lower)
    if month_match:
        month_name = month_match.group(1)
        month_num = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }.get(month_name, "01")
        year = month_match.group(2) or "2025"
        return {"start": f"{year}-{month_num}-01T00:00:00", "end": f"{year}-{month_num}-28T23:59:59"}
    elif year_match:
        year = year_match.group(1)
        return {"start": f"{year}-01-01T00:00:00", "end": f"{year}-12-31T23:59:59"}

    # "last 90 days" / "last 30 days"
    days_match = re.search(r'last\s+(\d+)\s+days?', query_lower)
    if days_match:
        return {"window_days": days_match.group(1)}

    return None


def _extract_relationship_types(query_lower: str) -> List[str]:
    """Extract relationship type keywords."""
    types = []
    if any(w in query_lower for w in ("financial", "money", "fund", "transfer", "transaction")):
        types.extend(["TRANSFERRED_TO", "TRANSFERRED_FUNDS", "USES_ACCOUNT"])
    if any(w in query_lower for w in ("communication", "call", "phone", "sms", "whatsapp")):
        types.extend(["CALLED", "SMS", "WHATSAPP", "COMMUNICATED_WITH"])
    if any(w in query_lower for w in ("meeting", "met", "meeting")):
        types.append("MEETING")
    if any(w in query_lower for w in ("location", "located", "near", "place")):
        types.extend(["LOCATED_AT", "OCCURRED_AT"])
    return types


# --------------------------------------------------------------------------- #
# Query planner
# --------------------------------------------------------------------------- #

class NLQueryEngine:
    """Natural language to structured query engine."""

    def __init__(self, graph: nx.MultiDiGraph, evidence_store: Optional[Any] = None) -> None:
        self.graph = graph
        self.evidence_store = evidence_store

    def _find_entity_by_label(self, label: str) -> Optional[str]:
        """Find entity ID by partial label match."""
        label_lower = label.lower().strip()
        # Exact match first
        for n, d in self.graph.nodes(data=True):
            name = (d.get("canonical_name") or d.get("label") or "").lower()
            if name == label_lower:
                return n
        # Partial match
        for n, d in self.graph.nodes(data=True):
            name = (d.get("canonical_name") or d.get("label") or "").lower()
            if label_lower in name or name in label_lower:
                return n
        return None

    def parse(self, query: str) -> QueryInterpretation:
        """Parse natural language into structured query."""
        query_lower = query.lower().strip()
        entities = _extract_entity_refs(query_lower)
        entity_labels = []
        time_range = _extract_time_range(query_lower)
        rel_types = _extract_relationship_types(query_lower)

        # Intent detection
        intent = "general_search"
        matched_group = None
        for pattern, i in _INTENT_PATTERNS:
            m = re.search(pattern, query_lower)
            if m:
                intent = i
                matched_group = m
                break

        # If no entity refs found, try to extract from pattern group
        if not entities and matched_group:
            raw = matched_group.group(1) if matched_group.lastindex else ""
            if raw:
                # Try to resolve as entity ID or label
                entity_id = self._find_entity_by_label(raw)
                if entity_id:
                    entities = [entity_id]
                    entity_labels = [raw]
                else:
                    entities = [raw]
                    entity_labels = [raw]

        # Build structured query
        sq = StructuredQuery(
            intent=intent,
            entities=entities,
            entity_labels=entity_labels,
            relationship_types=rel_types,
            time_range=time_range,
            case_scope=None,
            evidence_required="evidence" in query_lower,
            max_results=25,
            original_query=query,
        )

        # Ambiguity check
        ambiguity = []
        if intent == "general_search":
            ambiguity.append("Could not determine a specific analytical intent. Showing general results.")
        if not entities:
            ambiguity.append("No specific entity reference found. Results are broad.")

        return QueryInterpretation(
            original_query=query,
            structured=sq,
            confidence=0.9 if entities and intent != "general_search" else 0.5,
            ambiguity_notes=ambiguity,
        )

    def execute(self, interpretation: QueryInterpretation) -> QueryResult:
        """Execute a structured query against the graph."""
        import time
        t0 = time.monotonic()

        sq = interpretation.structured
        results: List[QueryResultItem] = []

        if sq.intent == "entity_neighbors" and sq.entities:
            results = self._query_entity_neighbors(sq)
        elif sq.intent == "financial_flow":
            results = self._query_financial_flow(sq)
        elif sq.intent == "entity_lookup":
            results = self._query_entity_lookup(sq)
        elif sq.intent == "community_bridge":
            results = self._query_bridges(sq)
        elif sq.intent == "evidence_lookup":
            results = self._query_evidence(sq)
        elif sq.intent == "contradiction_lookup":
            results = self._query_contradictions(sq)
        elif sq.intent == "motif_search":
            results = self._query_motifs(sq)
        elif sq.intent == "cross_case_search":
            results = self._query_cross_case(sq)
        elif sq.intent == "temporal_change":
            results = self._query_temporal(sq)
        elif sq.intent == "geo_lookup":
            results = self._query_geo(sq)
        else:
            results = self._query_general(sq)

        elapsed = (time.monotonic() - t0) * 1000

        return QueryResult(
            query=interpretation,
            results=results[:sq.max_results],
            total=len(results),
            execution_time_ms=round(elapsed, 2),
            limitations=[
                "Results are generated from deterministic graph analysis, not semantic understanding.",
                "The system interprets patterns, not intent; complex queries may need refinement.",
                "Evidence-backed results depend on the existing evidence index.",
            ],
        )

    # ------------------------------------------------------------------ #
    # Query executors
    # ------------------------------------------------------------------ #
    def _query_entity_neighbors(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        for eid in sq.entities:
            if eid not in self.graph:
                continue
            neighbors = set()
            for _, tgt, d in self.graph.out_edges(eid, data=True):
                rel = d.get("relation", "")
                if not sq.relationship_types or rel in sq.relationship_types:
                    neighbors.add(tgt)
            for src, _, d in self.graph.in_edges(eid, data=True):
                rel = d.get("relation", "")
                if not sq.relationship_types or rel in sq.relationship_types:
                    neighbors.add(src)
            for nb in neighbors:
                nd = self.graph.nodes.get(nb, {})
                results.append(QueryResultItem(
                    item_id=nb, item_type="ENTITY",
                    label=nd.get("canonical_name") or nd.get("label", nb),
                    detail=f"Connected to {eid}",
                    relevance_score=0.8,
                ))
        return results

    def _query_financial_flow(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        for eid in sq.entities:
            if eid not in self.graph:
                continue
            for _, tgt, key, d in self.graph.out_edges(eid, keys=True, data=True):
                rel = d.get("relation", "")
                if rel in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS", "USES_ACCOUNT"):
                    a = d.get("attributes") or {}
                    nested = a.get("attributes") or {}
                    amt = nested.get("amount") or a.get("amount") or "unknown"
                    tgt_name = self.graph.nodes.get(tgt, {}).get("canonical_name") or tgt
                    results.append(QueryResultItem(
                        item_id=f"{eid}-{tgt}", item_type="RELATIONSHIP",
                        label=f"{eid} → {tgt_name}",
                        detail=f"Financial transfer: ₹{amt}",
                        relevance_score=0.9,
                        metadata={"amount": amt, "target": tgt},
                    ))
        return results

    def _query_entity_lookup(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        for eid in sq.entities:
            if eid in self.graph:
                d = self.graph.nodes[eid]
                deg = self.graph.degree(eid)
                results.append(QueryResultItem(
                    item_id=eid, item_type="ENTITY",
                    label=d.get("canonical_name") or d.get("label", eid),
                    detail=f"Type: {d.get('entity_type', 'UNKNOWN')}, Connections: {deg}",
                    relevance_score=1.0,
                ))
        # Also search by label
        for label in sq.entity_labels:
            found = self._find_entity_by_label(label)
            if found and found not in sq.entities:
                d = self.graph.nodes[found]
                results.append(QueryResultItem(
                    item_id=found, item_type="ENTITY",
                    label=d.get("canonical_name") or d.get("label", found),
                    detail=f"Matched label: {label}",
                    relevance_score=0.7,
                ))
        return results

    def _query_bridges(self, sq: StructuredQuery) -> List[QueryResultItem]:
        ug = self.graph.to_undirected()
        betweenness = nx.betweenness_centrality(ug, k=min(128, ug.number_of_nodes())) if ug.number_of_nodes() > 2 else {}
        results = []
        for n, btwn in sorted(betweenness.items(), key=lambda x: -x[1])[:20]:
            if btwn > 0.05:
                nd = self.graph.nodes.get(n, {})
                results.append(QueryResultItem(
                    item_id=n, item_type="ENTITY",
                    label=nd.get("canonical_name") or nd.get("label", n),
                    detail=f"Betweenness: {btwn:.4f}",
                    relevance_score=btwn,
                ))
        return results

    def _query_evidence(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        if not self.evidence_store:
            return results
        for eid in sq.entities:
            try:
                records = self.evidence_store.get_evidence_for_node(eid, limit=20)
                for r in (records or []):
                    results.append(QueryResultItem(
                        item_id=r.evidence_id, item_type="EVIDENCE",
                        label=r.evidence_id,
                        detail=r.text_excerpt[:100] if r.text_excerpt else r.source_type,
                        evidence_ids=[r.evidence_id],
                        relevance_score=r.confidence,
                    ))
            except Exception:
                pass
        return results

    def _query_contradictions(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        try:
            import json
            from src.api.paths import FINDINGS_PATH
            if FINDINGS_PATH.exists():
                data = json.loads(FINDINGS_PATH.read_text())
                for f in data.get("findings", []):
                    counters = f.get("counter_evidence_ids", [])
                    if counters:
                        results.append(QueryResultItem(
                            item_id=f.get("id", ""), item_type="FINDING",
                            label=f.get("subject_label", f.get("id", "")),
                            detail=f"{len(counters)} contradictory evidence items",
                            evidence_ids=counters[:5],
                            relevance_score=min(1.0, len(counters) / 5),
                        ))
        except Exception:
            pass
        return results

    def _query_motifs(self, sq: StructuredQuery) -> List[QueryResultItem]:
        from src.analysis.motif_detector import MotifDetector
        detector = MotifDetector(self.graph)
        report = detector.detect_all(top_n=20)
        results = []
        for m in report.motifs:
            entity_match = any(e.get("id") in sq.entities for e in m.entities)
            if entity_match or not sq.entities:
                results.append(QueryResultItem(
                    item_id=m.motif_id, item_type="MOTIF",
                    label=m.motif_type,
                    detail=m.description[:100],
                    relevance_score=m.confidence,
                ))
        return results

    def _query_cross_case(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        try:
            import json, os
            from src.api.paths import CASES_DIR
            if CASES_DIR.exists():
                for p in CASES_DIR.glob("*.json"):
                    data = json.loads(p.read_text())
                    case_id = data.get("case_id", p.stem)
                    # Check if any entity from query appears in this case
                    case_entities = set()
                    for e in data.get("entities", []):
                        case_entities.add(e.get("id", ""))
                        case_entities.add(e.get("label", ""))
                    if any(eid in case_entities or label in case_entities
                           for eid in sq.entities for label in sq.entity_labels):
                        results.append(QueryResultItem(
                            item_id=case_id, item_type="CASE",
                            label=case_id,
                            detail=data.get("title", ""),
                            relevance_score=0.8,
                        ))
        except Exception:
            pass
        return results

    def _query_temporal(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        time_range = sq.time_range or {}
        start = time_range.get("start", "2020-01-01")
        end = time_range.get("end", "2026-12-31")
        count = 0
        for src, tgt, key, d in self.graph.edges(keys=True, data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            ts = nested.get("timestamp") or a.get("timestamp") or ""
            if start <= str(ts)[:19] <= end:
                src_name = self.graph.nodes.get(src, {}).get("canonical_name") or src
                tgt_name = self.graph.nodes.get(tgt, {}).get("canonical_name") or tgt
                results.append(QueryResultItem(
                    item_id=f"{src}-{tgt}", item_type="RELATIONSHIP",
                    label=f"{src_name} → {tgt_name}",
                    detail=f"Timestamp: {ts}",
                    relevance_score=0.7,
                    metadata={"timestamp": str(ts)},
                ))
                count += 1
                if count > 50:
                    break
        return results

    def _query_geo(self, sq: StructuredQuery) -> List[QueryResultItem]:
        from src.analysis.geospatial import GeospatialEngine
        geo = GeospatialEngine(self.graph)
        report = geo.analyze()
        results = []
        for obs in report.observations[:30]:
            results.append(QueryResultItem(
                item_id=obs.observation_id, item_type="LOCATION",
                label=obs.location_name or obs.entity_label,
                detail=f"({obs.latitude}, {obs.longitude})",
                relevance_score=obs.location_confidence,
            ))
        return results

    def _query_general(self, sq: StructuredQuery) -> List[QueryResultItem]:
        results = []
        for n, d in list(self.graph.nodes(data=True))[:30]:
            name = d.get("canonical_name") or d.get("label", n)
            if any(label.lower() in name.lower() for label in sq.entity_labels):
                results.append(QueryResultItem(
                    item_id=n, item_type="ENTITY",
                    label=name,
                    detail=f"Type: {d.get('entity_type', 'UNKNOWN')}",
                    relevance_score=0.6,
                ))
        return results


# --------------------------------------------------------------------------- #
# Mock provider for deterministic demo
# --------------------------------------------------------------------------- #

class MockAnalystQueryProvider:
    """Deterministic NL query provider for demo/offline mode."""

    DEMO_QUERIES = {
        "show financial connections": {
            "intent": "financial_flow",
            "description": "Show all financial relationships in the network",
        },
        "who are the brokers": {
            "intent": "community_bridge",
            "description": "Find entities bridging communities",
        },
        "what changed recently": {
            "intent": "temporal_change",
            "description": "Temporal changes in the network",
        },
    }

    @staticmethod
    def available_queries() -> List[Dict[str, str]]:
        return [
            {"query": q, "intent": info["intent"], "description": info["description"]}
            for q, info in MockAnalystQueryProvider.DEMO_QUERIES.items()
        ]
