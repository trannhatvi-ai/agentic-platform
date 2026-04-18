from __future__ import annotations

import time

from redis.asyncio import Redis


class RateLimiter:
    def __init__(self, redis: Redis, limit_per_minute: int) -> None:
        self._redis = redis
        self._limit = limit_per_minute

    async def allow(self, user_id: str) -> bool:
        key = f"ratelimit:{user_id}"
        now = time.time()
        window_start = now - 60.0

        pipeline = self._redis.pipeline()
        pipeline.zremrangebyscore(key, 0, window_start)
        pipeline.zadd(key, {str(now): now})
        pipeline.zcard(key)
        pipeline.expire(key, 61)
        _, _, count, _ = await pipeline.execute()
        return int(count) <= self._limit
