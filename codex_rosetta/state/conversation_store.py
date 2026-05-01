from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from codex_rosetta.utils.logging import get_logger

logger = get_logger("conversation_store")


@dataclass
class ConversationEntry:
    messages: list[dict[str, Any]]
    output_items: list[dict[str, Any]]
    created_at: float = field(default_factory=time.time)


class ConversationStore(ABC):
    @abstractmethod
    async def store(
        self,
        response_id: str,
        messages: list[dict[str, Any]],
        output_items: list[dict[str, Any]],
        conversation_id: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def retrieve_messages(self, response_id: str) -> list[dict[str, Any]] | None: ...

    @abstractmethod
    async def retrieve_output_items(self, response_id: str) -> list[dict[str, Any]] | None: ...

    @abstractmethod
    async def delete(self, response_id: str) -> None: ...

    @abstractmethod
    async def retrieve_by_conversation_id(
        self, conversation_id: str
    ) -> list[dict[str, Any]] | None: ...

    @abstractmethod
    async def link_conversation(
        self, conversation_id: str, response_id: str
    ) -> None: ...


class InMemoryConversationStore(ConversationStore):
    """In-memory conversation store with TTL-based eviction."""

    def __init__(self, max_history: int = 100, ttl_seconds: int = 3600) -> None:
        self._store: dict[str, ConversationEntry] = {}
        self._conversation_map: dict[str, str] = {}  # conversation_id -> response_id
        self._max_history = max_history
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    async def store(
        self,
        response_id: str,
        messages: list[dict[str, Any]],
        output_items: list[dict[str, Any]],
        conversation_id: str | None = None,
    ) -> None:
        async with self._lock:
            self._evict_expired()
            self._store[response_id] = ConversationEntry(
                messages=messages[-self._max_history:],
                output_items=output_items,
            )
            if conversation_id:
                self._conversation_map[conversation_id] = response_id

        logger.debug(
            "conversation_stored",
            response_id=response_id,
            conversation_id=conversation_id,
            message_count=len(messages),
            output_count=len(output_items),
            store_size=len(self._store),
        )

    async def retrieve_messages(self, response_id: str) -> list[dict[str, Any]] | None:
        async with self._lock:
            entry = self._store.get(response_id)
            if entry is None:
                logger.debug("conversation_miss", response_id=response_id)
                return None
            if self._is_expired(entry):
                del self._store[response_id]
                logger.debug("conversation_expired", response_id=response_id)
                return None
            result = self._reconstruct_messages(entry)
            logger.debug("conversation_hit", response_id=response_id, message_count=len(result))
            return result

    async def retrieve_output_items(self, response_id: str) -> list[dict[str, Any]] | None:
        async with self._lock:
            entry = self._store.get(response_id)
            if entry is None:
                return None
            if self._is_expired(entry):
                del self._store[response_id]
                return None
            return entry.output_items

    async def delete(self, response_id: str) -> None:
        async with self._lock:
            self._store.pop(response_id, None)

    async def retrieve_by_conversation_id(
        self, conversation_id: str
    ) -> list[dict[str, Any]] | None:
        """Retrieve messages by conversation ID."""
        async with self._lock:
            response_id = self._conversation_map.get(conversation_id)
            if response_id is None:
                logger.debug("conversation_miss_by_conv_id", conversation_id=conversation_id)
                return None
            entry = self._store.get(response_id)
            if entry is None:
                del self._conversation_map[conversation_id]
                logger.debug("conversation_miss_by_conv_id", conversation_id=conversation_id)
                return None
            if self._is_expired(entry):
                del self._store[response_id]
                del self._conversation_map[conversation_id]
                logger.debug("conversation_expired_by_conv_id", conversation_id=conversation_id)
                return None
            result = self._reconstruct_messages(entry)
            logger.debug("conversation_hit_by_conv_id", conversation_id=conversation_id, message_count=len(result))
            return result

    async def link_conversation(
        self, conversation_id: str, response_id: str
    ) -> None:
        """Link a conversation_id to a response_id."""
        async with self._lock:
            self._conversation_map[conversation_id] = response_id
        logger.debug("conversation_linked", conversation_id=conversation_id, response_id=response_id)

    def _reconstruct_messages(self, entry: ConversationEntry) -> list[dict[str, Any]]:
        """Reconstruct full message list including output items from previous response."""
        messages = list(entry.messages)

        # Convert output items back to Chat Completions message format
        assistant_content: str | None = None
        tool_calls: list[dict[str, Any]] = []

        for item in entry.output_items:
            if item.get("type") == "message" and item.get("role") == "assistant":
                content = item.get("content", [])
                texts = []
                for part in content:
                    if part.get("type") == "output_text":
                        texts.append(part.get("text", ""))
                    elif part.get("type") == "refusal":
                        pass  # Handle refusal if needed
                assistant_content = "\n".join(texts) if texts else None

            elif item.get("type") == "function_call":
                tool_calls.append({
                    "id": item.get("call_id", item.get("id", "")),
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments", "{}"),
                    },
                })

        if assistant_content is not None or tool_calls:
            msg: dict[str, Any] = {"role": "assistant", "content": assistant_content}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            messages.append(msg)

        return messages

    def _is_expired(self, entry: ConversationEntry) -> bool:
        return (time.time() - entry.created_at) > self._ttl_seconds

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [
            k for k, v in self._store.items()
            if (now - v.created_at) > self._ttl_seconds
        ]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug("conversation_evicted", count=len(expired))


