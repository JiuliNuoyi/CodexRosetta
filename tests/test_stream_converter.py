import json
import pytest

from codex_rosetta.converters.stream_converter import StreamConverter
from codex_rosetta.models.common import ConversionContext, make_simulated_function_name


@pytest.fixture
def ctx():
    return ConversionContext(response_id="resp_stream_test", model="gpt-4o")


def make_chunk(delta: dict, finish_reason=None, usage=None):
    """Helper to create a Chat Completions SSE chunk."""
    chunk = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1746000000,
        "model": "gpt-4o",
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }
    if usage:
        chunk["usage"] = usage
    return f"data: {json.dumps(chunk)}\n\n"


DONE_SENTINEL = "data: [DONE]\n\n"


class TestTextOnlyStreaming:
    @pytest.mark.asyncio
    async def test_text_stream_lifecycle(self, ctx):
        sc = StreamConverter(ctx)
        events = []

        # First chunk with role
        async for evt in sc.process_chunk(
            f'data: {json.dumps({"id":"chatcmpl-test","object":"chat.completion.chunk","created":1746000000,"model":"gpt-4o","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":None}]})}\n\n'
        ):
            events.append(evt)

        # Text delta chunks
        async for evt in sc.process_chunk(make_chunk({"content": "Hello"})):
            events.append(evt)
        async for evt in sc.process_chunk(make_chunk({"content": " world"})):
            events.append(evt)

        # Finalize
        async for evt in sc.finalize():
            events.append(evt)

        event_types = [e[0] for e in events]
        assert "response.created" in event_types
        assert "response.in_progress" in event_types
        assert "response.output_item.added" in event_types
        assert "response.content_part.added" in event_types
        assert "response.output_text.delta" in event_types
        assert "response.output_text.done" in event_types
        assert "response.content_part.done" in event_types
        assert "response.output_item.done" in event_types
        assert "response.completed" in event_types

        # Check delta content (first chunk has empty content "")
        deltas = [e[1] for e in events if e[0] == "response.output_text.delta"]
        assert len(deltas) == 3
        assert deltas[0]["delta"] == ""
        assert deltas[1]["delta"] == "Hello"
        assert deltas[2]["delta"] == " world"

        # Check done text is accumulated
        done_events = [e[1] for e in events if e[0] == "response.output_text.done"]
        assert done_events[0]["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_sequence_numbers_monotonic(self, ctx):
        sc = StreamConverter(ctx)
        events = []

        async for evt in sc.process_chunk(make_chunk({"content": "Hi"})):
            events.append(evt)
        async for evt in sc.finalize():
            events.append(evt)

        seq_nums = [e[1].get("sequence_number", 0) for e in events if e[1]]
        assert seq_nums == sorted(seq_nums)  # monotonically increasing
        assert len(seq_nums) == len(set(seq_nums))  # unique


class TestToolCallStreaming:
    @pytest.mark.asyncio
    async def test_tool_call_stream(self, ctx):
        sc = StreamConverter(ctx)
        events = []

        # Tool call start
        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 0,
                "id": "call_abc",
                "type": "function",
                "function": {"name": "get_weather", "arguments": ""},
            }]
        })):
            events.append(evt)

        # Arguments delta
        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 0,
                "function": {"arguments": '{"location":"SF"}'},
            }]
        })):
            events.append(evt)

        # Finalize
        async for evt in sc.finalize():
            events.append(evt)

        event_types = [e[0] for e in events]
        assert "response.output_item.added" in event_types
        assert "response.function_call_arguments.delta" in event_types
        assert "response.function_call_arguments.done" in event_types
        assert "response.output_item.done" in event_types

        # Check function call item
        added_events = [e[1] for e in events if e[0] == "response.output_item.added"]
        fc_added = [e for e in added_events if e.get("item", {}).get("type") == "function_call"]
        assert len(fc_added) == 1
        assert fc_added[0]["item"]["call_id"] == "call_abc"
        assert fc_added[0]["item"]["name"] == "get_weather"

        # Check arguments done
        args_done = [e[1] for e in events if e[0] == "response.function_call_arguments.done"]
        assert args_done[0]["arguments"] == '{"location":"SF"}'

    @pytest.mark.asyncio
    async def test_parallel_tool_calls_stream(self, ctx):
        sc = StreamConverter(ctx)
        events = []

        # First tool call
        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 0,
                "id": "call_1",
                "type": "function",
                "function": {"name": "func_a", "arguments": ""},
            }]
        })):
            events.append(evt)

        # Second tool call
        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 1,
                "id": "call_2",
                "type": "function",
                "function": {"name": "func_b", "arguments": ""},
            }]
        })):
            events.append(evt)

        # Finalize
        async for evt in sc.finalize():
            events.append(evt)

        fc_items = [e[1] for e in events if e[0] == "response.output_item.added"
                     and isinstance(e[1], dict) and e[1].get("item", {}).get("type") == "function_call"]
        assert len(fc_items) == 2


