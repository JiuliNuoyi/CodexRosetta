from __future__ import annotations

import json
import pytest

from codex_rosetta.search.base import SearchResult, SearchResponse, SearchProvider
from codex_rosetta.search.http_provider import HttpSearchProvider
from codex_rosetta.search.formatter import format_search_results
from codex_rosetta.api.router import (
    _extract_web_search_tool_calls,
    _parse_search_query,
    _inject_search_results,
    _should_forward_search_stream_event,
)


class MockSearchProvider(SearchProvider):
    def __init__(self, responses: dict[str, SearchResponse] | None = None) -> None:
        self._responses = responses or {}
        self._calls: list[str] = []

    async def search(self, query: str, max_results: int = 5) -> SearchResponse:
        self._calls.append(query)
        return self._responses.get(query, SearchResponse(
            results=[SearchResult(title=f"Result for {query}", url=f"https://example.com/{query}", snippet="Test snippet")],
            query=query,
        ))

    @property
    def calls(self) -> list[str]:
        return self._calls


class TestSearchResult:
    def test_creation(self):
        r = SearchResult(title="Test", url="https://example.com", snippet="Hello")
        assert r.title == "Test"
        assert r.url == "https://example.com"
        assert r.snippet == "Hello"

    def test_default_snippet(self):
        r = SearchResult(title="Test", url="https://example.com")
        assert r.snippet == ""


class TestSearchResponse:
    def test_creation(self):
        r = SearchResponse(results=[], query="test")
        assert r.results == []
        assert r.query == "test"

    def test_default_values(self):
        r = SearchResponse()
        assert r.results == []
        assert r.query == ""


class TestFormatter:
    def test_format_with_results(self):
        resp = SearchResponse(
            results=[
                SearchResult(title="Title 1", url="https://a.com", snippet="Snippet 1"),
                SearchResult(title="Title 2", url="https://b.com"),
            ],
            query="test query",
        )
        output = format_search_results(resp)
        assert "test query" in output
        assert "Title 1" in output
        assert "https://a.com" in output
        assert "Snippet 1" in output
        assert "Title 2" in output
        assert "2 条" in output

    def test_format_empty_results(self):
        resp = SearchResponse(results=[], query="nothing")
        output = format_search_results(resp)
        assert "未返回任何结果" in output


class TestExtractWebSearchToolCalls:
    def test_extracts_web_search_calls(self):
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {"id": "tc1", "function": {"name": "__rosetta_web_search", "arguments": '{"query": "test"}'}},
                        {"id": "tc2", "function": {"name": "other_func", "arguments": '{}'}},
                    ]
                }
            }]
        }
        result = _extract_web_search_tool_calls(response)
        assert len(result) == 1
        assert result[0]["id"] == "tc1"

    def test_extracts_web_search_2025_calls(self):
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {"id": "tc1", "function": {"name": "__rosetta_web_search_2025_08_26", "arguments": '{"query": "test"}'}},
                    ]
                }
            }]
        }
        result = _extract_web_search_tool_calls(response)
        assert len(result) == 1

    def test_no_tool_calls(self):
        response = {"choices": [{"message": {"content": "Hello"}}]}
        result = _extract_web_search_tool_calls(response)
        assert result == []

    def test_no_web_search_calls(self):
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {"id": "tc1", "function": {"name": "other_func", "arguments": '{}'}},
                    ]
                }
            }]
        }
        result = _extract_web_search_tool_calls(response)
        assert result == []


class TestParseSearchQuery:
    def test_parse_query(self):
        tc = {"function": {"arguments": '{"query": "python async"}'}}
        assert _parse_search_query(tc) == "python async"

    def test_parse_empty_query(self):
        tc = {"function": {"arguments": '{}'}}
        assert _parse_search_query(tc) == ""

    def test_parse_invalid_json(self):
        tc = {"function": {"arguments": "not json"}}
        assert _parse_search_query(tc) == ""

    def test_parse_dict_arguments(self):
        tc = {"function": {"arguments": {"query": "test"}}}
        assert _parse_search_query(tc) == "test"


class TestInjectSearchResults:
    def test_inject_results(self):
        chat_request = {"messages": [{"role": "user", "content": "search for python"}], "model": "gpt-4"}
        chat_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {"id": "tc1", "type": "function", "function": {"name": "__rosetta_web_search", "arguments": '{"query": "python"}'}},
                    ]
                }
            }]
        }
        search_results = {"tc1": "搜索结果：1. Python官网 https://python.org"}

        result = _inject_search_results(chat_request, chat_response, search_results)

        messages = result["messages"]
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["tool_calls"][0]["id"] == "tc1"
        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_call_id"] == "tc1"
        assert "Python官网" in messages[2]["content"]


class TestMockSearchProvider:
    @pytest.mark.asyncio
    async def test_mock_search(self):
        provider = MockSearchProvider()
        result = await provider.search("test query")
        assert result.query == "test query"
        assert len(result.results) == 1
        assert result.results[0].title == "Result for test query"

    @pytest.mark.asyncio
    async def test_mock_search_custom_response(self):
        provider = MockSearchProvider(responses={
            "custom": SearchResponse(results=[SearchResult(title="Custom", url="https://custom.com")], query="custom")
        })
        result = await provider.search("custom")
        assert result.results[0].title == "Custom"

    @pytest.mark.asyncio
    async def test_mock_tracks_calls(self):
        provider = MockSearchProvider()
        await provider.search("query1")
        await provider.search("query2")
        assert provider.calls == ["query1", "query2"]


class TestSearchStreamEventFilter:
    def test_forwards_message_item_events(self):
        assert _should_forward_search_stream_event(
            "response.output_item.added",
            {"item": {"type": "message"}},
        ) is True

    def test_filters_reasoning_and_search_item_events(self):
        assert _should_forward_search_stream_event(
            "response.output_item.added",
            {"item": {"type": "reasoning"}},
        ) is False
        assert _should_forward_search_stream_event(
            "response.output_item.done",
            {"item": {"type": "web_search_call"}},
        ) is False
        assert _should_forward_search_stream_event(
            "response.reasoning.delta",
            {"delta": "thinking"},
        ) is False
