from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResponsesApiRequest(BaseModel):
    model: str
    input: str | list[Any]
    instructions: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    parallel_tool_calls: bool | None = None
    previous_response_id: str | None = None
    stream: bool = False
    store: bool | None = None
    metadata: dict[str, str] | None = None
    reasoning: dict[str, Any] | None = None
    text: dict[str, Any] | None = None
    truncation: Literal["auto", "disabled"] | None = None
    service_tier: str | None = None
    user: str | None = None
    safety_identifier: str | None = None
    prompt_cache_key: str | None = None
    top_logprobs: int | None = None

    model_config = {"extra": "allow"}


class ResponseOutputText(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str = ""
    annotations: list[Any] = Field(default_factory=list)


class ResponseRefusal(BaseModel):
    type: Literal["refusal"] = "refusal"
    refusal: str


class ResponseOutputMessage(BaseModel):
    type: Literal["message"] = "message"
    id: str
    role: Literal["assistant"] = "assistant"
    status: str = "completed"
    content: list[dict[str, Any]] = Field(default_factory=list)
    phase: str | None = None


class ResponseFunctionCall(BaseModel):
    type: Literal["function_call"] = "function_call"
    id: str
    call_id: str
    name: str
    arguments: str
    status: str = "completed"


class ResponseUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_tokens_details: dict[str, int] = Field(default_factory=lambda: {"cached_tokens": 0})
    output_tokens_details: dict[str, int] = Field(default_factory=lambda: {"reasoning_tokens": 0})


class ResponsesApiResponse(BaseModel):
    id: str
    object: Literal["response"] = "response"
    created_at: float
    completed_at: float | None = None
    model: str
    status: str = "completed"
    output: list[dict[str, Any]] = Field(default_factory=list)
    usage: ResponseUsage | None = None
    error: dict[str, Any] | None = None
    instructions: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, str] | None = None
    previous_response_id: str | None = None
    parallel_tool_calls: bool | None = None

    model_config = {"extra": "allow"}
