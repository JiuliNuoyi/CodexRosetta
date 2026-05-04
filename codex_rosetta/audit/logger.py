from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from typing import Any


class AuditLogger:
    """Per-request audit logger. Writes a JSON file per request."""

    def __init__(self, request_id: str, audit_dir: str) -> None:
        self._request_id = request_id
        self._audit_dir = audit_dir
        self._start_time = time.monotonic()
        self._data: dict[str, Any] = {
            "request_id": request_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._upstream_chunks_raw: list[str] = []
        self._upstream_chunk_count: int = 0
        self._output_events: list[dict[str, Any]] = []
        self._finish_reason: str | None = None
        self._output_types: list[str] = []

    @property
    def request_id(self) -> str:
        return self._request_id

    def record_original_request(self, body: dict[str, Any]) -> None:
        safe = deepcopy(body)
        if "api_key" in safe:
            safe["api_key"] = "***"
        self._data["original_request"] = safe

    def record_converted_request(self, body: dict[str, Any]) -> None:
        safe = deepcopy(body)
        self._data["converted_request"] = safe

    def record_upstream_chunk(self, chunk: bytes) -> None:
        self._upstream_chunk_count += 1
        self._upstream_chunks_raw.append(chunk.decode("utf-8", errors="replace"))

    def record_output_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        self._output_events.append({
            "type": event_type,
            "data": deepcopy(event_data),
        })

    def set_finish_reason(self, reason: str) -> None:
        self._finish_reason = reason

    def set_output_types(self, types: list[str]) -> None:
        self._output_types = types

    def finalize(
        self,
        status_code: int = 200,
        chunk_count: int | None = None,
        finish_reason: str | None = None,
        output_types: list[str] | None = None,
    ) -> None:
        duration_ms = round((time.monotonic() - self._start_time) * 1000)
        self._data["upstream_chunks_raw"] = self._upstream_chunks_raw
        self._data["output_events"] = self._output_events
        self._data["metadata"] = {
            "status_code": status_code,
            "duration_ms": duration_ms,
            "upstream_chunk_count": chunk_count if chunk_count is not None else self._upstream_chunk_count,
            "output_event_count": len(self._output_events),
            "output_types": output_types if output_types is not None else self._output_types,
            "finish_reason": finish_reason if finish_reason is not None else self._finish_reason,
        }
        self._write()

    def _write(self) -> None:
        os.makedirs(self._audit_dir, exist_ok=True)
        path = os.path.join(self._audit_dir, f"req_{self._request_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class NoOpAuditLogger:
    """No-op audit logger used when audit is disabled."""

    def record_original_request(self, body: dict[str, Any]) -> None:
        pass

    def record_converted_request(self, body: dict[str, Any]) -> None:
        pass

    def record_upstream_chunk(self, chunk: bytes) -> None:
        pass

    def record_output_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        pass

    def set_finish_reason(self, reason: str) -> None:
        pass

    def set_output_types(self, types: list[str]) -> None:
        pass

    def finalize(
        self,
        status_code: int = 200,
        chunk_count: int | None = None,
        finish_reason: str | None = None,
        output_types: list[str] | None = None,
    ) -> None:
        pass
