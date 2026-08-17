"""Phase 11 — reporting labels, request id, provenance API, classification."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services
from spectra.auth.session import reset_auth_service
from spectra.events.sse import reset_sse_hub
from spectra.reporting.export import (
    CLASS_FINDING,
    CLASS_INFERENCE,
    ReportExporter,
)


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


def test_request_id_header_echo(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "p11-test-rid"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == "p11-test-rid"


def test_request_id_generated(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")


def test_report_markdown_has_classification_and_limitations(client):
    cr = client.post("/api/v1/cases", json={"name": "p11-report-case"})
    assert cr.status_code == 201
    cid = cr.json()["id"]
    r = client.get(f"/api/v1/reports/{cid}/markdown")
    assert r.status_code == 200
    body = r.text
    assert "Classification Legend" in body
    assert "INFERENCE" in body
    assert "Limitations" in body
    assert "PolicyEngine" in body
    assert "FACT" in body
    assert "AI prose is never treated as FACT" in body or "never treated as FACT" in body


def test_report_json_epistemic_fields(client):
    cr = client.post("/api/v1/cases", json={"name": "p11-json-report"})
    assert cr.status_code == 201
    cid = cr.json()["id"]
    r = client.get(f"/api/v1/reports/{cid}/json")
    assert r.status_code == 200
    data = r.json()
    assert "classification_legend" in data
    assert "limitations" in data
    assert "reproducibility" in data
    assert data["reproducibility"].get("policy_gate") == "PolicyEngine"
    assert data["reproducibility"].get("shell") is False
    assert data["reproducibility"].get("offline_default") is True


def test_provenance_list_endpoint(client):
    cr = client.post("/api/v1/cases", json={"name": "p11-prov-case"})
    assert cr.status_code == 201
    cid = cr.json()["id"]
    r = client.get(f"/api/v1/provenance/by-case/{cid}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_exporter_labels_findings():
    from spectra.cases.service import CaseService
    from spectra.models.case import CaseCreate

    case = CaseService().create(CaseCreate(name="p11-exp-label"))
    exporter = ReportExporter()
    bundle = exporter.build(case, findings=[])
    assert CLASS_FINDING in bundle.classification_legend
    assert CLASS_INFERENCE in bundle.classification_legend
    md = exporter.to_markdown(bundle)
    assert "Limitations" in md
    assert "Reproducibility" in md


def test_schema_version_at_least_11(db, settings):
    from spectra.core.migrations import SCHEMA_VERSION, current_schema_version, ensure_schema

    v = ensure_schema(settings)
    assert SCHEMA_VERSION >= 11
    assert v >= 11
    assert current_schema_version() is not None
