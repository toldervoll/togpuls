"""HTTP client for the kix-avvik journey-status read (notification-api v1).

Grades every Vy and SJ train on a from→to route for today. Best-effort: any
upstream failure maps to None so a flaky service never breaks the analysis.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

JOURNEY_STATUS_URL = "https://kix-avvik.entur.io/notification-api/v1/journey-status"
HEADERS = {"ET-Client-Name": "kengu-togpuls"}
TIMEOUT_SECONDS = 5.0
OSLO = ZoneInfo("Europe/Oslo")

# kix-avvik allows 30 reads/min per stop pair across all callers. Each
# horizon_min value has its own analysis cache entry, so cap our own reads.
# ponytail: per-process cap; needs a shared store if togpuls runs several instances.
MAX_READS_PER_MIN = 6
_clock = time.monotonic
_recent: dict[tuple[str, str], list[float]] = {}


def window(now: datetime, past_min: int, future_min: int) -> tuple[str, str]:
    """`begin`/`end` as HH:MM Oslo time for [now - past_min, now + future_min].

    Arithmetic runs in UTC so a DST shift inside the window is handled.
    """
    utc = now.astimezone(timezone.utc)
    begin = (utc - timedelta(minutes=past_min)).astimezone(OSLO)
    end = (utc + timedelta(minutes=future_min)).astimezone(OSLO)
    return begin.strftime("%H:%M"), end.strftime("%H:%M")


def _allow(pair: tuple[str, str]) -> bool:
    t = _clock()
    recent = [s for s in _recent.get(pair, []) if t - s < 60]
    allowed = len(recent) < MAX_READS_PER_MIN
    _recent[pair] = recent + [t] if allowed else recent
    return allowed


async def fetch_journey_status(
    client: httpx.AsyncClient,
    from_stop: str,
    to_stop: str,
    now: datetime,
    past_min: int,
    future_min: int,
) -> dict | None:
    """Read journey-status for one route and window; None on any failure."""
    if not _allow((from_stop, to_stop)):
        return None
    begin, end = window(now, past_min, future_min)
    try:
        resp = await client.get(
            JOURNEY_STATUS_URL,
            params={"from_stop": from_stop, "to_stop": to_stop, "begin": begin, "end": end},
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    return data if isinstance(data, dict) else None
