"""Structured observations from capability executions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ObservationStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    MALFORMED = "malformed"


class Observation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    case_id: UUID | None = None
    source: str = "executor"
    capability: str = ""
    status: ObservationStatus = ObservationStatus.SUCCESS
    summary: str = Field(default="", max_length=4096)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[UUID] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
