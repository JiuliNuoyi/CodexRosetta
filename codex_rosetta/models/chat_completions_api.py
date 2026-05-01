from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any = None
    temperature: float | None = None
    top_p: float | None = None
    max_completion_tokens: int | None = None
    parallel_tool_calls: bool | None = None
    stream: bool = False
    stream_options: dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    reasoning_effort: str | None = None
    seed: int | None = None
    stop: str | list[str] | None = None
    service_tier: str | None = None
    store: bool | None = None
    metadata: dict[str, str] | None = None
    user: str | None = None
    safety_identifier: str | None = None
    prompt_cache_key: str | None = None
    top_logprobs: int | None = None
    logprobs: bool | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None

    model_config = {"extra": "allow"}


class ChatCompletionToolCall(BaseModel):
    id: str
    type: str = "function"
    function: dict[str, str]  # {"name": "...", "arguments": "..."}


class ChatCompletionMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    refusal: str | None = None
    name: str | None = None

    model_config = {"extra": "allow"}


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    completion_tokens_details: dict[str, int] = Field(default_factory=dict)
    prompt_tokens_details: dict[str, int] = Field(default_factory=dict)


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict[str, Any]] = Field(default_factory=list)
    usage: ChatCompletionUsage | None = None

    model_config = {"extra": "allow"}
