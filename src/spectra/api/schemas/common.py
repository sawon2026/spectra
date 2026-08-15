"""Shared API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    detail: str
    code: str = "error"
    extras: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    database: str = "sqlite"
    policy_gate: str = "active"
    offline_default: bool = True
    ai_configured: bool = False
    roles: list[str] = Field(default_factory=lambda: ["admin", "researcher", "viewer"])


class RoleInfo(BaseModel):
    subject: str
    role: str
    offline: bool
