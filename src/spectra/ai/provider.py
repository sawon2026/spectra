"""LLM provider abstraction — structured outputs only, never shell."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from spectra.intelligence.task import ArtifactType, TaskType


class StructuredTaskResponse(BaseModel):
    """Validated structured output from a model — not executable commands."""

    task_type: TaskType = TaskType.UNKNOWN
    artifact_type: ArtifactType = ArtifactType.UNKNOWN
    objectives: list[str] = Field(default_factory=list)
    requested_capabilities: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    network_required: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str = Field(default="", max_length=2000)

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> StructuredTaskResponse:
        forbidden = {"command", "shell", "cmd", "exec", "bash", "powershell"}
        for key in list(data.keys()):
            if key.lower() in forbidden:
                raise ValueError(f"Forbidden field in model output: {key}")
        return cls.model_validate(data)


class LLMProvider(ABC):
    @abstractmethod
    def classify_task(self, text: str) -> StructuredTaskResponse:
        ...

    def is_configured(self) -> bool:
        return False


class NullLLMProvider(LLMProvider):
    """Default provider — always offline / not configured."""

    def classify_task(self, text: str) -> StructuredTaskResponse:
        raise RuntimeError("No LLM provider configured; use DeterministicClassifier")

    def is_configured(self) -> bool:
        return False


def parse_model_json(raw: str | dict[str, Any]) -> StructuredTaskResponse:
    """Parse and validate model output; reject malformed / command-bearing payloads."""
    if isinstance(raw, str):
        import json

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed model JSON: {exc}") from exc
    else:
        data = raw
    if not isinstance(data, dict):
        raise ValueError("Model output must be a JSON object")
    try:
        return StructuredTaskResponse.from_raw(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid structured task: {exc}") from exc
