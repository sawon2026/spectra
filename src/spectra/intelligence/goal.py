"""Research Goal Engine — structured goals never become shell commands."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.intelligence.classifier import DeterministicClassifier, TaskClassifier
from spectra.intelligence.task import Task, TaskCreate
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class GoalStatus(str, Enum):
    CREATED = "created"
    CLASSIFIED = "classified"
    PLANNED = "planned"
    RUNNING = "running"
    BLOCKED = "blocked"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchGoal(BaseModel):
    """A structured research goal — never an executable command."""

    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    text: str = Field(..., min_length=1, max_length=8192)
    status: GoalStatus = GoalStatus.CREATED
    task_ids: list[UUID] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("artifact_paths")
    @classmethod
    def no_traversal(cls, v: list[str]) -> list[str]:
        for p in v:
            if ".." in p:
                raise ValueError("artifact path must not contain '..'")
        return v

    def transition(self, status: GoalStatus) -> None:
        self.status = status
        self.updated_at = datetime.now(UTC)


class GoalEngine:
    """Converts natural-language research goals into structured Tasks.

    Never executes tools. Never produces shell commands.
    """

    def __init__(
        self,
        classifier: TaskClassifier | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.classifier = classifier or DeterministicClassifier()
        self._bus = event_bus

    def create(self, case_id: UUID, text: str, artifact_paths: list[str] | None = None) -> ResearchGoal:
        goal = ResearchGoal(
            case_id=case_id,
            text=text,
            artifact_paths=list(artifact_paths or []),
        )
        self._emit(
            EventType.GOAL_CREATED,
            case_id,
            f"Goal created: {text[:80]}",
            {"goal_id": str(goal.id)},
        )
        return goal

    def classify(self, goal: ResearchGoal) -> tuple[ResearchGoal, Task]:
        task = self.classifier.classify(
            TaskCreate(
                text=goal.text,
                case_id=goal.case_id,
                artifact_paths=goal.artifact_paths,
            )
        )
        goal.task_ids.append(task.id)
        goal.objectives = list(task.objectives)
        goal.transition(GoalStatus.CLASSIFIED)
        self._emit(
            EventType.TASK_CLASSIFIED,
            goal.case_id,
            f"Goal classified as {task.task_type.value}",
            {
                "goal_id": str(goal.id),
                "task_id": str(task.id),
                "task_type": task.task_type.value,
                "capabilities": task.requested_capabilities,
            },
        )
        return goal, task

    def _emit(self, event_type: EventType, case_id: UUID | None, message: str, payload: dict[str, Any]) -> None:
        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=event_type,
                    case_id=case_id,
                    message=message,
                    payload=payload,
                    actor="goal_engine",
                )
            )
