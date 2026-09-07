"""API contract tests: evidence / findings / dossiers / cases / search /
subgraph / paths endpoints, pagination, validation and error envelopes."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def graph_doc():
    from src.api import paths

    return json.loads(paths.GRAPH_DATA_PATH.read_text())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_evidence_group(client):
    stats = client.get("/api/evidence/stats/summary")
    assert stats.status_code == 200
    assert stats.json()["total"] > 1000

    search = client.get("/api/evidence/search?q=called")
    assert search.status_code == 200
    assert "items" in search.json()


def test_evidence_route_ordering(client):
    """Static routes must not be shadowed by /{evidence_id}."""
    r = client.get("/api/evidence/search?q=x")
    assert r.status_code != 404 or "not found" not in r.text.lower()


def test_findings_generate_and_list(client):
    gen = client.post("/api/findings/generate")
    assert gen.status_code == 200
    assert gen.json()["generated"] >= 1
    listing = client.get("/api/findings")
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    first = listing.json()["items"][0]
    detail = client.get(f"/api/findings/{first['id']}")
    assert detail.status_code == 200
    assert detail.json()["human_review"]["required"] is True


def test_dossier_generate_validate_review(client):
    findings = client.get("/api/findings").json()
    subject = findings["items"][0]["subject_id"]
    gen = client.post("/api/dossiers/generate", json={"subject_id": subject})
    assert gen.status_code == 201
    dossier = gen.json()["dossier"]
    assert dossier["status"] == "DRAFT_FOR_HUMAN_REVIEW"
    assert gen.json()["validation"]["valid"] is True

    review = client.post(
        f"/api/dossiers/{dossier['id']}/review",
        json={"reviewer": "pytest", "decision": "endorsed", "note": "ok"},
    )
    assert review.status_code == 200
    assert review.json()["human_review"]["decision"] == "endorsed"


def test_dossier_request_validation(client):
    r = client.post("/api/dossiers/generate", json={"subject_id": "x", "bogus": 1})
    assert r.status_code == 422  # extra="forbid"


def test_case_workspace_crud(client):
    created = client.post("/api/cases", json={"title": "pytest case"})
    assert created.status_code == 201
    case = created.json()
    assert case["disclaimer"]
    cid = case["id"]

    patched = client.patch(
        f"/api/cases/{cid}",
        json={"note": "n1", "add_item": {"kind": "entity", "ref_id": "NODE-1"}},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert len(body["items"]) == 1 and body["notes"][0]["text"] == "n1"

    listing = client.get("/api/cases")
    assert listing.status_code == 200

    deleted = client.delete(f"/api/cases/{cid}")
    assert deleted.status_code == 200


def test_subgraph_limits_and_focus(client, graph_doc):
    node = next(n for n in graph_doc["nodes"] if n.get("type") == "PERSON")
    r = client.get(
        f"/api/graph/subgraph?node_id={node['id']}&depth=2&max_nodes=25"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["node_count"] <= 25
    assert body["method"] == "SERVER_SIDE_SUBGRAPH"
    assert any(e.get("evidence_ids") for e in body["edges"]), \
        "subgraph edges should carry evidence links"


def test_subgraph_validation(client):
    assert client.get("/api/graph/subgraph").status_code == 422  # missing node_id
    assert client.get(
        "/api/graph/subgraph?node_id=nope&depth=9"
    ).status_code in (404, 422)


def test_paths_endpoint(client, graph_doc):
    nodes = [n for n in graph_doc["nodes"] if n.get("type") == "PERSON"][:2]
    if len(nodes) < 2:
        pytest.skip("need two person nodes")
    r = client.get(f"/api/graph/paths/{nodes[0]['id']}/{nodes[1]['id']}?k=2")
    assert r.status_code == 200
    body = r.json()
    for path in body["paths"]:
        assert "path_length" in path and "edges" in path
        for edge in path["edges"]:
            assert "relation" in edge and "evidence_ids" in edge


def test_global_search(client, graph_doc):
    person = next(n for n in graph_doc["nodes"] if n.get("type") == "PERSON")
    r = client.get(f"/api/search?q={person['label'][:6]}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items, "search should match the seeded person"
    assert {"result_type", "id", "display_name"} <= set(items[0].keys())


def test_pagination_envelope(client):
    r = client.get("/api/graph/entities?page=2&page_size=10")
    body = r.json()
    assert {"items", "total", "page", "page_size"} <= set(body.keys())
    assert body["page"] == 2 and len(body["items"]) <= 10


def test_audit_log_records_actions(client):
    client.get("/api/evidence/search?q=called")
    entries = client.get("/api/audit?limit=10").json()["items"]
    assert any(e["action"] == "evidence.search" for e in entries)
    for entry in entries:
        assert {"timestamp", "action", "object_ids"} <= set(entry.keys())


def test_missing_artifact_is_consistent_404(client):
    r = client.get("/api/graph/metrics")
    if r.status_code == 404:
        assert "detail" in r.json()
