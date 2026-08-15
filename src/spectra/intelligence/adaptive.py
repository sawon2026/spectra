"""Adaptive Planner — reacts to observations; never executes."""

from __future__ import annotations

from spectra.capabilities.registry import CapabilityRegistry
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.intelligence.interpreter import ObservationInterpreter
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.intelligence.planner import DeterministicPlanner, Plan, Planner
from spectra.intelligence.selection import CapabilitySelectionEngine
from spectra.intelligence.state import InvestigationState, PlanStep, StepStatus
from spectra.intelligence.task import Task
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class AdaptivePlanner(Planner):
    """Extends deterministic planning with observation-driven replan.

    Hard rule: produces PlanStep capability requests only. Never shell.
    """

    def __init__(
        self,
        selection: CapabilitySelectionEngine | None = None,
        interpreter: ObservationInterpreter | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._base = DeterministicPlanner()
        self.selection = selection or CapabilitySelectionEngine(event_bus=event_bus)
        self.interpreter = interpreter or ObservationInterpreter()
        self._bus = event_bus

    def create_plan(
        self,
        task: Task,
        state: InvestigationState,
        registry: CapabilityRegistry,
    ) -> Plan:
        base = self._base.create_plan(task, state, registry)
        requests = self.selection.select(task, state, registry, observations=[])
        existing = {s.capability for s in base.steps}
        order = len(base.steps)
        for req in requests:
            if req.capability in existing:
                continue
            base.steps.append(
                PlanStep(
                    capability=req.capability,
                    inputs=req.inputs,
                    objective=req.objective,
                    order=order,
                )
            )
            existing.add(req.capability)
            order += 1
        base.rationale = (base.rationale or "") + " | adaptive-selection"
        base.version = "adaptive-0.1"
        state.planner_version = "adaptive-0.1"
        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.PLAN_CREATED,
                    case_id=state.case_id,
                    message=f"Adaptive plan with {len(base.steps)} steps",
                    payload={"plan_id": str(base.id), "steps": [s.capability for s in base.steps]},
                    actor="adaptive_planner",
                )
            )
        return base

    def replan(
        self,
        task: Task,
        state: InvestigationState,
        registry: CapabilityRegistry,
        observation: Observation,
    ) -> Plan:
        interpretation = self.interpreter.interpret(observation)
        available = {c.name for c in registry.list()}
        done = {s.capability for s in state.completed_steps}
        done |= {s.capability for s in state.current_plan if s.status == StepStatus.COMPLETED}
        pending_caps = {
            s.capability
            for s in state.current_plan
            if s.status == StepStatus.PENDING
        }

        new_steps: list[PlanStep] = []
        order = max((s.order for s in state.current_plan), default=-1) + 1

        for s in state.current_plan:
            if s.status == StepStatus.PENDING:
                new_steps.append(s)

        suggestions = list(interpretation.next_step_suggestions)
        if observation.status == ObservationStatus.SUCCESS:
            for name in self.selection._suggest_from_observation(observation):
                if name not in suggestions:
                    suggestions.append(name)

        for name in suggestions:
            if name not in available or name in done or name in pending_caps:
                continue
            path = state.target or ""
            inputs = {"path": path} if path else {}
            new_steps.append(
                PlanStep(
                    capability=name,
                    inputs=inputs,
                    objective=f"replan_{name}",
                    order=order,
                )
            )
            pending_caps.add(name)
            order += 1

        if observation.status in (
            ObservationStatus.FAILED,
            ObservationStatus.BLOCKED,
            ObservationStatus.UNAVAILABLE,
            ObservationStatus.TIMEOUT,
        ):
            for alt in ("file-info", "hash-compute"):
                if alt in available and alt not in done and alt not in pending_caps:
                    path = state.target or ""
                    new_steps.append(
                        PlanStep(
                            capability=alt,
                            inputs={"path": path} if path else {},
                            objective=f"fallback_{alt}",
                            order=order,
                        )
                    )
                    pending_caps.add(alt)
                    order += 1

        plan = Plan(
            investigation_id=state.id,
            steps=new_steps,
            rationale=f"Replan after {observation.capability}:{observation.status.value}",
            version="adaptive-0.1",
        )
        existing_ids = {s.id for s in state.current_plan}
        for s in new_steps:
            if s.id not in existing_ids and s.status == StepStatus.PENDING:
                state.current_plan.append(s)

        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.REPLAN_TRIGGERED,
                    case_id=state.case_id,
                    message=plan.rationale,
                    payload={
                        "observation_id": str(observation.id),
                        "new_capabilities": [s.capability for s in new_steps if s.status == StepStatus.PENDING],
                    },
                    actor="adaptive_planner",
                )
            )
        return plan
