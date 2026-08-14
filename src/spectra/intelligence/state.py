"""Investigation state machine — explicit, testable transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class InvestigationStatus(str, Enum):
    CREATED = "created"
    CLASSIFIED = "classified"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    REPLANNING = "replanning"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    """A single planned capability request — never a raw shell command."""

    id: UUID = Field(default_factory=uuid4)
    capability: str = Field(..., min_length=1, max_length=128)
    inputs: dict[str, Any] = Field(default_factory=dict)
    objective: str = Field(default="", max_length=512)
    status: StepStatus = StepStatus.PENDING
    observation_id: UUID | None = None
    error: str | None = None
    order: int = 0


class InvestigationState(BaseModel):
    """Persistent investigation state."""

    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    task_id: UUID | None = None
    status: InvestigationStatus = InvestigationStatus.CREATED
    target: str = ""
    objectives: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    current_plan: list[PlanStep] = Field(default_factory=list)
    completed_steps: list[PlanStep] = Field(default_factory=list)
    pending_steps: list[PlanStep] = Field(default_factory=list)
    failed_steps: list[PlanStep] = Field(default_factory=list)
    blocked_steps: list[PlanStep] = Field(default_factory=list)
    observation_ids: list[UUID] = Field(default_factory=list)
    evidence_refs: list[UUID] = Field(default_factory=list)
    planner_version: str = "deterministic-0.1"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def transition(self, new_status: InvestigationStatus) -> None:
        """Explicit status transition with timestamp update."""
        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def next_pending_step(self) -> PlanStep | None:
        for step in self.current_plan:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def mark_step(self, step_id: UUID, status: StepStatus, error: str | None = None) -> PlanStep | None:
        for step in self.current_plan:
            if step.id == step_id:
                step.status = status
                step.error = error
                if status == StepStatus.COMPLETED:
                    self.completed_steps.append(step)
                elif status == StepStatus.FAILED:
                    self.failed_steps.append(step)
                elif status == StepStatus.BLOCKED:
                    self.blocked_steps.append(step)
                elif status == StepStatus.UNAVAILABLE:
                    self.failed_steps.append(step)
                self.updated_at = datetime.now(UTC)
                return step
        return None
