import pytest

from codex_rosetta.converters.tool_transformer import ToolTransformer
from codex_rosetta.models.common import ConversionContext, make_simulated_function_name


@pytest.fixture
def tt():
    return ToolTransformer()


@pytest.fixture
def ctx():
    return ConversionContext(response_id="resp_test", model="gpt-4o")


class TestFunctionTool:
    def test_convert_function_tool(self, tt, ctx):
        responses_tool = {
            "type": "function",
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
            "strict": True,
        }
        result = tt.convert_tools([responses_tool], ctx)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_weather"
        assert result[0]["function"]["description"] == "Get weather"
        assert result[0]["function"]["strict"] is True
        assert "parameters" in result[0]["function"]

    def test_empty_tools(self, tt, ctx):
        assert tt.convert_tools([], ctx) == []

    def test_none_tools(self, tt, ctx):
        assert tt.convert_tools([], ctx) == []


class TestBuiltinToolSimulation:
    def test_web_search_simulated(self, tt, ctx):
        responses_tool = {"type": "web_search"}
        result = tt.convert_tools([responses_tool], ctx)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == make_simulated_function_name("web_search")
        assert "__rosetta_web_search" in result[0]["function"]["name"]

    def test_file_search_simulated(self, tt, ctx):
        responses_tool = {"type": "file_search"}
        result = tt.convert_tools([responses_tool], ctx)
        assert result[0]["function"]["name"] == make_simulated_function_name("file_search")

    def test_computer_use_simulated(self, tt, ctx):
        responses_tool = {"type": "computer_use_preview"}
        result = tt.convert_tools([responses_tool], ctx)
        assert result[0]["function"]["name"] == make_simulated_function_name("computer_use_preview")

    def test_code_interpreter_simulated(self, tt, ctx):
        responses_tool = {"type": "code_interpreter"}
        result = tt.convert_tools([responses_tool], ctx)
        assert result[0]["function"]["name"] == make_simulated_function_name("code_interpreter")

    def test_image_generation_simulated(self, tt, ctx):
        responses_tool = {"type": "image_generation"}
        result = tt.convert_tools([responses_tool], ctx)
        assert result[0]["function"]["name"] == make_simulated_function_name("image_generation")

    def test_builtin_registered_in_context(self, tt, ctx):
        tt.convert_tools([{"type": "web_search"}], ctx)
        sim_name = make_simulated_function_name("web_search")
        assert ctx.get_original_tool_type(sim_name) == "web_search"


class TestMixedTools:
    def test_mixed_function_and_builtin(self, tt, ctx):
        tools = [
            {"type": "function", "name": "get_weather", "parameters": {"type": "object", "properties": {}}},
            {"type": "web_search"},
        ]
        result = tt.convert_tools(tools, ctx)
        assert len(result) == 2
        assert result[0]["function"]["name"] == "get_weather"
        assert result[1]["function"]["name"] == make_simulated_function_name("web_search")


class TestToolChoice:
    def test_string_tool_choice(self, tt, ctx):
        assert tt.convert_tool_choice("auto", ctx) == "auto"
        assert tt.convert_tool_choice("none", ctx) == "none"
        assert tt.convert_tool_choice("required", ctx) == "required"

    def test_none_tool_choice(self, tt, ctx):
        assert tt.convert_tool_choice(None, ctx) is None

    def test_function_tool_choice(self, tt, ctx):
        result = tt.convert_tool_choice(
            {"type": "function", "name": "get_weather"}, ctx
        )
        assert result == {
            "type": "function",
            "function": {"name": "get_weather"},
        }