class RedisConversationStore(ConversationStore):
    """Redis-backed conversation store for persistence across restarts."""

    def __init__(self, redis_url: str, ttl_seconds: int = 3600) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(redis_url)
        self._ttl_seconds = ttl_seconds
        self._prefix = "codex_rosetta:conv:"

    async def store(
        self,
        response_id: str,
        messages: list[dict[str, Any]],
        output_items: list[dict[str, Any]],
        conversation_id: str | None = None,
    ) -> None:
        import json

        key = f"{self._prefix}{response_id}"
        data = json.dumps({
            "messages": messages,
            "output_items": output_items,
            "created_at": time.time(),
        })
        await self._redis.setex(key, self._ttl_seconds, data)
        if conversation_id:
            conv_key = f"{self._prefix}conv:{conversation_id}"
            await self._redis.setex(conv_key, self._ttl_seconds, response_id)

        logger.debug(
            "redis_conversation_stored",
            response_id=response_id,
            conversation_id=conversation_id,
        )

    async def retrieve_messages(self, response_id: str) -> list[dict[str, Any]] | None:
        entry = await self._retrieve_entry(response_id)
        if entry is None:
            logger.debug("redis_conversation_miss", response_id=response_id)
            return None
        # Reconstruct using same logic as in-memory
        temp_store = InMemoryConversationStore()
        conv_entry = ConversationEntry(
            messages=entry["messages"],
            output_items=entry["output_items"],
            created_at=entry["created_at"],
        )
        result = temp_store._reconstruct_messages(conv_entry)
        logger.debug("redis_conversation_hit", response_id=response_id, message_count=len(result))
        return result

    async def retrieve_output_items(self, response_id: str) -> list[dict[str, Any]] | None:
        entry = await self._retrieve_entry(response_id)
        if entry is None:
            return None
        return entry["output_items"]

    async def delete(self, response_id: str) -> None:
        key = f"{self._prefix}{response_id}"
        await self._redis.delete(key)

    async def retrieve_by_conversation_id(
        self, conversation_id: str
    ) -> list[dict[str, Any]] | None:
        conv_key = f"{self._prefix}conv:{conversation_id}"
        response_id = await self._redis.get(conv_key)
        if response_id is None:
            logger.debug("redis_conversation_miss_by_conv_id", conversation_id=conversation_id)
            return None
        response_id = response_id.decode() if isinstance(response_id, bytes) else response_id
        return await self.retrieve_messages(response_id)

    async def link_conversation(
        self, conversation_id: str, response_id: str
    ) -> None:
        conv_key = f"{self._prefix}conv:{conversation_id}"
        await self._redis.setex(conv_key, self._ttl_seconds, response_id)
        logger.debug("redis_conversation_linked", conversation_id=conversation_id, response_id=response_id)

    async def _retrieve_entry(self, response_id: str) -> dict[str, Any] | None:
        import json

        key = f"{self._prefix}{response_id}"
        data = await self._redis.get(key)
        if data is None:
            return None
        return json.loads(data)
