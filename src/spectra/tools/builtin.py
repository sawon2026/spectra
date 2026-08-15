"""Built-in safe tool adapters (Phase 1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from spectra.core.config import get_settings
from spectra.models.capability import (
    Capability,
    CapabilityCategory,
    ExecutionMode,
    InputType,
    OutputType,
    RiskLevel,
)
from spectra.models.events import EventType, SpectraEvent
from spectra.models.scope import Scope
from spectra.tools.base import ToolAdapter, ToolResult, resolve_allowed_binary, run_safe_command


class FileInfoAdapter(ToolAdapter):
    name = "file-info"
    capability = Capability(
        name="file-info",
        category=CapabilityCategory.UTILITY,
        description="Identify file type (read-only).",
        input_types=[InputType.FILE],
        output_types=[OutputType.JSON, OutputType.EVIDENCE],
        risk_level=RiskLevel.NONE,
        requires_authorization=False,
        execution_mode=ExecutionMode.READ_ONLY,
        health_status="healthy",
    )

    def is_available(self) -> bool:
        return resolve_allowed_binary("file") is not None

    def execute(
        self,
        *,
        scope: Scope | None,
        case_id: UUID,
        inputs: dict[str, Any],
        timeout: int | None = None,
    ) -> ToolResult:
        path = inputs.get("path")
        if not path or not isinstance(path, str):
            return ToolResult(success=False, error="Missing or invalid 'path' input")
        p = Path(path)
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        settings = get_settings()
        if self.capability.requires_authorization or settings.require_scope_for_execution:
            decision = self._check_policy(scope, "file-info", asset=str(p))
            if not decision.allowed:
                return ToolResult(success=False, error=decision.reason)

        result = run_safe_command("file", ["-b", str(p)], timeout=timeout or 30)
        if self.event_bus:
            self.event_bus.publish(
                SpectraEvent(
                    event_type=EventType.TOOL_EXECUTED if result.success else EventType.TOOL_FAILED,
                    case_id=case_id,
                    message=f"file-info on {p.name}",
                    payload={"adapter": self.name, "success": result.success},
                    actor="file_info_adapter",
                )
            )
        return result


class HashComputeAdapter(ToolAdapter):
    name = "hash-compute"
    capability = Capability(
        name="hash-compute",
        category=CapabilityCategory.UTILITY,
        description="Compute SHA-256 of a file (read-only).",
        input_types=[InputType.FILE],
        output_types=[OutputType.JSON, OutputType.EVIDENCE],
        risk_level=RiskLevel.NONE,
        requires_authorization=False,
        execution_mode=ExecutionMode.READ_ONLY,
        health_status="healthy",
    )

    def is_available(self) -> bool:
        return resolve_allowed_binary("sha256sum") is not None or True  # pure Python fallback

    def execute(
        self,
        *,
        scope: Scope | None,
        case_id: UUID,
        inputs: dict[str, Any],
        timeout: int | None = None,
    ) -> ToolResult:
        import hashlib

        path = inputs.get("path")
        if not path or not isinstance(path, str):
            return ToolResult(success=False, error="Missing or invalid 'path' input")
        p = Path(path)
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        settings = get_settings()
        if self.capability.requires_authorization or settings.require_scope_for_execution:
            decision = self._check_policy(scope, "hash-compute", asset=str(p))
            if not decision.allowed:
                return ToolResult(success=False, error=decision.reason)

        try:
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            digest = h.hexdigest()
            result = ToolResult(
                success=True,
                stdout=digest,
                metadata={"algorithm": "sha256", "path": str(p)},
            )
        except OSError as exc:
            result = ToolResult(success=False, error=str(exc))

        if self.event_bus:
            self.event_bus.publish(
                SpectraEvent(
                    event_type=EventType.TOOL_EXECUTED if result.success else EventType.TOOL_FAILED,
                    case_id=case_id,
                    message=f"hash-compute on {p.name}",
                    payload={"adapter": self.name, "success": result.success},
                    actor="hash_compute_adapter",
                )
            )
        return result


class StringsExtractAdapter(ToolAdapter):
    name = "strings-extract"
    capability = Capability(
        name="strings-extract",
        category=CapabilityCategory.REVERSE_ENGINEERING,
        description="Extract printable strings from a file (pure Python, read-only).",
        input_types=[InputType.BINARY, InputType.FILE],
        output_types=[OutputType.TEXT, OutputType.EVIDENCE],
        risk_level=RiskLevel.LOW,
        requires_authorization=True,
        execution_mode=ExecutionMode.READ_ONLY,
        health_status="healthy",
    )

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        *,
        scope: Scope | None,
        case_id: UUID,
        inputs: dict[str, Any],
        timeout: int | None = None,
    ) -> ToolResult:
        path = inputs.get("path")
        if not path or not isinstance(path, str):
            return ToolResult(success=False, error="Missing or invalid 'path' input")
        p = Path(path)
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        settings = get_settings()
        if self.capability.requires_authorization or settings.require_scope_for_execution:
            decision = self._check_policy(scope, "strings-extract", asset=str(p))
            if not decision.allowed:
                return ToolResult(success=False, error=decision.reason)

        try:
            data = p.read_bytes()[:2_000_000]  # cap
            out: list[str] = []
            cur = bytearray()
            for b in data:
                if 32 <= b < 127:
                    cur.append(b)
                else:
                    if len(cur) >= 4:
                        out.append(cur.decode("ascii", errors="ignore"))
                    cur = bytearray()
            if len(cur) >= 4:
                out.append(cur.decode("ascii", errors="ignore"))
            text = "\n".join(out[:500])
            result = ToolResult(success=True, stdout=text, metadata={"count": len(out)})
        except OSError as exc:
            result = ToolResult(success=False, error=str(exc))

        if self.event_bus:
            self.event_bus.publish(
                SpectraEvent(
                    event_type=EventType.TOOL_EXECUTED if result.success else EventType.TOOL_FAILED,
                    case_id=case_id,
                    message=f"strings-extract on {p.name}",
                    payload={"adapter": self.name, "success": result.success},
                    actor="strings_extract_adapter",
                )
            )
        return result
