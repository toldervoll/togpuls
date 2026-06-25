"""HTTP client for the disruption-impact service.

Predicts how the situations affecting a from→to corridor impact the trains a
passenger's trip depends on (cancellation probability and delay at the boarding
and alighting stops). Best-effort enrichment: any upstream failure maps to an
empty dict so a flaky service never breaks the analysis.
"""

from __future__ import annotations

import httpx

DISRUPTION_ESTIMATE_URL = (
    "https://kix-avvik-disruptions-305411154596.europe-west1.run.app/impact"
)


async def fetch_estimates(
    client: httpx.AsyncClient,
    from_stop: str,
    to_stop: str | None = None,
    at: str | None = None,
) -> dict[str, object]:
    """Fetch per-situation impact predictions for a corridor.

    A single call to /impact scores the trains the passenger's trip depends on
    — ``from_stop`` (boarding) → optional ``to_stop`` (alighting), as NSR stop
    place IDs (e.g. ``NSR:StopPlace:337``) — and returns the situations
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
        resp = await client.get(
            DISRUPTION_ESTIMATE_URL,
            params=params,
            timeout=10.0,
        )
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
