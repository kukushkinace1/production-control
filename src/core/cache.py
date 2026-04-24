from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.config import get_settings


class CacheService:
    def __init__(self) -> None:
        self.redis = Redis.from_url(get_settings().redis_url, decode_responses=True)

    async def get_json(self, key: str) -> Any | None:
        try:
            value = await self.redis.get(key)
        except RedisError:
            return None
        if value is None:
            return None
        return json.loads(value)

    async def set_json(self, key: str, value: Any, *, ttl: int) -> None:
        try:
            await self.redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except RedisError:
            return

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await self.redis.delete(*keys)
        except RedisError:
            return

    async def delete_pattern(self, pattern: str) -> None:
        try:
            keys = [key async for key in self.redis.scan_iter(match=pattern)]
            if keys:
                await self.redis.delete(*keys)
        except RedisError:
            return
