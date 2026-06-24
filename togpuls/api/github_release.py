"""Slå opp siste macOS-release fra GitHub.

Holder GitHub-spesifikkene unna ``app.py``. Tag-prefiks ``macos-v`` matcher
``make macos-release`` så vi ikke plukker opp andre tags (om en annen
leveransekanal får egen versjonering senere).
"""

from __future__ import annotations

import httpx

GITHUB_REPO = "kengu/togpuls"
RELEASE_TAG_PREFIX = "macos-v"
DMG_EXTENSION = ".dmg"


async def latest_macos_release(client: httpx.AsyncClient) -> dict | None:
    """Returnerer metadata om siste macOS-release, eller None.

    Slår opp ``GET /repos/{repo}/releases`` (siste først) og finner den
    første releasen med tag som starter på ``macos-v`` og som har en
    DMG-asset. ``None`` om GitHub ikke svarer, ingen slik release finnes,
    eller releasen mangler DMG.

    Cachen ligger i ``app.py`` (TTLCache) — denne funksjonen er ren henting.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    headers = {"Accept": "application/vnd.github+json"}

    try:
        resp = await client.get(url, headers=headers, timeout=10.0)
    except httpx.HTTPError:
        return None

    if resp.status_code != 200:
        return None

    try:
        releases = resp.json()
    except ValueError:
        return None
    if not isinstance(releases, list):
        return None

    for release in releases:
        tag = release.get("tag_name") or ""
        if not tag.startswith(RELEASE_TAG_PREFIX):
            continue
        if release.get("draft") or release.get("prerelease"):
            continue
        for asset in release.get("assets") or []:
            name = asset.get("name") or ""
            if name.endswith(DMG_EXTENSION):
                return {
                    "version": tag[len(RELEASE_TAG_PREFIX):],
                    "tag": tag,
                    "url": asset["browser_download_url"],
                    "dmg_filename": name,
                    "size": asset.get("size"),
                    "published_at": release.get("published_at"),
                    "release_url": release.get("html_url"),
                }
    return None
