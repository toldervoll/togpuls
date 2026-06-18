"""HTTP client for the experimental Entur disruptions enrichment service."""

from __future__ import annotations

import os

import httpx

DISRUPTIONS_URL = os.environ.get(
    "DISRUPTIONS_URL",
    "https://kix-avvik-disruptions-305411154596.europe-west1.run.app",
)
HEADERS = {"ET-Client-Name": "kengu-togpuls"}


async def fetch_disruptions(client: httpx.AsyncClient | None = None) -> dict:
    """Fetch today's active and recently-reopened disruptions.

    Returns the parsed JSON from GET /disruptions. Raises RuntimeError on
    non-2xx responses or JSON decode errors so callers can swallow it cleanly.
    """
    async def _get(c: httpx.AsyncClient) -> dict:
        resp = await c.get(
            f"{DISRUPTIONS_URL}/disruptions",
            headers=HEADERS,
            timeout=8.0,
        )
        resp.raise_for_status()
        return resp.json()

    if client is None:
        async with httpx.AsyncClient() as c:
            return await _get(c)
    return await _get(client)
