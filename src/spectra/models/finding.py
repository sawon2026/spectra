"""Finding models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NONE = "none"


class FindingStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED_RISK = "accepted_risk"
    FIXED = "fixed"


class FindingCreate(BaseModel):
    case_id: UUID
    title: str = Field(..., min_length=1, max_length=256)
    severity: FindingSeverity = FindingSeverity.INFO
    status: FindingStatus = FindingStatus.CANDIDATE
    category: str = Field(default="other", max_length=64)
    evidence_ids: list[UUID] = Field(default_factory=list)
    location: str = Field(default="", max_length=512)
    impact: str = Field(default="", max_length=2048)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    remediation: str = Field(default="", max_length=4096)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    title: str
    severity: FindingSeverity
    status: FindingStatus
    category: str = "other"
    evidence_ids: list[UUID] = Field(default_factory=list)
    location: str = ""
    impact: str = ""
    confidence: float = 0.5
    remediation: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
