"""Stable plugin interfaces (Phase 6 + Phase 12 SDK v2).

Plugins never gain unrestricted privileges. Capability/tool plugins still
must go through PolicyEngine at execution time.
Plugin enablement is NOT execution authorization.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PluginKind(str, Enum):
    CAPABILITY = "capability"
    TOOL_ADAPTER = "tool_adapter"
    TOOL = "tool"
    PARSER = "parser"
    ANALYZER = "analyzer"
    REPORTER = "reporter"
    INTEGRATION = "integration"
    EVIDENCE_PROCESSOR = "evidence_processor"
    FINDING_ANALYZER = "finding_analyzer"
    AI_PROVIDER = "ai_provider"
    REPORT_EXPORTER = "report_exporter"


class PluginState(str, Enum):
    REGISTERED = "registered"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNHEALTHY = "unhealthy"


class PluginHealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PluginManifest(BaseModel):
    """Versioned plugin descriptor — no automatic privilege escalation."""

    name: str = Field(..., min_length=1, max_length=128)
    version: str = Field(default="0.1.0", max_length=32)
    kind: PluginKind
    description: str = Field(default="", max_length=1024)
    entrypoint: str = Field(default="", max_length=256)
    requires_authorization: bool = True
    network_required: bool = False
    requires_network: bool = False
    offline_safe: bool = True
    capabilities: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def no_path_traversal(cls, v: str) -> str:
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Plugin name must not contain path separators")
        return v


class PluginHealth(BaseModel):
    name: str
    status: PluginHealthStatus = PluginHealthStatus.UNKNOWN
    message: str = ""
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class PluginLifecycleEvent(BaseModel):
    name: str
    from_state: PluginState | None = None
    to_state: PluginState
    actor: str = "system"
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    note: str = ""


def validate_manifest(data: dict[str, Any]) -> PluginManifest:
    forbidden = {"shell", "command", "sudo", "privilege_escalate", "policy_override"}
    for key in list(data.keys()):
        if key.lower() in forbidden:
            raise ValueError(f"Forbidden manifest field: {key}")
    return PluginManifest.model_validate(data)


class PluginRegistry:
    """In-process registry of validated manifests (no dynamic code loading)."""

    def __init__(self) -> None:
        self._manifests: dict[str, PluginManifest] = {}
        self._states: dict[str, PluginState] = {}
        self._health: dict[str, PluginHealth] = {}

    def register(self, manifest: PluginManifest | dict[str, Any]) -> PluginManifest:
        if isinstance(manifest, dict):
            manifest = validate_manifest(manifest)
        if manifest.name in self._manifests:
            raise ValueError(f"Plugin already registered: {manifest.name}")
        self._manifests[manifest.name] = manifest
        self._states[manifest.name] = PluginState.REGISTERED
        self._health[manifest.name] = PluginHealth(
            name=manifest.name,
            status=PluginHealthStatus.OK,
            message="registered",
        )
        return manifest

    def enable(self, name: str) -> PluginState:
        if name not in self._manifests:
            raise KeyError(name)
        self._states[name] = PluginState.ENABLED
        return PluginState.ENABLED

    def disable(self, name: str) -> PluginState:
        if name not in self._manifests:
            raise KeyError(name)
        self._states[name] = PluginState.DISABLED
        return PluginState.DISABLED

    def set_health(
        self, name: str, status: PluginHealthStatus, message: str = ""
    ) -> PluginHealth:
        if name not in self._manifests:
            raise KeyError(name)
        h = PluginHealth(name=name, status=status, message=message)
        self._health[name] = h
        if status == PluginHealthStatus.UNAVAILABLE:
            self._states[name] = PluginState.UNHEALTHY
        return h

    def get(self, name: str) -> PluginManifest | None:
        return self._manifests.get(name)

    def state(self, name: str) -> PluginState | None:
        return self._states.get(name)

    def health(self, name: str) -> PluginHealth | None:
        return self._health.get(name)

    def list_manifests(self, kind: PluginKind | None = None) -> list[PluginManifest]:
        items = list(self._manifests.values())
        if kind:
            items = [m for m in items if m.kind == kind]
        return items

    def list_with_status(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in self._manifests.values():
            h = self._health.get(m.name)
            out.append(
                {
                    "name": m.name,
                    "version": m.version,
                    "kind": m.kind.value,
                    "state": self._states.get(m.name, PluginState.REGISTERED).value,
                    "health": h.status.value if h is not None else "unknown",
                    "capabilities": list(m.capabilities),
                    "offline_safe": m.offline_safe,
                    "requires_network": m.requires_network or m.network_required,
                }
            )
        return out

    def unregister(self, name: str) -> bool:
        self._states.pop(name, None)
        self._health.pop(name, None)
        return self._manifests.pop(name, None) is not None

    # Backward-compatible alias (avoid shadowing builtin in annotations)
    list = list_manifests
