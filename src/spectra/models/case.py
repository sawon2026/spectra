"""Case domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class CaseStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    REVIEW = "review"
    CLOSED = "closed"
    ARCHIVED = "archived"


class CaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=4096)
    project_id: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: str) -> str:
        forbidden = {"/", "\\", "..", "\0", "\n", "\r"}
        for ch in forbidden:
            if ch in v:
                raise ValueError(f"Case name contains forbidden character or sequence: {ch!r}")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Case name cannot be empty or whitespace")
        return cleaned


class Case(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    status: CaseStatus = CaseStatus.DRAFT
    project_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
