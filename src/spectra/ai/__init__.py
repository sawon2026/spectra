"""Optional LLM provider interfaces — never required for core operation."""

from spectra.ai.provider import (
    LLMProvider,
    NullLLMProvider,
    OpenAICompatibleProvider,
    ProviderInfo,
    ProviderRegistry,
    StructuredTaskResponse,
    parse_model_json,
)

__all__ = [
    "LLMProvider",
    "StructuredTaskResponse",
    "NullLLMProvider",
    "OpenAICompatibleProvider",
    "ProviderRegistry",
    "ProviderInfo",
    "parse_model_json",
]
