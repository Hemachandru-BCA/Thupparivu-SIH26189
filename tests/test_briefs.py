"""
tests/test_briefs.py
--------------------
Unit and API integration tests for Phase E: LLM Entity Briefs,
Relationship Explanations, and Why-Flagged Narratives.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any

from fastapi.testclient import TestClient
import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.main import app
from src.llm.prompts import (
    ENTITY_BRIEF_PROMPT_V1,
    PROMPT_VERSION_ENTITY_BRIEF,
    PROMPT_VERSION_RELATIONSHIP,
    PROMPT_VERSION_WHY_FLAGGED,
    RELATIONSHIP_EXPLANATION_PROMPT_V1,
    WHY_FLAGGED_PROMPT_V1,
)
from src.xai.llm_providers import MockLLMProvider

client = TestClient(app)


def test_prompts_and_versions_exist():
    """Verify prompt templates and versions are properly exposed."""
    assert "SentinelGraph Intelligence Copilot" in ENTITY_BRIEF_PROMPT_V1
    assert "Entity A and Entity B" in RELATIONSHIP_EXPLANATION_PROMPT_V1
    assert "WHY this entity was flagged" in WHY_FLAGGED_PROMPT_V1
    assert PROMPT_VERSION_ENTITY_BRIEF == "entity_brief_v1"
    assert PROMPT_VERSION_RELATIONSHIP == "relationship_explanation_v1"
    assert PROMPT_VERSION_WHY_FLAGGED == "why_flagged_v1"


def test_entity_brief_endpoint():
    """Test generating an entity brief for a real entity."""
    # First get an entity ID from priority or graph info
    resp = client.get("/api/priority/?limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) > 0
    entity_id = data["items"][0]["entity_id"]

    # Request brief
    brief_resp = client.post(
        f"/api/briefs/entity/{entity_id}",
        json={"provider_override": "mock", "detail_level": "standard"},
    )
    assert brief_resp.status_code == 200
    body = brief_resp.json()

    assert body["entity_id"] == entity_id
    assert body["priority_score"] >= 0.0
    assert body["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert body["deterministic"] is True
    assert body["prompt_version"] == "entity_brief_v1"
    assert len(body["brief_text"]) > 0
    assert isinstance(body["key_findings"], list)
    assert isinstance(body["connected_associates"], list)


def test_entity_brief_404_for_unknown():
    """Test 404 response for unknown entity."""
    resp = client.post(
        "/api/briefs/entity/NON_EXISTENT_ENTITY_12345",
        json={"provider_override": "mock"},
    )
    assert resp.status_code == 404


def test_relationship_brief_endpoint():
    """Test generating relationship explanation between two connected entities."""
    # Find two connected entities from graph
    resp = client.get("/api/graph/metrics")
    assert resp.status_code == 200

    # Get priority entity and its neighbors
    p_resp = client.get("/api/priority/?limit=5")
    assert p_resp.status_code == 200
    entities = p_resp.json()["items"]
    assert len(entities) >= 2

    e1 = entities[0]["entity_id"]
    e2 = entities[1]["entity_id"]

    rel_resp = client.post(
        f"/api/briefs/relationship/{e1}/{e2}",
        json={"provider_override": "mock"},
    )
    assert rel_resp.status_code == 200
    body = rel_resp.json()

    assert body["entity_1"] == e1
    assert body["entity_2"] == e2
    assert body["prompt_version"] == "relationship_explanation_v1"
    assert body["deterministic"] is True
    assert 0.0 <= body["connection_strength"] <= 1.0
    assert isinstance(body["shared_associates"], list)
    assert isinstance(body["evidence_ids"], list)


def test_relationship_brief_404():
    """Test 404 when one or both entities are not found."""
    resp = client.post("/api/briefs/relationship/NON_EXISTENT_1/NON_EXISTENT_2")
    assert resp.status_code == 404


def test_why_flagged_endpoint():
    """Test why-flagged breakdown endpoint."""
    resp = client.get("/api/priority/?limit=1")
    assert resp.status_code == 200
    entity_id = resp.json()["items"][0]["entity_id"]

    why_resp = client.post(
        f"/api/briefs/why-flagged/{entity_id}",
        json={"provider_override": "mock"},
    )
    assert why_resp.status_code == 200
    body = why_resp.json()

    assert body["entity_id"] == entity_id
    assert body["priority_score"] >= 0.0
    assert body["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert len(body["primary_driver"]) > 0
    assert len(body["narrative"]) > 0
    assert isinstance(body["driver_breakdown"], list)
    assert isinstance(body["recommended_actions"], list)
    assert len(body["recommended_actions"]) > 0
    assert body["prompt_version"] == "why_flagged_v1"


def test_why_flagged_404():
    """Test 404 for why-flagged on nonexistent entity."""
    resp = client.post("/api/briefs/why-flagged/NON_EXISTENT_ENTITY_XYZ")
    assert resp.status_code == 404
