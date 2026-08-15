"""Stable plugin interfaces (Phase 6).

Plugins never gain unrestricted privileges. Capability/tool plugins still
must go through PolicyEngine at execution time.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PluginKind(str, Enum):
    CAPABILITY = "capability"
    TOOL_ADAPTER = "tool_adapter"
    PARSER = "parser"
    EVIDENCE_PROCESSOR = "evidence_processor"
    FINDING_ANALYZER = "finding_analyzer"
    AI_PROVIDER = "ai_provider"
    REPORT_EXPORTER = "report_exporter"


class PluginManifest(BaseModel):
    """Versioned plugin descriptor — no automatic privilege escalation."""

    name: str = Field(..., min_length=1, max_length=128)
    version: str = Field(default="0.1.0", max_length=32)
    kind: PluginKind
    description: str = Field(default="", max_length=1024)
    entrypoint: str = Field(default="", max_length=256)
    requires_authorization: bool = True
    network_required: bool = False
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def no_path_traversal(cls, v: str) -> str:
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Plugin name must not contain path separators")
        return v


def validate_manifest(data: dict[str, Any]) -> PluginManifest:
    forbidden = {"shell", "command", "sudo", "privilege_escalate"}
    for key in list(data.keys()):
        if key.lower() in forbidden:
            raise ValueError(f"Forbidden manifest field: {key}")
    return PluginManifest.model_validate(data)


class PluginRegistry:
    """In-process registry of validated manifests (no dynamic code loading yet)."""

    def __init__(self) -> None:
        self._manifests: dict[str, PluginManifest] = {}

    def register(self, manifest: PluginManifest | dict[str, Any]) -> PluginManifest:
        if isinstance(manifest, dict):
            manifest = validate_manifest(manifest)
        if manifest.name in self._manifests:
            raise ValueError(f"Plugin already registered: {manifest.name}")
        self._manifests[manifest.name] = manifest
        return manifest

    def get(self, name: str) -> PluginManifest | None:
        return self._manifests.get(name)

    def list(self, kind: PluginKind | None = None) -> list[PluginManifest]:
        items = list(self._manifests.values())
        if kind:
            items = [m for m in items if m.kind == kind]
        return items

    def unregister(self, name: str) -> bool:
        return self._manifests.pop(name, None) is not None
