from __future__ import annotations

from typing import Any

from codex_rosetta.builtin_tools.registry import BuiltinToolSimulator
from codex_rosetta.utils.id_generation import generate_item_id


class ImageGenerationSimulator(BuiltinToolSimulator):

    @property
    def original_type(self) -> str:
        return "image_generation"

    def convert_to_builtin_output(
        self, function_call_item: dict[str, Any], arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "type": "image_generation_call",
            "id": generate_item_id("image_generation"),
            "result": "",
            "status": "completed",
        }

    def generate_streaming_lifecycle_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ig_id = generate_item_id("image_generation")
        return [
            {
                "type": "response.image_gen_call.in_progress",
                "data": {
                    "type": "response.image_gen_call.in_progress",
                    "id": ig_id,
                    "output_index": output_index,
                    "status": "in_progress",
                },
            },
            {
                "type": "response.image_gen_call.generating",
                "data": {
                    "type": "response.image_gen_call.generating",
                    "id": ig_id,
                    "output_index": output_index,
                },
            },
        ]

    def generate_completion_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ig_id = generate_item_id("image_generation")
        return [
            {
                "type": "response.image_gen_call.completed",
                "data": {
                    "type": "response.image_gen_call.completed",
                    "id": ig_id,
                    "output_index": output_index,
                    "result": "",
                    "status": "completed",
                },
            },
        ]
