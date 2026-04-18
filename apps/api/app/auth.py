from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


async def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    if not x_api_key or x_api_key not in settings.api_keys_set:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return x_api_key


def resolve_user_id(
    x_user_id: str | None = Header(default=None),
    api_key: str = Depends(require_api_key),
) -> str:
    if x_user_id and x_user_id.strip():
        return x_user_id.strip()
    return f"key:{api_key[:8]}"
