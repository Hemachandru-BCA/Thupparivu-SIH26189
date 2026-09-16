"""Regression tests for CORS configuration.

The backend must always allow the GitHub Pages frontend origins so that the
deployed Pages site can talk to the Railway-hosted API without being blocked
by the Same Origin Policy.
"""
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

GITHUB_PAGES_ORIGINS = [
    "https://Hemachandru-BCA.github.io",
    "https://hemachandru-bca.github.io",
]


def test_health_returns_cors_for_github_pages_lowercase():
    resp = client.get("/api/health", headers={"Origin": "https://hemachandru-bca.github.io"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://hemachandru-bca.github.io"


def test_health_returns_cors_for_github_pages_capitalized():
    resp = client.get("/api/health", headers={"Origin": "https://Hemachandru-BCA.github.io"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://Hemachandru-BCA.github.io"


def test_health_returns_cors_credentials():
    resp = client.get("/api/health", headers={"Origin": "https://hemachandru-bca.github.io"})
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_preflight_allows_github_pages_origin():
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "https://hemachandru-bca.github.io",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin in GITHUB_PAGES_ORIGINS
    assert resp.headers.get("access-control-allow-methods") is not None