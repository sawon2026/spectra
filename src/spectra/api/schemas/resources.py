"""Resource schemas for /api/v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CaseCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CaseOut(BaseModel):
    id: UUID
    name: str
    description: str = ""
    status: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScopeCreateIn(BaseModel):
    auth_status: str = "pending"
    network_profile: str = "offline"
    allowed_activities: list[str] = Field(default_factory=list)
    forbidden_activities: list[str] = Field(default_factory=list)
    auth_basis: str = ""
    notes: str = ""


class ScopeOut(BaseModel):
    id: UUID
    case_id: UUID
    auth_status: str
    network_profile: str
    allowed_activities: list[str] = Field(default_factory=list)
    ready_for_act: bool = False


class EvidenceCreateIn(BaseModel):
    title: str
    source_type: str = "manual"
    source_ref: str = ""
    raw_excerpt: str = ""
    content_hash: str | None = None
    artifact_path: str | None = None
    confidence: float = 1.0


class EvidenceOut(BaseModel):
    id: UUID
    case_id: UUID
    title: str
    source_type: str
    source_ref: str = ""
    content_hash: str | None = None
    confidence: float = 1.0


class FindingOut(BaseModel):
    id: UUID
    case_id: UUID
    title: str
    severity: str
    status: str
    confidence: float = 0.5


class WorkflowStartIn(BaseModel):
    goal: str = Field(..., min_length=1, max_length=4000)
    artifact_path: str = ""
    max_steps: int = Field(default=8, ge=1, le=50)


class WorkflowOut(BaseModel):
    id: UUID
    case_id: UUID
    status: str
    investigation_id: UUID | None = None
    observation_ids: list[UUID] = Field(default_factory=list)
    decision_count: int = 0
    recovery_notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineEntryOut(BaseModel):
    id: UUID
    case_id: UUID
    kind: str
    source: str
    summary: str
    confidence: float | None = None
    created_at: datetime | None = None


class CapabilityOut(BaseModel):
    name: str
    category: str = ""
    risk_level: str = "low"
    requires_authorization: bool = True
    description: str = ""


class ProviderOut(BaseModel):
    name: str
    available: bool
    offline: bool
    model: str = ""
    capabilities: list[str] = Field(default_factory=list)


class GraphNodeOut(BaseModel):
    id: UUID
    case_id: UUID | None = None
    node_type: str
    label: str = ""


class GraphEdgeOut(BaseModel):
    id: UUID
    relation: str
    from_node_id: UUID
    to_node_id: UUID
