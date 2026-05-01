import pytest

from codex_rosetta.converters.response_converter import ResponseConverter
from codex_rosetta.converters.content_transformer import ContentTransformer
from codex_rosetta.models.common import ConversionContext, make_simulated_function_name


@pytest.fixture
def rc():
    return ResponseConverter(ContentTransformer())


@pytest.fixture
def ctx():
    return ConversionContext(response_id="resp_test123", model="gpt-4o")


class TestSimpleTextResponse:
    def test_simple_text(self, rc, ctx):
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello!"},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result = rc.convert(chat_resp, ctx)
        assert result["id"] == "resp_test123"
        assert result["object"] == "response"
        assert result["status"] == "completed"
        assert result["model"] == "gpt-4o"
        assert len(result["output"]) >= 1

        # Find message item
        msg_items = [o for o in result["output"] if o["type"] == "message"]
        assert len(msg_items) == 1
        assert msg_items[0]["role"] == "assistant"
        assert any(p.get("text") == "Hello!" for p in msg_items[0]["content"])


class TestToolCallResponse:
    def test_response_with_tool_calls(self, rc, ctx):
        chat_resp = {
            "id": "chatcmpl-xyz",
            "object": "chat.completion",
            "created": 1746000001,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "Let me check.",
                    "tool_calls": [{
                        "id": "call_abc",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"location":"SF"}'},
                    }],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        result = rc.convert(chat_resp, ctx)

        # Should have message item + function_call item
        msg_items = [o for o in result["output"] if o["type"] == "message"]
        fc_items = [o for o in result["output"] if o["type"] == "function_call"]
        assert len(msg_items) == 1
        assert len(fc_items) == 1

        fc = fc_items[0]
        assert fc["call_id"] == "call_abc"
        assert fc["name"] == "get_weather"
        assert fc["arguments"] == '{"location":"SF"}'
        assert fc["status"] == "completed"

    def test_parallel_tool_calls(self, rc, ctx):
        chat_resp = {
            "id": "chatcmpl-xyz",
            "object": "chat.completion",
            "created": 1746000001,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"SF"}'}},
                        {"id": "call_2", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"NYC"}'}},
                    ],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        result = rc.convert(chat_resp, ctx)
        fc_items = [o for o in result["output"] if o["type"] == "function_call"]
        assert len(fc_items) == 2
        assert fc_items[0]["call_id"] == "call_1"
        assert fc_items[1]["call_id"] == "call_2"


class TestBuiltinToolReverseMapping:
    def test_web_search_reverse_mapping(self, rc, ctx):
        sim_name = make_simulated_function_name("web_search")
        ctx.register_builtin_tool(sim_name, "web_search")

        chat_resp = {
            "id": "chatcmpl-xyz",
            "object": "chat.completion",
            "created": 1746000001,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_ws",
                        "type": "function",
                        "function": {"name": sim_name, "arguments": '{"search_context_size":"medium"}'},
                    }],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        result = rc.convert(chat_resp, ctx)

        # Should be converted to web_search_call, not function_call
        ws_items = [o for o in result["output"] if o["type"] == "web_search_call"]
        assert len(ws_items) == 1
        assert ws_items[0]["action"]["type"] == "search"
        assert "queries" in ws_items[0]["action"]
        assert "sources" in ws_items[0]["action"]

    def test_computer_use_reverse_mapping(self, rc, ctx):
        sim_name = make_simulated_function_name("computer_use_preview")
        ctx.register_builtin_tool(sim_name, "computer_use_preview")

        chat_resp = {
            "id": "chatcmpl-xyz",
            "object": "chat.completion",
            "created": 1746000001,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_cu",
                        "type": "function",
                        "function": {
                            "name": sim_name,
                            "arguments": '{"action":{"type":"click","x":100,"y":200}}',
                        },
                    }],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        result = rc.convert(chat_resp, ctx)
        cu_items = [o for o in result["output"] if o["type"] == "computer_call"]
        assert len(cu_items) == 1
        assert cu_items[0]["action"]["type"] == "click"


class TestUsageMapping:
    def test_usage_fields_renamed(self, rc, ctx):
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hi"},
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": {"cached_tokens": 30},
                "completion_tokens_details": {"reasoning_tokens": 10},
            },
        }
        result = rc.convert(chat_resp, ctx)
        usage = result["usage"]
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["total_tokens"] == 150
        assert usage["input_tokens_details"]["cached_tokens"] == 30
        assert usage["output_tokens_details"]["reasoning_tokens"] == 10

    def test_no_usage(self, rc, ctx):
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hi"},
            }],
        }
        result = rc.convert(chat_resp, ctx)
        assert result["usage"]["input_tokens"] == 0


class TestRefusal:
    def test_refusal_converted(self, rc, ctx):
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "refusal": "I cannot help with that.",
                },
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result = rc.convert(chat_resp, ctx)
        msg_items = [o for o in result["output"] if o["type"] == "message"]
        refusal_parts = [p for p in msg_items[0]["content"] if p.get("type") == "refusal"]
        assert len(refusal_parts) == 1
        assert refusal_parts[0]["refusal"] == "I cannot help with that."


class TestErrorResponse:
    def test_error_response(self, rc, ctx):
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "error": {"code": "server_error", "message": "Internal error"},
            "choices": [],
        }
        result = rc.convert(chat_resp, ctx)
        assert result["status"] == "failed"
        assert result["error"] is not None
