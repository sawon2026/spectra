"""Phase 4 tests: android adapter, reports, LLM validation, doctor."""

from __future__ import annotations

import zipfile
from uuid import uuid4

import pytest

from spectra.ai.provider import NullLLMProvider, parse_model_json
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.knowledge.findings import FindingEngine
from spectra.models.case import CaseCreate
from spectra.models.scope import AuthStatus, NetworkProfile, ScopeCreate
from spectra.reporting.export import ReportExporter
from spectra.tools.android.apk_meta import ApkMetadataAdapter


def test_apk_metadata_on_minimal_zip(policy, event_bus, tmp_path, case_service):
    apk = tmp_path / "sample.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"not-real-binary-xml")
        zf.writestr("classes.dex", b"dex\n")
        zf.writestr("META-INF/CERT.RSA", b"cert")

    case = case_service.create(CaseCreate(name="apk-case"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["android.apk.metadata"],
            in_scope_assets=[],
        )
    )
    scope = case_service.get_scope(case.id)
    adapter = ApkMetadataAdapter(policy, event_bus)
    assert adapter.is_available()
    result = adapter.execute(scope=scope, case_id=case.id, inputs={"path": str(apk)})
    assert result.success
    assert result.metadata.get("has_android_manifest") is True
    assert result.metadata.get("has_dex") is True
    assert result.metadata.get("sha256")


def test_apk_metadata_blocked_without_scope(policy, event_bus, tmp_path):
    apk = tmp_path / "x.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"x")
    adapter = ApkMetadataAdapter(policy, event_bus)
    result = adapter.execute(scope=None, case_id=uuid4(), inputs={"path": str(apk)})
    assert not result.success
    assert "scope" in (result.error or "").lower() or "auth" in (result.error or "").lower()


def test_apk_malformed(policy, event_bus, tmp_path, case_service):
    bad = tmp_path / "bad.apk"
    bad.write_bytes(b"not-a-zip")
    case = case_service.create(CaseCreate(name="bad-apk"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["android.apk.metadata"],
        )
    )
    adapter = ApkMetadataAdapter(policy, event_bus)
    result = adapter.execute(
        scope=case_service.get_scope(case.id),
        case_id=case.id,
        inputs={"path": str(bad)},
    )
    assert not result.success


def test_report_markdown_json(case_service, event_bus):
    case = case_service.create(CaseCreate(name="report-case", description="demo"))
    engine = FindingEngine(event_bus=event_bus)
    obs = Observation(
        investigation_id=uuid4(),
        capability="android.apk.metadata",
        status=ObservationStatus.SUCCESS,
        summary="manifest present",
    )
    engine.create_from_observation(case_id=case.id, observation=obs, title="Manifest present")
    exporter = ReportExporter(engine)
    bundle = exporter.build(case)
    md = exporter.to_markdown(bundle)
    assert "Executive Summary" in md
    assert "Manifest present" in md
    js = exporter.to_json(bundle)
    assert "findings" in js


def test_llm_parse_valid():
    resp = parse_model_json(
        {
            "task_type": "android",
            "artifact_type": "apk",
            "objectives": ["inspect_manifest"],
            "requested_capabilities": ["android.apk.metadata"],
            "risk_level": "low",
            "confidence": 0.8,
        }
    )
    assert resp.task_type.value == "android"


def test_llm_rejects_shell_field():
    with pytest.raises(ValueError, match="Forbidden|Invalid|command"):
        parse_model_json({"task_type": "android", "command": "rm -rf /"})


def test_llm_rejects_malformed():
    with pytest.raises(ValueError):
        parse_model_json("not-json{")


def test_null_provider_not_configured():
    p = NullLLMProvider()
    assert p.is_configured() is False


def test_doctor_runs(capsys):
    from spectra.cli.main import doctor

    doctor()
    out = capsys.readouterr().out
    assert "Core" in out or "Spectra" in out
    assert "Policy" in out or "policy" in out.lower() or "OK" in out
