from __future__ import annotations

from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


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


def get_settings() -> Settings:
    return Settings()
