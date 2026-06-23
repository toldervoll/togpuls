"""HTTP client for the disruption-estimate service.

Estimates how long a SIRI situation will last. Best-effort enrichment: any
upstream failure maps to None so a flaky estimate service never breaks the
analysis.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx

DISRUPTION_ESTIMATE_URL = (
    "https://kix-avvik-disruptions-305411154596.europe-west1.run.app/situation"
)


async def _fetch_one(
    client: httpx.AsyncClient,
    situation_id: str,
    from_stop: str | None,
    to_stop: str | None,
):
    """Fetch one estimate; return None on any upstream failure."""
    params = {"id": situation_id}
    if from_stop:
        params["from_stop"] = from_stop
    if to_stop:
        params["to_stop"] = to_stop
    try:
        resp = await client.get(
            DISRUPTION_ESTIMATE_URL,
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError):
        return None


async def fetch_estimates(
    situation_ids: Iterable[str],
    client: httpx.AsyncClient,
    from_stop: str | None = None,
    to_stop: str | None = None,
) -> dict[str, object]:
    """Fetch disruption estimates for many situations concurrently.

    ``from_stop`` and ``to_stop`` are the corridor the user selected, as NSR
    stop place IDs (e.g. ``NSR:StopPlace:337``); they are passed to the
    estimate service so it can scope the estimate to that origin/destination.
    ``to_stop`` is None when no destination is selected (all directions).

    Returns a dict keyed by situation id; a situation whose estimate cannot be
    fetched maps to None. Never raises — failures are swallowed per situation.
    """
    ids = sorted({sid for sid in situation_ids if sid})
    if not ids:
        return {}
    results = await asyncio.gather(
        *(_fetch_one(client, sid, from_stop, to_stop) for sid in ids)
    )
    return dict(zip(ids, results))
