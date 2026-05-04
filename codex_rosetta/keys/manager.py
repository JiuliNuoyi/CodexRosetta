from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from codex_rosetta.config import Settings, get_settings
from codex_rosetta.utils.logging import get_logger

logger = get_logger("keys")


class KeyEntry(BaseModel):
    name: str
    key: str
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    models: list[str] = []
    active: bool = False


class KeyManager:
    def __init__(self, keys_file: str) -> None:
        self._keys_file = Path(keys_file)
        self._entries: list[KeyEntry] = []
        self._load()

    def _load(self) -> None:
        if not self._keys_file.exists():
            return
        try:
            data = json.loads(self._keys_file.read_text(encoding="utf-8"))
            self._entries = [KeyEntry(**item) for item in data]
            logger.info("keys_loaded", count=len(self._entries), path=str(self._keys_file))
        except Exception as e:
            logger.error("keys_load_failed", error=str(e))
            self._entries = []

    def _save(self) -> None:
        self._keys_file.parent.mkdir(parents=True, exist_ok=True)
        data = [item.model_dump() for item in self._entries]
        self._keys_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @property
    def entries(self) -> list[KeyEntry]:
        return list(self._entries)

    def get_active(self) -> KeyEntry | None:
        for entry in self._entries:
            if entry.active:
                return entry
        return None

    def get(self, name: str) -> KeyEntry | None:
        for entry in self._entries:
            if entry.name == name:
                return entry
        return None

    def add(self, entry: KeyEntry) -> None:
        existing = self.get(entry.name)
        if existing:
            raise ValueError(f"Key with name '{entry.name}' already exists")
        if entry.active:
            for e in self._entries:
                e.active = False
        if not self._entries:
            entry.active = True
        self._entries.append(entry)
        self._save()
        logger.info("key_added", name=entry.name)

    def remove(self, name: str) -> None:
        entry = self.get(name)
        if entry is None:
            raise ValueError(f"Key '{name}' not found")
        was_active = entry.active
        self._entries.remove(entry)
        if was_active and self._entries:
            self._entries[0].active = True
            logger.info("key_auto_activated", name=self._entries[0].name)
        self._save()
        logger.info("key_removed", name=name)

    def activate(self, name: str) -> KeyEntry:
        entry = self.get(name)
        if entry is None:
            raise ValueError(f"Key '{name}' not found")
        for e in self._entries:
            e.active = False
        entry.active = True
        self._save()
        logger.info("key_activated", name=name)
        return entry

    def update(self, name: str, **fields) -> KeyEntry:
        entry = self.get(name)
        if entry is None:
            raise ValueError(f"Key '{name}' not found")
        was_active = entry.active
        for k, v in fields.items():
            if v is not None and hasattr(entry, k):
                setattr(entry, k, v)
        if fields.get("active") and not was_active:
            for e in self._entries:
                e.active = False
            entry.active = True
        self._save()
        logger.info("key_updated", name=name)
        return entry

    def initialize_from_env(self, settings: Settings) -> None:
        if self._entries:
            return
        if not settings.UPSTREAM_API_KEY:
            return
        default_entry = KeyEntry(
            name="default",
            key=settings.UPSTREAM_API_KEY,
            provider=settings.UPSTREAM_PROVIDER,
            base_url=settings.UPSTREAM_BASE_URL,
            active=True,
        )
        self._entries = [default_entry]
        self._save()
        logger.info("keys_initialized_from_env", key_count=1)

    @staticmethod
    def mask_key(key: str) -> str:
        if len(key) <= 8:
            return "***"
        return key[:8] + "***"
