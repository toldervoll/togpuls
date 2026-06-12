"""Tiny async TTL cache.

One entry per (stop_place_id, horizon_min). A per-key asyncio.Lock prevents a
thundering herd of concurrent OTP calls when the entry expires.
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, ttl_seconds: float = 20.0) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[tuple, tuple[float, object]] = {}
        self._locks: dict[tuple, asyncio.Lock] = {}

    def _lock(self, key: tuple) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def get_or_compute(
        self,
        key: tuple,
        compute: Callable[[], Awaitable[T]],
    ) -> T:
        now = time.monotonic()
        entry = self._entries.get(key)
        if entry and now - entry[0] < self._ttl:
            return entry[1]  # type: ignore[return-value]

        async with self._lock(key):
            entry = self._entries.get(key)
            if entry and time.monotonic() - entry[0] < self._ttl:
                return entry[1]  # type: ignore[return-value]
            value = await compute()
            self._entries[key] = (time.monotonic(), value)
            return value
