from __future__ import annotations

import asyncio
import json
import re
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
from codex_rosetta.models.common import is_simulated_function, extract_original_type, ROSETTA_TOOL_PREFIX
from codex_rosetta.search.base import SearchProvider
from codex_rosetta.search.formatter import format_search_results
from codex_rosetta.utils.logging import get_logger
from codex_rosetta.utils.sse import format_sse_event

logger = get_logger("router")

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _get_search_provider() -> SearchProvider | None:
    s = get_settings()
    if not s.WEB_SEARCH_ENABLED:
        return None

    provider = s.WEB_SEARCH_PROVIDER

    if provider == "tavily":
        if not s.WEB_SEARCH_API_KEY:
            return None
        from codex_rosetta.search.tavily_provider import TavilySearchProvider
        return TavilySearchProvider(api_key=s.WEB_SEARCH_API_KEY)

    if provider == "searxng":
        if not s.WEB_SEARCH_BASE_URL:
            return None
        from codex_rosetta.search.searxng_provider import SearXNGSearchProvider
        return SearXNGSearchProvider(base_url=s.WEB_SEARCH_BASE_URL, api_key=s.WEB_SEARCH_API_KEY)

    if provider == "brave":
        if not s.WEB_SEARCH_API_KEY:
            return None
        from codex_rosetta.search.brave_provider import BraveSearchProvider
        return BraveSearchProvider(api_key=s.WEB_SEARCH_API_KEY)

    if provider == "duckduckgo":
        from codex_rosetta.search.duckduckgo_provider import DuckDuckGoSearchProvider
        return DuckDuckGoSearchProvider(base_url=s.WEB_SEARCH_BASE_URL, api_key=s.WEB_SEARCH_API_KEY)

    if not s.WEB_SEARCH_BASE_URL:
        return None
    from codex_rosetta.search.http_provider import HttpSearchProvider
    return HttpSearchProvider(
        base_url=s.WEB_SEARCH_BASE_URL,
        api_key=s.WEB_SEARCH_API_KEY,
    )


@router.post("/v1/responses", response_model=None)
async def create_response(request: Request):
    request_id = getattr(request.state, "request_id", "unknown")
    log = logger.bind(request_id=request_id)

    body = await request.json()

    auditor = getattr(request.state, "auditor", NoOpAuditLogger())

    log.info(
        "request_received",
        model=body.get("model"),
        stream=body.get("stream", False),
        has_tools=bool(body.get("tools")),
        has_previous_response_id=bool(body.get("previous_response_id")),
        has_conversation=bool(body.get("conversation")),
        has_instructions=bool(body.get("instructions")),
    )

    upstream = get_upstream_client()
    store = get_conversation_store()
    request_converter = RequestConverter()

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

    chat_request, context = await request_converter.convert(body, conversation_messages, auditor=auditor)

    log.info(
        "request_converted",
        response_id=context.response_id,
        message_count=len(chat_request.get("messages", [])),
        has_tools=bool(chat_request.get("tools")),
        tool_count=len(chat_request.get("tools", [])),
    )

    if get_settings().LOG_UPSTREAM_REQUESTS:
        log.debug("upstream_request_body", body=chat_request)

    is_streaming = body.get("stream", False)
    search_provider = _get_search_provider()

    if is_streaming:
        return StreamingResponse(
            _stream_response(upstream, chat_request, context, store, body, log, auditor, search_provider),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            if search_provider:
                chat_response = await _search_loop_non_streaming(
                    upstream, chat_request, context, log, search_provider, auditor,
                )
            else:
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

        if get_settings().LOG_UPSTREAM_RESPONSES:
            log.debug("upstream_response_body", body=chat_response)

        response_converter = ResponseConverter()
        responses_response = response_converter.convert(chat_response, context)

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


def _extract_web_search_tool_calls(
    chat_response: dict[str, Any],
) -> list[dict[str, Any]]:
    choices = chat_response.get("choices") or []
    web_search_calls = []
    for choice in choices:
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        for tc in tool_calls:
            func = tc.get("function") or {}
            name = func.get("name", "")
            if _is_web_search_function_name(name):
                web_search_calls.append(tc)
    return web_search_calls


def _is_web_search_function_name(name: str) -> bool:
    return name in {
        f"{ROSETTA_TOOL_PREFIX}web_search",
        f"{ROSETTA_TOOL_PREFIX}web_search_2025_08_26",
    }


def _chat_request_has_web_search_tool(chat_request: dict[str, Any]) -> bool:
    tools = chat_request.get("tools") or []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        func = tool.get("function") or {}
        if _is_web_search_function_name(func.get("name", "")):
            return True
    return False


def _parse_search_query(tool_call: dict[str, Any]) -> str:
    func = tool_call.get("function") or {}
    arguments_str = func.get("arguments", "{}")
    try:
        arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
    except json.JSONDecodeError:
        arguments = {}
    return arguments.get("query", "")


def _inject_search_results(
    chat_request: dict[str, Any],
    chat_response: dict[str, Any],
    search_results_map: dict[str, str],
) -> dict[str, Any]:
    messages = list(chat_request.get("messages", []))

    choices = chat_response.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        assistant_msg = {"role": "assistant"}
        content = message.get("content")
        if content:
            assistant_msg["content"] = content
        tool_calls = message.get("tool_calls")
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        for tc in tool_calls or []:
            tc_id = tc.get("id", "")
            tc_result = search_results_map.get(tc_id, "搜索未返回结果。")
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tc_result,
            })

    new_request = dict(chat_request)
    new_request["messages"] = messages
    return new_request