class TestDoneSentinel:
    @pytest.mark.asyncio
    async def test_done_sentinel_ignored(self, ctx):
        sc = StreamConverter(ctx)
        events = []

        async for evt in sc.process_chunk(DONE_SENTINEL):
            events.append(evt)

        async for evt in sc.finalize():
            events.append(evt)

        # Should still get created/in_progress/completed events
        event_types = [e[0] for e in events]
        assert "response.created" in event_types
        assert "response.completed" in event_types


class TestUsageInStream:
    @pytest.mark.asyncio
    async def test_usage_in_final_chunk(self, ctx):
        sc = StreamConverter(ctx)
        events = []

        async for evt in sc.process_chunk(make_chunk({"content": "Hi"})):
            events.append(evt)

        # Usage chunk (Chat Completions sends this before [DONE] when include_usage=True)
        async for evt in sc.process_chunk(
            f'data: {json.dumps({"id":"chatcmpl-test","object":"chat.completion.chunk","created":1746000000,"model":"gpt-4o","choices":[],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}})}\n\n'
        ):
            events.append(evt)

        async for evt in sc.finalize():
            events.append(evt)

        completed_events = [e[1] for e in events if e[0] == "response.completed"]
        assert len(completed_events) == 1
        usage = completed_events[0]["response"]["usage"]
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 5
        assert usage["total_tokens"] == 15


class TestBuiltinToolReverseMapping:
    @pytest.mark.asyncio
    async def test_web_search_reverse_in_stream(self, ctx):
        sim_name = make_simulated_function_name("web_search")
        ctx.register_builtin_tool(sim_name, "web_search")

        sc = StreamConverter(ctx)
        events = []

        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 0,
                "id": "call_ws",
                "type": "function",
                "function": {"name": sim_name, "arguments": ""},
            }]
        })):
            events.append(evt)

        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 0,
                "function": {"arguments": '{"query":"AI news"}'},
            }]
        })):
            events.append(evt)

        async for evt in sc.finalize():
            events.append(evt)

        # Check that the final output item is a web_search_call, not function_call
        done_events = [e[1] for e in events if e[0] == "response.output_item.done"]
        ws_items = [e for e in done_events if e.get("item", {}).get("type") == "web_search_call"]
        assert len(ws_items) == 1

        # Check web_search lifecycle events
        ws_lifecycle = [e[0] for e in events if "web_search_call" in e[0]]
        assert "response.web_search_call.completed" in ws_lifecycle

    @pytest.mark.asyncio
    async def test_builtin_tool_current_output_items(self, ctx):
        sim_name = make_simulated_function_name("file_search")
        ctx.register_builtin_tool(sim_name, "file_search")

        sc = StreamConverter(ctx)

        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 0,
                "id": "call_fs",
                "type": "function",
                "function": {"name": sim_name, "arguments": '{"query":"docs"}'},
            }]
        })):
            pass

        async for evt in sc.finalize():
            pass

        items = sc.current_output_items
        fs_items = [i for i in items if i.get("type") == "file_search_call"]
        assert len(fs_items) == 1


class TestMixedTextAndToolCalls:
    @pytest.mark.asyncio
    async def test_text_then_tool_call(self, ctx):
        sc = StreamConverter(ctx)
        events = []

        # Text content
        async for evt in sc.process_chunk(make_chunk({"content": "Let me search."})):
            events.append(evt)

        # Tool call
        async for evt in sc.process_chunk(make_chunk({
            "tool_calls": [{
                "index": 0,
                "id": "call_1",
                "type": "function",
                "function": {"name": "search", "arguments": "{}"},
            }]
        })):
            events.append(evt)

        async for evt in sc.finalize():
            events.append(evt)

        # Should have both message and function_call output items
        output = sc.current_output_items
        types = [i.get("type") for i in output]
        assert "message" in types
        assert "function_call" in types
