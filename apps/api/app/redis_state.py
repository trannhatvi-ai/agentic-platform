from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis


class RedisStateStore:
    def __init__(self, redis: Redis, ttl_seconds: int = 3600) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def save_session_state(self, session_id: str, state: dict[str, Any]) -> None:
        key = f"session:{session_id}"
        await self._redis.set(key, json.dumps(state), ex=self._ttl_seconds)

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        key = f"session:{session_id}"
        value = await self._redis.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)
