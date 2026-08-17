"""Phase 10 — pagination and API list contracts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spectra.api.app import create_app
from spectra.api.deps import reset_services
from spectra.auth.session import reset_auth_service
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


def test_cases_default_limit(client):
    for i in range(3):
        r = client.post("/api/v1/cases", json={"name": f"p10-def-{i}"})
        assert r.status_code == 201
    r = client.get("/api/v1/cases")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 3


def test_cases_custom_limit(client):
    for i in range(5):
        assert client.post("/api/v1/cases", json={"name": f"p10-lim-{i}"}).status_code == 201
    r = client.get("/api/v1/cases?limit=2")
    assert r.status_code == 200
    assert len(r.json()) <= 2


def test_cases_limit_validation(client):
    assert client.get("/api/v1/cases?limit=0").status_code == 422
    assert client.get("/api/v1/cases?limit=501").status_code == 422
    assert client.get("/api/v1/cases?limit=1").status_code == 200


def test_cases_stable_list_after_create(client):
    names = [f"p10-ord-{i}" for i in range(3)]
    for n in names:
        assert client.post("/api/v1/cases", json={"name": n}).status_code == 201
    r = client.get("/api/v1/cases?limit=50")
    got = [c["name"] for c in r.json()]
    for n in names:
        assert n in got


def test_schema_version_recorded(db, settings):
    from spectra.core.migrations import SCHEMA_VERSION, current_schema_version, ensure_schema

    v = ensure_schema(settings)
    assert v == SCHEMA_VERSION
    assert current_schema_version() == SCHEMA_VERSION
