"""Investigation Workflow Engine — pause/resume/cancel with persisted state."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.capabilities.registry import CapabilityRegistry
from spectra.cases.service import CaseService
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.intelligence.adaptive import AdaptivePlanner
from spectra.intelligence.goal import GoalEngine, GoalStatus, ResearchGoal
from spectra.intelligence.observation import Observation
from spectra.intelligence.orchestrator import InvestigationOrchestrator
from spectra.intelligence.state import InvestigationState, InvestigationStatus
from spectra.intelligence.task import Task
from spectra.knowledge.investigation_repo import InvestigationRepository
from spectra.models.events import EventType, SpectraEvent
from spectra.policy.engine import PolicyEngine

logger = get_logger(__name__)


class WorkflowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionRecord(BaseModel):
    """Explainable decision history entry."""

    id: UUID = Field(default_factory=uuid4)
    kind: str  # e.g. plan, replan, policy_deny, capability_select
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InvestigationWorkflow(BaseModel):
    """Reusable investigation workflow container."""

    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    goal: ResearchGoal | None = None
    investigation_id: UUID | None = None
    task_id: UUID | None = None
    status: WorkflowStatus = WorkflowStatus.CREATED
    decision_history: list[DecisionRecord] = Field(default_factory=list)
    observation_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def record_decision(self, kind: str, summary: str, payload: dict[str, Any] | None = None) -> None:
        self.decision_history.append(
            DecisionRecord(kind=kind, summary=summary, payload=payload or {})
        )
        self.updated_at = datetime.now(UTC)


class WorkflowEngine:
    """Orchestrates goal → classify → plan → policy-gated execute with pause/resume.

    Recovery uses InvestigationRepository for investigation state.
    Workflow metadata is held in-memory for this phase (persisted via investigation).
    """

    def __init__(
        self,
        policy: PolicyEngine,
        registry: CapabilityRegistry,
        case_service: CaseService,
        event_bus: EventBus | None = None,
    ) -> None:
        self.policy = policy
        self.registry = registry
        self.cases = case_service
        self.bus = event_bus or EventBus(persist=True)
        self.goals = GoalEngine(event_bus=self.bus)
        self.planner = AdaptivePlanner(event_bus=self.bus)
        self.orch = InvestigationOrchestrator(
            policy=policy,
            registry=registry,
            case_service=case_service,
            event_bus=self.bus,
            planner=self.planner,
        )
        self._inv_repo = InvestigationRepository()
        self._workflows: dict[UUID, InvestigationWorkflow] = {}

    def start(
        self,
        case_id: UUID,
        goal_text: str,
        artifact_path: str = "",
        max_steps: int = 8,
    ) -> tuple[InvestigationWorkflow, Task, InvestigationState, list[Observation]]:
        goal = self.goals.create(
            case_id,
            goal_text,
            artifact_paths=[artifact_path] if artifact_path else [],
        )
        goal, task = self.goals.classify(goal)
        goal.transition(GoalStatus.PLANNED)

        wf = InvestigationWorkflow(
            case_id=case_id,
            goal=goal,
            task_id=task.id,
            status=WorkflowStatus.RUNNING,
        )
        wf.record_decision("goal_classified", f"task_type={task.task_type.value}", {
            "capabilities": task.requested_capabilities,
        })

        # Use orchestrator for policy-gated execution
        task2, state, observations = self.orch.run_to_completion(
            case_id, goal_text, artifact_path, max_steps=max_steps
        )
        wf.investigation_id = state.id
        wf.observation_ids = [o.id for o in observations]
        for o in observations:
            wf.record_decision(
                "observation",
                f"{o.capability}:{o.status.value}",
                {"summary": (o.summary or "")[:200]},
            )

        if state.status == InvestigationStatus.COMPLETED:
            wf.status = WorkflowStatus.COMPLETED
            goal.transition(GoalStatus.COMPLETED)
        elif state.status == InvestigationStatus.BLOCKED:
            wf.status = WorkflowStatus.BLOCKED
            goal.transition(GoalStatus.BLOCKED)
        elif state.status == InvestigationStatus.FAILED:
            wf.status = WorkflowStatus.FAILED
            goal.transition(GoalStatus.FAILED)
        else:
            wf.status = WorkflowStatus.RUNNING

        self._workflows[wf.id] = wf
        self._emit(EventType.INVESTIGATION_COMPLETED if wf.status == WorkflowStatus.COMPLETED else EventType.AUDIT,
                   case_id, f"Workflow {wf.status.value}", {"workflow_id": str(wf.id)})
        return wf, task2, state, observations

    def pause(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        wf = self._workflows.get(workflow_id)
        if not wf or wf.status not in (WorkflowStatus.RUNNING, WorkflowStatus.BLOCKED):
            return None
        wf.status = WorkflowStatus.PAUSED
        wf.record_decision("pause", "User paused investigation")
        if wf.investigation_id:
            state = self._inv_repo.get(wf.investigation_id)
            if state:
                state.transition(InvestigationStatus.CANCELLED)  # soft pause marker via metadata
                state.metadata["paused"] = True
                self._inv_repo.save(state)
        self._emit(EventType.INVESTIGATION_PAUSED, wf.case_id, "Investigation paused", {"workflow_id": str(wf.id)})
        return wf

    def resume(self, workflow_id: UUID, max_steps: int = 5) -> tuple[InvestigationWorkflow, InvestigationState, list[Observation]] | None:
        wf = self._workflows.get(workflow_id)
        if not wf or wf.status != WorkflowStatus.PAUSED:
            return None
        if not wf.investigation_id or not wf.goal:
            return None
        state = self._inv_repo.get(wf.investigation_id)
        if state is None:
            return None
        state.metadata.pop("paused", None)
        state.transition(InvestigationStatus.EXECUTING)
        self._inv_repo.save(state)

        # Continue execution via orchestrator step loop
        from spectra.intelligence.task import Task

        task = Task(case_id=wf.case_id, text=wf.goal.text, id=wf.task_id or uuid4())
        scope = self.cases.get_scope(wf.case_id)
        observations: list[Observation] = []
        for _ in range(max_steps):
            if state.status in (
                InvestigationStatus.COMPLETED,
                InvestigationStatus.FAILED,
                InvestigationStatus.BLOCKED,
                InvestigationStatus.CANCELLED,
            ):
                break
            state, obs = self.orch.execute_next(task, state, scope)
            if obs:
                observations.append(obs)
                wf.observation_ids.append(obs.id)
            if state.next_pending_step() is None:
                if state.status not in (
                    InvestigationStatus.COMPLETED,
                    InvestigationStatus.FAILED,
                    InvestigationStatus.BLOCKED,
                ):
                    state.transition(InvestigationStatus.COMPLETED)
                break

        wf.status = {
            InvestigationStatus.COMPLETED: WorkflowStatus.COMPLETED,
            InvestigationStatus.FAILED: WorkflowStatus.FAILED,
            InvestigationStatus.BLOCKED: WorkflowStatus.BLOCKED,
        }.get(state.status, WorkflowStatus.RUNNING)
        wf.record_decision("resume", f"Resumed; status={wf.status.value}")
        self._emit(EventType.INVESTIGATION_RESUMED, wf.case_id, "Investigation resumed", {"workflow_id": str(wf.id)})
        return wf, state, observations

    def cancel(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return None
        wf.status = WorkflowStatus.CANCELLED
        if wf.goal:
            wf.goal.transition(GoalStatus.CANCELLED)
        wf.record_decision("cancel", "Investigation cancelled")
        if wf.investigation_id:
            state = self._inv_repo.get(wf.investigation_id)
            if state:
                state.transition(InvestigationStatus.CANCELLED)
                self._inv_repo.save(state)
        return wf

    def get(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        return self._workflows.get(workflow_id)

    def _emit(self, event_type: EventType, case_id: UUID | None, message: str, payload: dict[str, Any]) -> None:
        self.bus.publish(
            SpectraEvent(
                event_type=event_type,
                case_id=case_id,
                message=message,
                payload=payload,
                actor="workflow_engine",
            )
        )
