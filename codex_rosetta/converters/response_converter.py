from __future__ import annotations

from typing import Any

from codex_rosetta.converters.content_transformer import ContentTransformer
from codex_rosetta.models.common import (
    ConversionContext,
    is_simulated_function,
    extract_original_type,
)
from codex_rosetta.utils.id_generation import generate_item_id, unix_timestamp


class ResponseConverter:
    """Convert Chat Completions responses to Responses API responses."""

    def __init__(self, content_transformer: ContentTransformer | None = None) -> None:
        self._ct = content_transformer or ContentTransformer()

    def convert(
        self,
        chat_response: dict[str, Any],
        context: ConversionContext,
    ) -> dict[str, Any]:
        """Convert a Chat Completions response to a Responses API response."""
        created_at = unix_timestamp()

        # Build output items
        output_items: list[dict[str, Any]] = []
        choices = chat_response.get("choices") or []

        for choice in choices:
            message = choice.get("message") or {}
            output_items.extend(
                self._convert_message_to_output_items(message, context)
            )

        # Convert usage
        usage = self._convert_usage(chat_response.get("usage"))

        # Inject null placeholders for requested include fields
        self._inject_include_placeholders(output_items, context)

        # Truncate tool calls if max_tool_calls is set
        self._truncate_tool_calls(output_items, context)

        response: dict[str, Any] = {
            "id": context.response_id,
            "object": "response",
            "created_at": created_at,
            "completed_at": unix_timestamp(),
            "model": context.model or chat_response.get("model", ""),
            "status": "completed",
            "output": output_items,
            "usage": usage,
        }

        # Carry over instructions if present
        if context.original_instructions:
            response["instructions"] = context.original_instructions

        # Carry over error if present
        error = chat_response.get("error")
        if error:
            response["error"] = error
            response["status"] = "failed"

        return response

    def _convert_message_to_output_items(
        self,
        message: dict[str, Any],
        context: ConversionContext,
    ) -> list[dict[str, Any]]:
        """Convert a Chat Completions assistant message to Responses API output items.

        A single assistant message with tool_calls becomes:
        - One "message" output item (with content)
        - Separate "function_call" output items for each tool call
        """
        items: list[dict[str, Any]] = []
        tool_calls = message.get("tool_calls") or []
        content = message.get("content")
        refusal = message.get("refusal")
        reasoning_content = message.get("reasoning_content")

        # Add reasoning item if present (GLM, DeepSeek, etc.)
        if reasoning_content:
            items.append({
                "type": "reasoning",
                "id": generate_item_id("reasoning"),
                "summary": [],
                "encrypted_content": None,
                "status": "completed",
            })

        # Build content parts for the message item
        content_parts: list[dict[str, Any]] = []

        if content:
            content_parts.extend(self._ct.chat_content_to_responses_output(content))

        if refusal:
            refusal_part = self._ct.refusal_to_responses(refusal)
            if refusal_part:
                content_parts.append(refusal_part)

        # Create the message output item (even if content is empty)
        msg_item: dict[str, Any] = {
            "type": "message",
            "id": generate_item_id("message"),
            "role": "assistant",
            "status": "completed",
            "content": content_parts,
        }
        items.append(msg_item)

        # Create function_call output items
        for tc in tool_calls:
            fc_item = self._convert_tool_call(tc, context)
            if fc_item is not None:
                items.append(fc_item)

        return items

    def _convert_tool_call(
        self,
        tool_call: dict[str, Any],
        context: ConversionContext,
    ) -> dict[str, Any] | None:
        """Convert a Chat Completions tool_call to a Responses API output item."""
        tc_type = tool_call.get("type", "function")
        tc_id = tool_call.get("id", "")
        call_id = tc_id  # Chat Completions uses id; Responses uses call_id

        if tc_type == "function":
            func = tool_call.get("function", {})
            name = func.get("name", "")
            arguments = func.get("arguments", "{}")

            # Check if this maps to a simulated built-in tool
            if is_simulated_function(name):
                return self._convert_simulated_builtin(name, arguments, call_id, context)

            return {
                "type": "function_call",
                "id": generate_item_id("function_call"),
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
                "status": "completed",
            }

        elif tc_type == "custom":
            custom = tool_call.get("custom", {})
            return {
                "type": "custom_tool_call",
                "id": generate_item_id("custom_tool_call"),
                "call_id": call_id,
                "name": custom.get("name", ""),
                "input": custom.get("input", ""),
                "status": "completed",
            }

        return None

    def _convert_simulated_builtin(
        self,
        function_name: str,
        arguments: str,
        call_id: str,
        context: ConversionContext,
    ) -> dict[str, Any]:
        """Convert a simulated built-in tool function call back to its native type."""
        import json

        original_type = extract_original_type(function_name)

        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            args = {}

        if original_type in ("web_search", "web_search_2025_08_26"):
            return {
                "type": "web_search_call",
                "id": generate_item_id("web_search"),
                "action": {
                    "type": "search",
                    "queries": [],
                    "sources": [],
                },
                "status": "completed",
            }

        elif original_type == "file_search":
            return {
                "type": "file_search_call",
                "id": generate_item_id("file_search"),
                "queries": [args.get("query", "")],
                "status": "completed",
            }

        elif original_type in ("computer_use_preview", "computer"):
            action = args.get("action", {})
            return {
                "type": "computer_call",
                "id": generate_item_id("computer_call"),
                "call_id": call_id,
                "action": action,
                "pending_safety_checks": [],
                "status": "completed",
            }

        elif original_type == "code_interpreter":
            return {
                "type": "code_interpreter_call",
                "id": generate_item_id("code_interpreter"),
                "code": args.get("code", ""),
                "container_id": None,
                "outputs": [],
                "status": "completed",
            }

        elif original_type == "image_generation":
            return {
                "type": "image_generation_call",
                "id": generate_item_id("image_generation"),
                "result": "",
                "status": "completed",
            }

        # Fallback: treat as regular function call
        return {
            "type": "function_call",
            "id": generate_item_id("function_call"),
            "call_id": call_id,
            "name": function_name,
            "arguments": arguments,
            "status": "completed",
        }

    def _convert_usage(
        self, usage: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Convert Chat Completions usage to Responses API usage."""
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

    def _inject_include_placeholders(
        self, output_items: list[dict[str, Any]], context: ConversionContext
    ) -> None:
        """Inject null placeholders for requested include fields."""
        if not context.include_fields:
            return

        for field in context.include_fields:
            if field == "reasoning.encrypted_content":
                # Add a reasoning item with null encrypted_content if not present
                has_reasoning = any(
                    item.get("type") == "reasoning" for item in output_items
                )
                if not has_reasoning:
                    output_items.append({
                        "type": "reasoning",
                        "id": generate_item_id("reasoning"),
                        "summary": [],
                        "encrypted_content": None,
                        "status": "completed",
                    })
                else:
                    for item in output_items:
                        if item.get("type") == "reasoning":
                            item.setdefault("encrypted_content", None)

            elif field == "message.output_text.logprobs":
                for item in output_items:
                    if item.get("type") == "message":
                        for part in item.get("content", []):
                            if part.get("type") == "output_text":
                                part.setdefault("logprobs", None)

    def _truncate_tool_calls(
        self, output_items: list[dict[str, Any]], context: ConversionContext
    ) -> None:
        """Truncate tool call output items when max_tool_calls limit is exceeded."""
        if context.max_tool_calls is None:
            return

        # Count tool-call-like items (function_call, web_search_call, etc.)
        tool_call_types = {
            "function_call", "web_search_call", "file_search_call",
            "computer_call", "code_interpreter_call", "image_generation_call",
            "custom_tool_call", "mcp_call",
        }
        tool_indices = [
            i for i, item in enumerate(output_items)
            if item.get("type") in tool_call_types
        ]

        if len(tool_indices) <= context.max_tool_calls:
            return

        # Remove excess tool call items (keep first max_tool_calls)
        excess_indices = set(tool_indices[context.max_tool_calls:])
        output_items[:] = [
            item for i, item in enumerate(output_items)
            if i not in excess_indices
        ]
