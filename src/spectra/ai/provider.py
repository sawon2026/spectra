"""LLM provider abstraction — structured outputs only, never shell or policy authority.

Providers never execute tools, modify scope, or authorize actions.
Offline deterministic fallback is mandatory when no provider is configured.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib import error, request

from pydantic import BaseModel, Field, ValidationError

from spectra.core.logging import get_logger
from spectra.intelligence.contracts import AIPlanResponse, validate_ai_plan
from spectra.intelligence.task import ArtifactType, TaskType

logger = get_logger(__name__)


class ProviderCapability(str, Enum):
    CLASSIFY = "classify"
    PLAN = "plan"
    STRUCTURED_JSON = "structured_json"


@dataclass
class ProviderInfo:
    name: str
    version: str = "0.1"
    model: str = ""
    available: bool = False
    offline: bool = True
    capabilities: list[str] = field(default_factory=list)
    structured_output: bool = True
    limits: dict[str, Any] = field(default_factory=dict)


class StructuredTaskResponse(BaseModel):
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
    name: str = "base"

    @abstractmethod
    def classify_task(self, text: str) -> StructuredTaskResponse:
        ...

    def plan(self, goal: str, context: dict[str, Any] | None = None) -> AIPlanResponse:
        raise RuntimeError(f"Provider {self.name} does not support planning")

    def is_configured(self) -> bool:
        return False

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            available=self.is_configured(),
            offline=not self.is_configured(),
            capabilities=[],
            structured_output=True,
        )


class NullLLMProvider(LLMProvider):
    name = "null"

    def classify_task(self, text: str) -> StructuredTaskResponse:
        raise RuntimeError("No LLM provider configured; use DeterministicClassifier")

    def is_configured(self) -> bool:
        return False

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="null",
            available=False,
            offline=True,
            capabilities=[],
            structured_output=True,
            limits={"reason": "not configured"},
        )


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        self.api_base = (api_base or os.environ.get("SPECTRA_MODEL_API_BASE") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("SPECTRA_MODEL_API_KEY") or ""
        self.model = model or os.environ.get("SPECTRA_MODEL_NAME") or "gpt-4o-mini"
        self.timeout = timeout_seconds
        self.max_retries = max(0, max_retries)

    def is_configured(self) -> bool:
        return bool(self.api_base and self.api_key)

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            model=self.model,
            available=self.is_configured(),
            offline=not self.is_configured(),
            capabilities=[
                ProviderCapability.CLASSIFY.value,
                ProviderCapability.PLAN.value,
                ProviderCapability.STRUCTURED_JSON.value,
            ],
            structured_output=True,
            limits={"timeout": self.timeout, "max_retries": self.max_retries},
        )

    def classify_task(self, text: str) -> StructuredTaskResponse:
        prompt = (
            "Classify this security research task. Respond with JSON only containing: "
            "task_type, artifact_type, objectives, requested_capabilities, risk_level, "
            "network_required, confidence, notes. Never include command/shell fields.\n\n"
            f"Task: {text[:2000]}"
        )
        data = self._chat_json(prompt)
        return StructuredTaskResponse.from_raw(data)

    def plan(self, goal: str, context: dict[str, Any] | None = None) -> AIPlanResponse:
        ctx = json.dumps(context or {}, default=str)[:4000]
        prompt = (
            "Propose a structured security research plan as JSON with fields: "
            "goal, reasoning_summary, proposed_steps, capability_requests, confidence, assumptions. "
            "Never include command, shell, bash, authorization, or policy fields.\n\n"
            f"Goal: {goal[:1500]}\nContext: {ctx}"
        )
        data = self._chat_json(prompt)
        return validate_ai_plan(data)

    def _chat_json(self, user_prompt: str) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("OpenAI-compatible provider not configured")
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a security research assistant for Spectra. Output strict JSON only. Never propose shell commands.",
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._http_post(f"{self.api_base}/chat/completions", body)
            except Exception as exc:
                last_err = exc
                logger.warning("llm_request_failed", attempt=attempt, error=str(exc)[:200])
        raise RuntimeError(f"LLM provider failed: {last_err}")

    def _http_post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {exc.read()[:300]!r}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Network error: {exc}") from exc
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("Empty LLM response")
        content = choices[0].get("message", {}).get("content") or "{}"
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed LLM JSON: {exc}") from exc
        if isinstance(content, dict):
            return content
        raise ValueError("Unexpected LLM content type")


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self.register(NullLLMProvider())
        self.register(OpenAICompatibleProvider())

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> LLMProvider | None:
        return self._providers.get(name)

    def list_info(self) -> list[ProviderInfo]:
        return [p.info() for p in self._providers.values()]

    def active(self) -> LLMProvider:
        for name, p in self._providers.items():
            if name != "null" and p.is_configured():
                return p
        return self._providers.get("null") or NullLLMProvider()

    def is_any_configured(self) -> bool:
        return any(p.is_configured() for n, p in self._providers.items() if n != "null")


def parse_model_json(raw: str | dict[str, Any]) -> StructuredTaskResponse:
    if isinstance(raw, str):
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
        raise ValueError(f"Invalid structured task: {exc}") from exp if False else ValueError(f"Invalid structured task: {exc}") from exc
