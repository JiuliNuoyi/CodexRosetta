from __future__ import annotations

import time
from typing import Any, AsyncIterator

import httpx

from codex_rosetta.config import Settings, get_settings
from codex_rosetta.upstream.provider_adapters import ProviderAdapter, get_provider_adapter
from codex_rosetta.utils.logging import get_logger

logger = get_logger("upstream")


class UpstreamClient:
    """Async HTTP client for forwarding requests to the upstream Chat Completions API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._adapter: ProviderAdapter = get_provider_adapter(settings.UPSTREAM_PROVIDER)
        self._client = httpx.AsyncClient(
            base_url=settings.UPSTREAM_BASE_URL,
            timeout=httpx.Timeout(
                connect=settings.UPSTREAM_TIMEOUT_CONNECT,
                read=settings.UPSTREAM_TIMEOUT_READ,
                write=30.0,
                pool=30.0,
            ),
        )
        self._log = logger.bind(
            base_url=settings.UPSTREAM_BASE_URL,
            provider=settings.UPSTREAM_PROVIDER,
        )
        self._log_upstream_requests = settings.LOG_UPSTREAM_REQUESTS
        self._log_upstream_responses = settings.LOG_UPSTREAM_RESPONSES

    @property
    def adapter(self) -> ProviderAdapter:
        return self._adapter

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        headers.update(self._adapter.get_auth_headers(self._settings.UPSTREAM_API_KEY))
        return headers

    async def chat_completions(self, request_body: dict[str, Any]) -> dict[str, Any]:
        """Send a non-streaming request to upstream /v1/chat/completions."""
        adapted = self._adapter.adapt_request(request_body)
        headers = self._get_headers()

        self._log.info(
            "upstream_request_sent",
            model=adapted.get("model"),
            message_count=len(adapted.get("messages", [])),
            stream=adapted.get("stream", False),
        )

        if self._log_upstream_requests:
            self._log.debug("upstream_request_body", body=adapted)

        start = time.monotonic()
        response = await self._client.post(
            "/chat/completions",
            json=adapted,
            headers=headers,
        )
        duration_ms = round((time.monotonic() - start) * 1000)

        self._log.info(
            "upstream_response_received",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        if response.status_code >= 400:
            error_body = response.text
            self._log.error(
                "upstream_error_response",
                status_code=response.status_code,
                error_body=error_body[:2000],
            )

        response.raise_for_status()

        data = response.json()
        result = self._adapter.adapt_response(data)

        if self._log_upstream_responses:
            self._log.debug("upstream_response_body", body=result)

        return result

    async def chat_completions_stream(
        self, request_body: dict[str, Any]
    ) -> AsyncIterator[bytes]:
        """Stream from upstream /v1/chat/completions."""
        adapted = self._adapter.adapt_request(request_body)
        headers = self._get_headers()

        self._log.info(
            "upstream_stream_started",
            model=adapted.get("model"),
            message_count=len(adapted.get("messages", [])),
        )

        if self._log_upstream_requests:
            self._log.debug("upstream_request_body", body=adapted)

        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=adapted,
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                error_body = response.text
                self._log.error(
                    "upstream_error_response",
                    status_code=response.status_code,
                    error_body=error_body[:2000],
                )
            response.raise_for_status()
            chunk_count = 0
            async for chunk in response.aiter_bytes():
                chunk_count += 1
                yield chunk

            self._log.info("upstream_stream_ended", chunk_count=chunk_count)

    async def close(self) -> None:
        await self._client.aclose()
