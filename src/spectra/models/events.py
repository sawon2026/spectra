"""Event models for observability."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    CASE_CREATED = "case.created"
    CASE_UPDATED = "case.updated"
    CASE_CLOSED = "case.closed"
    SCOPE_CREATED = "scope.created"
    SCOPE_UPDATED = "scope.updated"
    SCOPE_READY = "scope.ready"
    POLICY_CHECK = "policy.check"
    POLICY_DENIED = "policy.denied"
    CAPABILITY_REGISTERED = "capability.registered"
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"
    EVIDENCE_RECORDED = "evidence.recorded"
    FINDING_CREATED = "finding.created"
    FINDING_UPDATED = "finding.updated"
    TASK_CLASSIFIED = "task.classified"
    PLAN_CREATED = "plan.created"
    PLAN_VALIDATED = "plan.validated"
    CAPABILITY_REQUESTED = "capability.requested"
    OBSERVATION_CREATED = "observation.created"
    REPLAN_TRIGGERED = "replan.triggered"
    INVESTIGATION_COMPLETED = "investigation.completed"
    EVIDENCE_CREATED = "evidence.created"
    EVIDENCE_VERIFIED = "evidence.verified"
    OBSERVATION_PERSISTED = "observation.persisted"
    FINDING_CORRELATED = "finding.correlated"
    FINDING_VALIDATED = "finding.validated"
    FINDING_REJECTED = "finding.rejected"
    GRAPH_RELATION_CREATED = "graph.relation_created"
    MEMORY_RETRIEVED = "memory.retrieved"
    MEMORY_ADDED = "memory.added"
    PLAN_UPDATED = "plan.updated"
    ERROR = "error"
    AUDIT = "audit"


class SpectraEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    case_id: UUID | None = None
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}
