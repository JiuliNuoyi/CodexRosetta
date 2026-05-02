from __future__ import annotations

import time
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from codex_rosetta.config import Settings, get_settings
from codex_rosetta.utils.logging import setup_logging, get_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        logger = get_logger("access").bind(request_id=request_id)
        start = time.monotonic()

        logger.info(
            "request_received",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, log_file=settings.DEBUG_LOG_FILE)

    logger = get_logger("startup")
    logger.info("codex_rosetta_starting", log_level=settings.LOG_LEVEL)
    if settings.DEBUG_LOG_FILE:
        logger.info("debug_log_file_enabled", path=settings.DEBUG_LOG_FILE)
    if settings.LOG_UPSTREAM_REQUESTS:
        logger.info("upstream_request_logging_enabled")
    if settings.LOG_UPSTREAM_RESPONSES:
        logger.info("upstream_response_logging_enabled")

    app = FastAPI(
        title="CodexRosetta",
        version="0.1.0",
        description="Responses API <-> Chat Completions API proxy",
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.AUDIT_ENABLED:
        from codex_rosetta.audit.middleware import AuditMiddleware

        app.add_middleware(AuditMiddleware, audit_dir=settings.AUDIT_DIR, enabled=True)
        logger.info("audit_enabled", audit_dir=settings.AUDIT_DIR)

    from codex_rosetta.api.router import router
    from codex_rosetta.api.keys_router import router as keys_router
    from codex_rosetta.api.settings_router import router as settings_router
    from codex_rosetta.api.web_router import mount_webui

    app.include_router(router)
    app.include_router(keys_router)
    app.include_router(settings_router)

    mount_webui(app)

    from codex_rosetta.api.keys_router import get_key_manager
    key_manager = get_key_manager()
    active = key_manager.get_active()
    if active:
        logger.info("active_key", name=active.name, base_url=active.base_url)
        from codex_rosetta.api.dependencies import get_upstream_client
        active_settings = settings.model_copy(update={
            "UPSTREAM_BASE_URL": active.base_url,
            "UPSTREAM_API_KEY": active.key,
            "UPSTREAM_PROVIDER": active.provider,
        })
        get_upstream_client(active_settings)
    else:
        logger.warning("no_active_key_configured")

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "codex_rosetta.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )


if __name__ == "__main__":
    run()
