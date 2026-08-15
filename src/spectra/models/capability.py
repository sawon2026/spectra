"""Capability registry models."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CapabilityCategory(str, Enum):
    UTILITY = "utility"
    REVERSE_ENGINEERING = "reverse_engineering"
    ANDROID = "android"
    NETWORK = "network"
    MALWARE = "malware"
    FORENSICS = "forensics"
    OTHER = "other"


class InputType(str, Enum):
    FILE = "file"
    BINARY = "binary"
    APK = "apk"
    DIRECTORY = "directory"
    URL = "url"
    TEXT = "text"
    NONE = "none"


class OutputType(str, Enum):
    JSON = "json"
    TEXT = "text"
    EVIDENCE = "evidence"
    FINDING = "finding"
    BINARY = "binary"


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionMode(str, Enum):
    READ_ONLY = "read_only"
    LOCAL = "local"
    NETWORK = "network"
    SANDBOX = "sandbox"


class Capability(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=128)
    version: str = "0.1.0"
    category: CapabilityCategory = CapabilityCategory.OTHER
    description: str = ""
    supported_platforms: list[str] = Field(default_factory=lambda: ["linux", "darwin", "win32"])
    input_types: list[InputType] = Field(default_factory=list)
    output_types: list[OutputType] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_authorization: bool = True
    execution_mode: ExecutionMode = ExecutionMode.LOCAL
    default_timeout_seconds: float = 300
    produces_evidence: bool = True
    health_status: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
