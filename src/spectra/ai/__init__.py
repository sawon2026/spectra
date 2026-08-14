"""Optional LLM provider interfaces — never required for core operation."""

from spectra.ai.provider import LLMProvider, NullLLMProvider, StructuredTaskResponse

__all__ = ["LLMProvider", "StructuredTaskResponse", "NullLLMProvider"]