async def _execute_searches(
    tool_calls: list[dict[str, Any]],
    search_provider: SearchProvider,
    max_results: int,
    log: Any,
    auditor: Any,
) -> dict[str, str]:
    results_map: dict[str, str] = {}
    for tc in tool_calls:
        query = _parse_search_query(tc)
        if not query:
            tc_id = tc.get("id", "")
            results_map[tc_id] = "搜索查询为空，无法执行搜索。"
            continue

        log.info("web_search_executing", query=query)
        search_response = await search_provider.search(query, max_results=max_results)
        formatted = format_search_results(search_response)
        tc_id = tc.get("id", "")
        results_map[tc_id] = formatted

        log.info("web_search_completed", query=query, result_count=len(search_response.results))
        auditor.record_output_event("web_search", {
            "query": query,
            "result_count": len(search_response.results),
        })

    return results_map


async def _search_loop_non_streaming(
    upstream: Any,
    chat_request: dict[str, Any],
    context: Any,
    log: Any,
    search_provider: SearchProvider,
    auditor: Any,
) -> dict[str, Any]:
    s = get_settings()
    max_rounds = s.WEB_SEARCH_MAX_ROUNDS
    max_results = s.WEB_SEARCH_MAX_RESULTS

    current_request = chat_request
    for round_num in range(max_rounds):
        chat_response = await _call_upstream_with_retry(upstream, current_request, context, log)

        web_search_calls = _extract_web_search_tool_calls(chat_response)
        if not web_search_calls:
            log.debug("search_loop_no_web_search_call", round=round_num)
            return chat_response

        log.info("search_loop_round", round=round_num + 1, search_calls=len(web_search_calls))

        search_results = await _execute_searches(
            web_search_calls, search_provider, max_results, log, auditor,
        )

        current_request = _inject_search_results(current_request, chat_response, search_results)

    log.warning("search_loop_max_rounds_reached", max_rounds=max_rounds)
    return await _call_upstream_with_retry(upstream, current_request, context, log)


