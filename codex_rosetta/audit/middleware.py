from __future__ import annotations

import json
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from codex_rosetta.audit.logger import AuditLogger, NoOpAuditLogger


class AuditMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that captures original request body and final response."""

    def __init__(self, app: Any, audit_dir: str, enabled: bool = True) -> None:
        super().__init__(app)
        self._audit_dir = audit_dir
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._enabled or request.url.path != "/v1/responses":
            return await call_next(request)

        # Use existing request_id if set, otherwise generate one
        request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        auditor = AuditLogger(request_id, self._audit_dir)

        # Capture original request body
        body = await request.body()
        try:
            parsed = json.loads(body)
            auditor.record_original_request(parsed)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Store auditor in request state for downstream use
        request.state.auditor = auditor

        response = await call_next(request)

        # For non-streaming responses, capture the final body
        if isinstance(response, StreamingResponse):
            return self._wrap_streaming_response(response, auditor)
        else:
            # Non-streaming: capture response body
            resp_body = b""
            async for chunk in response.body_iterator:
                resp_body += chunk if isinstance(chunk, bytes) else chunk.encode()
            try:
                resp_data = json.loads(resp_body)
                auditor.record_output_event("response.completed", {"response": resp_data})
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            auditor.finalize(status_code=response.status_code)
            return Response(
                content=resp_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

    def _wrap_streaming_response(
        self, response: StreamingResponse, auditor: AuditLogger
    ) -> StreamingResponse:
        original_body = response.body_iterator

        async def audit_stream():
            async for chunk in original_body:
                yield chunk
            # Stream ended, finalize audit
            auditor.finalize(status_code=response.status_code)

        return StreamingResponse(
            audit_stream(),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
