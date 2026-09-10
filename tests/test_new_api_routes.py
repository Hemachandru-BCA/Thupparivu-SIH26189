"""Tests for the new intelligence API routes (Phase B1/B2/B3)."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "thupparivu"


def test_temporal_info():
    resp = client.get("/api/temporal/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "edge_count" in data
    assert "timestamp_coverage" in data
    assert "layers" in data
    assert "bucket_timestamps" in data


def test_temporal_timeline():
    resp = client.get("/api/temporal/timeline?n_buckets=4")
    assert resp.status_code == 200
    data = resp.json()
    assert "buckets" in data
    assert len(data["buckets"]) == 4


def test_temporal_layers():
    resp = client.get("/api/temporal/layers")
    assert resp.status_code == 200
    data = resp.json()
    assert "layers" in data
    assert "COMMUNICATION" in data["layers"]


def test_temporal_diff():
    resp = client.get("/api/temporal/diff?start=2025-06-01T00:00:00&end=2025-12-01T00:00:00")
    assert resp.status_code == 200
    data = resp.json()
    assert "delta" in data
    assert "nodes_added" in data["delta"]


def test_communities_list():
    resp = client.get("/api/communities?min_size=2&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_investigation_operations():
    resp = client.get("/api/investigation/counterfactual/operations")
    assert resp.status_code == 200
    data = resp.json()
    assert "operations" in data
    assert len(data["operations"]) >= 5


def test_models_list():
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 1


def test_intel_gaps():
    resp = client.get("/api/intel/gaps")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


def test_intel_cross_case():
    resp = client.get("/api/intel/cross-case")
    assert resp.status_code == 200
    data = resp.json()
    assert "case_count" in data