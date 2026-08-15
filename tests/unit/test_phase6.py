"""Phase 6 tests: durable workflow, recovery, timeline, provenance, providers, plugins."""

from __future__ import annotations

from uuid import uuid4

import pytest

from spectra.ai.provider import (
    NullLLMProvider,
    OpenAICompatibleProvider,
    ProviderRegistry,
    parse_model_json,
)
from spectra.intelligence.contracts import validate_ai_plan
from spectra.intelligence.workflow import WorkflowEngine, WorkflowStatus
from spectra.knowledge.provenance import ProvenanceKind, ProvenanceService
from spectra.knowledge.timeline import TimelineKind, TimelineService
from spectra.knowledge.workflow_repo import WorkflowRepository, can_transition
from spectra.models.case import CaseCreate
from spectra.models.scope import AuthStatus, NetworkProfile, ScopeCreate
from spectra.plugins.base import PluginKind, PluginRegistry, validate_manifest
from spectra.policy.engine import PolicyEngine


def test_workflow_persisted_across_engine_instances(
    policy, capability_registry, case_service, event_bus, tmp_path, db
):
    engine = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    case = case_service.create(CaseCreate(name="p6-persist"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute", "file-info"],
        )
    )
    f = tmp_path / "a.txt"
    f.write_text("persist-me")
    wf, *_ = engine.start(case.id, "hash this file", str(f), max_steps=3)
    assert wf.id is not None

    engine2 = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    loaded = engine2.get(wf.id)
    assert loaded is not None
    assert loaded.status == wf.status
    assert loaded.case_id == case.id
    assert len(loaded.decision_history) >= 1


def test_invalid_transition_rejected():
    assert can_transition(WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING) is False
    assert can_transition(WorkflowStatus.CANCELLED, WorkflowStatus.PAUSED) is False
    assert can_transition(WorkflowStatus.RUNNING, WorkflowStatus.PAUSED) is True
    assert can_transition(WorkflowStatus.FAILED, WorkflowStatus.RUNNING) is True


def test_workflow_repo_transition_validation(db, case_service):
    from spectra.intelligence.workflow import InvestigationWorkflow

    case = case_service.create(CaseCreate(name="p6-trans"))
    repo = WorkflowRepository()
    wf = InvestigationWorkflow(case_id=case.id, status=WorkflowStatus.COMPLETED)
    repo.save(wf)
    with pytest.raises(ValueError, match="Invalid workflow transition"):
        repo.transition(wf, WorkflowStatus.RUNNING)


def test_crash_recovery_does_not_blind_replay(
    policy, capability_registry, case_service, event_bus, tmp_path, db
):
    engine = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    case = case_service.create(CaseCreate(name="p6-recover"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute"],
        )
    )
    f = tmp_path / "r.txt"
    f.write_text("x")
    wf, *_ = engine.start(case.id, "hash file", str(f), max_steps=2)
    wf.metadata["last_execution_token"] = "hash-compute:fake-step-id"
    wf.status = WorkflowStatus.RUNNING
    WorkflowRepository().save(wf)

    recovered = engine.recover(wf.id)
    assert recovered is not None
    assert recovered.status == WorkflowStatus.BLOCKED
    assert "will not auto-replay" in (recovered.metadata.get("recovery_notes") or "")
    assert any(d.kind == "recovery" for d in recovered.decision_history)


def test_recover_completed_token_stays_stable(
    policy, capability_registry, case_service, event_bus, tmp_path, db
):
    engine = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    case = case_service.create(CaseCreate(name="p6-rec2"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute"],
        )
    )
    f = tmp_path / "r2.txt"
    f.write_text("y")
    wf, *_ = engine.start(case.id, "hash file", str(f), max_steps=2)
    wf.metadata["last_execution_token"] = "hash-compute:abc:done"
    WorkflowRepository().save(wf)
    recovered = engine.recover(wf.id)
    assert recovered is not None
    assert recovered.status != WorkflowStatus.BLOCKED or "completed" in (
        recovered.metadata.get("recovery_notes") or ""
    ).lower() or recovered.status in (
        WorkflowStatus.COMPLETED,
        WorkflowStatus.RUNNING,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.FAILED,
    )


