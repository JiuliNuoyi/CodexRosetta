import pytest

from codex_rosetta.converters.content_transformer import ContentTransformer
from codex_rosetta.converters.input_transformer import InputTransformer


@pytest.fixture
def tf():
    return InputTransformer(ContentTransformer())


class TestSimpleInput:
    @pytest.mark.asyncio
    async def test_string_input(self, tf):
        result = tf.transform_input("Hello")
        assert result == [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_string_with_instructions(self, tf):
        result = tf.transform_input("Hello", instructions="Be helpful")
        assert result[0] == {"role": "system", "content": "Be helpful"}
        assert result[1] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_instructions_only(self, tf):
        result = tf.transform_input("Hello", instructions="Be helpful")
        assert len(result) == 2
        assert result[0]["role"] == "system"


class TestMessageItems:
    @pytest.mark.asyncio
    async def test_user_message_with_text(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Hi"}]}
        ])
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hi"

    @pytest.mark.asyncio
    async def test_developer_role_mapped_to_system(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "developer", "content": "Be precise"}
        ])
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "Be precise"

    @pytest.mark.asyncio
    async def test_system_message(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "system", "content": "Be helpful"}
        ])
        assert result[0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "user", "content": "Hi"},
            {"type": "message", "role": "assistant", "content": "Hello!"},
            {"type": "message", "role": "user", "content": "How are you?"},
        ])
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"


class TestFunctionCallGrouping:
    @pytest.mark.asyncio
    async def test_assistant_with_function_calls(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "user", "content": "Weather in SF?"},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Let me check."}]},
            {"type": "function_call", "name": "get_weather", "call_id": "call_abc", "arguments": '{"location":"SF"}'},
        ])
        # Should be: user msg + assistant msg with tool_calls
        assert len(result) == 2
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Let me check."
        assert len(result[1]["tool_calls"]) == 1
        assert result[1]["tool_calls"][0]["id"] == "call_abc"
        assert result[1]["tool_calls"][0]["function"]["name"] == "get_weather"
        assert result[1]["tool_calls"][0]["function"]["arguments"] == '{"location":"SF"}'

    @pytest.mark.asyncio
    async def test_function_call_output(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Let me check."}]},
            {"type": "function_call", "name": "get_weather", "call_id": "call_abc", "arguments": '{"location":"SF"}'},
            {"type": "function_call_output", "call_id": "call_abc", "output": '{"temp":72}'},
        ])
        # assistant msg + tool msg
        assert len(result) == 2
        assert result[0]["role"] == "assistant"
        assert result[0]["tool_calls"][0]["id"] == "call_abc"
        assert result[1]["role"] == "tool"
        assert result[1]["tool_call_id"] == "call_abc"
        assert result[1]["content"] == '{"temp":72}'

    @pytest.mark.asyncio
    async def test_assistant_with_null_content_and_tool_calls(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "assistant", "content": None},
            {"type": "function_call", "name": "get_weather", "call_id": "call_1", "arguments": '{}'},
        ])
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] is None
        assert len(result[0]["tool_calls"]) == 1

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "assistant", "content": None},
            {"type": "function_call", "name": "get_weather", "call_id": "call_1", "arguments": '{"location":"SF"}'},
            {"type": "function_call", "name": "get_weather", "call_id": "call_2", "arguments": '{"location":"NYC"}'},
        ])
        assert len(result[0]["tool_calls"]) == 2
        assert result[0]["tool_calls"][0]["id"] == "call_1"
        assert result[0]["tool_calls"][1]["id"] == "call_2"

    @pytest.mark.asyncio
    async def test_full_tool_call_lifecycle(self, tf):
        """Complete multi-turn: user -> assistant+tool_call -> tool_result -> user followup"""
        result = tf.transform_input([
            {"type": "message", "role": "user", "content": "Weather in SF?"},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Checking..."}]},
            {"type": "function_call", "name": "get_weather", "call_id": "call_abc", "arguments": '{"location":"SF"}'},
            {"type": "function_call_output", "call_id": "call_abc", "output": '{"temp":72}'},
            {"type": "message", "role": "user", "content": "Thanks!"},
        ])
        # user, assistant+tool_calls, tool, user
        assert len(result) == 4
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert "tool_calls" in result[1]
        assert result[2]["role"] == "tool"
        assert result[3]["role"] == "user"


class TestFunctionCallOutputWithListContent:
    @pytest.mark.asyncio
    async def test_function_call_output_with_list_content(self, tf):
        result = tf.transform_input([
            {"type": "function_call_output", "call_id": "call_1", "output": [
                {"type": "output_text", "text": "line1"},
                {"type": "output_text", "text": "line2"},
            ]},
        ])
        assert result[0]["role"] == "tool"
        assert "line1" in result[0]["content"]
        assert "line2" in result[0]["content"]


class TestMixedContent:
    @pytest.mark.asyncio
    async def test_user_with_image(self, tf):
        result = tf.transform_input([
            {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "What is this?"},
                {"type": "input_image", "image_url": "https://img.png"},
            ]}
        ])
        assert result[0]["role"] == "user"
        content = result[0]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
