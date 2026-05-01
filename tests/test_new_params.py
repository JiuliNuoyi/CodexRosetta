import pytest

from codex_rosetta.converters.request_converter import RequestConverter
from codex_rosetta.converters.response_converter import ResponseConverter
from codex_rosetta.converters.content_transformer import ContentTransformer
from codex_rosetta.models.common import ConversionContext


class TestVerbosity:
    @pytest.mark.asyncio
    async def test_verbosity_low_appends_to_system(self):
        rc = RequestConverter()
        chat_req, ctx = await rc.convert({
            "model": "gpt-4o",
            "instructions": "You are helpful.",
            "input": "Hi",
            "text": {"verbosity": "low"},
        })
        system_msgs = [m for m in chat_req["messages"] if m.get("role") == "system"]
        assert len(system_msgs) == 1
        assert "concise" in system_msgs[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_verbosity_high_appends_to_system(self):
        rc = RequestConverter()
        chat_req, ctx = await rc.convert({
            "model": "gpt-4o",
            "instructions": "You are helpful.",
            "input": "Hi",
            "text": {"verbosity": "high"},
        })
        system_msgs = [m for m in chat_req["messages"] if m.get("role") == "system"]
        assert "detailed" in system_msgs[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_verbosity_medium_no_append(self):
        rc = RequestConverter()
        chat_req, ctx = await rc.convert({
            "model": "gpt-4o",
            "instructions": "You are helpful.",
            "input": "Hi",
            "text": {"verbosity": "medium"},
        })
        system_msgs = [m for m in chat_req["messages"] if m.get("role") == "system"]
        assert system_msgs[0]["content"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_verbosity_low_creates_system_if_none(self):
        rc = RequestConverter()
        chat_req, ctx = await rc.convert({
            "model": "gpt-4o",
            "input": "Hi",
            "text": {"verbosity": "low"},
        })
        system_msgs = [m for m in chat_req["messages"] if m.get("role") == "system"]
        assert len(system_msgs) == 1
        assert "concise" in system_msgs[0]["content"].lower()


class TestInclude:
    @pytest.mark.asyncio
    async def test_include_fields_recorded_in_context(self):
        rc = RequestConverter()
        _, ctx = await rc.convert({
            "model": "gpt-4o",
            "input": "Hi",
            "include": ["reasoning.encrypted_content", "message.output_text.logprobs"],
        })
        assert "reasoning.encrypted_content" in ctx.include_fields
        assert "message.output_text.logprobs" in ctx.include_fields

    def test_include_reasoning_placeholder_injected(self):
        rc = ResponseConverter(ContentTransformer())
        ctx = ConversionContext(
            response_id="resp_test",
            model="gpt-4o",
            include_fields=["reasoning.encrypted_content"],
        )
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello"},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result = rc.convert(chat_resp, ctx)
        reasoning_items = [o for o in result["output"] if o.get("type") == "reasoning"]
        assert len(reasoning_items) == 1
        assert reasoning_items[0]["encrypted_content"] is None

    def test_include_logprobs_placeholder_injected(self):
        rc = ResponseConverter(ContentTransformer())
        ctx = ConversionContext(
            response_id="resp_test",
            model="gpt-4o",
            include_fields=["message.output_text.logprobs"],
        )
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello"},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result = rc.convert(chat_resp, ctx)
        msg_items = [o for o in result["output"] if o.get("type") == "message"]
        text_parts = [p for p in msg_items[0]["content"] if p.get("type") == "output_text"]
        assert text_parts[0].get("logprobs") is None

    def test_no_include_fields_means_no_placeholders(self):
        rc = ResponseConverter(ContentTransformer())
        ctx = ConversionContext(response_id="resp_test", model="gpt-4o")
        chat_resp = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1746000000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello"},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result = rc.convert(chat_resp, ctx)
        reasoning_items = [o for o in result["output"] if o.get("type") == "reasoning"]
        assert len(reasoning_items) == 0


class TestMaxToolCalls:
    @pytest.mark.asyncio
    async def test_max_tool_calls_recorded_in_context(self):
        rc = RequestConverter()
        _, ctx = await rc.convert({
            "model": "gpt-4o",
            "input": "Hi",
            "max_tool_calls": 2,
        })
        assert ctx.max_tool_calls == 2

    def test_max_tool_calls_truncation(self):
        rc = ResponseConverter(ContentTransformer())
        ctx = ConversionContext(
            response_id="resp_test",
            model="gpt-4o",
            max_tool_calls=1,
        )
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
                        {"id": "call_1", "type": "function", "function": {"name": "func_a", "arguments": "{}"}},
                        {"id": "call_2", "type": "function", "function": {"name": "func_b", "arguments": "{}"}},
                        {"id": "call_3", "type": "function", "function": {"name": "func_c", "arguments": "{}"}},
                    ],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        result = rc.convert(chat_resp, ctx)
        fc_items = [o for o in result["output"] if o.get("type") == "function_call"]
        assert len(fc_items) == 1
        assert fc_items[0]["call_id"] == "call_1"

    def test_max_tool_calls_no_truncation_when_under_limit(self):
        rc = ResponseConverter(ContentTransformer())
        ctx = ConversionContext(
            response_id="resp_test",
            model="gpt-4o",
            max_tool_calls=5,
        )
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
                        {"id": "call_1", "type": "function", "function": {"name": "func_a", "arguments": "{}"}},
                    ],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        result = rc.convert(chat_resp, ctx)
        fc_items = [o for o in result["output"] if o.get("type") == "function_call"]
        assert len(fc_items) == 1

    def test_max_tool_calls_none_means_no_limit(self):
        rc = ResponseConverter(ContentTransformer())
        ctx = ConversionContext(
            response_id="resp_test",
            model="gpt-4o",
            max_tool_calls=None,
        )
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
                        {"id": "call_1", "type": "function", "function": {"name": "func_a", "arguments": "{}"}},
                        {"id": "call_2", "type": "function", "function": {"name": "func_b", "arguments": "{}"}},
                    ],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        result = rc.convert(chat_resp, ctx)
        fc_items = [o for o in result["output"] if o.get("type") == "function_call"]
        assert len(fc_items) == 2


class TestTruncation:
    @pytest.mark.asyncio
    async def test_truncation_recorded_in_context(self):
        rc = RequestConverter()
        _, ctx = await rc.convert({
            "model": "gpt-4o",
            "input": "Hi",
            "truncation": "auto",
        })
        assert ctx.truncation == "auto"


class TestConversation:
    @pytest.mark.asyncio
    async def test_conversation_id_resolves_messages(self):
        from codex_rosetta.state.conversation_store import InMemoryConversationStore

        store = InMemoryConversationStore()
        # Store a response with a conversation_id
        await store.store(
            "resp_1",
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there"}],
            [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Hi there", "annotations": []}]}],
            conversation_id="conv_abc",
        )

        # Retrieve by conversation_id
        messages = await store.retrieve_by_conversation_id("conv_abc")
        assert messages is not None
        assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_conversation_id_not_found(self):
        from codex_rosetta.state.conversation_store import InMemoryConversationStore

        store = InMemoryConversationStore()
        messages = await store.retrieve_by_conversation_id("conv_nonexistent")
        assert messages is None

    @pytest.mark.asyncio
    async def test_link_conversation(self):
        from codex_rosetta.state.conversation_store import InMemoryConversationStore

        store = InMemoryConversationStore()
        await store.store("resp_1", [{"role": "user", "content": "Hi"}], [])
        await store.link_conversation("conv_xyz", "resp_1")

        messages = await store.retrieve_by_conversation_id("conv_xyz")
        assert messages is not None
