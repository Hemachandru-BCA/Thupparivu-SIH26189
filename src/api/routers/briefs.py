"""
routers/briefs.py
-----------------
LLM-powered Intelligence Briefs API (route group: /api/briefs/*).

Endpoints:
* POST /api/briefs/entity/{id}               - Evidence-grounded Entity Brief
* POST /api/briefs/relationship/{e1}/{e2}    - Relationship & Interaction Explanation
* POST /api/briefs/why-flagged/{id}          - Structured "Why Flagged?" Narrative

Contracts & Safety Constraints:
- Uses bounded context from graph analytics, priority scores, behavior profiles,
  and the evidence store.
- Supports deterministic MockLLMProvider for offline zero-credential execution,
  as well as real OpenAI/Gemini compatible endpoints via environment keys.
- Never asserts guilt or legal culpability.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query
import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from src.analysis.behavior_profile import BehaviorChangeDetector, BehaviorProfileBuilder
from src.analysis.investigation_priority import InvestigationPriorityEngine
from src.api import audit, services, services_intel
from src.llm.prompts import (
    ENTITY_BRIEF_PROMPT_V1,
    PROMPT_VERSION_ENTITY_BRIEF,
    PROMPT_VERSION_RELATIONSHIP,
    PROMPT_VERSION_WHY_FLAGGED,
    RELATIONSHIP_EXPLANATION_PROMPT_V1,
    WHY_FLAGGED_PROMPT_V1,
)
from src.xai.llm_providers import MockLLMProvider, provider_from_env

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefs", tags=["briefs"])


# --------------------------------------------------------------------------- #
# Request & Response Schemas
# --------------------------------------------------------------------------- #

class BriefOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_override: Optional[str] = Field(
        None, description="Set 'mock' to force deterministic offline provider."
    )
    detail_level: str = Field(
        "standard", description="Level of detail: 'concise', 'standard', or 'comprehensive'."
    )


class EntityBriefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    canonical_name: str
    entity_type: str
    priority_score: float
    risk_tier: str
    brief_text: str
    key_findings: List[str]
    evidence_ids: List[str]
    connected_associates: List[Dict[str, Any]]
    provider: str
    prompt_version: str
    deterministic: bool
    generated_at: str


class RelationshipBriefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_1: str
    entity_2: str
    direct_connections_count: int
    interaction_types: List[str]
    explanation_text: str
    shared_associates: List[str]
    evidence_ids: List[str]
    connection_strength: float
    provider: str
    prompt_version: str
    deterministic: bool
    generated_at: str


class WhyFlaggedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    priority_score: float
    risk_tier: str
    primary_driver: str
    narrative: str
    driver_breakdown: List[Dict[str, Any]]
    anomalies_detected: List[Dict[str, Any]]
    evidence_ids: List[str]
    recommended_actions: List[str]
    provider: str
    prompt_version: str
    deterministic: bool
    generated_at: str


# --------------------------------------------------------------------------- #
# Context Builders
# --------------------------------------------------------------------------- #

def _get_provider(provider_override: Optional[str] = None):
    if provider_override == "mock":
        return MockLLMProvider()
    return provider_from_env()


def _extract_entity_evidence(entity_id: str, store: Any, max_items: int = 15) -> List[Dict[str, Any]]:
    """Retrieve evidence items referencing the target entity."""
    results: List[Dict[str, Any]] = []
    if store is None:
        return results
    try:
        items = list(store.get_all()) if hasattr(store, "get_all") else []
        for it in items:
            subjs = it.get("subject_ids") or []
            if entity_id in subjs or it.get("entity_id") == entity_id:
                results.append({
                    "evidence_id": it.get("evidence_id"),
                    "source_type": it.get("source_type"),
                    "timestamp": it.get("timestamp"),
                    "text_excerpt": (it.get("text_excerpt") or "")[:250],
                })
                if len(results) >= max_items:
                    break
    except Exception as exc:
        logger.warning("Failed extracting evidence for entity %s: %s", entity_id, exc)
    return results


def _build_entity_context(
    entity_id: str,
    graph: nx.MultiDiGraph,
    store: Any,
    priority_engine: InvestigationPriorityEngine,
) -> Dict[str, Any]:
    node_data = graph.nodes.get(entity_id, {})
    priority_res = priority_engine.score_entity(entity_id)

    # Behavior profile
    profile_builder = BehaviorProfileBuilder(graph)
    profile = profile_builder.build(entity_id)
    detector = BehaviorChangeDetector(graph)
    change = detector.detect_change(entity_id, window_days=30)

    # Associates / Neighbors
    associates: List[Dict[str, Any]] = []
    for neighbor in list(graph.successors(entity_id))[:10]:
        nbr_data = graph.nodes.get(neighbor, {})
        edge_data = graph.get_edge_data(entity_id, neighbor, default={})
        edge_types = list({ed.get("relation", "LINK") for ed in edge_data.values()}) if isinstance(edge_data, dict) else []
        associates.append({
            "entity_id": neighbor,
            "name": nbr_data.get("canonical_name", neighbor),
            "type": nbr_data.get("entity_type", "UNKNOWN"),
            "relations": edge_types,
        })

    evidence_items = _extract_entity_evidence(entity_id, store)

    return {
        "target_entity": {
            "entity_id": entity_id,
            "canonical_name": node_data.get("canonical_name", entity_id),
            "entity_type": node_data.get("entity_type", "UNKNOWN"),
            "community": node_data.get("community"),
            "degree": graph.degree(entity_id) if entity_id in graph else 0,
            "betweenness_centrality": node_data.get("betweenness_centrality", 0.0),
            "pagerank": node_data.get("pagerank", 0.0),
        },
        "priority_assessment": priority_res.model_dump(),
        "behavior_profile": profile.model_dump() if profile else None,
        "behavior_change_30d": change.model_dump() if change else None,
        "top_associates": associates,
        "evidence_records": evidence_items,
    }


def _build_relationship_context(
    e1: str,
    e2: str,
    graph: nx.MultiDiGraph,
    store: Any,
) -> Dict[str, Any]:
    n1_data = graph.nodes.get(e1, {})
    n2_data = graph.nodes.get(e2, {})

    # Direct edges
    direct_edges_fwd = graph.get_edge_data(e1, e2, default={})
    direct_edges_rev = graph.get_edge_data(e2, e1, default={})

    edges_summary: List[Dict[str, Any]] = []
    evidence_ids: List[str] = []

    for _, ed in (direct_edges_fwd.items() if isinstance(direct_edges_fwd, dict) else []):
        edges_summary.append({
            "direction": f"{e1} -> {e2}",
            "relation": ed.get("relation", "ASSOCIATED_WITH"),
            "timestamp": ed.get("timestamp"),
            "weight": ed.get("weight", 1.0),
            "amount": ed.get("amount"),
            "duration": ed.get("duration"),
        })
        if ed.get("evidence_id"):
            evidence_ids.append(ed["evidence_id"])

    for _, ed in (direct_edges_rev.items() if isinstance(direct_edges_rev, dict) else []):
        edges_summary.append({
            "direction": f"{e2} -> {e1}",
            "relation": ed.get("relation", "ASSOCIATED_WITH"),
            "timestamp": ed.get("timestamp"),
            "weight": ed.get("weight", 1.0),
            "amount": ed.get("amount"),
            "duration": ed.get("duration"),
        })
        if ed.get("evidence_id"):
            evidence_ids.append(ed["evidence_id"])

    # Shared neighbors
    nbrs1 = set(graph.to_undirected().neighbors(e1)) if e1 in graph else set()
    nbrs2 = set(graph.to_undirected().neighbors(e2)) if e2 in graph else set()
    shared_nbrs = list(nbrs1.intersection(nbrs2))[:10]

    # Path distance
    shortest_path = None
    try:
        if e1 in graph and e2 in graph:
            shortest_path = nx.shortest_path(graph.to_undirected(), e1, e2)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        shortest_path = None

    return {
        "entity_1": {
            "entity_id": e1,
            "name": n1_data.get("canonical_name", e1),
            "type": n1_data.get("entity_type", "UNKNOWN"),
            "community": n1_data.get("community"),
        },
        "entity_2": {
            "entity_id": e2,
            "name": n2_data.get("canonical_name", e2),
            "type": n2_data.get("entity_type", "UNKNOWN"),
            "community": n2_data.get("community"),
        },
        "direct_interactions": edges_summary,
        "shared_intermediaries": [
            {
                "entity_id": sn,
                "name": graph.nodes.get(sn, {}).get("canonical_name", sn),
                "type": graph.nodes.get(sn, {}).get("entity_type", "UNKNOWN"),
            }
            for sn in shared_nbrs
        ],
        "shortest_path": shortest_path,
        "evidence_ids": list(set(evidence_ids)),
    }


def _format_text_from_llm_response(raw_output: str, fallback_header: str) -> str:
    """Format raw LLM output or json mock into a readable structured text."""
    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, dict) and "sections" in parsed:
            lines = [f"# {fallback_header}\n"]
            for s in parsed.get("sections", []):
                lines.append(f"## {s.get('heading', 'Section')}\n{s.get('content', '')}\n")
            return "\n".join(lines).strip()
    except Exception:
        pass
    return raw_output


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@router.post("/entity/{entity_id}", response_model=EntityBriefResponse)
def generate_entity_brief(
    entity_id: str = Path(..., description="Target entity identifier"),
    options: Optional[BriefOptions] = None,
):
    """Generate an evidence-grounded Intelligence Brief for a target entity."""
    graph = services.load_graph()
    if entity_id not in graph:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    store = services.evidence_store()
    engine = services_intel.priority_engine(
        builder=lambda: InvestigationPriorityEngine(graph=graph, evidence_store=store)
    )

    context = _build_entity_context(entity_id, graph, store, engine)
    opts = options or BriefOptions()
    provider = _get_provider(opts.provider_override)

    try:
        raw_text = provider.generate(ENTITY_BRIEF_PROMPT_V1, [context])
    except Exception as exc:
        logger.error("LLM generation failed for entity %s: %s", entity_id, exc)
        raw_text = f"Entity Brief for {context['target_entity']['canonical_name']} ({entity_id}). Score: {context['priority_assessment']['priority_score']}."

    node_data = graph.nodes[entity_id]
    priority_res = context["priority_assessment"]

    # Key findings
    key_findings = [
        f"Investigation Priority Score: {priority_res['priority_score']:.1f}/100 (Tier: {priority_res['tier']})",
        f"Network Position: Degree {graph.degree(entity_id)}, Centrality {node_data.get('betweenness_centrality', 0.0):.4f}",
    ]
    if context.get("behavior_change_30d"):
        chg = context["behavior_change_30d"]
        key_findings.append(f"30-Day Activity Delta: {chg.get('activity_delta_pct', 0):+.1f}% (Severity: {chg.get('severity', 'LOW')})")

    ev_ids = [e["evidence_id"] for e in context["evidence_records"] if e.get("evidence_id")]
    formatted_brief = _format_text_from_llm_response(raw_text, f"Intelligence Brief: {node_data.get('canonical_name', entity_id)}")

    audit.record_action("briefs.entity", object_ids=[entity_id])

    return EntityBriefResponse(
        entity_id=entity_id,
        canonical_name=node_data.get("canonical_name", entity_id),
        entity_type=node_data.get("entity_type", "UNKNOWN"),
        priority_score=priority_res["priority_score"],
        risk_tier=priority_res["tier"],
        brief_text=formatted_brief,
        key_findings=key_findings,
        evidence_ids=ev_ids,
        connected_associates=context["top_associates"],
        provider=provider.name,
        prompt_version=PROMPT_VERSION_ENTITY_BRIEF,
        deterministic=getattr(provider, "name", "") == "mock",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/relationship/{entity_1}/{entity_2}", response_model=RelationshipBriefResponse)
def generate_relationship_brief(
    entity_1: str = Path(..., description="First entity identifier"),
    entity_2: str = Path(..., description="Second entity identifier"),
    options: Optional[BriefOptions] = None,
):
    """Explain the relationship, direct interactions, and indirect paths between two entities."""
    graph = services.load_graph()
    if entity_1 not in graph:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_1}")
    if entity_2 not in graph:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_2}")

    store = services.evidence_store()
    context = _build_relationship_context(entity_1, entity_2, graph, store)

    opts = options or BriefOptions()
    provider = _get_provider(opts.provider_override)

    try:
        raw_text = provider.generate(RELATIONSHIP_EXPLANATION_PROMPT_V1, [context])
    except Exception as exc:
        logger.error("LLM generation failed for relationship %s - %s: %s", entity_1, entity_2, exc)
        raw_text = f"Relationship analysis between {entity_1} and {entity_2}."

    interactions = context["direct_interactions"]
    interaction_types = list({ix.get("relation", "LINK") for ix in interactions})
    shared_names = [sn["name"] for sn in context["shared_intermediaries"]]

    connection_strength = min(1.0, (len(interactions) * 0.2) + (0.5 if context.get("shortest_path") and len(context["shortest_path"]) <= 2 else 0.1))

    formatted_text = _format_text_from_llm_response(
        raw_text, f"Relationship Brief: {context['entity_1']['name']} & {context['entity_2']['name']}"
    )

    audit.record_action("briefs.relationship", object_ids=[entity_1, entity_2])

    return RelationshipBriefResponse(
        entity_1=entity_1,
        entity_2=entity_2,
        direct_connections_count=len(interactions),
        interaction_types=interaction_types,
        explanation_text=formatted_text,
        shared_associates=shared_names,
        evidence_ids=context["evidence_ids"],
        connection_strength=round(connection_strength, 3),
        provider=provider.name,
        prompt_version=PROMPT_VERSION_RELATIONSHIP,
        deterministic=getattr(provider, "name", "") == "mock",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/why-flagged/{entity_id}", response_model=WhyFlaggedResponse)
def generate_why_flagged_brief(
    entity_id: str = Path(..., description="Target entity identifier"),
    options: Optional[BriefOptions] = None,
):
    """Generate an objective, driver-decomposed explanation of why an entity was flagged."""
    graph = services.load_graph()
    if entity_id not in graph:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    store = services.evidence_store()
    engine = services_intel.priority_engine(
        builder=lambda: InvestigationPriorityEngine(graph=graph, evidence_store=store)
    )

    priority_res = engine.score_entity(entity_id)
    detector = BehaviorChangeDetector(graph)
    change = detector.detect_change(entity_id, window_days=30)
    evidence_items = _extract_entity_evidence(entity_id, store)

    # Sort components by score contribution
    active_components = [c.model_dump() for c in priority_res.components if c.available]
    active_components.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    primary_driver = active_components[0]["name"] if active_components else "network_influence"

    # Identify anomalies
    anomalies: List[Dict[str, Any]] = []
    if change and change.severity in ("HIGH", "CRITICAL"):
        anomalies.append({
            "type": "BEHAVIORAL_DELTA",
            "description": f"Activity shifted {change.activity_delta_pct:+.1f}% across 30-day baseline.",
            "severity": change.severity,
        })
    if graph.nodes[entity_id].get("betweenness_centrality", 0.0) > 0.1:
        anomalies.append({
            "type": "STRUCTURAL_BRIDGE",
            "description": "High betweenness centrality indicates structural gatekeeper or intermediary.",
            "severity": "HIGH",
        })

    context = {
        "entity_id": entity_id,
        "canonical_name": graph.nodes[entity_id].get("canonical_name", entity_id),
        "priority_score": priority_res.priority_score,
        "risk_tier": priority_res.tier,
        "primary_driver": primary_driver,
        "components": active_components,
        "anomalies": anomalies,
        "evidence_records": evidence_items,
    }

    opts = options or BriefOptions()
    provider = _get_provider(opts.provider_override)

    try:
        raw_text = provider.generate(WHY_FLAGGED_PROMPT_V1, [context])
    except Exception as exc:
        logger.error("LLM generation failed for why-flagged %s: %s", entity_id, exc)
        raw_text = f"Entity {entity_id} flagged with priority score {priority_res.priority_score} due to {primary_driver}."

    ev_ids = [e["evidence_id"] for e in evidence_items if e.get("evidence_id")]
    formatted_narrative = _format_text_from_llm_response(raw_text, f"Why Flagged: {context['canonical_name']}")

    recommendations = [
        f"Review direct associates and communications for primary driver: {primary_driver}.",
        f"Cross-reference {len(ev_ids)} linked evidence items in the Evidence Store.",
        "Perform pre-incident window analysis if linked to specific FIRs.",
    ]

    audit.record_action("briefs.why_flagged", object_ids=[entity_id])

    return WhyFlaggedResponse(
        entity_id=entity_id,
        priority_score=priority_res.priority_score,
        risk_tier=priority_res.tier,
        primary_driver=primary_driver,
        narrative=formatted_narrative,
        driver_breakdown=active_components,
        anomalies_detected=anomalies,
        evidence_ids=ev_ids,
        recommended_actions=recommendations,
        provider=provider.name,
        prompt_version=PROMPT_VERSION_WHY_FLAGGED,
        deterministic=getattr(provider, "name", "") == "mock",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
