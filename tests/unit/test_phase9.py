"""Phase 9 — persistent auth, plugins, PDF, SSE multi-worker mode."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services
from spectra.auth.session import AuthService, Role, reset_auth_service
from spectra.events.sse import reset_sse_hub


@pytest.fixture()
def client(db, settings):
    reset_services()
    reset_sse_hub()
    reset_auth_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_services()
    reset_sse_hub()
    reset_auth_service()


def test_persistent_session_create_and_resolve(db, settings):
    auth = AuthService()
    token, sess = auth.create_session("bob", Role.RESEARCHER)
    assert token
    resolved = auth.resolve(token)
    assert resolved is not None
    assert resolved.subject == "bob"
    assert resolved.role == Role.RESEARCHER


def test_session_revoke(db, settings):
    auth = AuthService()
    token, _ = auth.create_session("carol", Role.RESEARCHER)
    assert auth.revoke(token) is True
    assert auth.resolve(token) is None


def test_login_logout_api(client):
    r = client.post("/api/v1/auth/login", json={"subject": "alice", "role": "researcher"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["subject"] == "alice"
    out = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert out.status_code == 200
    assert out.json()["revoked"] is True


def test_plugins_list_and_disable(client):
    r = client.get("/api/v1/plugins")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert any(p["name"] == "hash-compute" for p in items)
    name = items[0]["name"]
    r2 = client.post(f"/api/v1/plugins/{name}/state", json={"state": "disabled"})
    assert r2.status_code == 200
    assert r2.json()["state"] == "disabled"


def test_report_pdf(client):
    r = client.post("/api/v1/cases", json={"name": "p9-pdf"})
    cid = r.json()["id"]
    pdf = client.get(f"/api/v1/reports/{cid}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"


def test_events_hub_multi_worker_mode(client):
    r = client.get("/api/v1/events/hub-status")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "hub+db"
    assert body.get("multi_worker") == "db-poll"


def test_viewer_cannot_disable_plugin(client):
    r = client.get("/api/v1/plugins")
    name = r.json()[0]["name"]
    r2 = client.post(
        f"/api/v1/plugins/{name}/state",
        json={"state": "disabled"},
        headers={"X-Spectra-Role": "viewer"},
    )
    assert r2.status_code == 403
