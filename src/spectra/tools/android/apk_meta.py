"""APK metadata inspection — pure Python (zip + optional binary tools)."""

from __future__ import annotations

import hashlib
import zipfile
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
from spectra.tools.base import ToolAdapter, ToolResult


class ApkMetadataAdapter(ToolAdapter):
    name = "android.apk.metadata"
    capability = Capability(
        name="android.apk.metadata",
        category=CapabilityCategory.ANDROID,
        description="Inspect APK as zip: entries, AndroidManifest presence, cert paths, size, sha256.",
        input_types=[InputType.APK, InputType.FILE],
        output_types=[OutputType.JSON, OutputType.EVIDENCE],
        risk_level=RiskLevel.LOW,
        requires_authorization=True,
        execution_mode=ExecutionMode.READ_ONLY,
        health_status="healthy",
    )

    def is_available(self) -> bool:
        return True  # pure Python

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
            return ToolResult(success=False, error="Missing or invalid 'path'")
        p = Path(path)
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        settings = get_settings()
        if self.capability.requires_authorization or settings.require_scope_for_execution:
            decision = self._check_policy(scope, self.capability.name, asset=str(p))
            if not decision.allowed:
                return ToolResult(success=False, error=decision.reason)

        try:
            data = p.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            if not zipfile.is_zipfile(p):
                return ToolResult(
                    success=False,
                    error="Not a valid ZIP/APK archive",
                    metadata={"sha256": sha, "size": len(data)},
                )
            with zipfile.ZipFile(p, "r") as zf:
                names = zf.namelist()
                has_manifest = any(n.upper().endswith("ANDROIDMANIFEST.XML") for n in names)
                has_dex = any(n.endswith(".dex") for n in names)
                cert_entries = [n for n in names if "META-INF/" in n and (n.endswith(".RSA") or n.endswith(".DSA") or n.endswith(".EC"))]
                sample_entries = names[:50]
            meta = {
                "sha256": sha,
                "size": len(data),
                "entry_count": len(names),
                "has_android_manifest": has_manifest,
                "has_dex": has_dex,
                "cert_entries": cert_entries,
                "sample_entries": sample_entries,
            }
            summary = (
                f"APK size={len(data)} sha256={sha[:16]}… "
                f"entries={len(names)} manifest={has_manifest} dex={has_dex}"
            )
            result = ToolResult(success=True, stdout=summary, metadata=meta)
        except (OSError, zipfile.BadZipFile) as exc:
            result = ToolResult(success=False, error=str(exc))

        if self.event_bus:
            self.event_bus.publish(
                SpectraEvent(
                    event_type=EventType.TOOL_EXECUTED if result.success else EventType.TOOL_FAILED,
                    case_id=case_id,
                    message=f"android.apk.metadata on {p.name}",
                    payload={"adapter": self.name, "success": result.success},
                    actor="apk_metadata_adapter",
                )
            )
        return result
