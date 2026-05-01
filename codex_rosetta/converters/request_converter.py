from __future__ import annotations

from typing import Any

from codex_rosetta.converters.content_transformer import ContentTransformer
from codex_rosetta.converters.input_transformer import InputTransformer
from codex_rosetta.converters.tool_transformer import ToolTransformer
from codex_rosetta.models.common import ConversionContext, is_simulated_function
from codex_rosetta.utils.id_generation import generate_response_id


class RequestConverter:
    """Convert Responses API requests to Chat Completions requests."""

    def __init__(self, tool_transformer: ToolTransformer | None = None) -> None:
        self._ct = ContentTransformer()
        self._input_tf = InputTransformer(self._ct)
        self._tool_tf = tool_transformer or ToolTransformer()

    async def convert(
        self,
        responses_request: dict[str, Any],
        conversation_messages: list[dict[str, Any]] | None = None,
        auditor: Any = None,
    ) -> tuple[dict[str, Any], ConversionContext]:
        """Convert a Responses API request to a Chat Completions request.

        Returns:
            Tuple of (chat_completions_request_body, conversion_context)
        """
        context = ConversionContext(
            response_id=generate_response_id(),
            model=responses_request.get("model", ""),
            original_instructions=responses_request.get("instructions"),
        )

        chat_request: dict[str, Any] = {}

        # Model
        chat_request["model"] = responses_request.get("model", "")

        # Messages from input
        input_data = responses_request.get("input", "")
        instructions = responses_request.get("instructions")
        messages = self._input_tf.transform_input(input_data, instructions)

        # If previous_response_id provided, prepend stored conversation history
        if conversation_messages:
            # Insert stored messages before the new ones, but after system message
            system_msgs = [m for m in messages if m.get("role") == "system"]
            non_system_msgs = [m for m in messages if m.get("role") != "system"]
            messages = system_msgs + conversation_messages + non_system_msgs

        chat_request["messages"] = messages

        # Tools
        tools = responses_request.get("tools", [])
        if tools:
            chat_tools = self._tool_tf.convert_tools(tools, context)
            if chat_tools:
                chat_request["tools"] = chat_tools

        # Tool choice
        tool_choice = responses_request.get("tool_choice")
        if tool_choice is not None:
            chat_request["tool_choice"] = self._tool_tf.convert_tool_choice(
                tool_choice, context
            )

        # Parameter mappings
        self._map_parameters(responses_request, chat_request)

        # text.verbosity — append hint to system message
        text_config = responses_request.get("text")
        if text_config and isinstance(text_config, dict):
            verbosity = text_config.get("verbosity")
            if verbosity:
                self._apply_verbosity(messages, verbosity)

        # include — record for null placeholder injection in response
        include = responses_request.get("include")
        if include and isinstance(include, list):
            context.include_fields = include

        # max_tool_calls — record for truncation in response
        max_tool_calls = responses_request.get("max_tool_calls")
        if max_tool_calls is not None:
            context.max_tool_calls = max_tool_calls

        # truncation — record for retry-on-context-overflow
        truncation = responses_request.get("truncation")
        if truncation:
            context.truncation = truncation

        # Stream
        is_streaming = responses_request.get("stream", False)
        chat_request["stream"] = is_streaming
        context.had_streaming = is_streaming

        if is_streaming:
            stream_options = responses_request.get("stream_options")
            if stream_options:
                chat_request["stream_options"] = stream_options
            else:
                chat_request["stream_options"] = {"include_usage": True}

        # Text format -> response_format
        text_config = responses_request.get("text")
        if text_config and isinstance(text_config, dict):
            context.original_text_format = text_config
            fmt = text_config.get("format")
            if fmt:
                chat_request["response_format"] = fmt

        # Reasoning -> reasoning_effort
        reasoning = responses_request.get("reasoning")
        if reasoning and isinstance(reasoning, dict):
            effort = reasoning.get("effort")
            if effort:
                chat_request["reasoning_effort"] = effort

        # Pass-through fields
        for field in (
            "temperature",
            "top_p",
            "parallel_tool_calls",
            "seed",
            "stop",
            "service_tier",
            "store",
            "metadata",
            "user",
            "safety_identifier",
            "prompt_cache_key",
            "top_logprobs",
            "logprobs",
            "frequency_penalty",
            "presence_penalty",
        ):
            value = responses_request.get(field)
            if value is not None:
                chat_request[field] = value

        # Sanitize messages — fix broken tool_call arguments
        self._sanitize_messages(messages)

        # Audit: record converted request
        if auditor is not None:
            auditor.record_converted_request(chat_request)

        return chat_request, context

    def _map_parameters(
        self,
        responses_request: dict[str, Any],
        chat_request: dict[str, Any],
    ) -> None:
        """Map parameter names between APIs."""
        # max_output_tokens -> max_completion_tokens
        max_output = responses_request.get("max_output_tokens")
        if max_output is not None:
            chat_request["max_completion_tokens"] = max_output

    def _apply_verbosity(
        self, messages: list[dict[str, Any]], verbosity: str
    ) -> None:
        """Append a verbosity hint to the system message."""
        hints = {
            "low": "Be concise and brief in your responses.",
            "high": "Provide detailed and thorough responses.",
        }
        hint = hints.get(verbosity)
        if not hint:
            return

        # Append to existing system message, or create one
        for msg in messages:
            if msg.get("role") == "system" and isinstance(msg.get("content"), str):
                msg["content"] += f"\n{hint}"
                return

        messages.insert(0, {"role": "system", "content": hint})

    @staticmethod
    def _sanitize_messages(messages: list[dict[str, Any]]) -> None:
        """Fix broken tool_call arguments in messages to prevent upstream 400 errors.

        Some models (e.g. GLM) may generate malformed JSON in tool_call arguments.
        This breaks the upstream API contract. We attempt to repair truncated JSON
        or replace it with an empty object if unrepairable.
        """
        import json as _json

        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                continue

            for tc in tool_calls:
                func = tc.get("function")
                if not func:
                    continue
                args = func.get("arguments")
                if not args or not isinstance(args, str):
                    continue

                # Try parsing — if valid, skip
                try:
                    _json.loads(args)
                    continue
                except _json.JSONDecodeError:
                    pass

                # Attempt to repair truncated JSON
                repaired = RequestConverter._try_repair_json(args)
                func["arguments"] = repaired

    @staticmethod
    def _try_repair_json(raw: str) -> str:
        """Attempt to repair truncated/malformed JSON arguments.

        Common cases:
        - Truncated string: {"key": "value that got cut...
        - Truncated object: {"key": "value", "key2": "val...
        """
        import json as _json

        stripped = raw.strip()

        # Try closing open strings and objects
        attempts = []

        # Simple: just close all open structures
        repaired = stripped
        # Count unclosed quotes (outside of escaped ones)
        in_string = False
        escape = False
        for ch in stripped:
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string

        if in_string:
            repaired += '"'
        # Close open braces/brackets
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')
        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)

        attempts.append(repaired)

        # Also try empty object as fallback
        attempts.append('{}')

        for attempt in attempts:
            try:
                _json.loads(attempt)
                return attempt
            except _json.JSONDecodeError:
                continue

        return '{}'
