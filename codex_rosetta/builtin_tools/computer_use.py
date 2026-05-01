from __future__ import annotations

from typing import Any

from codex_rosetta.builtin_tools.registry import BuiltinToolSimulator
from codex_rosetta.utils.id_generation import generate_item_id


class ComputerUseSimulator(BuiltinToolSimulator):

    @property
    def original_type(self) -> str:
        return "computer_use_preview"

    def convert_to_builtin_output(
        self, function_call_item: dict[str, Any], arguments: dict[str, Any]
    ) -> dict[str, Any]:
        action = arguments.get("action", {})
        call_id = function_call_item.get("call_id", "")
        return {
            "type": "computer_call",
            "id": generate_item_id("computer_call"),
            "call_id": call_id,
            "action": action,
            "pending_safety_checks": [],
            "status": "completed",
        }

    def generate_streaming_lifecycle_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return []

    def generate_completion_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return []
