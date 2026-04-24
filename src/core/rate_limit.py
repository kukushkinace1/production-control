from __future__ import annotations

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.responses import JSONResponse

from src.core.config import get_settings


class RedisRateLimitMiddleware:
    def __init__(self, app) -> None:
        self.app = app
        self.settings = get_settings()
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)

    async def __call__(
        self,
        scope,
        receive,
        send,
    ) -> None:
        if scope["type"] != "http" or not self.settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if request.url.path.startswith(("/health", "/docs", "/openapi.json")):
            await self.app(scope, receive, send)
            return

        allowed = await self._is_allowed(request)
        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded."},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _is_allowed(self, request: Request) -> bool:
        client_host = request.client.host if request.client else "unknown"
        key = self._window_key(client_host)
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, self.settings.rate_limit_window_seconds)
            return count <= self.settings.rate_limit_requests
        except RedisError:
            return True

    def _window_key(self, client_host: str) -> str:
        import time

        window = int(time.time() // self.settings.rate_limit_window_seconds)
        return f"rate_limit:{client_host}:{window}"
