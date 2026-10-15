"""Redis response cache and per-client rate limiting. Both degrade to no-ops if Redis is down."""

import logging
import os
from functools import cache
from typing import Any

import redis

log = logging.getLogger(__name__)


@cache
def get_store() -> Any:
    """Redis client (get/setex/incr/expire), or None when REDIS_URL is unset."""
    url = os.environ.get("REDIS_URL")
    return (
        redis.Redis.from_url(url, socket_timeout=0.2, socket_connect_timeout=0.2) if url else None
    )


def cached(key: str) -> bytes | None:
    store = get_store()
    if store is None:
        return None
    try:
        hit: bytes | None = store.get(key)
        return hit
    except redis.RedisError as exc:
        log.warning("cache read failed: %s", exc)
        return None


def store_cached(key: str, value: bytes, ttl_s: int) -> None:
    store = get_store()
    if store is None:
        return
    try:
        store.setex(key, ttl_s, value)
    except redis.RedisError as exc:
        log.warning("cache write failed: %s", exc)


def over_limit(client_id: str, window_id: int, limit: int) -> bool:
    """Fixed-window counter. The key holds only an opaque client id and expires with the window."""
    store = get_store()
    if store is None:
        return False
    key = f"rl:{client_id}:{window_id}"
    try:
        count: int = store.incr(key)
        if count == 1:
            store.expire(key, 120)
        return count > limit
    except redis.RedisError as exc:
        log.warning("rate limit check failed, allowing: %s", exc)
        return False
