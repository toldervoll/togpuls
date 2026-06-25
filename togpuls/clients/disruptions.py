"""HTTP client for the disruption-estimate service.

Two complementary, best-effort enrichments — any upstream failure maps to an
empty result so a flaky service never breaks the analysis:

* ``fetch_estimates`` (``/situation``) — how long a SIRI situation typically
  lasts (historical baseline: cancel/trouble rates, delay percentiles, clear
  ETA), keyed by situation id.
* ``fetch_impact`` (``/impact``) — how the situations affecting a from→to
  corridor impact the specific trains a passenger's trip depends on
  (cancellation probability and delay at the boarding/alighting stops), keyed
  by situation number.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx

DISRUPTION_ESTIMATE_URL = (
    "https://kix-avvik-disruptions-305411154596.europe-west1.run.app/situation"
)
DISRUPTION_IMPACT_URL = (
    "https://kix-avvik-disruptions-305411154596.europe-west1.run.app/impact"
)


async def _fetch_one(client: httpx.AsyncClient, situation_id: str):
    """Fetch one estimate; return None on any upstream failure."""
    try:
        resp = await client.get(
            DISRUPTION_ESTIMATE_URL,
            params={"id": situation_id},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError):
        return None


async def fetch_estimates(
    situation_ids: Iterable[str],
    client: httpx.AsyncClient,
) -> dict[str, object]:
    """Fetch disruption estimates for many situations concurrently.

    Returns a dict keyed by situation id; a situation whose estimate cannot be
    fetched maps to None. Never raises — failures are swallowed per situation.
    """
    ids = sorted({sid for sid in situation_ids if sid})
    if not ids:
        return {}
    results = await asyncio.gather(*(_fetch_one(client, sid) for sid in ids))
    return dict(zip(ids, results))


async def fetch_impact(
    client: httpx.AsyncClient,
    from_stop: str,
    to_stop: str | None = None,
    at: str | None = None,
) -> dict[str, object]:
    """Fetch per-situation impact predictions for a corridor.

    A single call to ``/impact`` scores the trains the passenger's trip depends
    on — ``from_stop`` (boarding) → optional ``to_stop`` (alighting), as NSR
    stop place IDs (e.g. ``NSR:StopPlace:337``) — and returns the situations
    affecting it, each with a departure (and, when ``to_stop`` is given,
    arrival) prediction. ``at`` is the intended departure time (ISO 8601) used
    to pick, per line, the affected train closest to it; defaults to now when
    omitted.

    Returns a dict keyed by SIRI-SX situationNumber so it lines up with the
    situation entries built in ``analyse()``; each value is that situation's
    impact object. Returns {} on any upstream failure or when nothing affects
    the trip — never raises.
    """
    params = {"from_stop": from_stop}
    if to_stop:
        params["to_stop"] = to_stop
    if at:
        params["at"] = at
    try:
        resp = await client.get(DISRUPTION_IMPACT_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {}
    situations = data.get("situations") if isinstance(data, dict) else None
    return {
        sit["situation_number"]: sit
        for sit in (situations or [])
        if isinstance(sit, dict) and sit.get("situation_number")
    }
