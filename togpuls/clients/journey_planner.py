"""HTTP client for the Entur Journey Planner v3 GraphQL API."""

from __future__ import annotations

import os

import httpx

from togpuls.queries.stop_place_query import (
    STOP_PLACE_DEPARTURES_QUERY,
    stop_place_variables,
)

JOURNEY_PLANNER_URL = os.environ.get(
    "JOURNEY_PLANNER_URL",
    "https://api.entur.io/journey-planner/v3/graphql",
)
HEADERS = {
    "ET-Client-Name": "kengu-togpuls",
    "Content-Type": "application/json",
}


async def _post(client: httpx.AsyncClient, query: str, variables: dict) -> dict:
    resp = await client.post(
        JOURNEY_PLANNER_URL,
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30.0,
    )
    resp.raise_for_status()
    body = resp.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]


async def query_stop_place_departures(
    stop_place_id: str,
    num_departures_per_quay: int = 80,
    time_range_seconds: int = 5400,
    start_time: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch estimated calls grouped by quay at a stop place in one request."""
    variables = stop_place_variables(
        stop_place_id, num_departures_per_quay, time_range_seconds, start_time
    )
    if client is None:
        async with httpx.AsyncClient() as c:
            return await _post(c, STOP_PLACE_DEPARTURES_QUERY, variables)
    return await _post(client, STOP_PLACE_DEPARTURES_QUERY, variables)
