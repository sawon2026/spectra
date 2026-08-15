"""Phase 8 tests — SSE hub, auth, audit, reports."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services
from spectra.audit.service import AuditService
from spectra.auth.session import AuthService, Permission, Role, reset_auth_service
from spectra.events.sse import SSEHub, event_to_sse_dict, reset_sse_hub, sanitize_payload
from spectra.models.events import EventType, SpectraEvent


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


def test_sanitize_redacts_secrets():
    out = sanitize_payload({"api_key": "sk-secret", "title": "ok", "token": "x"})
    assert out["api_key"] == "[redacted]"
    assert out["token"] == "[redacted]"
    assert out["title"] == "ok"


def test_sse_hub_register_and_push():
    hub = SSEHub()
    client = hub.register(case_id=None)
    assert hub.client_count == 1
    ev = SpectraEvent(event_type=EventType.AUDIT, message="hello", payload={"x": 1})
    hub.on_event(ev)
    item = client.queue.get_nowait()
    assert item["message"] == "hello"
    assert item["event_type"] == "audit"
    hub.unregister(client.id)
    assert hub.client_count == 0


def test_sse_sanitizes_on_event():
    hub = SSEHub()
    client = hub.register()
    ev = SpectraEvent(
        event_type=EventType.AUDIT,
        message="auth",
        payload={"api_key": "secret-value", "ok": True},
    )
    hub.on_event(ev)
    item = client.queue.get_nowait()
    assert item["payload"]["api_key"] == "[redacted]"
    assert item["payload"]["ok"] is True


def test_event_to_sse_dict_fields():
    ev = SpectraEvent(event_type=EventType.CASE_CREATED, message="c", case_id=uuid4())
    d = event_to_sse_dict(ev)
    assert "id" in d and "event_type" in d and "payload" in d


def test_auth_offline_admin():
    svc = AuthService()
    sess = svc.resolve(None)
    assert sess is not None
    assert sess.role == Role.ADMIN
    assert sess.has(Permission.SYSTEM_ADMIN)


def test_auth_viewer_no_write_perm():
    svc = AuthService()
    sess = svc.resolve(None, role_hint="viewer")
    assert sess is not None
    assert sess.role == Role.VIEWER
    assert not sess.has(Permission.CASE_WRITE)
    assert sess.has(Permission.CASE_READ)


def test_auth_create_and_resolve_session():
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
    assert "timeline" in body and "evidence" in body
    h = client.get(f"/api/v1/reports/{cid}/html")
    assert h.status_code == 200
    assert "Spectra Report" in h.text
    assert "never labeled as FACT" in h.text


def test_events_hub_status(client):
    r = client.get("/api/v1/events/hub-status")
    assert r.status_code == 200
    assert r.json()["mode"] == "eventbus-sse"


def test_audit_api(client):
    r = client.get("/api/v1/audit")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_cases_list_api(client):
    client.post("/api/v1/cases", json={"name": "p8-list-a"})
    client.post("/api/v1/cases", json={"name": "p8-list-b"})
    r = client.get("/api/v1/cases")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "p8-list-a" in names
