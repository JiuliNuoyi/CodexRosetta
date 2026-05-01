from __future__ import annotations

import json
from typing import AsyncIterator


def parse_sse_lines(raw: bytes | str) -> list[tuple[str | None, dict | None]]:
    """Parse raw SSE bytes into (event_type, data_dict) tuples.

    Handles multi-line SSE data and the [DONE] sentinel.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")

    events: list[tuple[str | None, dict | None]] = []
    current_event: str | None = None
    current_data_lines: list[str] = []

    for line in raw.split("\n"):
        line = line.rstrip("\r")

        if line.startswith("event:"):
            current_event = line[6:].strip()

        elif line.startswith("data:"):
            current_data_lines.append(line[5:].strip())

        elif line == "":
            if current_data_lines:
                data_str = "\n".join(current_data_lines)
                if data_str == "[DONE]":
                    events.append((current_event, None))
                else:
                    try:
                        data = json.loads(data_str)
                        events.append((current_event, data))
                    except json.JSONDecodeError:
                        pass
                current_event = None
                current_data_lines = []

    return events


def format_sse_event(event_type: str, data: dict) -> str:
    """Format a Responses API SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def parse_upstream_sse_stream(
    stream: AsyncIterator[bytes],
) -> AsyncIterator[tuple[str | None, dict | None]]:
    """Parse an upstream Chat Completions SSE byte stream into parsed events."""
    buffer = ""

    async for chunk in stream:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8", errors="replace")

        buffer += chunk

        while "\n\n" in buffer:
            event_block, buffer = buffer.split("\n\n", 1)
            parsed = parse_sse_lines(event_block)
            for event_type, data in parsed:
                yield event_type, data

    # Handle remaining buffer
    if buffer.strip():
        parsed = parse_sse_lines(buffer)
        for event_type, data in parsed:
            yield event_type, data
