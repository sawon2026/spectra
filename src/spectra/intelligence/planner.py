"""Investigation planner — produces structured capability requests only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.capabilities.registry import CapabilityRegistry
from spectra.core.logging import get_logger
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.intelligence.state import InvestigationState, PlanStep, StepStatus
from spectra.intelligence.task import Task

logger = get_logger(__name__)


class Plan(BaseModel):
    """Validated investigation plan of capability requests."""

    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    steps: list[PlanStep] = Field(default_factory=list)
    rationale: str = ""
    version: str = "deterministic-0.1"


class Planner(ABC):
    """Plan investigations using the capability registry — never raw shell."""

    @abstractmethod
    def create_plan(
        self,
        task: Task,
        state: InvestigationState,
        registry: CapabilityRegistry,
    ) -> Plan:
        ...

    @abstractmethod
    def replan(
        self,
        task: Task,
        state: InvestigationState,
        registry: CapabilityRegistry,
        observation: Observation,
    ) -> Plan:
        ...


class DeterministicPlanner(Planner):
    """Offline planner that maps task objectives to known capabilities."""

    def create_plan(
        self,
        task: Task,
        state: InvestigationState,
        registry: CapabilityRegistry,
    ) -> Plan:
        available = {c.name for c in registry.list()}
        steps: list[PlanStep] = []
        order = 0

        for name in task.requested_capabilities:
            if name in available:
                steps.append(
                    PlanStep(
                        capability=name,
                        inputs=self._default_inputs(name, state),
                        objective=f"run_{name}",
                        order=order,
                    )
                )
                order += 1
            else:
                logger.info("capability_unavailable_at_plan", capability=name)

        if "compute_hashes" in task.objectives and "hash-compute" in available:
            if not any(s.capability == "hash-compute" for s in steps):
                steps.append(
                    PlanStep(
                        capability="hash-compute",
                        inputs=self._default_inputs("hash-compute", state),
                        objective="compute_hashes",
                        order=order,
                    )
                )
                order += 1

        if not steps and "file-info" in available:
            steps.append(
                PlanStep(
                    capability="file-info",
                    inputs=self._default_inputs("file-info", state),
                    objective="inspect_artifact",
                    order=0,
                )
            )

        plan = Plan(
            investigation_id=state.id,
            steps=steps,
            rationale=f"Deterministic plan for task_type={task.task_type.value}",
        )
        state.current_plan = list(steps)
        state.pending_steps = [s for s in steps if s.status == StepStatus.PENDING]
        return plan

    def replan(
        self,
        task: Task,
        state: InvestigationState,
        registry: CapabilityRegistry,
        observation: Observation,
    ) -> Plan:
        """Extend plan based on observation signals."""
        available = {c.name for c in registry.list()}
        new_steps: list[PlanStep] = list(state.current_plan)
        existing_caps = {s.capability for s in new_steps}
        order = max((s.order for s in new_steps), default=-1) + 1

        summary = (observation.summary or "").lower()
        data = observation.structured_data or {}

        if any(k in summary for k in ("native", "elf", "shared object", ".so")) or data.get(
            "native_detected"
        ):
            if "strings-extract" in available and "strings-extract" not in existing_caps:
                new_steps.append(
                    PlanStep(
                        capability="strings-extract",
                        inputs=self._default_inputs("strings-extract", state),
                        objective="analyze_native_strings",
                        order=order,
                    )
                )
                order += 1

        if observation.status == ObservationStatus.UNAVAILABLE:
            logger.info("replan_skip_unavailable", capability=observation.capability)

        plan = Plan(
            investigation_id=state.id,
            steps=new_steps,
            rationale="Replan after observation",
            version="deterministic-0.1-replan",
        )
        state.current_plan = list(new_steps)
        state.pending_steps = [s for s in new_steps if s.status == StepStatus.PENDING]
        state.planner_version = plan.version
        return plan

    @staticmethod
    def _default_inputs(capability: str, state: InvestigationState) -> dict[str, Any]:
        path = state.target or state.metadata.get("artifact_path", "")
        return {"path": path} if path else {}
