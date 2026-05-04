from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = ".env"
_PROVIDERS_FILE = "data/search_providers.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Upstream API
    UPSTREAM_BASE_URL: str = "https://api.openai.com/v1"
    UPSTREAM_API_KEY: str = ""
    UPSTREAM_PROVIDER: Literal["openai", "anthropic", "google", "other"] = "openai"

    # Optional Redis
    REDIS_URL: Optional[str] = None

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 33131

    # Timeouts
    UPSTREAM_TIMEOUT_CONNECT: float = 10.0
    UPSTREAM_TIMEOUT_READ: float = 300.0

    # Conversation store
    MAX_CONVERSATION_HISTORY: int = 100
    CONVERSATION_TTL_SECONDS: int = 3600

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_UPSTREAM_REQUESTS: bool = False
    LOG_UPSTREAM_RESPONSES: bool = False
    DEBUG_LOG_FILE: Optional[str] = None

    # Audit
    AUDIT_ENABLED: bool = False
    AUDIT_DIR: str = "./audit"

    # Keys management
    KEYS_FILE: str = "./data/keys.json"

    # Web Search
    WEB_SEARCH_ENABLED: bool = False
    WEB_SEARCH_PROVIDER: Literal["custom", "tavily", "searxng", "brave", "duckduckgo"] = "custom"
    WEB_SEARCH_BASE_URL: str = ""
    WEB_SEARCH_API_KEY: str = ""
    WEB_SEARCH_MAX_RESULTS: int = 5
    WEB_SEARCH_MAX_ROUNDS: int = 3
    WEB_SEARCH_SIMULATED_STREAMING_ENABLED: bool = True
    WEB_SEARCH_SIMULATED_STREAM_DELAY_MS: int = 25
    WEB_SEARCH_SIMULATED_STREAM_MAX_CHARS: int = 32


PROVIDER_FIELD_DEFS: dict[str, dict[str, str]] = {
    "tavily": {"WEB_SEARCH_BASE_URL": "clear", "WEB_SEARCH_API_KEY": "required"},
    "searxng": {"WEB_SEARCH_BASE_URL": "required", "WEB_SEARCH_API_KEY": "clear"},
    "brave": {"WEB_SEARCH_BASE_URL": "clear", "WEB_SEARCH_API_KEY": "required"},
    "duckduckgo": {"WEB_SEARCH_BASE_URL": "clear", "WEB_SEARCH_API_KEY": "clear"},
    "custom": {"WEB_SEARCH_BASE_URL": "required", "WEB_SEARCH_API_KEY": "optional"},
}


def _load_provider_saved() -> dict[str, dict[str, str]]:
    path = Path(_PROVIDERS_FILE)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {p: {} for p in PROVIDER_FIELD_DEFS}


def _save_provider_saved_to_file(saved: dict[str, dict[str, str]]) -> None:
    path = Path(_PROVIDERS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


_PROVIDER_SAVED: dict[str, dict[str, str]] = _load_provider_saved()


def save_provider_state(provider: str, base_url: str = "", api_key: str = "") -> None:
    if provider not in PROVIDER_FIELD_DEFS:
        return
    field_defs = PROVIDER_FIELD_DEFS.get(provider, {})
    changed = False
    if base_url and field_defs.get("WEB_SEARCH_BASE_URL") in ("required", "optional"):
        _PROVIDER_SAVED.setdefault(provider, {})["WEB_SEARCH_BASE_URL"] = base_url
        changed = True
    if api_key and field_defs.get("WEB_SEARCH_API_KEY") in ("required", "optional"):
        _PROVIDER_SAVED.setdefault(provider, {})["WEB_SEARCH_API_KEY"] = api_key
        changed = True
    if changed:
        _save_provider_saved_to_file(_PROVIDER_SAVED)


def get_provider_saved(provider: str, field: str) -> str:
    return _PROVIDER_SAVED.get(provider, {}).get(field, "")

_runtime_overrides: dict[str, Any] = {}


def get_settings() -> Settings:
    base = Settings()
    if _runtime_overrides:
        return base.model_copy(update=_runtime_overrides)
    return base


def update_settings(overrides: dict[str, Any]) -> Settings:
    _runtime_overrides.update(overrides)
    return get_settings()


def get_runtime_overrides() -> dict[str, Any]:
    return dict(_runtime_overrides)


def persist_to_env(updates: dict[str, Any]) -> None:
    """Write key=value pairs to .env file, preserving comments and structure."""
    env_path = Path(_ENV_FILE)

    lines: list[str] = []
    existing_keys: set[str] = set()

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys.add(key)
                    if key in updates:
                        val = updates[key]
                        if val is None:
                            val = ""
                        elif isinstance(val, bool):
                            val = str(val).lower()
                        lines.append(f"{key}={val}\n")
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
    else:
        lines.append("# CodexRosetta Configuration\n")

    # Append keys not yet in file
    for key, val in updates.items():
        if key not in existing_keys:
            if val is None:
                val = ""
            elif isinstance(val, bool):
                val = str(val).lower()
            lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
