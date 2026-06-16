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
