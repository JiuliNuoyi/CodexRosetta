from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutputItemState:
    """Tracks the state of a single output item being built during streaming."""

    item_id: str
    item_type: str  # "message" or "function_call"
    output_index: int
    content_index: int = 0
    accumulated_text: str = ""
    accumulated_arguments: str = ""
    call_id: str | None = None
    function_name: str | None = None
    has_content_part_added: bool = False
    has_item_added: bool = False
    is_closed: bool = False

    # For built-in tool simulation
    original_tool_type: str | None = None
    has_emitted_lifecycle: bool = False


@dataclass
class StreamState:
    """Overall streaming conversion state."""

    response_id: str
    model: str
    created_at: float = 0.0
    sequence_number: int = 0
    output_items: list[OutputItemState] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    has_emitted_created: bool = False
    has_emitted_in_progress: bool = False
    instructions: str | None = None

    # Track which Chat Completions tool_call indices map to which output items
    tool_call_index_map: dict[int, OutputItemState] = field(default_factory=dict)

    def next_sequence_number(self) -> int:
        self.sequence_number += 1
        return self.sequence_number

    def get_current_message_item(self) -> OutputItemState | None:
        """Get the last message-type output item that hasn't been closed."""
        for item in reversed(self.output_items):
            if item.item_type == "message" and not item.is_closed:
                return item
        return None

    def create_message_item(self, item_id: str) -> OutputItemState:
        """Create a new message output item."""
        item = OutputItemState(
            item_id=item_id,
            item_type="message",
            output_index=len(self.output_items),
        )
        self.output_items.append(item)
        return item

    def create_function_call_item(
        self, item_id: str, call_id: str, function_name: str
    ) -> OutputItemState:
        """Create a new function_call output item."""
        item = OutputItemState(
            item_id=item_id,
            item_type="function_call",
            output_index=len(self.output_items),
            call_id=call_id,
            function_name=function_name,
        )
        self.output_items.append(item)
        return item

    def ensure_message_item(self, item_id: str) -> OutputItemState:
        """Get or create the current message output item."""
        msg = self.get_current_message_item()
        if msg is None:
            msg = self.create_message_item(item_id)
        return msg

    def get_current_reasoning_item(self) -> OutputItemState | None:
        """Get the last reasoning-type output item that hasn't been closed."""
        for item in reversed(self.output_items):
            if item.item_type == "reasoning" and not item.is_closed:
                return item
        return None

    def create_reasoning_item(self, item_id: str) -> OutputItemState:
        """Create a new reasoning output item."""
        item = OutputItemState(
            item_id=item_id,
            item_type="reasoning",
            output_index=len(self.output_items),
        )
        self.output_items.append(item)
        return item
