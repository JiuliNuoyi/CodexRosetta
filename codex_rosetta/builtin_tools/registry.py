from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BuiltinToolSimulator(ABC):
    """Base class for built-in tool simulators."""

    @property
    @abstractmethod
    def original_type(self) -> str: ...

    @abstractmethod
    def convert_to_builtin_output(
        self, function_call_item: dict[str, Any], arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert a simulated function_call item back to its native built-in tool output type."""
        ...

    @abstractmethod
    def generate_streaming_lifecycle_events(
        self, item_id: str, call_id: str, output_index: int, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate built-in tool lifecycle events for streaming."""
        ...


class BuiltinToolRegistry:
    """Registry mapping built-in tool types to their simulators."""

    def __init__(self) -> None:
        self._simulators: dict[str, BuiltinToolSimulator] = {}

    def register(self, simulator: BuiltinToolSimulator) -> None:
        self._simulators[simulator.original_type] = simulator

    def get_simulator(self, tool_type: str) -> BuiltinToolSimulator | None:
        return self._simulators.get(tool_type)

    def has_simulator(self, tool_type: str) -> bool:
        return tool_type in self._simulators


def create_default_registry() -> BuiltinToolRegistry:
    """Create a registry with all default built-in tool simulators."""
    from codex_rosetta.builtin_tools.web_search import WebSearchSimulator
    from codex_rosetta.builtin_tools.file_search import FileSearchSimulator
    from codex_rosetta.builtin_tools.computer_use import ComputerUseSimulator
    from codex_rosetta.builtin_tools.code_interpreter import CodeInterpreterSimulator
    from codex_rosetta.builtin_tools.image_generation import ImageGenerationSimulator

    registry = BuiltinToolRegistry()
    for sim in (
        WebSearchSimulator(),
        FileSearchSimulator(),
        ComputerUseSimulator(),
        CodeInterpreterSimulator(),
        ImageGenerationSimulator(),
    ):
        registry.register(sim)
    return registry
