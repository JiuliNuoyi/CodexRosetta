from __future__ import annotations

from typing import Any

from codex_rosetta.builtin_tools.registry import BuiltinToolSimulator
from codex_rosetta.utils.id_generation import generate_item_id


class CodeInterpreterSimulator(BuiltinToolSimulator):

    @property
    def original_type(self) -> str:
        return "code_interpreter"

    def convert_to_builtin_output(
        self, function_call_item: dict[str, Any], arguments: dict[str, Any]
    ) -> dict[str, Any]:
        code = arguments.get("code", "")
        return {
            "type": "code_interpreter_call",
            "id": generate_item_id("code_interpreter"),
            "code": code,
            "container_id": None,
            "outputs": [],
            "status": "completed",
        }

    def generate_streaming_lifecycle_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ci_id = generate_item_id("code_interpreter")
        code = arguments.get("code", "")
        return [
            {
                "type": "response.code_interpreter_call.in_progress",
                "data": {
                    "type": "response.code_interpreter_call.in_progress",
                    "id": ci_id,
                    "output_index": output_index,
                    "code": code,
                    "status": "in_progress",
                },
            },
        ]

    def generate_completion_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ci_id = generate_item_id("code_interpreter")
        code = arguments.get("code", "")
        return [
            {
                "type": "response.code_interpreter_call.completed",
                "data": {
                    "type": "response.code_interpreter_call.completed",
                    "id": ci_id,
                    "output_index": output_index,
                    "code": code,
                    "outputs": [],
                    "status": "completed",
                },
            },
        ]
