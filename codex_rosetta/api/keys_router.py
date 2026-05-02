from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from codex_rosetta.api.dependencies import rebuild_upstream_client
from codex_rosetta.config import get_settings
from codex_rosetta.keys.manager import KeyManager, KeyEntry

router = APIRouter(prefix="/v1/keys", tags=["keys"])

_key_manager: KeyManager | None = None


def get_key_manager() -> KeyManager:
    global _key_manager
    if _key_manager is None:
        settings = get_settings()
        _key_manager = KeyManager(settings.KEYS_FILE)
        _key_manager.initialize_from_env(settings)
    return _key_manager


class KeyCreateRequest(BaseModel):
    name: str
    key: str
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    models: list[str] = []
    active: bool = False


class KeyUpdateRequest(BaseModel):
    key: str | None = None
    provider: str | None = None
    base_url: str | None = None
    models: list[str] | None = None
    active: bool | None = None


class KeyResponse(BaseModel):
    name: str
    key_masked: str
    provider: str
    base_url: str
    models: list[str]
    active: bool


def _entry_to_response(entry: KeyEntry) -> KeyResponse:
    return KeyResponse(
        name=entry.name,
        key_masked=KeyManager.mask_key(entry.key),
        provider=entry.provider,
        base_url=entry.base_url,
        models=entry.models,
        active=entry.active,
    )


@router.get("")
async def list_keys() -> list[KeyResponse]:
    mgr = get_key_manager()
    return [_entry_to_response(e) for e in mgr.entries]


@router.post("")
async def add_key(req: KeyCreateRequest) -> KeyResponse:
    mgr = get_key_manager()
    entry = KeyEntry(
        name=req.name,
        key=req.key,
        provider=req.provider,
        base_url=req.base_url,
        models=req.models,
        active=req.active,
    )
    try:
        mgr.add(entry)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if entry.active:
        await _apply_active_key(entry)

    return _entry_to_response(entry)


@router.delete("/{name}")
async def delete_key(name: str) -> dict[str, str]:
    mgr = get_key_manager()
    was_active = (active := mgr.get_active()) and active.name == name
    try:
        mgr.remove(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if was_active:
        new_active = mgr.get_active()
        if new_active:
            await _apply_active_key(new_active)

    return {"status": "deleted", "name": name}


@router.put("/{name}/activate")
async def activate_key(name: str) -> KeyResponse:
    mgr = get_key_manager()
    try:
        entry = mgr.activate(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await _apply_active_key(entry)
    return _entry_to_response(entry)


@router.put("/{name}")
async def update_key(name: str, req: KeyUpdateRequest) -> KeyResponse:
    mgr = get_key_manager()
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        entry = mgr.get(name)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Key '{name}' not found")
        return _entry_to_response(entry)
    try:
        entry = mgr.update(name, **fields)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if entry.active:
        await _apply_active_key(entry)

    return _entry_to_response(entry)


async def _apply_active_key(entry: KeyEntry) -> None:
    current = get_settings()
    new_settings = current.model_copy(update={
        "UPSTREAM_BASE_URL": entry.base_url,
        "UPSTREAM_API_KEY": entry.key,
        "UPSTREAM_PROVIDER": entry.provider,
    })
    await rebuild_upstream_client(new_settings)
