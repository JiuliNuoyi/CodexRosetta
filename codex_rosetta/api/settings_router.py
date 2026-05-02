from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from codex_rosetta.config import get_settings, update_settings, get_runtime_overrides, persist_to_env
from codex_rosetta.utils.logging import setup_logging

router = APIRouter(prefix="/v1/settings", tags=["settings"])

_SENSITIVE_KEYS = {"UPSTREAM_API_KEY", "WEB_SEARCH_API_KEY", "REDIS_URL"}


class SettingsResponse(BaseModel):
    settings: dict[str, Any]
    overrides: dict[str, Any]


class SettingsUpdateRequest(BaseModel):
    LOG_LEVEL: str | None = None
    LOG_UPSTREAM_REQUESTS: bool | None = None
    LOG_UPSTREAM_RESPONSES: bool | None = None
    DEBUG_LOG_FILE: str | None = None
    WEB_SEARCH_ENABLED: bool | None = None
    WEB_SEARCH_PROVIDER: str | None = None
    WEB_SEARCH_BASE_URL: str | None = None
    WEB_SEARCH_API_KEY: str | None = None
    WEB_SEARCH_MAX_RESULTS: int | None = None
    WEB_SEARCH_MAX_ROUNDS: int | None = None


@router.get("")
async def get_current_settings() -> SettingsResponse:
    current = get_settings()
    data = current.model_dump()
    for key in _SENSITIVE_KEYS:
        if key in data and data[key]:
            data[key] = "***"
    return SettingsResponse(
        settings=data,
        overrides=get_runtime_overrides(),
    )


@router.put("")
async def update_current_settings(req: SettingsUpdateRequest) -> SettingsResponse:
    overrides: dict[str, Any] = {}
    if req.LOG_LEVEL is not None:
        overrides["LOG_LEVEL"] = req.LOG_LEVEL
    if req.LOG_UPSTREAM_REQUESTS is not None:
        overrides["LOG_UPSTREAM_REQUESTS"] = req.LOG_UPSTREAM_REQUESTS
    if req.LOG_UPSTREAM_RESPONSES is not None:
        overrides["LOG_UPSTREAM_RESPONSES"] = req.LOG_UPSTREAM_RESPONSES
    if req.DEBUG_LOG_FILE is not None:
        overrides["DEBUG_LOG_FILE"] = req.DEBUG_LOG_FILE or None
    if req.WEB_SEARCH_ENABLED is not None:
        overrides["WEB_SEARCH_ENABLED"] = req.WEB_SEARCH_ENABLED
    if req.WEB_SEARCH_PROVIDER is not None:
        overrides["WEB_SEARCH_PROVIDER"] = req.WEB_SEARCH_PROVIDER
    if req.WEB_SEARCH_BASE_URL is not None:
        overrides["WEB_SEARCH_BASE_URL"] = req.WEB_SEARCH_BASE_URL
    if req.WEB_SEARCH_API_KEY is not None and req.WEB_SEARCH_API_KEY != "***":
        overrides["WEB_SEARCH_API_KEY"] = req.WEB_SEARCH_API_KEY
    if req.WEB_SEARCH_MAX_RESULTS is not None:
        overrides["WEB_SEARCH_MAX_RESULTS"] = req.WEB_SEARCH_MAX_RESULTS
    if req.WEB_SEARCH_MAX_ROUNDS is not None:
        overrides["WEB_SEARCH_MAX_ROUNDS"] = req.WEB_SEARCH_MAX_ROUNDS

    if overrides:
        new_settings = update_settings(overrides)
        persist_to_env(overrides)
        setup_logging(
            new_settings.LOG_LEVEL,
            log_file=new_settings.DEBUG_LOG_FILE,
        )

    current = get_settings()
    data = current.model_dump()
    for key in _SENSITIVE_KEYS:
        if key in data and data[key]:
            data[key] = "***"
    return SettingsResponse(
        settings=data,
        overrides=get_runtime_overrides(),
    )
