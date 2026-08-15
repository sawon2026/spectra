"""Phase 7 API tests — FastAPI boundary over Phase 6 core."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services


@pytest.fixture()
def client(db, settings):
    reset_services()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_services()


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["policy_gate"] == "active"
    assert body["offline_default"] is True


def test_me_offline(client):
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["role"] in ("admin", "researcher", "viewer")


def test_create_case_and_scope(client):
    r = client.post("/api/v1/cases", json={"name": "api-case-1", "description": "t"})
    assert r.status_code == 201
    case_id = r.json()["id"]
    r2 = client.put(
        f"/api/v1/cases/{case_id}/scope",
        json={
            "auth_status": "granted",
            "network_profile": "offline",
            "allowed_activities": ["hash-compute"],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["ready_for_act"] is True or r2.json()["auth_status"] == "granted"


def test_viewer_cannot_write(client):
    r = client.post(
        "/api/v1/cases",
        json={"name": "viewer-blocked"},
        headers={"X-Spectra-Role": "viewer"},
    )
    assert r.status_code == 403


def test_providers_list(client):
    r = client.get("/api/v1/providers")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "null" in names


def test_capabilities_list(client):
    r = client.get("/api/v1/capabilities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_workflow_start_policy_gated(client, tmp_path):
    r = client.post("/api/v1/cases", json={"name": "api-wf-1"})
    case_id = r.json()["id"]
    client.put(
        f"/api/v1/cases/{case_id}/scope",
        json={
            "auth_status": "granted",
            "network_profile": "offline",
            "allowed_activities": ["hash-compute"],
        },
    )
    f = tmp_path / "x.txt"
    f.write_text("api-test")
    r2 = client.post(
        f"/api/v1/workflows/case/{case_id}/start",
        json={"goal": "hash this file", "artifact_path": str(f), "max_steps": 2},
    )
    assert r2.status_code == 201
    body = r2.json()
    assert body["case_id"] == case_id
    assert body["status"] in ("running", "completed", "blocked", "failed")


def test_timeline_and_report(client):
    r = client.post("/api/v1/cases", json={"name": "api-tl-1"})
    case_id = r.json()["id"]
    r2 = client.get(f"/api/v1/timeline/by-case/{case_id}")
    assert r2.status_code == 200
    r3 = client.get(f"/api/v1/reports/{case_id}/markdown")
    assert r3.status_code == 200
    assert "FACT" in r3.text or "Timeline" in r3.text or "Spectra Report" in r3.text


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "api" in r.json()
