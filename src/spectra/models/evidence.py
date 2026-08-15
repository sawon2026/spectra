"""Evidence models with provenance fields."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class EvidenceSourceType(str, Enum):
    TOOL = "tool"
    MANUAL = "manual"
    IMPORT = "import"
    SYSTEM = "system"


class EvidenceCreate(BaseModel):
    case_id: UUID
    title: str = Field(..., min_length=1, max_length=256)
    source_type: EvidenceSourceType = EvidenceSourceType.TOOL
    source_ref: str = Field(default="", max_length=1024)
    content_hash: str | None = Field(default=None, max_length=128)
    artifact_path: str | None = Field(default=None, max_length=1024)
    repro_command: str = Field(default="", max_length=2048)
    raw_excerpt: str = Field(default="", max_length=65536)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tool_name: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("artifact_path")
    @classmethod
    def no_traversal(cls, v: str | None) -> str | None:
        if v and ".." in v:
            raise ValueError("artifact_path must not contain '..'")
        return v


class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    title: str
    source_type: EvidenceSourceType
    source_ref: str = ""
    content_hash: str | None = None
    artifact_path: str | None = None
    repro_command: str = ""
    raw_excerpt: str = ""
    confidence: float = 1.0
    tool_name: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