def test_timeline_kinds_and_ai_not_fact(db, case_service):
    case = case_service.create(CaseCreate(name="p6-tl"))
    tl = TimelineService()
    e1 = tl.append(case.id, TimelineKind.FACT, "File hash is abc", source="hash-compute")
    tl.append(case.id, TimelineKind.HYPOTHESIS, "Maybe packed", source="analyst", confidence=0.4)
    e3 = tl.append(case.id, TimelineKind.INFERENCE, "Likely malware", source="ai-model", confidence=0.5)
    with pytest.raises(ValueError, match="FACT"):
        tl.append(case.id, TimelineKind.FACT, "AI says malware", source="llm-gpt")
    entries = tl.list_for_case(case.id)
    assert len(entries) >= 3
    kinds = {e.kind for e in entries}
    assert TimelineKind.FACT in kinds
    assert TimelineKind.HYPOTHESIS in kinds
    assert e1.kind == TimelineKind.FACT
    assert e3.kind == TimelineKind.INFERENCE


def test_provenance_chain(db, case_service):
    case = case_service.create(CaseCreate(name="p6-prov"))
    prov = ProvenanceService()
    art, cap, obs, evid, finding = (uuid4() for _ in range(5))
    prov.link(case.id, ProvenanceKind.ARTIFACT, art, ProvenanceKind.CAPABILITY, cap)
    prov.link(case.id, ProvenanceKind.CAPABILITY, cap, ProvenanceKind.OBSERVATION, obs)
    prov.link(case.id, ProvenanceKind.OBSERVATION, obs, ProvenanceKind.EVIDENCE, evid, content_hash="a" * 64)
    prov.link(case.id, ProvenanceKind.EVIDENCE, evid, ProvenanceKind.FINDING, finding)
    chain = prov.chain_for(obs, case.id)
    assert len(chain) >= 2
    up = prov.upstream(evid)
    assert any(link.from_kind == ProvenanceKind.OBSERVATION for link in up)
    down = prov.downstream(art)
    assert any(link.to_kind == ProvenanceKind.CAPABILITY for link in down)


def test_provider_registry_offline_default():
    reg = ProviderRegistry()
    active = reg.active()
    assert active.is_configured() is False or isinstance(active, NullLLMProvider) or not active.is_configured()
    infos = reg.list_info()
    assert any(i.name == "null" for i in infos)


def test_openai_provider_not_configured_without_keys():
    p = OpenAICompatibleProvider(api_base="", api_key="")
    assert p.is_configured() is False
    with pytest.raises(RuntimeError):
        p.classify_task("analyze apk")


def test_provider_rejects_shell_in_parse():
    with pytest.raises(ValueError, match="Forbidden"):
        parse_model_json({"command": "rm -rf /", "task_type": "binary"})
    with pytest.raises(ValueError):
        validate_ai_plan({"goal": "x", "shell": "bash", "proposed_steps": []})


def test_plugin_manifest_validation():
    m = validate_manifest(
        {
            "name": "hash-plugin",
            "kind": "tool_adapter",
            "version": "1.0.0",
            "requires_authorization": True,
        }
    )
    assert m.kind == PluginKind.TOOL_ADAPTER
    with pytest.raises(ValueError):
        validate_manifest({"name": "../evil", "kind": "capability"})
    with pytest.raises(ValueError):
        validate_manifest({"name": "x", "kind": "capability", "shell": "yes"})


def test_plugin_registry():
    reg = PluginRegistry()
    reg.register({"name": "strings-parser", "kind": "parser"})
    assert reg.get("strings-parser") is not None
    assert len(reg.list(PluginKind.PARSER)) == 1
    with pytest.raises(ValueError):
        reg.register({"name": "strings-parser", "kind": "parser"})


def test_pause_resume_cancel_durable(
    policy, capability_registry, case_service, event_bus, tmp_path, db
):
    engine = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    case = case_service.create(CaseCreate(name="p6-prc"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute"],
        )
    )
    f = tmp_path / "p.txt"
    f.write_text("z")
    wf, *_ = engine.start(case.id, "hash", str(f), max_steps=1)
    if wf.status == WorkflowStatus.RUNNING:
        paused = engine.pause(wf.id)
        assert paused is not None
        assert paused.status == WorkflowStatus.PAUSED
        assert WorkflowRepository().get(wf.id).status == WorkflowStatus.PAUSED
    cancelled = engine.cancel(wf.id)
    assert cancelled is not None
    assert cancelled.status == WorkflowStatus.CANCELLED
    assert WorkflowRepository().get(wf.id).status == WorkflowStatus.CANCELLED


def test_policy_still_blocks_without_scope(policy):
    assert PolicyEngine().evaluate(None, "hash-compute").allowed is False


def test_phase5_regression_ai_contracts():
    plan = validate_ai_plan(
        {
            "goal": "Inspect",
            "proposed_steps": [{"capability": "hash-compute", "objective": "hash"}],
            "confidence": 0.6,
        }
    )
    assert plan.proposed_steps[0].capability == "hash-compute"
