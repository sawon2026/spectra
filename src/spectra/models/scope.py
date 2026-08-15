"""Scope and authorization models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AuthStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"


class NetworkProfile(str, Enum):
    OFFLINE = "offline"
    LAB_ONLY = "lab_only"
    AUTHORIZED_TARGET_ONLY = "authorized_target_only"
    UNRESTRICTED_LAB = "unrestricted_lab"


class ScopeAsset(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=512)
    asset_type: str = Field(default="unknown", max_length=64)
    notes: str = Field(default="", max_length=1024)


class ScopeCreate(BaseModel):
    case_id: UUID
    auth_status: AuthStatus = AuthStatus.PENDING
    auth_basis: str = Field(default="", max_length=256)
    auth_evidence: str = Field(default="", max_length=1024)
    in_scope_assets: list[ScopeAsset] = Field(default_factory=list)
    out_of_scope_assets: list[ScopeAsset] = Field(default_factory=list)
    allowed_activities: list[str] = Field(default_factory=list)
    forbidden_activities: list[str] = Field(default_factory=list)
    network_profile: NetworkProfile = NetworkProfile.OFFLINE
    time_window_start: datetime | None = None
    time_window_end: datetime | None = None
    notes: str = Field(default="", max_length=4096)

    @model_validator(mode="after")
    def validate_time_window(self) -> ScopeCreate:
        if self.time_window_start and self.time_window_end:
            if self.time_window_end <= self.time_window_start:
                raise ValueError("time_window_end must be after time_window_start")
        return self


class Scope(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    auth_status: AuthStatus = AuthStatus.PENDING
    auth_basis: str = ""
    auth_evidence: str = ""
    in_scope_assets: list[ScopeAsset] = Field(default_factory=list)
    out_of_scope_assets: list[ScopeAsset] = Field(default_factory=list)
    allowed_activities: list[str] = Field(default_factory=list)
    forbidden_activities: list[str] = Field(default_factory=list)
    network_profile: NetworkProfile = NetworkProfile.OFFLINE
    time_window_start: datetime | None = None
    time_window_end: datetime | None = None
    ready_for_act: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}

    def is_action_allowed(self, activity: str, asset_identifier: str | None = None) -> bool:
        if self.auth_status != AuthStatus.GRANTED:
            return False
        if not self.ready_for_act:
            return False
        now = datetime.now(UTC)
        if self.time_window_start and now < self.time_window_start:
            return False
        if self.time_window_end and now > self.time_window_end:
            return False
        if activity in self.forbidden_activities:
            return False
        if self.allowed_activities and activity not in self.allowed_activities:
            return False
        if asset_identifier is not None:
            in_ids = {a.identifier for a in self.in_scope_assets}
            out_ids = {a.identifier for a in self.out_of_scope_assets}
            if asset_identifier in out_ids:
                return False
            if in_ids and asset_identifier not in in_ids:
                return False
        return True
