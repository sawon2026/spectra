"""Phase 8 — platformization: sessions, audit, reports, hub status."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services
from spectra.audit.service import AuditService
from spectra.auth.session import AuthService, Permission, Role, reset_auth_service
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


def test_session_create_and_resolve(db, settings):
    svc = AuthService()
    token, session = svc.create_session("alice", Role.RESEARCHER)
    assert token
    resolved = svc.resolve(token)
    assert resolved is not None
    assert resolved.subject == "alice"
    assert resolved.has(Permission.INVESTIGATION_CONTROL)


def test_audit_record_and_list(db, settings):
    audit = AuditService()
    e = audit.record("case.created", actor="test", message="created case")
    assert e.action == "case.created"
    items = audit.list_recent(limit=10)
    assert any(i.action == "case.created" for i in items)


def test_report_json_and_html(client):
    r = client.post("/api/v1/cases", json={"name": "p8-report"})
    assert r.status_code == 201
    cid = r.json()["id"]
    j = client.get(f"/api/v1/reports/{cid}/json")
    assert j.status_code == 200
    body = j.json()
    assert body["case"]["name"] == "p8-report"
    assert "timeline" in body
    assert "evidence" in body or "evidence_count" in body
    assert "limitations" in body or "methodology" in body
    h = client.get(f"/api/v1/reports/{cid}/html")
    assert h.status_code == 200
    assert "Spectra Report" in h.text
    assert "FACT" in h.text and ("never" in h.text.lower() or "INFERENCE" in h.text)


def test_events_hub_status(client):
    r = client.get("/api/v1/events/hub-status")
    assert r.status_code == 200
    assert r.json()["mode"] == "hub+db"


def test_audit_api(client):
    r = client.get("/api/v1/audit")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
