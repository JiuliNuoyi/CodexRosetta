from __future__ import annotations

from typing import Any

from codex_rosetta.builtin_tools.registry import BuiltinToolSimulator
from codex_rosetta.utils.id_generation import generate_item_id


class FileSearchSimulator(BuiltinToolSimulator):

    @property
    def original_type(self) -> str:
        return "file_search"

    def convert_to_builtin_output(
        self, function_call_item: dict[str, Any], arguments: dict[str, Any]
    ) -> dict[str, Any]:
        query = arguments.get("query", "")
        return {
            "type": "file_search_call",
            "id": generate_item_id("file_search"),
            "queries": [query],
            "status": "completed",
        }

    def generate_streaming_lifecycle_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        fs_id = generate_item_id("file_search")
        query = arguments.get("query", "")
        return [
            {
                "type": "response.file_search_call.in_progress",
                "data": {
                    "type": "response.file_search_call.in_progress",
                    "id": fs_id,
                    "output_index": output_index,
                    "queries": [query],
                    "status": "in_progress",
                },
            },
            {
                "type": "response.file_search_call.searching",
                "data": {
                    "type": "response.file_search_call.searching",
                    "id": fs_id,
                    "output_index": output_index,
                    "queries": [query],
                },
            },
        ]

    def generate_completion_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        fs_id = generate_item_id("file_search")
        query = arguments.get("query", "")
        return [
            {
                "type": "response.file_search_call.completed",
                "data": {
                    "type": "response.file_search_call.completed",
                    "id": fs_id,
                    "output_index": output_index,
                    "queries": [query],
                    "status": "completed",
                },
            },
        ]
