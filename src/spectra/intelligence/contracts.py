"""AI Decision Contract — strict schemas; reject unsafe/malformed outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from spectra.intelligence.task import ArtifactType, TaskType

_FORBIDDEN_KEYS = frozenset({
    "command", "shell", "cmd", "exec", "bash", "powershell", "sh",
    "authorization", "auth_override", "policy_override", "scope_change",
    "network_enable", "sudo", "raw_command",
})


class ProposedStep(BaseModel):
    """A single AI-proposed capability step — never a shell command."""

    capability: str = Field(..., min_length=1, max_length=128)
    objective: str = Field(default="", max_length=512)
    inputs: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(default="", max_length=1024)

    @field_validator("capability")
    @classmethod
    def no_shell_capability(cls, v: str) -> str:
        lower = v.lower().strip()
        if lower in ("bash", "sh", "cmd", "powershell", "shell", "exec"):
            raise ValueError(f"Forbidden capability name: {v}")
        if any(c in v for c in (";", "|", "&", "`", "$", "\n")):
            raise ValueError("Capability name contains shell metacharacters")
        return v

    @field_validator("inputs")
    @classmethod
    def no_command_inputs(cls, v: dict[str, Any]) -> dict[str, Any]:
        for key in list(v.keys()):
            if key.lower() in _FORBIDDEN_KEYS:
                raise ValueError(f"Forbidden input key: {key}")
        return v


class AIPlanResponse(BaseModel):
    """Validated AI planning response — structured only.

    Must NOT contain shell commands, authorization decisions, or policy overrides.
    """

    goal: str = Field(default="", max_length=2048)
    reasoning_summary: str = Field(default="", max_length=4000)
    proposed_steps: list[ProposedStep] = Field(default_factory=list)
    capability_requests: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    task_type: TaskType = TaskType.UNKNOWN
    artifact_type: ArtifactType = ArtifactType.UNKNOWN

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> AIPlanResponse:
        if not isinstance(data, dict):
            raise ValueError("AI response must be a JSON object")
        for key in list(data.keys()):
            if key.lower() in _FORBIDDEN_KEYS:
                raise ValueError(f"Forbidden field in AI output: {key}")
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid AI plan schema: {exc}") from exc


def validate_ai_plan(raw: str | dict[str, Any]) -> AIPlanResponse:
    """Parse and validate AI plan; reject malformed/unsafe payloads."""
    if isinstance(raw, str):
        import json

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed AI JSON: {exc}") from exc
    else:
        data = raw
    return AIPlanResponse.from_raw(data)
