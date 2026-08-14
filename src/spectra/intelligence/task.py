"""Structured task representation for the intelligence layer."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TaskType(str, Enum):
    REVERSE_ENGINEERING = "reverse_engineering"
    ANDROID = "android"
    BINARY = "binary"
    WEB_API = "web_api"
    MALWARE = "malware"
    CODE_SECURITY = "code_security"
    NETWORK = "network"
    FORENSICS = "forensics"
    GENERAL = "general"
    UNKNOWN = "unknown"


class ArtifactType(str, Enum):
    APK = "apk"
    BINARY = "binary"
    FILE = "file"
    DIRECTORY = "directory"
    URL = "url"
    HOST = "host"
    SOURCE = "source"
    PCAP = "pcap"
    TEXT = "text"
    UNKNOWN = "unknown"
    NONE = "none"


class TaskCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=8192)
    case_id: UUID | None = None
    artifact_paths: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("artifact_paths")
    @classmethod
    def no_traversal(cls, v: list[str]) -> list[str]:
        for p in v:
            if ".." in p:
                raise ValueError("artifact path must not contain '..'")
        return v


class Task(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID | None = None
    text: str = ""
    task_type: TaskType = TaskType.UNKNOWN
    artifact_type: ArtifactType = ArtifactType.UNKNOWN
    objectives: list[str] = Field(default_factory=list)
    requested_capabilities: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    scope_required: bool = True
    authorization_required: bool = True
    network_required: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
