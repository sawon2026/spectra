"""Investigation Workflow Engine — durable pause/resume/cancel/recover (Phase 6)."""

from __future__ import annotations

from contextlib import suppress
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
from spectra.knowledge.provenance import ProvenanceKind, ProvenanceService
from spectra.knowledge.timeline import TimelineKind, TimelineService
from spectra.knowledge.workflow_repo import WorkflowRepository, can_transition
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
    kind: str
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InvestigationWorkflow(BaseModel):
    """Reusable investigation workflow container (durable via WorkflowRepository)."""

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
    """Orchestrates goal → classify → plan → policy-gated execute with durable state.

    Phase 6: workflows are persisted; crash recovery does not blindly replay
    unfinished capability executions.
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
        self._wf_repo = WorkflowRepository()
        self._timeline = TimelineService(event_bus=self.bus)
        self._provenance = ProvenanceService()

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
        wf.record_decision(
            "goal_classified",
            f"task_type={task.task_type.value}",
            {"capabilities": task.requested_capabilities},
        )
        self._wf_repo.save(wf)
        self._timeline.append(
            case_id,
            TimelineKind.WORKFLOW,
            f"Workflow started: {goal_text[:200]}",
            workflow_id=wf.id,
            source="workflow_engine",
        )
        if artifact_path:
            art_id = uuid4()
            wf.metadata["artifact_token"] = str(art_id)
            self._provenance.link(
                case_id,
                ProvenanceKind.ARTIFACT,
                art_id,
                ProvenanceKind.WORKFLOW,
                wf.id,
                relation="investigated_by",
                payload={"path": artifact_path[:512]},
            )

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
            self._timeline.append(
                case_id,
                TimelineKind.OBSERVATION,
                f"{o.capability}: {o.status.value} — {(o.summary or '')[:200]}",
                investigation_id=state.id,
                workflow_id=wf.id,
                source=o.capability or "executor",
                confidence=getattr(o, "confidence", None),
                references=[str(o.id)],
            )
            self._provenance.link(
                case_id,
                ProvenanceKind.EXECUTION,
                o.id,
                ProvenanceKind.OBSERVATION,
                o.id,
                relation="produced",
                payload={"capability": o.capability},
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

        pending = state.next_pending_step() if hasattr(state, "next_pending_step") else None
        if pending:
            wf.metadata["last_step_id"] = str(pending.id)
            wf.metadata["last_execution_token"] = f"{pending.capability}:{pending.id}"
        else:
            completed = state.completed_steps[-1] if state.completed_steps else None
            if completed:
                wf.metadata["last_step_id"] = str(completed.id)
                wf.metadata["last_execution_token"] = f"{completed.capability}:{completed.id}:done"

        self._wf_repo.save(wf)
        self._timeline.append(
            case_id,
            TimelineKind.WORKFLOW,
            f"Workflow status={wf.status.value}",
            investigation_id=state.id,
            workflow_id=wf.id,
            source="workflow_engine",
        )
        self._emit(
            EventType.INVESTIGATION_COMPLETED
            if wf.status == WorkflowStatus.COMPLETED
            else EventType.AUDIT,
            case_id,
            f"Workflow {wf.status.value}",
            {"workflow_id": str(wf.id)},
        )
        return wf, task2, state, observations

    def pause(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        wf = self._wf_repo.get(workflow_id)
        if not wf or wf.status not in (WorkflowStatus.RUNNING, WorkflowStatus.BLOCKED):
            return None
        if not can_transition(wf.status, WorkflowStatus.PAUSED):
            return None
        wf.status = WorkflowStatus.PAUSED
        wf.record_decision("pause", "User paused investigation")
        if wf.investigation_id:
            state = self._inv_repo.get(wf.investigation_id)
            if state:
                state.metadata["paused"] = True
                self._inv_repo.save(state)
        self._wf_repo.save(wf)
        self._timeline.append(
            wf.case_id,
            TimelineKind.DECISION,
            "Investigation paused",
            workflow_id=wf.id,
            investigation_id=wf.investigation_id,
            source="workflow_engine",
        )
        self._emit(
            EventType.INVESTIGATION_PAUSED,
            wf.case_id,
            "Investigation paused",
            {"workflow_id": str(wf.id)},
        )
        return wf

    def resume(
        self, workflow_id: UUID, max_steps: int = 5
    ) -> tuple[InvestigationWorkflow, InvestigationState, list[Observation]] | None:
        wf = self._wf_repo.get(workflow_id)
        if not wf or wf.status != WorkflowStatus.PAUSED:
            return None
        if not can_transition(wf.status, WorkflowStatus.RUNNING):
            return None
        if not wf.investigation_id or not wf.goal:
            return None
        state = self._inv_repo.get(wf.investigation_id)
        if state is None:
            return None
        state.metadata.pop("paused", None)
        if state.status == InvestigationStatus.CANCELLED and state.metadata.get("was_paused"):
            state.transition(InvestigationStatus.EXECUTING)
        elif state.status not in (
            InvestigationStatus.COMPLETED,
            InvestigationStatus.FAILED,
            InvestigationStatus.CANCELLED,
        ):
            with suppress(Exception):
                state.transition(InvestigationStatus.EXECUTING)
        self._inv_repo.save(state)

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
                self._timeline.append(
                    wf.case_id,
                    TimelineKind.OBSERVATION,
                    f"{obs.capability}: {obs.status.value}",
                    investigation_id=state.id,
                    workflow_id=wf.id,
                    source=obs.capability or "executor",
                    references=[str(obs.id)],
                )
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
        self._wf_repo.save(wf)
        self._emit(
            EventType.INVESTIGATION_RESUMED,
            wf.case_id,
            "Investigation resumed",
            {"workflow_id": str(wf.id)},
        )
        return wf, state, observations

    def cancel(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        wf = self._wf_repo.get(workflow_id)
        if not wf:
            return None
        if wf.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            return wf
        if not can_transition(wf.status, WorkflowStatus.CANCELLED):
            if wf.status == WorkflowStatus.FAILED:
                pass
            else:
                return None
        wf.status = WorkflowStatus.CANCELLED
        if wf.goal:
            wf.goal.transition(GoalStatus.CANCELLED)
        wf.record_decision("cancel", "Investigation cancelled")
        if wf.investigation_id:
            state = self._inv_repo.get(wf.investigation_id)
            if state:
                try:
                    state.transition(InvestigationStatus.CANCELLED)
                except Exception:
                    state.status = InvestigationStatus.CANCELLED
                self._inv_repo.save(state)
        self._wf_repo.save(wf)
        self._timeline.append(
            wf.case_id,
            TimelineKind.DECISION,
            "Investigation cancelled",
            workflow_id=wf.id,
            source="workflow_engine",
        )
        return wf

    def retry(self, workflow_id: UUID, max_steps: int = 5) -> tuple[
        InvestigationWorkflow, InvestigationState, list[Observation]
    ] | None:
        """Explicit retry from FAILED — does not auto-replay in-flight steps."""
        wf = self._wf_repo.get(workflow_id)
        if not wf or wf.status != WorkflowStatus.FAILED:
            return None
        if not can_transition(wf.status, WorkflowStatus.RUNNING):
            return None
        retries = dict(wf.metadata.get("retries") or {})
        count = int(retries.get("count", 0)) + 1
        retries["count"] = count
        retries["last_at"] = datetime.now(UTC).isoformat()
        wf.metadata["retries"] = retries
        wf.status = WorkflowStatus.RUNNING
        wf.record_decision("retry", f"Retry #{count}")
        self._wf_repo.save(wf)
        self._timeline.append(
            wf.case_id,
            TimelineKind.REPLAN,
            f"Retry #{count}",
            workflow_id=wf.id,
            source="workflow_engine",
        )
        if not wf.investigation_id:
            return None
        state = self._inv_repo.get(wf.investigation_id)
        if state is None:
            return None
        with suppress(Exception):
            state.transition(InvestigationStatus.EXECUTING)
        if state.status != InvestigationStatus.EXECUTING:
            state.status = InvestigationStatus.EXECUTING
        self._inv_repo.save(state)
        return self.resume(workflow_id, max_steps=max_steps) or (wf, state, [])

    def recover(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        """Crash recovery: load durable state; do not re-execute unfinished steps."""
        wf = self._wf_repo.get(workflow_id)
        if not wf:
            return None
        if wf.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            return wf

        token = str(wf.metadata.get("last_execution_token") or "")
        notes = []
        if token and not token.endswith(":done"):
            notes.append(
                f"Incomplete execution token '{token}' — will not auto-replay; "
                "mark for replan/manual review"
            )
            wf.metadata["recovery_notes"] = "; ".join(notes)
            wf.record_decision(
                "recovery",
                "Crash recovery: skipped incomplete execution",
                {"token": token},
            )
            if wf.status == WorkflowStatus.RUNNING:
                if can_transition(wf.status, WorkflowStatus.BLOCKED):
                    wf.status = WorkflowStatus.BLOCKED
        else:
            notes.append("Last step completed or no in-flight token")
            wf.metadata["recovery_notes"] = "; ".join(notes)
            wf.record_decision("recovery", "Crash recovery: durable state loaded", {})

        self._wf_repo.save(wf)
        self._timeline.append(
            wf.case_id,
            TimelineKind.RECOVERY,
            wf.metadata.get("recovery_notes", "recovered"),
            workflow_id=wf.id,
            investigation_id=wf.investigation_id,
            source="workflow_engine",
        )
        return wf

    def recover_all(self) -> list[InvestigationWorkflow]:
        recovered: list[InvestigationWorkflow] = []
        for wf in self._wf_repo.list_recoverable():
            r = self.recover(wf.id)
            if r:
                recovered.append(r)
        return recovered

    def get(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        return self._wf_repo.get(workflow_id)

    def list_for_case(self, case_id: UUID) -> list[InvestigationWorkflow]:
        return self._wf_repo.list_for_case(case_id)

    def _emit(
        self, event_type: EventType, case_id: UUID | None, message: str, payload: dict[str, Any]
    ) -> None:
        self.bus.publish(
            SpectraEvent(
                event_type=event_type,
                case_id=case_id,
                message=message,
                payload=payload,
                actor="workflow_engine",
            )
        )
