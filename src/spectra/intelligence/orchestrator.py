"""Investigation orchestrator — intelligence requests; execution is policy-gated.

Hard invariant: no capability runs without PolicyEngine.evaluate success.
The planner never invokes subprocesses; adapters + PolicyEngine do.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from spectra.capabilities.registry import CapabilityRegistry
from spectra.cases.service import CaseService
from spectra.core.config import get_settings
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.intelligence.classifier import DeterministicClassifier, TaskClassifier
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.intelligence.planner import DeterministicPlanner, Planner
from spectra.intelligence.state import (
    InvestigationState,
    InvestigationStatus,
    StepStatus,
)
from spectra.intelligence.task import Task, TaskCreate
from spectra.knowledge.investigation_repo import InvestigationRepository
from spectra.knowledge.observation_repo import ObservationRepository
from spectra.models.events import EventType, SpectraEvent
from spectra.models.scope import Scope
from spectra.policy.engine import PolicyEngine
from spectra.tools.base import ToolAdapter, ToolResult
from spectra.tools.builtin import FileInfoAdapter, HashComputeAdapter, StringsExtractAdapter

logger = get_logger(__name__)


class InvestigationOrchestrator:
    """Coordinates classify → plan → policy → execute → observe → replan."""

    def __init__(
        self,
        policy: PolicyEngine,
        registry: CapabilityRegistry,
        case_service: CaseService,
        event_bus: EventBus | None = None,
        classifier: TaskClassifier | None = None,
        planner: Planner | None = None,
        adapters: dict[str, ToolAdapter] | None = None,
    ) -> None:
        self.policy = policy
        self.registry = registry
        self.cases = case_service
        self.bus = event_bus or EventBus(persist=True)
        self.classifier = classifier or DeterministicClassifier()
        self.planner = planner or DeterministicPlanner()
        self._adapters = adapters or {}
        self._inv_repo = InvestigationRepository()
        self._obs_repo = ObservationRepository(event_bus=self.bus)
        if not self._adapters:
            self._adapters = {
                "file-info": FileInfoAdapter(policy, self.bus),
                "hash-compute": HashComputeAdapter(policy, self.bus),
                "strings-extract": StringsExtractAdapter(policy, self.bus),
            }

    def start(self, case_id: UUID, text: str, artifact_path: str = "") -> tuple[Task, InvestigationState]:
        task = self.classifier.classify(
            TaskCreate(text=text, case_id=case_id, artifact_paths=[artifact_path] if artifact_path else [])
        )
        self._emit(EventType.PLAN_CREATED, case_id, "task classified", {"task_type": task.task_type.value})

        state = InvestigationState(
            case_id=case_id,
            task_id=task.id,
            target=artifact_path,
            objectives=list(task.objectives),
            status=InvestigationStatus.CLASSIFIED,
            metadata={"artifact_path": artifact_path},
        )
        plan = self.planner.create_plan(task, state, self.registry)
        state.transition(InvestigationStatus.PLANNING)
        self._emit(
            EventType.PLAN_CREATED,
            case_id,
            f"plan with {len(plan.steps)} steps",
            {"plan_id": str(plan.id), "steps": [s.capability for s in plan.steps]},
        )
        state.transition(InvestigationStatus.EXECUTING)
        self._inv_repo.save(state)
        return task, state

    def execute_next(
        self,
        task: Task,
        state: InvestigationState,
        scope: Scope | None,
    ) -> tuple[InvestigationState, Observation | None]:
        step = state.next_pending_step()
        if step is None:
            state.transition(InvestigationStatus.COMPLETED)
            self._emit(EventType.CASE_UPDATED, state.case_id, "investigation completed", {})
            return state, None

        step.status = StepStatus.IN_PROGRESS
        state.transition(InvestigationStatus.EXECUTING)

        # --- POLICY GATE (mandatory) ---
        network_required = bool(task.network_required)
        decision = self.policy.evaluate(
            scope,
            activity=step.capability,
            asset_identifier=step.inputs.get("path") or state.target or None,
            network_required=network_required,
            risk_level=task.risk_level,
            case_id=state.case_id,
        )
        if not decision.allowed:
            obs = Observation(
                investigation_id=state.id,
                case_id=state.case_id,
                source="policy",
                capability=step.capability,
                status=ObservationStatus.BLOCKED,
                summary=decision.reason,
                error=decision.reason,
            )
            state.mark_step(step.id, StepStatus.BLOCKED, error=decision.reason)
            state.observation_ids.append(obs.id)
            self._obs_repo.save(obs)
            self._inv_repo.save(state)
            self._emit(
                EventType.POLICY_DENIED,
                state.case_id,
                decision.reason,
                {"capability": step.capability},
            )
            if not state.next_pending_step():
                state.transition(InvestigationStatus.BLOCKED)
            return state, obs

        self._emit(
            EventType.POLICY_CHECK,
            state.case_id,
            "policy allowed",
            {"capability": step.capability},
        )

        # Capability must exist
        cap = self.registry.get(step.capability)
        if cap is None:
            obs = Observation(
                investigation_id=state.id,
                case_id=state.case_id,
                source="registry",
                capability=step.capability,
                status=ObservationStatus.UNAVAILABLE,
                summary=f"Capability '{step.capability}' not registered",
                error="capability_not_registered",
            )
            state.mark_step(step.id, StepStatus.UNAVAILABLE, error=obs.error)
            state.observation_ids.append(obs.id)
            self._emit(EventType.TOOL_FAILED, state.case_id, obs.summary, {"capability": step.capability})
            state.transition(InvestigationStatus.REPLANNING)
            self.planner.replan(task, state, self.registry, obs)
            state.transition(InvestigationStatus.EXECUTING)
            return state, obs

        adapter = self._adapters.get(step.capability)
        if adapter is None or not adapter.is_available():
            obs = Observation(
                investigation_id=state.id,
                case_id=state.case_id,
                source="adapter",
                capability=step.capability,
                status=ObservationStatus.UNAVAILABLE,
                summary=f"Adapter for '{step.capability}' unavailable",
                error="adapter_unavailable",
            )
            state.mark_step(step.id, StepStatus.UNAVAILABLE, error=obs.error)
            state.observation_ids.append(obs.id)
            state.transition(InvestigationStatus.REPLANNING)
            self.planner.replan(task, state, self.registry, obs)
            state.transition(InvestigationStatus.EXECUTING)
            return state, obs

        # Execute via adapter (adapter also re-checks policy internally)
        settings = get_settings()
        timeout = min(cap.default_timeout_seconds, settings.max_command_timeout_seconds)
        result: ToolResult = adapter.execute(
            scope=scope,
            case_id=state.case_id,
            inputs=step.inputs,
            timeout=timeout,
        )

        if result.success:
            obs = Observation(
                investigation_id=state.id,
                case_id=state.case_id,
                source="adapter",
                capability=step.capability,
                status=ObservationStatus.SUCCESS,
                summary=(result.stdout or "")[:2000],
                structured_data={"metadata": result.metadata, "exit_code": result.exit_code},
            )
            state.mark_step(step.id, StepStatus.COMPLETED)
            self._emit(EventType.TOOL_EXECUTED, state.case_id, f"{step.capability} ok", {})
        else:
            status = ObservationStatus.FAILED
            err = result.error or result.stderr or "execution failed"
            if "timed out" in err.lower():
                status = ObservationStatus.TIMEOUT
            obs = Observation(
                investigation_id=state.id,
                case_id=state.case_id,
                source="adapter",
                capability=step.capability,
                status=status,
                summary=err[:2000],
                error=err,
            )
            state.mark_step(step.id, StepStatus.FAILED, error=err)
            self._emit(EventType.TOOL_FAILED, state.case_id, err[:200], {"capability": step.capability})

        state.observation_ids.append(obs.id)
        self._obs_repo.save(obs)
        self._inv_repo.save(state)
        state.transition(InvestigationStatus.OBSERVING)

        if obs.status == ObservationStatus.SUCCESS:
            state.transition(InvestigationStatus.REPLANNING)
            self.planner.replan(task, state, self.registry, obs)
            state.transition(InvestigationStatus.EXECUTING)

        if state.next_pending_step() is None and not state.blocked_steps:
            if state.failed_steps and not state.completed_steps:
                state.transition(InvestigationStatus.FAILED)
            else:
                state.transition(InvestigationStatus.COMPLETED)

        return state, obs

    def run_to_completion(
        self,
        case_id: UUID,
        text: str,
        artifact_path: str = "",
        max_steps: int = 10,
    ) -> tuple[Task, InvestigationState, list[Observation]]:
        """Convenience driver for tests — still policy-gated per step."""
        task, state = self.start(case_id, text, artifact_path)
        scope = self.cases.get_scope(case_id)
        observations: list[Observation] = []
        for _ in range(max_steps):
            if state.status in (
                InvestigationStatus.COMPLETED,
                InvestigationStatus.FAILED,
                InvestigationStatus.BLOCKED,
                InvestigationStatus.CANCELLED,
            ):
                break
            state, obs = self.execute_next(task, state, scope)
            if obs:
                observations.append(obs)
            if state.next_pending_step() is None:
                if state.status not in (
                    InvestigationStatus.COMPLETED,
                    InvestigationStatus.FAILED,
                    InvestigationStatus.BLOCKED,
                ):
                    state.transition(InvestigationStatus.COMPLETED)
                break
        return task, state, observations

    def _emit(self, event_type: EventType, case_id: UUID | None, message: str, payload: dict[str, Any]) -> None:
        self.bus.publish(
            SpectraEvent(
                event_type=event_type,
                case_id=case_id,
                message=message,
                payload=payload,
                actor="orchestrator",
            )
        )
