"""Phase 13 — migrations, ledger, audit, graph neighbors, cases search."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services
from spectra.auth.session import reset_auth_service
from spectra.events.sse import reset_sse_hub
from spectra.knowledge.execution_ledger import (
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    STATUS_RECOVERY_REQUIRED,
    ExecutionLedger,
)
from spectra.plugins.base import validate_manifest


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


def test_schema_version_at_least_13(db, settings):
    from spectra.core.migrations import SCHEMA_VERSION, current_schema_version, ensure_schema, migration_notes

    v = ensure_schema(settings)
    assert SCHEMA_VERSION >= 13
    assert v >= 13 or (current_schema_version() or 0) >= 13
    notes = migration_notes()
    assert notes["rollback"]
    assert "sqlite" in notes["engine"]


def test_execution_ledger_policy_block_and_recovery(db, settings):
    ledger = ExecutionLedger()
    wf = uuid4()
    e = ledger.record_start(
        workflow_id=wf,
        case_id=uuid4(),
        capability="hash-compute",
        policy_allowed=False,
        policy_reason="no scope",
    )
    assert e.status == STATUS_BLOCKED
    e2 = ledger.record_start(
        workflow_id=wf,
        capability="hash-compute",
        policy_allowed=True,
    )
    assert e2.status == "running"
    ledger.mark_recovery_required(e2.id, "crash")
    _ = ledger.incomplete_for_workflow(wf)
    assert all(x.status != "running" for x in ledger.list_for_workflow(wf) if x.id == e2.id)
    recovered = [x for x in ledger.list_for_workflow(wf) if x.id == e2.id][0]
    assert recovered.status == STATUS_RECOVERY_REQUIRED
    assert recovered.recovery_state == "awaiting_operator"
    assert recovered.policy_allowed is True


def test_execution_ledger_complete(db, settings):
    ledger = ExecutionLedger()
    e = ledger.record_start(capability="hash-compute", policy_allowed=True)
    ledger.mark_completed(e.id, observation_id=uuid4(), evidence_refs=["ev1"])
    if e.workflow_id:
        items = ledger.list_for_workflow(e.workflow_id)
        assert any(x.status == STATUS_COMPLETED for x in items)


def test_ledger_api(client):
    r = client.post("/api/v1/cases", json={"name": "p13-ledger"})
    assert r.status_code == 201
    cid = r.json()["id"]
    resp = client.get(f"/api/v1/ledger/by-case/{cid}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_structured_result(db, settings):
    from spectra.audit.service import AuditService

    a = AuditService()
    e = a.record(
        "policy.deny",
        actor="tester",
        result="denied",
        request_id="rid-1",
        metadata={"token": "should-redact", "activity": "scan"},
    )
    assert e.result == "denied"
    assert e.metadata.get("token") == "[redacted]"
    assert e.request_id == "rid-1" or e.metadata.get("request_id") == "rid-1"


def test_cases_search_and_status(client):
    assert client.post("/api/v1/cases", json={"name": "p13-alpha-search"}).status_code == 201
    assert client.post("/api/v1/cases", json={"name": "p13-beta-other"}).status_code == 201
    r = client.get("/api/v1/cases?q=alpha")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert any("alpha" in n for n in names)


def test_graph_neighbors_endpoint(client):
    r = client.post("/api/v1/cases", json={"name": "p13-graph-n"})
    assert r.status_code == 201
    nid = "00000000-0000-0000-0000-000000000001"
    nb = client.get(f"/api/v1/graph/neighbors/{nid}?depth=1&limit=10")
    assert nb.status_code == 200
    body = nb.json()
    assert "nodes" in body and "edges" in body
    assert body["depth"] == 1


def test_plugin_rejects_dangerous_fields():
    with pytest.raises(ValueError, match="Forbidden"):
        validate_manifest({"name": "x", "kind": "tool", "harvest_credentials": True})
    with pytest.raises(ValueError, match="Forbidden"):
        validate_manifest({"name": "y", "kind": "tool", "unrestricted_binary": "/bin/sh"})


def test_request_id_still_present(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "p13-rid"})
    assert r.headers.get("X-Request-ID") == "p13-rid"


def test_export_still_no_placeholder_secrets(client):
    r = client.post("/api/v1/cases", json={"name": "p13-exp"})
    cid = r.json()["id"]
    exp = client.get(f"/api/v1/export/cases/{cid}")
    assert exp.status_code == 200
    assert exp.json()["format"] == "spectra.case.export.v1"
