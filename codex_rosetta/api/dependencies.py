from __future__ import annotations

import asyncio
from functools import lru_cache

from codex_rosetta.config import Settings, get_settings
from codex_rosetta.state.conversation_store import ConversationStore, InMemoryConversationStore
from codex_rosetta.upstream.client import UpstreamClient


_upstream_client: UpstreamClient | None = None
_client_lock = asyncio.Lock()


def get_upstream_client(settings: Settings | None = None) -> UpstreamClient:
    global _upstream_client
    if _upstream_client is not None:
        return _upstream_client
    if settings is None:
        settings = get_settings()
    _upstream_client = UpstreamClient(settings)
    return _upstream_client


async def rebuild_upstream_client(settings: Settings) -> UpstreamClient:
    global _upstream_client
    async with _client_lock:
        old = _upstream_client
        _upstream_client = UpstreamClient(settings)
        if old is not None:
            await old.close()
    return _upstream_client


def get_conversation_store(settings: Settings | None = None) -> ConversationStore:
    if settings is None:
        settings = get_settings()
    if settings.REDIS_URL:
        try:
            from codex_rosetta.state.conversation_store import RedisConversationStore
            return RedisConversationStore(settings.REDIS_URL, settings.CONVERSATION_TTL_SECONDS)
        except ImportError:
            pass
    return InMemoryConversationStore(
        max_history=settings.MAX_CONVERSATION_HISTORY,
        ttl_seconds=settings.CONVERSATION_TTL_SECONDS,
    )