def _reconstruct_response(chunks: list[bytes]) -> dict[str, Any]:
    combined = b"".join(chunks)
    lines = combined.decode("utf-8", errors="replace").split("\n")

    data_parts: list[str] = []
    for line in lines:
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload == "[DONE]":
                break
            data_parts.append(payload)

    if not data_parts:
        return {}

    choices: dict[int, dict[str, Any]] = {}
    model = ""
    usage = None

    for part in data_parts:
        try:
            chunk = json.loads(part)
        except json.JSONDecodeError:
            continue

        model = chunk.get("model", model)
        chunk_usage = chunk.get("usage")
        if chunk_usage:
            usage = chunk_usage

        for c in chunk.get("choices", []):
            idx = c.get("index", 0)
            if idx not in choices:
                choices[idx] = {
                    "message": {"role": "assistant", "content": "", "tool_calls": []},
                    "finish_reason": None,
                }

            delta = c.get("delta", {})

            content = delta.get("content")
            if content:
                choices[idx]["message"]["content"] += content

            tc_deltas = delta.get("tool_calls")
            if tc_deltas:
                for tc_delta in tc_deltas:
                    tc_index = tc_delta.get("index", 0)
                    while len(choices[idx]["message"]["tool_calls"]) <= tc_index:
                        choices[idx]["message"]["tool_calls"].append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        })
                    tc_entry = choices[idx]["message"]["tool_calls"][tc_index]

                    if tc_delta.get("id"):
                        tc_entry["id"] = tc_delta["id"]
                    func_delta = tc_delta.get("function", {})
                    if func_delta.get("name"):
                        tc_entry["function"]["name"] = func_delta["name"]
                    if func_delta.get("arguments"):
                        tc_entry["function"]["arguments"] += func_delta["arguments"]

            fr = c.get("finish_reason")
            if fr:
                choices[idx]["finish_reason"] = fr

    choices_list = []
    for idx in sorted(choices.keys()):
        ch = choices[idx]
        msg = ch["message"]
        if not msg.get("content") and not msg.get("tool_calls"):
            msg["content"] = None
        if not msg["tool_calls"]:
            del msg["tool_calls"]
        choices_list.append({"index": idx, "message": msg, "finish_reason": ch["finish_reason"]})

    result: dict[str, Any] = {
        "choices": choices_list,
        "model": model,
    }
    if usage:
        result["usage"] = usage

    return result


async def _consume_stream_full(
    upstream: Any,
    chat_request: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    full_chunks: list[bytes] = []
    async for raw_chunk in upstream.chat_completions_stream(chat_request):
        full_chunks.append(raw_chunk)
    return _reconstruct_response(full_chunks), len(full_chunks)


async def _prepare_search_stream_request(
    upstream: Any,
    chat_request: dict[str, Any],
    context: Any,
    log: Any,
    auditor: Any,
    search_provider: SearchProvider,
) -> tuple[list[bytes], dict[str, Any], int]:
    s = get_settings()
    max_rounds = s.WEB_SEARCH_MAX_ROUNDS
    max_results = s.WEB_SEARCH_MAX_RESULTS
    current_request = chat_request
    consumed_chunk_count = 0

    for round_num in range(max_rounds):
        if round_num == 0:
            log.info("search_loop_stream_first_round")
        else:
            log.info("search_loop_stream_round", round=round_num + 1)

        round_chunks: list[bytes] = []
        async for raw_chunk in upstream.chat_completions_stream(current_request):
            round_chunks.append(raw_chunk)
            auditor.record_upstream_chunk(raw_chunk)

        chat_response = _reconstruct_response(round_chunks)
        chunk_count = len(round_chunks)
        consumed_chunk_count += chunk_count

        web_search_calls = _extract_web_search_tool_calls(chat_response)
        if not web_search_calls:
            log.debug("search_loop_stream_final_round_ready", round=round_num + 1)
            return round_chunks, current_request, consumed_chunk_count

        log.info(
            "search_loop_stream_search_found",
            round=round_num + 1,
            search_calls=len(web_search_calls),
        )

        search_results = await _execute_searches(
            web_search_calls, search_provider, max_results, log, auditor,
        )
        current_request = _inject_search_results(current_request, chat_response, search_results)

    log.warning("search_loop_stream_max_rounds_reached", max_rounds=max_rounds)
    return [], current_request, consumed_chunk_count


async def _stream_response(
    upstream: Any,
    chat_request: dict[str, Any],
    context: Any,
    store: Any,
    original_body: dict[str, Any],
    log: Any,
    auditor: Any,
    search_provider: SearchProvider | None = None,
) -> Any:
    if not search_provider or not _chat_request_has_web_search_tool(chat_request):
        async for event in _stream_response_passthrough(
            upstream, chat_request, context, store, original_body, log, auditor,
        ):
            yield event
        return

    final_chunks, final_request, consumed_chunk_count = await _prepare_search_stream_request(
        upstream, chat_request, context, log, auditor, search_provider,
    )
    log.info(
        "search_loop_stream_visible_final_round",
        prepared_chunk_count=consumed_chunk_count,
    )

    if final_chunks:
        async for event in _replay_stream_chunks(
            final_chunks, final_request, context, store, original_body, log, auditor,
        ):
            yield event
        return

    async for event in _stream_response_passthrough(
        upstream, final_request, context, store, original_body, log, auditor,
    ):
        yield event


def _split_simulated_delta(text: str, max_chars: int) -> list[str]:
    if not text or len(text) <= max_chars:
        return [text]

    tokens = re.findall(r"\S+\s*", text)
    if not tokens:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    parts: list[str] = []
    current = ""
    for token in tokens:
        if len(token) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(token[i:i + max_chars] for i in range(0, len(token), max_chars))
            continue

        if current and len(current) + len(token) > max_chars:
            parts.append(current)
            current = token
        else:
            current += token

    if current:
        parts.append(current)

    if len(parts) == 1 and len(parts[0]) == len(text):
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    return parts


async def _yield_replayed_event(
    stream_converter: StreamConverter,
    event_type: str,
    event_data: dict[str, Any],
) -> Any:
    settings = get_settings()
    if (
        not settings.WEB_SEARCH_SIMULATED_STREAMING_ENABLED
        or event_type != "response.output_text.delta"
    ):
        yield format_sse_event(event_type, event_data)
        return

    pieces = _split_simulated_delta(
        event_data.get("delta", ""),
        max(1, settings.WEB_SEARCH_SIMULATED_STREAM_MAX_CHARS),
    )
    delay_seconds = max(0, settings.WEB_SEARCH_SIMULATED_STREAM_DELAY_MS) / 1000

    for index, piece in enumerate(pieces):
        chunk_event = dict(event_data)
        chunk_event["delta"] = piece
        if index > 0:
            chunk_event["sequence_number"] = stream_converter.next_sequence_number()
        yield format_sse_event(event_type, chunk_event)
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)


