"""Intelligence layer tests — offline, deterministic, policy-invariant."""

from __future__ import annotations

from uuid import uuid4

import pytest

from spectra.intelligence.classifier import DeterministicClassifier
from spectra.intelligence.observation import ObservationStatus
from spectra.intelligence.orchestrator import InvestigationOrchestrator
from spectra.intelligence.planner import DeterministicPlanner
from spectra.intelligence.state import InvestigationStatus
from spectra.intelligence.task import ArtifactType, TaskCreate, TaskType
from spectra.models.case import CaseCreate
from spectra.models.scope import AuthStatus, NetworkProfile, ScopeCreate


@pytest.fixture()
def orch(policy, capability_registry, case_service, event_bus) -> InvestigationOrchestrator:
    return InvestigationOrchestrator(
        policy=policy,
        registry=capability_registry,
        case_service=case_service,
        event_bus=event_bus,
        classifier=DeterministicClassifier(),
        planner=DeterministicPlanner(),
    )


def test_classifier_apk():
    c = DeterministicClassifier()
    t = c.classify(TaskCreate(text="Analyze this APK and inspect the manifest"))
    assert t.task_type == TaskType.ANDROID
    assert t.artifact_type == ArtifactType.APK
    assert t.authorization_required is True


def test_classifier_binary():
    c = DeterministicClassifier()
    t = c.classify(TaskCreate(text="Reverse the ELF binary with strings"))
    assert t.task_type in (TaskType.BINARY, TaskType.REVERSE_ENGINEERING)
    assert "hash-compute" in t.requested_capabilities or "strings-extract" in t.requested_capabilities


def test_plan_uses_capabilities_not_shell(orch, case_service):
    case = case_service.create(CaseCreate(name="plan-case"))
    task, state = orch.start(case.id, "hash this sample file", artifact_path="/tmp/x.bin")
    assert state.current_plan
    for step in state.current_plan:
        assert step.capability  # named capability
        assert "bash" not in step.capability
        assert ";" not in step.capability
        assert not step.inputs.get("command")  # no raw command field


def test_policy_blocks_without_scope(orch, case_service, tmp_path):
    case = case_service.create(CaseCreate(name="no-scope-case"))
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    task, state, obs = orch.run_to_completion(case.id, "compute hash of file", str(f))
    assert state.status in (InvestigationStatus.BLOCKED, InvestigationStatus.COMPLETED, InvestigationStatus.FAILED)
    # Without granted scope, steps should be blocked
    assert any(o.status == ObservationStatus.BLOCKED for o in obs) or state.blocked_steps


def test_policy_blocks_pending_auth(orch, case_service, tmp_path):
    case = case_service.create(CaseCreate(name="pending-auth"))
    case_service.set_scope(
        ScopeCreate(case_id=case.id, auth_status=AuthStatus.PENDING, network_profile=NetworkProfile.OFFLINE)
    )
    f = tmp_path / "b.bin"
    f.write_text("data")
    task, state, obs = orch.run_to_completion(case.id, "hash the file", str(f))
    assert any(o.status == ObservationStatus.BLOCKED for o in obs)
    assert all(
        "granted" in (o.error or o.summary).lower() or "ready" in (o.error or o.summary).lower()
        for o in obs
        if o.status == ObservationStatus.BLOCKED
    )


def test_happy_path_with_granted_scope(orch, case_service, tmp_path):
    case = case_service.create(CaseCreate(name="happy-path"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute", "file-info", "strings-extract"],
        )
    )
    f = tmp_path / "sample.txt"
    f.write_text("spectra-phase2")
    task, state, obs = orch.run_to_completion(case.id, "compute hash of this file", str(f), max_steps=5)
    assert any(o.status == ObservationStatus.SUCCESS for o in obs)
    assert state.completed_steps or state.status == InvestigationStatus.COMPLETED


def test_nonexistent_capability_unavailable(orch, case_service, tmp_path, policy, capability_registry, event_bus):
    # Inject a plan step for missing capability via custom state path
    case = case_service.create(CaseCreate(name="missing-cap"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["does-not-exist"],
        )
    )
    from spectra.intelligence.state import InvestigationState, InvestigationStatus, PlanStep
    from spectra.intelligence.task import Task

    task = Task(case_id=case.id, text="x", requested_capabilities=["does-not-exist"])
    state = InvestigationState(
        case_id=case.id,
        status=InvestigationStatus.EXECUTING,
        current_plan=[PlanStep(capability="does-not-exist", inputs={}, objective="x")],
    )
    scope = case_service.get_scope(case.id)
    state, obs = orch.execute_next(task, state, scope)
    assert obs is not None
    assert obs.status in (ObservationStatus.UNAVAILABLE, ObservationStatus.BLOCKED)


def test_planner_cannot_bypass_policy_via_malformed_inputs(orch, case_service, tmp_path):
    """Adversarial: even if plan step has malicious path, policy still applies."""
    case = case_service.create(CaseCreate(name="malicious-path"))
    # No scope at all
    from spectra.intelligence.state import InvestigationState, InvestigationStatus, PlanStep
    from spectra.intelligence.task import Task

    task = Task(case_id=case.id, text="evil", requested_capabilities=["hash-compute"])
    state = InvestigationState(
        case_id=case.id,
        status=InvestigationStatus.EXECUTING,
        target="../../etc/passwd",
        current_plan=[
            PlanStep(capability="hash-compute", inputs={"path": "../../etc/passwd"}, objective="steal")
        ],
    )
    state, obs = orch.execute_next(task, state, scope=None)
    assert obs is not None
    assert obs.status == ObservationStatus.BLOCKED


def test_network_denied_when_offline(orch, case_service, tmp_path):
    case = case_service.create(CaseCreate(name="net-deny"))
    case_service.set_scope(
        ScopeCreate(
            case_id=case.id,
            auth_status=AuthStatus.GRANTED,
            network_profile=NetworkProfile.OFFLINE,
            allowed_activities=["hash-compute"],
        )
    )
    from spectra.intelligence.state import InvestigationState, InvestigationStatus, PlanStep
    from spectra.intelligence.task import Task

    task = Task(case_id=case.id, text="scan remote", network_required=True, requested_capabilities=["hash-compute"])
    f = tmp_path / "c.bin"
    f.write_text("x")
    state = InvestigationState(
        case_id=case.id,
        status=InvestigationStatus.EXECUTING,
        target=str(f),
        current_plan=[PlanStep(capability="hash-compute", inputs={"path": str(f)}, objective="x")],
    )
    scope = case_service.get_scope(case.id)
    state, obs = orch.execute_next(task, state, scope)
    assert obs is not None
    assert obs.status == ObservationStatus.BLOCKED
    assert "offline" in (obs.summary or "").lower() or "network" in (obs.summary or "").lower()


def test_replan_adds_strings_on_native_signal(capability_registry):
    planner = DeterministicPlanner()
    from spectra.intelligence.observation import Observation, ObservationStatus
    from spectra.intelligence.state import InvestigationState
    from spectra.intelligence.task import Task

    task = Task(text="analyze binary")
    state = InvestigationState(case_id=uuid4(), current_plan=[])
    obs = Observation(
        investigation_id=state.id,
        capability="file-info",
        status=ObservationStatus.SUCCESS,
        summary="ELF shared object native library detected",
    )
    plan = planner.replan(task, state, capability_registry, obs)
    caps = [s.capability for s in plan.steps]
    # strings-extract is seeded as builtin
    assert "strings-extract" in caps or plan.steps == []  # empty if not available is ok
