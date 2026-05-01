import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from codex_rosetta.main import app
from codex_rosetta.state.conversation_store import InMemoryConversationStore


@pytest.fixture
def mock_upstream():
    """Create a mock upstream client."""
    upstream = AsyncMock()
    upstream.chat_completions.return_value = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1746000000,
        "model": "gpt-4o",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "Hello from the model!"},
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return upstream


@pytest.fixture
def mock_store():
    return InMemoryConversationStore()


class TestHealthEndpoint:
    def test_health(self):
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


class TestNonStreamingProxy:
    def test_simple_text_request(self, mock_upstream, mock_store):
        with patch("codex_rosetta.api.router.get_upstream_client", return_value=mock_upstream), \
             patch("codex_rosetta.api.router.get_conversation_store", return_value=mock_store):
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                resp = client.post("/v1/responses", json={
                    "model": "gpt-4o",
                    "input": "Say hello",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "response"
        assert data["status"] == "completed"
        assert data["model"] == "gpt-4o"

        msg_items = [o for o in data["output"] if o["type"] == "message"]
        assert len(msg_items) == 1
        assert msg_items[0]["role"] == "assistant"
        texts = [p["text"] for p in msg_items[0]["content"] if p.get("type") == "output_text"]
        assert "Hello from the model!" in texts

    def test_request_with_instructions(self, mock_upstream, mock_store):
        with patch("codex_rosetta.api.router.get_upstream_client", return_value=mock_upstream), \
             patch("codex_rosetta.api.router.get_conversation_store", return_value=mock_store):
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                resp = client.post("/v1/responses", json={
                    "model": "gpt-4o",
                    "instructions": "Be concise",
                    "input": "Hi",
                })

        assert resp.status_code == 200
        # Verify system message was sent upstream
        call_args = mock_upstream.chat_completions.call_args[0][0]
        system_msgs = [m for m in call_args["messages"] if m.get("role") == "system"]
        assert len(system_msgs) >= 1
        assert system_msgs[0]["content"] == "Be concise"

    def test_request_with_tool_calls_response(self, mock_upstream, mock_store):
        mock_upstream.chat_completions.return_value = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1746000000,
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

        with patch("codex_rosetta.api.router.get_upstream_client", return_value=mock_upstream), \
             patch("codex_rosetta.api.router.get_conversation_store", return_value=mock_store):
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                resp = client.post("/v1/responses", json={
                    "model": "gpt-4o",
                    "input": "Weather in SF?",
                    "tools": [
                        {"type": "function", "name": "get_weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}},
                    ],
                })

        data = resp.json()
        fc_items = [o for o in data["output"] if o["type"] == "function_call"]
        assert len(fc_items) == 1
        assert fc_items[0]["call_id"] == "call_abc"
        assert fc_items[0]["name"] == "get_weather"

    def test_usage_mapping(self, mock_upstream, mock_store):
        mock_upstream.chat_completions.return_value = {
            "id": "chatcmpl-test",
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
                "completion_tokens_details": {"reasoning_tokens": 5},
            },
        }

        with patch("codex_rosetta.api.router.get_upstream_client", return_value=mock_upstream), \
             patch("codex_rosetta.api.router.get_conversation_store", return_value=mock_store):
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                resp = client.post("/v1/responses", json={"model": "gpt-4o", "input": "Hi"})

        data = resp.json()
        usage = data["usage"]
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["total_tokens"] == 150
        assert usage["input_tokens_details"]["cached_tokens"] == 30
        assert usage["output_tokens_details"]["reasoning_tokens"] == 5


class TestStreamingProxy:
    def test_streaming_text(self, mock_upstream, mock_store):
        async def mock_stream(*args, **kwargs):
            chunks = [
                b'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":1746000000,"model":"gpt-4o","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":1746000000,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":1746000000,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":1746000000,"model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
                b'data: [DONE]\n\n',
            ]
            for chunk in chunks:
                yield chunk

        mock_upstream.chat_completions_stream = mock_stream

        with patch("codex_rosetta.api.router.get_upstream_client", return_value=mock_upstream), \
             patch("codex_rosetta.api.router.get_conversation_store", return_value=mock_store):
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                resp = client.post("/v1/responses", json={
                    "model": "gpt-4o",
                    "input": "Hi",
                    "stream": True,
                })

        assert resp.status_code == 200

        content = resp.content.decode()
        events = []
        event_type = None
        for line in content.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
                try:
                    events.append({"event": event_type, "data": json.loads(data_str)})
                except json.JSONDecodeError:
                    pass

        event_types = [e["event"] for e in events]
        assert "response.created" in event_types
        assert "response.in_progress" in event_types
        assert "response.output_text.delta" in event_types
        assert "response.completed" in event_types

        deltas = [e for e in events if e["event"] == "response.output_text.delta"]
        texts = [d["data"]["delta"] for d in deltas]
        assert "Hello" in texts
        assert " world" in texts