async def _replay_stream_chunks(
    raw_chunks: list[bytes],
    chat_request: dict[str, Any],
    context: Any,
    store: Any,
    original_body: dict[str, Any],
    log: Any,
    auditor: Any,
) -> Any:
    stream_converter = StreamConverter(context, auditor=auditor)

    log.info("stream_started", model=context.model, response_id=context.response_id)
    start = time.monotonic()
    chunk_count = 0

    try:
        for raw_chunk in raw_chunks:
            chunk_count += 1
            async for event_type, event_data in stream_converter.process_chunk(raw_chunk):
                if event_data is None:
                    continue
                if event_type:
                    async for replayed in _yield_replayed_event(
                        stream_converter, event_type, event_data,
                    ):
                        yield replayed

        async for event_type, event_data in stream_converter.flush_buffer():
            if event_data is None:
                continue
            if event_type:
                async for replayed in _yield_replayed_event(
                    stream_converter, event_type, event_data,
                ):
                    yield replayed

        async for event_type, event_data in stream_converter.finalize():
            yield format_sse_event(event_type, event_data)

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


async def _stream_response_passthrough(
    upstream: Any,
    chat_request: dict[str, Any],
    context: Any,
    store: Any,
    original_body: dict[str, Any],
    log: Any,
    auditor: Any,
) -> Any:
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

        async for event_type, event_data in stream_converter.flush_buffer():
            if event_data is None:
                continue
            if event_type:
                yield format_sse_event(event_type, event_data)

        async for event_type, event_data in stream_converter.finalize():
            yield format_sse_event(event_type, event_data)

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

            try:
                error_body = e.response.json()
                error_msg = str(error_body.get("error", {})).lower()
            except Exception:
                error_msg = e.response.text.lower()

            context_keywords = ["context_length", "context length", "maximum context",
                                "token limit", "max_tokens", "too many tokens"]
            if not any(kw in error_msg for kw in context_keywords):
                raise

            messages = chat_request.get("messages", [])
            if len(messages) <= 2:
                raise

            system_msgs = [m for m in messages if m.get("role") == "system"]
            non_system = [m for m in messages if m.get("role") != "system"]

            trim_count = max(1, len(non_system) // 4)
            non_system = non_system[trim_count:]

            if not non_system:
                raise

            chat_request["messages"] = system_msgs + non_system

            log.warning(
                "context_overflow_trimming",
                attempt=attempt,
                trimmed_count=trim_count,
                remaining_messages=len(system_msgs) + len(non_system),
            )
