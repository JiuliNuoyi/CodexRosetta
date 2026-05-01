from __future__ import annotations

import json
from typing import Any, AsyncIterator

from codex_rosetta.builtin_tools.registry import BuiltinToolRegistry, create_default_registry
from codex_rosetta.converters.content_transformer import ContentTransformer
from codex_rosetta.models.common import ConversionContext, extract_original_type, is_simulated_function
from codex_rosetta.state.stream_state import OutputItemState, StreamState
from codex_rosetta.utils.id_generation import generate_item_id, unix_timestamp
from codex_rosetta.utils.sse import parse_sse_lines


def _build_reasoning_summary(text: str) -> list[dict[str, str]]:
    """Build a reasoning summary list from accumulated reasoning text."""
    if not text:
        return []
    return [{"type": "summary_text", "text": text}]


class StreamConverter:
    """State machine that converts Chat Completions SSE chunks into Responses API SSE events."""

    def __init__(
        self,
        context: ConversionContext,
        builtin_registry: BuiltinToolRegistry | None = None,
        auditor: Any = None,
    ) -> None:
        self._context = context
        self._ct = ContentTransformer()
        self._registry = builtin_registry or create_default_registry()
        self._auditor = auditor
        self._state = StreamState(
            response_id=context.response_id,
            model=context.model,
            created_at=unix_timestamp(),
        )
        self._sse_buffer: str = ""

    @property
    def finish_reason(self) -> str | None:
        return self._state.finish_reason

    def _record(self, event_type: str, event_data: dict[str, Any]) -> None:
        if self._auditor is not None:
            self._auditor.record_output_event(event_type, event_data)

    @property
    def current_output_items(self) -> list[dict[str, Any]]:
        """Return the current output items as dicts (for conversation store)."""
        is_incomplete = self._state.finish_reason == "length"
        items: list[dict[str, Any]] = []
        for item in self._state.output_items:
            if item.item_type == "message":
                item_status = "incomplete" if is_incomplete else "completed"
                msg: dict[str, Any] = {
                    "type": "message",
                    "id": item.item_id,
                    "role": "assistant",
                    "status": item_status,
                    "content": [{"type": "output_text", "text": item.accumulated_text, "annotations": []}],
                }
                if is_incomplete:
                    msg["incomplete_details"] = {"reason": "max_output_tokens"}
                items.append(msg)
            elif item.item_type == "reasoning":
                summary = _build_reasoning_summary(item.accumulated_text)
                items.append({
                    "type": "reasoning",
                    "id": item.item_id,
                    "summary": summary,
                    "encrypted_content": None,
                    "status": "completed",
                })
            elif item.item_type == "function_call":
                fc: dict[str, Any] = {
                    "type": "function_call",
                    "id": item.item_id,
                    "call_id": item.call_id,
                    "name": item.function_name,
                    "arguments": item.accumulated_arguments,
                    "status": "completed",
                }
                # Check for built-in tool reverse mapping
                if item.function_name and is_simulated_function(item.function_name):
                    original_type = extract_original_type(item.function_name)
                    try:
                        args = json.loads(item.accumulated_arguments) if item.accumulated_arguments else {}
                    except json.JSONDecodeError:
                        args = {}
                    sim = self._registry.get_simulator(original_type)
                    if sim:
                        fc = sim.convert_to_builtin_output(fc, args)
                items.append(fc)
        return items

    def next_sequence_number(self) -> int:
        return self._state.next_sequence_number()

    async def process_chunk(
        self, raw_chunk: bytes | str
    ) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
        """Process a raw SSE chunk from upstream, yielding (event_type, event_data) tuples.

        On the first chunk, emits response.created and response.in_progress events.
        Uses a buffer to handle SSE events split across chunk boundaries.
        """
        # Emit lifecycle start events on first real data
        if not self._state.has_emitted_created:
            self._state.has_emitted_created = True
            created_evt = self._build_lifecycle_event("response.created", "queued")
            self._record("response.created", created_evt)
            yield "response.created", created_evt
            self._state.has_emitted_in_progress = True
            in_progress_evt = self._build_lifecycle_event("response.in_progress", "in_progress")
            self._record("response.in_progress", in_progress_evt)
            yield "response.in_progress", in_progress_evt

        if isinstance(raw_chunk, bytes):
            raw_chunk = raw_chunk.decode("utf-8", errors="replace")

        self._sse_buffer += raw_chunk

        while "\n\n" in self._sse_buffer:
            event_block, self._sse_buffer = self._sse_buffer.split("\n\n", 1)
            events = parse_sse_lines(event_block + "\n\n")
            for event_type, data in events:
                if data is None:
                    continue
                async for evt in self._process_sse_event(data):
                    yield evt

    async def flush_buffer(self) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
        """Process any remaining data in the SSE buffer after the stream ends."""
        if self._sse_buffer.strip():
            events = parse_sse_lines(self._sse_buffer)
            self._sse_buffer = ""
            for event_type, data in events:
                if data is None:
                    continue
                async for evt in self._process_sse_event(data):
                    yield evt

    async def _process_sse_event(
        self, data: dict[str, Any]
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Process a single parsed SSE data object."""
        choices = data.get("choices") or []
        usage = data.get("usage")

        if usage:
            self._state.usage = usage

        for choice in choices:
            delta = choice.get("delta") or {}
            finish_reason = choice.get("finish_reason")

            # Text content delta
            if "content" in delta and delta["content"] is not None:
                async for evt in self._handle_text_delta(delta["content"]):
                    yield evt

            # Reasoning content delta (GLM, DeepSeek, etc.)
            if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                async for evt in self._handle_reasoning_delta(delta["reasoning_content"]):
                    yield evt

            # Tool calls delta
            if "tool_calls" in delta and delta["tool_calls"] is not None:
                for tc_delta in delta["tool_calls"]:
                    async for evt in self._handle_tool_call_delta(tc_delta):
                        yield evt

            # Refusal delta
            if "refusal" in delta and delta["refusal"]:
                async for evt in self._handle_refusal_delta(delta["refusal"]):
                    yield evt

            if finish_reason:
                self._state.finish_reason = finish_reason
                if self._auditor is not None:
                    self._auditor.set_finish_reason(finish_reason)

    async def _handle_text_delta(
        self, text: str
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Handle a text content delta, emitting appropriate Responses events."""
        msg_item = self._state.get_current_message_item()

        if msg_item is None:
            item_id = generate_item_id("message")
            msg_item = self._state.create_message_item(item_id)

        if not msg_item.has_item_added:
            msg_item.has_item_added = True
            yield "response.output_item.added", {
                "type": "response.output_item.added",
                "output_index": msg_item.output_index,
                "item": {
                    "type": "message",
                    "id": msg_item.item_id,
                    "role": "assistant",
                    "status": "in_progress",
                    "content": [],
                },
                "sequence_number": self._state.next_sequence_number(),
            }

        if not msg_item.has_content_part_added:
            msg_item.has_content_part_added = True
            yield "response.content_part.added", {
                "type": "response.content_part.added",
                "output_index": msg_item.output_index,
                "content_index": 0,
                "item_id": msg_item.item_id,
                "part": {"type": "output_text", "text": "", "annotations": []},
                "sequence_number": self._state.next_sequence_number(),
            }

        text_delta = {
            "type": "response.output_text.delta",
            "output_index": msg_item.output_index,
            "content_index": 0,
            "item_id": msg_item.item_id,
            "delta": text,
            "sequence_number": self._state.next_sequence_number(),
        }
        self._record("response.output_text.delta", text_delta)
        yield "response.output_text.delta", text_delta

        msg_item.accumulated_text += text

    async def _handle_reasoning_delta(
        self, reasoning_text: str
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Handle a reasoning_content delta, mapping to Responses API reasoning item."""
        reasoning_item = self._state.get_current_reasoning_item()

        if reasoning_item is None:
            item_id = generate_item_id("reasoning")
            reasoning_item = self._state.create_reasoning_item(item_id)

        if not reasoning_item.has_item_added:
            reasoning_item.has_item_added = True
            yield "response.output_item.added", {
                "type": "response.output_item.added",
                "output_index": reasoning_item.output_index,
                "item": {
                    "type": "reasoning",
                    "id": reasoning_item.item_id,
                    "summary": [],
                    "encrypted_content": None,
                    "status": "in_progress",
                },
                "sequence_number": self._state.next_sequence_number(),
            }

        reasoning_delta = {
            "type": "response.reasoning.delta",
            "output_index": reasoning_item.output_index,
            "item_id": reasoning_item.item_id,
            "delta": reasoning_text,
            "sequence_number": self._state.next_sequence_number(),
        }
        self._record("response.reasoning.delta", reasoning_delta)
        yield "response.reasoning.delta", reasoning_delta

        reasoning_item.accumulated_text += reasoning_text

    async def _handle_tool_call_delta(
        self, tc_delta: dict[str, Any]
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Handle a tool_call delta, emitting appropriate Responses events."""
        tc_index = tc_delta.get("index", 0)

        if tc_index not in self._state.tool_call_index_map:
            # New tool call starting
            call_id = tc_delta.get("id", f"call_{tc_index}")
            func_info = tc_delta.get("function") or {}
            func_name = func_info.get("name", "")

            item_id = generate_item_id("function_call")
            fc_item = self._state.create_function_call_item(item_id, call_id, func_name)
            self._state.tool_call_index_map[tc_index] = fc_item

            # Check for built-in tool mapping
            if func_name and is_simulated_function(func_name):
                original_type = extract_original_type(func_name)
                fc_item.original_tool_type = original_type
                sim = self._registry.get_simulator(original_type)
                if sim:
                    # Will emit lifecycle events after we have arguments
                    pass

            yield "response.output_item.added", {
                "type": "response.output_item.added",
                "output_index": fc_item.output_index,
                "item": {
                    "type": "function_call",
                    "id": fc_item.item_id,
                    "call_id": call_id,
                    "name": func_name,
                    "arguments": "",
                    "status": "in_progress",
                },
                "sequence_number": self._state.next_sequence_number(),
            }

        fc_item = self._state.tool_call_index_map[tc_index]

        # Arguments delta
        func_info = tc_delta.get("function") or {}
        args_delta = func_info.get("arguments", "")
        if args_delta:
            # Emit built-in tool lifecycle events on first argument delta
            if fc_item.original_tool_type and not fc_item.has_emitted_lifecycle:
                fc_item.has_emitted_lifecycle = True
                sim = self._registry.get_simulator(fc_item.original_tool_type)
                if sim:
                    try:
                        args = json.loads(fc_item.accumulated_arguments + args_delta) if (fc_item.accumulated_arguments + args_delta) else {}
                    except json.JSONDecodeError:
                        args = {}
                    lifecycle_events = sim.generate_streaming_lifecycle_events(
                        fc_item.item_id, fc_item.call_id or "", fc_item.output_index, args
                    )
                    for evt in lifecycle_events:
                        yield evt["type"], {
                            **evt["data"],
                            "sequence_number": self._state.next_sequence_number(),
                        }

            args_event = {
                "type": "response.function_call_arguments.delta",
                "output_index": fc_item.output_index,
                "item_id": fc_item.item_id,
                "delta": args_delta,
                "sequence_number": self._state.next_sequence_number(),
            }
            self._record("response.function_call_arguments.delta", args_event)
            yield "response.function_call_arguments.delta", args_event
            fc_item.accumulated_arguments += args_delta

    async def _handle_refusal_delta(
        self, refusal: str
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Handle a refusal delta."""
        # Ensure we have a message item
        msg_item = self._state.ensure_message_item(generate_item_id("message"))

        if not msg_item.has_item_added:
            msg_item.has_item_added = True
            yield "response.output_item.added", {
                "type": "response.output_item.added",
                "output_index": msg_item.output_index,
                "item": {
                    "type": "message",
                    "id": msg_item.item_id,
                    "role": "assistant",
                    "status": "in_progress",
                    "content": [],
                },
                "sequence_number": self._state.next_sequence_number(),
            }

        yield "response.refusal.delta", {
            "type": "response.refusal.delta",
            "output_index": msg_item.output_index,
            "item_id": msg_item.item_id,
            "delta": refusal,
            "sequence_number": self._state.next_sequence_number(),
        }

    async def finalize(self) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Emit finalization events for all open items and the completed response."""
        for item in self._state.output_items:
            if item.is_closed:
                continue

            if item.item_type == "message":
                async for evt in self._finalize_message_item(item):
                    yield evt

            elif item.item_type == "reasoning":
                async for evt in self._finalize_reasoning_item(item):
                    yield evt

            elif item.item_type == "function_call":
                async for evt in self._finalize_function_call_item(item):
                    yield evt

            item.is_closed = True

        # Build and emit response.completed
        completed_at = unix_timestamp()
        full_response = self._build_full_response(completed_at)

        completed_evt = {
            "type": "response.completed",
            "response": full_response,
            "sequence_number": self._state.next_sequence_number(),
        }
        self._record("response.completed", completed_evt)
        yield "response.completed", completed_evt

    async def _finalize_message_item(
        self, item: OutputItemState
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Emit done events for a message output item."""
        if item.has_content_part_added:
            yield "response.output_text.done", {
                "type": "response.output_text.done",
                "output_index": item.output_index,
                "content_index": 0,
                "item_id": item.item_id,
                "text": item.accumulated_text,
                "sequence_number": self._state.next_sequence_number(),
            }

            yield "response.content_part.done", {
                "type": "response.content_part.done",
                "output_index": item.output_index,
                "content_index": 0,
                "item_id": item.item_id,
                "part": {
                    "type": "output_text",
                    "text": item.accumulated_text,
                    "annotations": [],
                },
                "sequence_number": self._state.next_sequence_number(),
            }

        if item.has_item_added:
            is_incomplete = self._state.finish_reason == "length"
            item_status = "incomplete" if is_incomplete else "completed"
            item_data: dict[str, Any] = {
                "type": "message",
                "id": item.item_id,
                "role": "assistant",
                "status": item_status,
                "content": [
                    {"type": "output_text", "text": item.accumulated_text, "annotations": []}
                ],
            }
            if is_incomplete:
                item_data["incomplete_details"] = {"reason": "max_output_tokens"}
            yield "response.output_item.done", {
                "type": "response.output_item.done",
                "output_index": item.output_index,
                "item": item_data,
                "sequence_number": self._state.next_sequence_number(),
            }

    async def _finalize_reasoning_item(
        self, item: OutputItemState
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Emit done events for a reasoning output item."""
        if item.has_item_added:
            summary = _build_reasoning_summary(item.accumulated_text)
            yield "response.output_item.done", {
                "type": "response.output_item.done",
                "output_index": item.output_index,
                "item": {
                    "type": "reasoning",
                    "id": item.item_id,
                    "summary": summary,
                    "encrypted_content": None,
                    "status": "completed",
                },
                "sequence_number": self._state.next_sequence_number(),
            }

    async def _finalize_function_call_item(
        self, item: OutputItemState
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Emit done events for a function_call output item."""
        yield "response.function_call_arguments.done", {
            "type": "response.function_call_arguments.done",
            "output_index": item.output_index,
            "item_id": item.item_id,
            "name": item.function_name,
            "arguments": item.accumulated_arguments,
            "sequence_number": self._state.next_sequence_number(),
        }

        # Build final item dict
        final_item: dict[str, Any] = {
            "type": "function_call",
            "id": item.item_id,
            "call_id": item.call_id,
            "name": item.function_name,
            "arguments": item.accumulated_arguments,
            "status": "completed",
        }

        # Check for built-in tool reverse mapping
        if item.function_name and is_simulated_function(item.function_name):
            original_type = extract_original_type(item.function_name)
            try:
                args = json.loads(item.accumulated_arguments) if item.accumulated_arguments else {}
            except json.JSONDecodeError:
                args = {}

            sim = self._registry.get_simulator(original_type)
            if sim:
                # Emit built-in tool completion events
                completion_events = sim.generate_completion_events(
                    item.item_id, item.call_id or "", item.output_index, args
                )
                for evt in completion_events:
                    yield evt["type"], {
                        **evt["data"],
                        "sequence_number": self._state.next_sequence_number(),
                    }

                final_item = sim.convert_to_builtin_output(final_item, args)

        yield "response.output_item.done", {
            "type": "response.output_item.done",
            "output_index": item.output_index,
            "item": final_item,
            "sequence_number": self._state.next_sequence_number(),
        }

    def _build_lifecycle_event(self, event_type: str, status: str) -> dict[str, Any]:
        """Build a response lifecycle event (created, in_progress)."""
        return {
            "type": event_type,
            "response": {
                "id": self._state.response_id,
                "object": "response",
                "created_at": self._state.created_at,
                "model": self._state.model,
                "status": status,
                "output": [],
                "instructions": self._context.original_instructions,
            },
            "sequence_number": self._state.next_sequence_number(),
        }

    def _build_full_response(self, completed_at: float) -> dict[str, Any]:
        """Build the full Response object for the completed event."""
        output: list[dict[str, Any]] = []
        for item in self._state.output_items:
            if item.item_type == "message":
                output.append({
                    "type": "message",
                    "id": item.item_id,
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": item.accumulated_text, "annotations": []}
                    ],
                })
            elif item.item_type == "reasoning":
                summary = _build_reasoning_summary(item.accumulated_text)
                output.append({
                    "type": "reasoning",
                    "id": item.item_id,
                    "summary": summary,
                    "encrypted_content": None,
                    "status": "completed",
                })
            elif item.item_type == "function_call":
                fc: dict[str, Any] = {
                    "type": "function_call",
                    "id": item.item_id,
                    "call_id": item.call_id,
                    "name": item.function_name,
                    "arguments": item.accumulated_arguments,
                    "status": "completed",
                }
                # Built-in tool reverse mapping
                if item.function_name and is_simulated_function(item.function_name):
                    original_type = extract_original_type(item.function_name)
                    try:
                        args = json.loads(item.accumulated_arguments) if item.accumulated_arguments else {}
                    except json.JSONDecodeError:
                        args = {}
                    sim = self._registry.get_simulator(original_type)
                    if sim:
                        fc = sim.convert_to_builtin_output(fc, args)
                output.append(fc)

        usage = self._convert_usage()

        # Map upstream finish_reason to Responses API status
        is_incomplete = self._state.finish_reason == "length"
        status = "incomplete" if is_incomplete else "completed"

        response: dict[str, Any] = {
            "id": self._state.response_id,
            "object": "response",
            "created_at": self._state.created_at,
            "completed_at": completed_at,
            "model": self._state.model,
            "status": status,
            "output": output,
            "usage": usage,
            "instructions": self._context.original_instructions,
        }

        if is_incomplete:
            response["incomplete_details"] = {"reason": "max_output_tokens"}

        return response

    def _convert_usage(self) -> dict[str, Any]:
        """Convert Chat Completions usage to Responses API usage."""
        usage = self._state.usage
        if usage is None:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            }

        prompt_details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}

        return {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "input_tokens_details": {
                "cached_tokens": prompt_details.get("cached_tokens", 0),
            },
            "output_tokens_details": {
                "reasoning_tokens": completion_details.get("reasoning_tokens", 0),
            },
        }
