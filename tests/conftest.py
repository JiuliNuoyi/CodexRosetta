import pytest

from codex_rosetta.converters.content_transformer import ContentTransformer
from codex_rosetta.converters.input_transformer import InputTransformer
from codex_rosetta.converters.tool_transformer import ToolTransformer
from codex_rosetta.converters.request_converter import RequestConverter
from codex_rosetta.converters.response_converter import ResponseConverter
from codex_rosetta.models.common import ConversionContext


@pytest.fixture
def content_transformer():
    return ContentTransformer()


@pytest.fixture
def input_transformer(content_transformer):
    return InputTransformer(content_transformer)


@pytest.fixture
def tool_transformer():
    return ToolTransformer()


@pytest.fixture
def request_converter():
    return RequestConverter()


@pytest.fixture
def response_converter(content_transformer):
    return ResponseConverter(content_transformer)


@pytest.fixture
def conversion_context():
    return ConversionContext(
        response_id="resp_test123",
        model="gpt-4o",
        original_instructions="You are helpful.",
    )


# --- Sample payloads ---

SIMPLE_RESPONSES_REQUEST = {
    "model": "gpt-4o",
    "input": "Hello, how are you?",
}

RESPONSES_REQUEST_WITH_INSTRUCTIONS = {
    "model": "gpt-4o",
    "instructions": "You are a helpful assistant.",
    "input": "What is 2+2?",
}

RESPONSES_REQUEST_WITH_TOOLS = {
    "model": "gpt-4o",
    "input": "What's the weather in SF?",
    "tools": [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        }
    ],
}

RESPONSES_REQUEST_WITH_BUILTIN_TOOLS = {
    "model": "gpt-4o",
    "input": "Search the web for recent AI news",
    "tools": [
        {"type": "web_search"},
        {
            "type": "function",
            "name": "get_weather",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    ],
}

RESPONSES_REQUEST_MULTI_TURN = {
    "model": "gpt-4o",
    "input": [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Search for weather"}]},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Let me search for that."}]},
        {"type": "function_call", "name": "get_weather", "call_id": "call_abc", "arguments": '{"location":"SF"}'},
        {"type": "function_call_output", "call_id": "call_abc", "output": '{"temp":72}'},
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "What about NYC?"}]},
    ],
}

SIMPLE_CHAT_RESPONSE = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1746000000,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "I'm doing well, thank you!",
            },
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 8,
        "total_tokens": 18,
        "prompt_tokens_details": {"cached_tokens": 5},
        "completion_tokens_details": {"reasoning_tokens": 0},
    },
}

CHAT_RESPONSE_WITH_TOOL_CALLS = {
    "id": "chatcmpl-xyz789",
    "object": "chat.completion",
    "created": 1746000001,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": "Let me check the weather.",
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location":"SF"}',
                        },
                    }
                ],
            },
        }
    ],
    "usage": {
        "prompt_tokens": 20,
        "completion_tokens": 15,
        "total_tokens": 35,
    },
}
