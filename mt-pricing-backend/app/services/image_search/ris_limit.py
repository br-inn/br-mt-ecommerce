"""Daily call counter para Reverse Image Search — Redis INCR pattern (US-F15-02-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class RedisLike(Protocol):
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> None: ...


_KEY_TEMPLATE = "mt:ris:daily_count:{date}"


async def check_and_increment(redis: RedisLike, *, limit: int) -> bool:
    """Retorna True si se puede llamar (bajo el límite), False si se alcanzó."""
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    key = _KEY_TEMPLATE.format(date=today)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    return count <= limit


__all__ = ["RedisLike", "check_and_increment"]
