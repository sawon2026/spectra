"""Phase 12 — export, graph filters, plugin registry, schema."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services
from spectra.auth.session import reset_auth_service
from spectra.events.sse import reset_sse_hub
from spectra.plugins.base import (
    PluginHealthStatus,
    PluginKind,
    PluginRegistry,
    validate_manifest,
)
from spectra.reporting.backup import build_case_export


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


def test_case_export_bundle(client):
    r = client.post("/api/v1/cases", json={"name": "p12-export"})
    assert r.status_code == 201
    cid = r.json()["id"]
    exp = client.get(f"/api/v1/export/cases/{cid}")
    assert exp.status_code == 200
    body = exp.json()
    assert body["format"] == "spectra.case.export.v1"
    assert body["case"]["name"] == "p12-export"
    assert "integrity" in body
    assert "limitations" in body
    assert body["integrity"]["case_id"] == cid or body["case"]["id"] == cid


def test_export_build_helper():
    b = build_case_export(case={"id": "x", "name": "n"}, evidence=[{"id": "e1"}])
    assert b.integrity["evidence_count"] == 1
    assert "secrets" in b.limitations.lower() or "tokens" in b.limitations.lower()


def test_graph_nodes_filter_params(client):
    r = client.post("/api/v1/cases", json={"name": "p12-graph"})
    assert r.status_code == 201
    cid = r.json()["id"]
    g = client.get(f"/api/v1/graph/nodes/{cid}?limit=10")
    assert g.status_code == 200
    assert isinstance(g.json(), list)
    g2 = client.get(f"/api/v1/graph/nodes/{cid}?node_type=finding&q=test")
    assert g2.status_code == 200


def test_plugin_forbidden_manifest_fields():
    with pytest.raises(ValueError, match="Forbidden"):
        validate_manifest({"name": "bad", "shell": True})
    with pytest.raises(ValueError, match="Forbidden"):
        validate_manifest({"name": "bad2", "policy_override": 1})


def test_plugin_registry_lifecycle():
    reg = PluginRegistry()
    m = reg.register(
        {
            "name": "p12-hash-helper",
            "version": "0.1.0",
            "kind": "tool",
            "capabilities": ["hash-compute"],
            "offline_safe": True,
        }
    )
    assert m.kind == PluginKind.TOOL
    assert reg.state("p12-hash-helper") is not None
    reg.enable("p12-hash-helper")
    assert reg.state("p12-hash-helper").value == "enabled"
    reg.disable("p12-hash-helper")
    assert reg.state("p12-hash-helper").value == "disabled"
    h = reg.set_health("p12-hash-helper", PluginHealthStatus.OK, "fine")
    assert h.status == PluginHealthStatus.OK
    listed = reg.list_with_status()
    assert any(x["name"] == "p12-hash-helper" for x in listed)


def test_schema_version_at_least_12(db, settings):
    from spectra.core.migrations import SCHEMA_VERSION, current_schema_version, ensure_schema

    v = ensure_schema(settings)
    assert SCHEMA_VERSION >= 12
    assert v >= 12 or current_schema_version() is not None


def test_sanitize_payload_redacts_secrets():
    from spectra.events.sse import sanitize_payload

    out = sanitize_payload({"token": "secret-value", "ok": "yes", "api_key": "k"})
    assert out["token"] == "[redacted]"
    assert out["api_key"] == "[redacted]"
    assert out["ok"] == "yes"
