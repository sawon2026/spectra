"""Phase 4 tests: android adapter, reporting, AI provider null, doctor surface."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from spectra.ai.provider import NullLLMProvider, parse_model_json
from spectra.models.scope import AuthStatus, NetworkProfile, Scope
from spectra.reporting.export import ReportBundle, ReportExporter
from spectra.tools.android.apk_meta import ApkMetadataAdapter


def _make_minimal_apk(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"dummy")
        zf.writestr("classes.dex", b"dex\n")
        zf.writestr("META-INF/CERT.RSA", b"cert")


def test_apk_metadata_adapter(tmp_path: Path):
    apk = tmp_path / "sample.apk"
    _make_minimal_apk(apk)
    adapter = ApkMetadataAdapter()
    assert adapter.is_available() is True
    scope = Scope(
        case_id=uuid4(),
        auth_status=AuthStatus.GRANTED,
        network_profile=NetworkProfile.OFFLINE,
    )
    result = adapter.execute(scope=scope, case_id=scope.case_id, inputs={"path": str(apk)})
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.get("has_android_manifest") is True
    assert result.metadata.get("has_dex") is True
    assert "sha256" in result.metadata


def test_apk_rejects_non_zip(tmp_path: Path):
    f = tmp_path / "not.apk"
    f.write_text("not a zip")
    adapter = ApkMetadataAdapter()
    scope = Scope(
        case_id=uuid4(),
        auth_status=AuthStatus.GRANTED,
        network_profile=NetworkProfile.OFFLINE,
    )
    result = adapter.execute(scope=scope, case_id=scope.case_id, inputs={"path": str(f)})
    assert result.success is False


def test_report_exporter_markdown_json():
    bundle = ReportBundle(
        case_id=str(uuid4()),
        case_name="demo",
        findings=[{"title": "f1", "severity": "low"}],
        evidence_count=1,
        observations=[],
    )
    exporter = ReportExporter()
    md = exporter.to_markdown(bundle)
    assert "demo" in md
    js = exporter.to_json(bundle)
    data = json.loads(js)
    assert data["case_name"] == "demo"


def test_null_llm_provider():
    p = NullLLMProvider()
    assert p.is_available() is False
    out = p.complete("hello")
    assert out is None or out == ""


def test_parse_model_json_valid():
    raw = '{"tasks": [{"name": "x"}], "notes": "ok"}'
    parsed = parse_model_json(raw)
    assert parsed is not None
    assert "tasks" in parsed


def test_parse_model_json_invalid():
    assert parse_model_json("not json") is None
    assert parse_model_json("") is None


def test_apk_policy_gate(tmp_path: Path):
    apk = tmp_path / "s.apk"
    _make_minimal_apk(apk)
    adapter = ApkMetadataAdapter()
    scope = Scope(
        case_id=uuid4(),
        auth_status=AuthStatus.DENIED,
        network_profile=NetworkProfile.OFFLINE,
    )
    result = adapter.execute(scope=scope, case_id=scope.case_id, inputs={"path": str(apk)})
    assert result.success is False


def test_report_bundle_defaults():
    b = ReportBundle(case_id="x", case_name="y")
    assert b.findings == []
    assert b.evidence_count == 0


def test_apk_missing_path():
    adapter = ApkMetadataAdapter()
    result = adapter.execute(scope=None, case_id=uuid4(), inputs={})
    assert result.success is False
