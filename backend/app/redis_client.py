import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

PUMP_CHANNEL = "pumps:telemetry"

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def publish(channel: str, payload: dict[str, Any]) -> None:
    await get_redis().publish(channel, json.dumps(payload, default=str))


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
