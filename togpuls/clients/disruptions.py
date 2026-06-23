"""HTTP client for the disruption-impact service.

Predicts cancellation probability and delay for the SIRI situations on a
from→to corridor. Best-effort enrichment: any upstream failure maps to an
empty result so a flaky impact service never breaks the analysis.
"""

from __future__ import annotations

import httpx

DISRUPTION_ESTIMATE_URL = "http://localhost:8008/impact"


async def fetch_estimates(
    client: httpx.AsyncClient,
    from_stop: str | None,
    to_stop: str | None = None,
) -> dict[str, object]:
    """Fetch disruption impact predictions for a corridor.

    A single request to the /impact endpoint returns predictions for every
    SIRI situation on the ``from_stop`` → ``to_stop`` corridor. The stops are
    NSR stop place IDs (e.g. ``NSR:StopPlace:337``); ``to_stop`` is None when
    no destination is selected (all directions).

    Returns a dict keyed by ``situation_number`` — the same key `analyse()`
    looks up — with each value being that situation's entry from the response
    (its ``summary`` plus ``departure_prediction`` / ``arrival_prediction``).
    Returns {} when there is no origin to query, or on any upstream failure.
    Never raises — failures are swallowed.
    """
    if not from_stop:
        return {}
    params = {"from_stop": from_stop}
    if to_stop:
        params["to_stop"] = to_stop
    try:
        resp = await client.get(DISRUPTION_ESTIMATE_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return {}

    situations = payload.get("situations") if isinstance(payload, dict) else None
    if not isinstance(situations, list):
        return {}
    return {
        sit["situation_number"]: sit
        for sit in situations
        if isinstance(sit, dict) and sit.get("situation_number")
    }
