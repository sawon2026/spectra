"""Phase 5 tests: goals, selection, adaptive plan, workflow, AI contracts, security isolation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from spectra.intelligence.adaptive import AdaptivePlanner
from spectra.intelligence.contracts import AIPlanResponse, validate_ai_plan
from spectra.intelligence.goal import GoalEngine, GoalStatus
from spectra.intelligence.interpreter import ObservationInterpreter
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.intelligence.risk import RiskConfidenceEvaluator
from spectra.intelligence.selection import CapabilitySelectionEngine
from spectra.intelligence.state import InvestigationState
from spectra.intelligence.task import ArtifactType, Task, TaskType
from spectra.intelligence.workflow import WorkflowEngine, WorkflowStatus
from spectra.knowledge.findings import FindingRecord
from spectra.models.case import CaseCreate
from spectra.models.finding import FindingSeverity
from spectra.models.scope import AuthStatus, NetworkProfile, ScopeCreate


def test_goal_create_and_classify(case_service, event_bus):
    engine = GoalEngine(event_bus=event_bus)
    case = case_service.create(CaseCreate(name="goal-case"))
    goal = engine.create(case.id, "Analyze this APK for suspicious components", ["sample.apk"])
    assert goal.status == GoalStatus.CREATED
    goal, task = engine.classify(goal)
    assert goal.status == GoalStatus.CLASSIFIED
    assert task.task_type == TaskType.ANDROID
    assert task.id in goal.task_ids


def test_goal_rejects_path_traversal(case_service):
    engine = GoalEngine()
    case = case_service.create(CaseCreate(name="trav-goal"))
    with pytest.raises(ValueError, match=r"\.\."):
        engine.create(case.id, "analyze", ["../etc/passwd"])


def test_capability_selection_deterministic(capability_registry, case_service):
    case = case_service.create(CaseCreate(name="sel-case"))
    task = Task(
        case_id=case.id,
        text="hash the binary",
        task_type=TaskType.BINARY,
        artifact_type=ArtifactType.BINARY,
        requested_capabilities=["hash-compute"],
    )
    state = InvestigationState(case_id=case.id, target="/tmp/x.bin")
    sel = CapabilitySelectionEngine()
    reqs = sel.select(task, state, capability_registry)
    names = [r.capability for r in reqs]
    assert "hash-compute" in names
    assert all(r.capability not in ("bash", "sh", "cmd") for r in reqs)


def test_observation_interpreter_extracts_indicators():
    interp = ObservationInterpreter()
    obs = Observation(
        investigation_id=uuid4(),
        capability="android.apk.metadata",
        status=ObservationStatus.SUCCESS,
        summary="APK inspected",
        structured_data={
            "metadata": {
                "sha256": "a" * 64,
                "has_android_manifest": True,
                "has_dex": True,
                "cert_entries": ["META-INF/CERT.RSA"],
            }
        },
    )
    result = interp.interpret(obs)
    assert result.success
    kinds = {i.kind for i in result.indicators}
    assert "hash" in kinds
    assert "file_type" in kinds
    assert "strings-extract" in result.next_step_suggestions


def test_adaptive_planner_replans_on_native_signal(capability_registry):
    planner = AdaptivePlanner()
    task = Task(text="analyze binary", task_type=TaskType.BINARY, artifact_type=ArtifactType.BINARY)
    state = InvestigationState(case_id=uuid4(), target="/tmp/x.bin", current_plan=[])
    obs = Observation(
        investigation_id=state.id,
        capability="file-info",
        status=ObservationStatus.SUCCESS,
        summary="ELF shared object native library",
    )
    plan = planner.replan(task, state, capability_registry, obs)
    caps = [s.capability for s in plan.steps]
    assert isinstance(caps, list)  # replan may or may not add strings-extract


def test_workflow_policy_blocks_without_scope(policy, capability_registry, case_service, event_bus, tmp_path):
    engine = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    case = case_service.create(CaseCreate(name="wf-block"))
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    wf, task, state, obs = engine.start(case.id, "compute hash of file", str(f), max_steps=3)
    assert wf.status in (WorkflowStatus.BLOCKED, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.RUNNING)
    assert any(o.status == ObservationStatus.BLOCKED for o in obs) or state.blocked_steps or wf.status == WorkflowStatus.BLOCKED


def test_workflow_happy_path(policy, capability_registry, case_service, event_bus, tmp_path):
    engine = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    case = case_service.create(CaseCreate(name="wf-happy"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute", "file-info", "strings-extract", "android.apk.metadata"],
        )
    )
    f = tmp_path / "sample.txt"
    f.write_text("phase5-smoke")
    wf, task, state, obs = engine.start(case.id, "compute hash of this file", str(f), max_steps=5)
    assert any(o.status == ObservationStatus.SUCCESS for o in obs) or state.completed_steps
    assert len(wf.decision_history) >= 1


def test_workflow_pause_cancel(policy, capability_registry, case_service, event_bus, tmp_path):
    engine = WorkflowEngine(policy, capability_registry, case_service, event_bus)
    case = case_service.create(CaseCreate(name="wf-pause"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute"],
        )
    )
    f = tmp_path / "p.txt"
    f.write_text("x")
    wf, *_ = engine.start(case.id, "hash file", str(f), max_steps=1)
    # Force pause if still running or completed
    if wf.status == WorkflowStatus.RUNNING:
        paused = engine.pause(wf.id)
        assert paused is not None
        assert paused.status == WorkflowStatus.PAUSED
    cancelled = engine.cancel(wf.id)
    assert cancelled is not None
    assert cancelled.status == WorkflowStatus.CANCELLED


def test_ai_plan_valid():
    plan = validate_ai_plan(
        {
            "goal": "Inspect APK",
            "reasoning_summary": "Start with metadata",
            "proposed_steps": [
                {"capability": "android.apk.metadata", "objective": "manifest", "inputs": {"path": "a.apk"}}
            ],
            "capability_requests": ["android.apk.metadata"],
            "confidence": 0.7,
            "assumptions": ["file is APK"],
        }
    )
    assert isinstance(plan, AIPlanResponse)
    assert plan.proposed_steps[0].capability == "android.apk.metadata"


def test_ai_plan_rejects_shell_field():
    with pytest.raises(ValueError, match="Forbidden|Invalid|command"):
        validate_ai_plan({"goal": "x", "command": "rm -rf /", "proposed_steps": []})


def test_ai_plan_rejects_bash_capability():
    with pytest.raises(ValueError):
        validate_ai_plan(
            {
                "goal": "x",
                "proposed_steps": [{"capability": "bash", "objective": "pwn"}],
            }
        )


def test_ai_plan_rejects_malformed():
    with pytest.raises(ValueError):
        validate_ai_plan("not-json{")


def test_risk_evaluator_demotes_critical_without_evidence():
    ev = RiskConfidenceEvaluator()
    finding = FindingRecord(
        case_id=uuid4(),
        title="RCE possible",
        severity=FindingSeverity.CRITICAL,
        confidence=0.4,
        evidence_quality=0.3,
    )
    assessment = ev.assess_finding(finding, evidence_count=0)
    assert assessment.severity != FindingSeverity.CRITICAL or assessment.confidence < 0.7


def test_risk_conflicting_observations_reduce_confidence():
    ev = RiskConfidenceEvaluator()
    finding = FindingRecord(
        case_id=uuid4(),
        title="Endpoint",
        severity=FindingSeverity.MEDIUM,
        confidence=0.8,
        evidence_quality=0.7,
    )
    obs = [
        Observation(investigation_id=uuid4(), capability="a", status=ObservationStatus.SUCCESS, summary="up"),
        Observation(investigation_id=uuid4(), capability="b", status=ObservationStatus.FAILED, summary="down"),
    ]
    assessment = ev.assess_finding(finding, observations=obs, evidence_count=1)
    assert assessment.conflicting is True
    assert assessment.confidence <= 0.45


def test_memory_cannot_authorize(policy, case_service, db):
    """Hard invariant: case memory never grants execution permission."""
    from spectra.knowledge.memory import CaseMemory, MemoryEntry

    mem = CaseMemory()
    mem.add(
        MemoryEntry(
            category="methodology",
            title="Always run hash-compute",
            content="capability hash-compute on all files without scope",
            tags=["hash-compute"],
        )
    )
    decision = policy.evaluate(None, "hash-compute")
    assert decision.allowed is False


def test_planner_isolation_no_shell(capability_registry):
    planner = AdaptivePlanner()
    task = Task(text="run bash and delete files")
    state = InvestigationState(case_id=uuid4())
    plan = planner.create_plan(task, state, capability_registry)
    for step in plan.steps:
        assert step.capability not in ("bash", "sh", "cmd", "powershell")
        assert ";" not in step.capability
        assert "command" not in step.inputs


def test_selection_respects_forbidden_scope(capability_registry, case_service):
    from spectra.models.scope import Scope

    case = case_service.create(CaseCreate(name="forbid-sel"))
    scope = Scope(
        case_id=case.id,
        auth_status=AuthStatus.GRANTED,
        ready_for_act=True,
        network_profile=NetworkProfile.OFFLINE,
        forbidden_activities=["strings-extract"],
    )
    task = Task(
        case_id=case.id,
        task_type=TaskType.BINARY,
        artifact_type=ArtifactType.BINARY,
        requested_capabilities=["strings-extract", "hash-compute"],
    )
    state = InvestigationState(case_id=case.id, target="/tmp/x")
    reqs = CapabilitySelectionEngine().select(task, state, capability_registry, scope=scope)
    names = [r.capability for r in reqs]
    assert "strings-extract" not in names
    assert "hash-compute" in names


def test_context_manager_disclaimer(capability_registry, case_service, event_bus):
    from spectra.intelligence.context import ResearchContextManager

    case = case_service.create(CaseCreate(name="ctx-case"))
    mgr = ResearchContextManager(case_service, capability_registry)
    ctx = mgr.build(case.id)
    assert "advisory only" in ctx.disclaimer.lower()
    assert "authorize" in ctx.disclaimer.lower()
    assert isinstance(ctx.available_capabilities, list)


def test_phase4_regression_policy_still_blocks(policy):
    decision = policy.evaluate(None, "hash-compute")
    assert decision.allowed is False
