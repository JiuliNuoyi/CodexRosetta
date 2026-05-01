from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from codex_rosetta.api.dependencies import get_conversation_store, get_upstream_client
from codex_rosetta.audit.logger import NoOpAuditLogger
from codex_rosetta.config import get_settings
from codex_rosetta.converters.request_converter import RequestConverter
from codex_rosetta.converters.response_converter import ResponseConverter
from codex_rosetta.converters.stream_converter import StreamConverter
from codex_rosetta.utils.logging import get_logger
from codex_rosetta.utils.sse import format_sse_event

logger = get_logger("router")
settings = get_settings()

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/responses", response_model=None)
async def create_response(request: Request):
    request_id = getattr(request.state, "request_id", "unknown")
    log = logger.bind(request_id=request_id)

    body = await request.json()

    # Get auditor from middleware (no-op if audit disabled)
    auditor = getattr(request.state, "auditor", NoOpAuditLogger())

    # Log incoming request
    log.info(
        "request_received",
        model=body.get("model"),
        stream=body.get("stream", False),
        has_tools=bool(body.get("tools")),
        has_previous_response_id=bool(body.get("previous_response_id")),
        has_conversation=bool(body.get("conversation")),
        has_instructions=bool(body.get("instructions")),
    )

    # Set up components
    upstream = get_upstream_client()
    store = get_conversation_store()
    request_converter = RequestConverter()

    # Resolve previous_response_id or conversation parameter
    conversation_messages: list[dict[str, Any]] | None = None
    prev_id = body.get("previous_response_id")
    conv_param = body.get("conversation")
    if prev_id:
        conversation_messages = await store.retrieve_messages(prev_id)
        log.debug("conversation_resolved", via="previous_response_id", response_id=prev_id, found=conversation_messages is not None)
    elif conv_param:
        conv_id = conv_param if isinstance(conv_param, str) else conv_param.get("id")
        if conv_id:
            conversation_messages = await store.retrieve_by_conversation_id(conv_id)
            log.debug("conversation_resolved", via="conversation", conversation_id=conv_id, found=conversation_messages is not None)

    # Convert request
    chat_request, context = await request_converter.convert(body, conversation_messages, auditor=auditor)

    log.info(
        "request_converted",
        response_id=context.response_id,
        message_count=len(chat_request.get("messages", [])),
        has_tools=bool(chat_request.get("tools")),
        tool_count=len(chat_request.get("tools", [])),
    )

    if settings.LOG_UPSTREAM_REQUESTS:
        log.debug("upstream_request_body", body=chat_request)

    is_streaming = body.get("stream", False)

    if is_streaming:
        return StreamingResponse(
            _stream_response(upstream, chat_request, context, store, body, log, auditor),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            chat_response = await _call_upstream_with_retry(
                upstream, chat_request, context, log
            )
        except httpx.HTTPStatusError as e:
            log.warning("upstream_error", status=e.response.status_code, error=str(e))
            return JSONResponse(
                status_code=e.response.status_code,
                content=_make_error_response(
                    context.response_id,
                    "upstream_error",
                    str(e),
                ),
            )

        if settings.LOG_UPSTREAM_RESPONSES:
            log.debug("upstream_response_body", body=chat_response)

        response_converter = ResponseConverter()
        responses_response = response_converter.convert(chat_response, context)

        # Summarize output items
        output_items = responses_response.get("output", [])
        item_types = [item.get("type", "unknown") for item in output_items]
        usage = responses_response.get("usage", {})

        log.info(
            "response_sent",
            response_id=context.response_id,
            output_count=len(output_items),
            output_types=item_types,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

        # Store conversation state
        conv_id = _extract_conversation_id(body)
        await store.store(
            context.response_id,
            chat_request.get("messages", []),
            responses_response.get("output", []),
            conversation_id=conv_id,
        )
        log.debug("conversation_stored", response_id=context.response_id, conversation_id=conv_id)

        auditor.record_output_event("response.completed", {"response": responses_response})

        return JSONResponse(content=responses_response)


async def _stream_response(
    upstream: Any,
    chat_request: dict[str, Any],
    context: Any,
    store: Any,
    original_body: dict[str, Any],
    log: Any,
    auditor: Any,
) -> Any:
    """Yield Responses API SSE events converted from upstream Chat Completions stream."""
    stream_converter = StreamConverter(context, auditor=auditor)

    log.info("stream_started", model=context.model, response_id=context.response_id)
    start = time.monotonic()
    chunk_count = 0

    try:
        async for raw_chunk in upstream.chat_completions_stream(chat_request):
            chunk_count += 1
            auditor.record_upstream_chunk(raw_chunk)
            async for event_type, event_data in stream_converter.process_chunk(raw_chunk):
                if event_data is None:
                    continue
                if event_type:
                    yield format_sse_event(event_type, event_data)

        # Flush any remaining buffered SSE data
        async for event_type, event_data in stream_converter.flush_buffer():
            if event_data is None:
                continue
            if event_type:
                yield format_sse_event(event_type, event_data)

        # Emit finalization events
        async for event_type, event_data in stream_converter.finalize():
            yield format_sse_event(event_type, event_data)

        # Store conversation state
        output_items = stream_converter.current_output_items
        conv_id = _extract_conversation_id(original_body)
        await store.store(
            context.response_id,
            chat_request.get("messages", []),
            output_items,
            conversation_id=conv_id,
        )

        duration_ms = round((time.monotonic() - start) * 1000)
        item_types = [item.get("type", "unknown") for item in output_items]

        log.info(
            "stream_completed",
            response_id=context.response_id,
            output_count=len(output_items),
            output_types=item_types,
            chunk_count=chunk_count,
            duration_ms=duration_ms,
        )
        log.debug("conversation_stored", response_id=context.response_id, conversation_id=conv_id)

        auditor.set_output_types(item_types)

    except Exception as e:
        log.error("stream_error", error=str(e), exc_info=True)
        error_event = {
            "type": "response.error",
            "error": {"code": "stream_error", "message": str(e)},
            "sequence_number": stream_converter.next_sequence_number(),
        }
        yield format_sse_event("response.error", error_event)

        failed_event = {
            "type": "response.failed",
            "response": {
                "id": context.response_id,
                "object": "response",
                "status": "failed",
                "error": {"code": "stream_error", "message": str(e)},
            },
            "sequence_number": stream_converter.next_sequence_number(),
        }
        yield format_sse_event("response.failed", failed_event)


def _make_error_response(response_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "status": "failed",
        "error": {"code": code, "message": message},
        "output": [],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        },
    }


def _extract_conversation_id(body: dict[str, Any]) -> str | None:
    """Extract conversation_id from the conversation parameter."""
    conv_param = body.get("conversation")
    if conv_param is None:
        return None
    if isinstance(conv_param, str):
        return conv_param
    if isinstance(conv_param, dict):
        return conv_param.get("id")
    return None


async def _call_upstream_with_retry(
    upstream: Any,
    chat_request: dict[str, Any],
    context: Any,
    log: Any = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Call upstream with automatic message trimming on context overflow."""
    if log is None:
        log = logger

    for attempt in range(max_retries + 1):
        try:
            start = time.monotonic()
            result = await upstream.chat_completions(chat_request)
            duration_ms = round((time.monotonic() - start) * 1000)
            log.debug("upstream_call_completed", attempt=attempt, duration_ms=duration_ms)
            return result
        except httpx.HTTPStatusError as e:
            if context.truncation != "auto":
                raise
            if e.response.status_code != 400:
                raise

            # Check if it's a context length error
            try:
                error_body = e.response.json()
                error_msg = str(error_body.get("error", {})).lower()
            except Exception:
                error_msg = e.response.text.lower()

            context_keywords = ["context_length", "context length", "maximum context",
                                "token limit", "max_tokens", "too many tokens"]
            if not any(kw in error_msg for kw in context_keywords):
                raise

            # Trim messages from head (keep system messages)
            messages = chat_request.get("messages", [])
            if len(messages) <= 2:
                raise  # Can't trim further

            system_msgs = [m for m in messages if m.get("role") == "system"]
            non_system = [m for m in messages if m.get("role") != "system"]

            # Remove oldest non-system messages (trim 25%)
            trim_count = max(1, len(non_system) // 4)
            non_system = non_system[trim_count:]

            if not non_system:
                raise  # Nothing left after trimming

            chat_request["messages"] = system_msgs + non_system

            log.warning(
                "context_overflow_trimming",
                attempt=attempt,
                trimmed_count=trim_count,
                remaining_messages=len(system_msgs) + len(non_system),
            )
