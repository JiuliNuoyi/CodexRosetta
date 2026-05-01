from __future__ import annotations

from typing import Any

from codex_rosetta.builtin_tools.registry import BuiltinToolSimulator
from codex_rosetta.utils.id_generation import generate_item_id


class WebSearchSimulator(BuiltinToolSimulator):

    @property
    def original_type(self) -> str:
        return "web_search"

    def convert_to_builtin_output(
        self, function_call_item: dict[str, Any], arguments: dict[str, Any]
    ) -> dict[str, Any]:
        search_context_size = arguments.get("search_context_size", "medium")
        filters = arguments.get("filters", {})
        user_location = arguments.get("user_location", {})
        
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

    def generate_streaming_lifecycle_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ws_id = generate_item_id("web_search")
        search_context_size = arguments.get("search_context_size", "medium")
        
        return [
            {
                "type": "response.web_search_call.in_progress",
                "data": {
                    "type": "response.web_search_call.in_progress",
                    "id": ws_id,
                    "output_index": output_index,
                    "action": {"type": "search", "queries": [], "sources": []},
                    "status": "in_progress",
                },
            },
            {
                "type": "response.web_search_call.searching",
                "data": {
                    "type": "response.web_search_call.searching",
                    "id": ws_id,
                    "output_index": output_index,
                    "action": {"type": "search", "queries": [], "sources": []},
                },
            },
        ]

    def generate_completion_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ws_id = generate_item_id("web_search")
        
        return [
            {
                "type": "response.web_search_call.completed",
                "data": {
                    "type": "response.web_search_call.completed",
                    "id": ws_id,
                    "output_index": output_index,
                    "action": {"type": "search", "queries": [], "sources": []},
                    "status": "completed",
                },
            },
        ]


class WebSearch20250826Simulator(WebSearchSimulator):

    @property
    def original_type(self) -> str:
        return "web_search_2025_08_26"
