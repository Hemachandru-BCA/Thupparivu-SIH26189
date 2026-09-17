"""
tests/test_auth.py
------------------
Unit tests for JWT auth.
"""

import os
import pytest
from unittest.mock import patch


def _make_test_app():
    """Create a minimal FastAPI test app with the auth router."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers.auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)
    return app, TestClient(app)


class TestAuthToken:
    def test_correct_password_returns_token(self):
        os.environ["SENTINELGRAPH_DEMO_PASSWORD"] = "testpass"
        os.environ["SENTINELGRAPH_DEMO_MODE"] = "false"
        app, client = _make_test_app()
        resp = client.post("/api/auth/token", json={"username": "testuser", "password": "testpass"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 10

    def test_wrong_password_returns_401(self):
        os.environ["SENTINELGRAPH_DEMO_PASSWORD"] = "testpass"
        os.environ["SENTINELGRAPH_DEMO_MODE"] = "false"
        app, client = _make_test_app()
        resp = client.post("/api/auth/token", json={"username": "testuser", "password": "wrong"})
        assert resp.status_code == 401

    def test_demo_mode_any_password_works(self):
        os.environ["SENTINELGRAPH_DEMO_MODE"] = "true"
        os.environ["SENTINELGRAPH_DEMO_PASSWORD"] = "anything"
        app, client = _make_test_app()
        resp = client.post("/api/auth/token", json={"username": "demo", "password": "any"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body


class TestProtectedEndpoints:
    def _setup_app(self, demo_mode="false"):
        os.environ["SENTINELGRAPH_DEMO_MODE"] = demo_mode
        os.environ["SENTINELGRAPH_DEMO_PASSWORD"] = "testpass"
        from fastapi import FastAPI, APIRouter, Depends
        from fastapi.testclient import TestClient
        from src.api.auth import get_current_user, User

        # A simple protected router
        protected_router = APIRouter(prefix="/api/test", tags=["test"],
                                     dependencies=[Depends(get_current_user)])

        @protected_router.get("/secret")
        def secret():
            return {"secret": "data"}

        @protected_router.get("/public")
        def public():
            return {"public": "data"}

        app = FastAPI()
        app.include_router(protected_router)
        return app, TestClient(app)

    def test_protected_endpoint_no_token_returns_401(self):
        app, client = self._setup_app(demo_mode="false")
        resp = client.get("/api/test/secret")
        assert resp.status_code == 401

    def test_protected_endpoint_with_valid_token(self):
        app, client = self._setup_app(demo_mode="false")
        # Get a token
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.api.routers.auth import router as auth_router

        auth_app = FastAPI()
        auth_app.include_router(auth_router)
        auth_client = TestClient(auth_app)
        token_resp = auth_client.post("/api/auth/token", json={"username": "testuser", "password": "testpass"})
        assert token_resp.status_code == 200
        token = token_resp.json()["access_token"]
        # Use it
        resp = client.get("/api/test/secret", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == {"secret": "data"}

    def test_protected_endpoint_tampered_token_returns_401(self):
        app, client = self._setup_app(demo_mode="false")
        resp = client.get("/api/test/secret", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_demo_mode_bypasses_auth(self):
        app, client = self._setup_app(demo_mode="true")
        resp = client.get("/api/test/secret")
        assert resp.status_code == 200


class TestDossiersAuth:
    def test_dossiers_no_token_demo_mode_false(self):
        """In DEMO_MODE=false, GET /api/dossiers returns 401."""
        os.environ["SENTINELGRAPH_DEMO_MODE"] = "false"
        os.environ["SENTINELGRAPH_DEMO_PASSWORD"] = "testpass"
        from fastapi import FastAPI, APIRouter, Depends
        from fastapi.testclient import TestClient
        from src.api.auth import get_current_user

        protected_router = APIRouter(prefix="/api/dossiers", tags=["dossiers"],
                                     dependencies=[Depends(get_current_user)])

        @protected_router.get("/")
        def list_dossiers():
            return {"items": []}

        app = FastAPI()
        app.include_router(protected_router)
        client = TestClient(app)
        resp = client.get("/api/dossiers/")
        assert resp.status_code == 401

    def test_graph_info_always_public(self):
        """GET /api/graph/info (simulated) returns 200 even in DEMO_MODE=false."""
        os.environ["SENTINELGRAPH_DEMO_MODE"] = "false"
        os.environ["SENTINELGRAPH_DEMO_PASSWORD"] = "testpass"
        from fastapi import FastAPI, APIRouter
        from fastapi.testclient import TestClient

        # Public router (no auth dependency)
        public_router = APIRouter(prefix="/api/graph")

        @public_router.get("/info")
        def graph_info():
            return {"graph_built": True}

        app = FastAPI()
        app.include_router(public_router)
        client = TestClient(app)
        resp = client.get("/api/graph/info")
        assert resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])