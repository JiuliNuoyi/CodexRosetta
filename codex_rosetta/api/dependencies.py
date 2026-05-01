from __future__ import annotations

from functools import lru_cache

from codex_rosetta.config import Settings, get_settings
from codex_rosetta.state.conversation_store import ConversationStore, InMemoryConversationStore
from codex_rosetta.upstream.client import UpstreamClient


@lru_cache
def get_upstream_client(settings: Settings | None = None) -> UpstreamClient:
    if settings is None:
        settings = get_settings()
    return UpstreamClient(settings)


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
