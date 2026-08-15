"""Observation Interpretation Engine — structured signals only, never AI prose as evidence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.core.logging import get_logger

logger = get_logger(__name__)


class Indicator(BaseModel):
    """Normalized indicator extracted from structured observation data."""

    kind: str
    value: str
    source_capability: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class InterpretationResult(BaseModel):
    """Structured interpretation of a tool observation."""

    observation_id: UUID
    indicators: list[Indicator] = Field(default_factory=list)
    candidate_finding_titles: list[str] = Field(default_factory=list)
    evidence_quality_signal: float = Field(default=0.5, ge=0.0, le=1.0)
    next_step_suggestions: list[str] = Field(default_factory=list)
    notes: str = ""
    success: bool = False


class ObservationInterpreter:
    """Convert structured tool results into indicators and next-step suggestions.

    Does NOT treat free-form AI prose as evidence.
    Only structured metadata and bounded summaries are used.
    """

    def interpret(self, observation: Observation) -> InterpretationResult:
        result = InterpretationResult(
            observation_id=observation.id,
            success=observation.status == ObservationStatus.SUCCESS,
        )
        if observation.status != ObservationStatus.SUCCESS:
            result.notes = f"Non-success status: {observation.status.value}"
            return result

        data: dict[str, Any] = dict(observation.structured_data or {})
        raw_meta = data.get("metadata")
        meta: dict[str, Any] = dict(raw_meta) if isinstance(raw_meta, dict) else data
        cap = observation.capability or ""

        sha = meta.get("sha256") or meta.get("hash") or data.get("sha256")
        if isinstance(sha, str) and len(sha) >= 32:
            result.indicators.append(
                Indicator(kind="hash", value=sha[:64], source_capability=cap, confidence=0.95)
            )

        if meta.get("has_android_manifest"):
            result.indicators.append(
                Indicator(kind="file_type", value="apk_with_manifest", source_capability=cap, confidence=0.9)
            )
            result.candidate_finding_titles.append("APK contains AndroidManifest")
            result.next_step_suggestions.append("strings-extract")
        if meta.get("has_dex"):
            result.indicators.append(
                Indicator(kind="file_type", value="dalvik_dex", source_capability=cap, confidence=0.9)
            )
        certs = meta.get("cert_entries") or []
        if isinstance(certs, list) and certs:
            for c in certs[:5]:
                result.indicators.append(
                    Indicator(kind="cert", value=str(c)[:256], source_capability=cap, confidence=0.7)
                )

        summary = (observation.summary or "").lower()
        if "elf" in summary:
            result.indicators.append(
                Indicator(kind="file_type", value="elf", source_capability=cap, confidence=0.85)
            )
            result.next_step_suggestions.append("strings-extract")
        if "pe32" in summary or "portable executable" in summary:
            result.indicators.append(
                Indicator(kind="file_type", value="pe", source_capability=cap, confidence=0.85)
            )
            result.next_step_suggestions.append("strings-extract")

        for token in ("http://", "https://", ".onion", "password", "api_key", "secret"):
            if token in summary:
                result.indicators.append(
                    Indicator(kind="keyword", value=token, source_capability=cap, confidence=0.4)
                )
                result.candidate_finding_titles.append(f"Possible indicator: {token}")
                result.evidence_quality_signal = min(0.6, result.evidence_quality_signal + 0.1)

        if result.indicators:
            result.evidence_quality_signal = min(1.0, 0.4 + 0.1 * len(result.indicators))

        return result
