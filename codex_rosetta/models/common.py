from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Prefix for simulated built-in tool function names
ROSETTA_TOOL_PREFIX = "__rosetta_"

# Mapping from Responses API built-in tool types to their simulated function names
BUILTIN_TOOL_TYPES = {
    "web_search",
    "web_search_2025_08_26",
    "file_search",
    "computer_use_preview",
    "computer",
    "code_interpreter",
    "image_generation",
}


def make_simulated_function_name(original_type: str) -> str:
    return f"{ROSETTA_TOOL_PREFIX}{original_type}"


def is_simulated_function(name: str) -> bool:
    return name.startswith(ROSETTA_TOOL_PREFIX)


def extract_original_type(simulated_name: str) -> str:
    if not is_simulated_function(simulated_name):
        return simulated_name
    return simulated_name[len(ROSETTA_TOOL_PREFIX):]


@dataclass
class ConversionContext:
    """Metadata tracked during request conversion for use in response conversion."""

    response_id: str = ""
    model: str = ""
    original_tool_types: dict[str, str] = field(default_factory=dict)
    # simulated_function_name -> original_builtin_type
    original_instructions: str | None = None
    original_text_format: dict | None = None
    had_streaming: bool = False
    include_fields: list[str] = field(default_factory=list)
    # Requested include fields for null placeholder injection
    max_tool_calls: int | None = None
    truncation: str | None = None
    # "auto" or "disabled"

    def register_builtin_tool(self, simulated_name: str, original_type: str) -> None:
        self.original_tool_types[simulated_name] = original_type

    def get_original_tool_type(self, function_name: str) -> str | None:
        return self.original_tool_types.get(function_name)
