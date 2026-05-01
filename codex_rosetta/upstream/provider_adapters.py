from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from codex_rosetta.config import Settings


class ProviderAdapter(ABC):
    """Base class for provider-specific request/response adaptations."""

    @abstractmethod
    def get_auth_headers(self, api_key: str) -> dict[str, str]: ...

    @abstractmethod
    def adapt_request(self, body: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def adapt_response(self, response: dict[str, Any]) -> dict[str, Any]: ...


class OpenAIAdapter(ProviderAdapter):
    """Passthrough adapter for OpenAI-compatible APIs."""

    def get_auth_headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def adapt_request(self, body: dict[str, Any]) -> dict[str, Any]:
        return body

    def adapt_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return response


class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic's Chat Completions-compatible endpoint."""

    def get_auth_headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

    def adapt_request(self, body: dict[str, Any]) -> dict[str, Any]:
        # Anthropic requires max_tokens but may not accept max_completion_tokens
        if "max_completion_tokens" in body and "max_tokens" not in body:
            body["max_tokens"] = body.pop("max_completion_tokens")
        elif "max_completion_tokens" in body:
            body.pop("max_completion_tokens")
            if "max_tokens" not in body:
                body["max_tokens"] = 4096

        # Anthropic doesn't support some OpenAI-specific params
        for key in ("service_tier", "store", "logprobs", "top_logprobs", "seed",
                     "reasoning_effort", "prompt_cache_key", "safety_identifier",
                     "frequency_penalty", "presence_penalty"):
            body.pop(key, None)

        return body

    def adapt_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return response


class GoogleAdapter(ProviderAdapter):
    """Adapter for Google Vertex AI / Gemini Chat Completions-compatible endpoint."""

    def get_auth_headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def adapt_request(self, body: dict[str, Any]) -> dict[str, Any]:
        for key in ("service_tier", "store", "logprobs", "top_logprobs", "seed",
                     "reasoning_effort", "prompt_cache_key", "safety_identifier"):
            body.pop(key, None)
        return body

    def adapt_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return response


_ADAPTERS = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "google": GoogleAdapter,
}


def get_provider_adapter(provider: str) -> ProviderAdapter:
    cls = _ADAPTERS.get(provider, OpenAIAdapter)
    return cls()
