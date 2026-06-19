"""FastAPI app exposing the togpuls analysis as HTTP."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from togpuls.analysis import analyse, build_timeline, collect_situation_ids
from togpuls.api.cache import TTLCache
from togpuls.clients.disruptions import fetch_estimates
from togpuls.clients.journey_planner import query_stop_place_departures
from togpuls.models import Analysis

DEFAULT_STOP_PLACE_ID = "NSR:StopPlace:337"  # Oslo S
DEFAULT_HORIZON_MIN = 90
TIMELINE_SPAN_MIN = 90
TIMELINE_BUCKET_MIN = 5
CACHE_TTL_SECONDS = 20.0

# Common stations — IDs taken from the IDs that the Journey Planner actually
# emits in `serviceJourney.quays[].stopPlace.id` (the Entur geocoder returns
# sibling NSR IDs for the same physical station, which do NOT match these and
# would yield empty corridors).
COMMON_STATIONS: dict[str, str] = {
    "NSR:StopPlace:337": "Oslo S",
    "NSR:StopPlace:451": "Lillestrøm",
    "NSR:StopPlace:269": "Oslo lufthavn",
    "NSR:StopPlace:418": "Asker",
    "NSR:StopPlace:11": "Drammen",
    "NSR:StopPlace:127": "Ski",
    "NSR:StopPlace:192": "Halden",
    "NSR:StopPlace:136": "Skien",
    "NSR:StopPlace:548": "Bergen",
    "NSR:StopPlace:596": "Stavanger",
    "NSR:StopPlace:659": "Trondheim S",
}

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

_cache = TTLCache(ttl_seconds=CACHE_TTL_SECONDS)

# Shared query parameter: how far ahead departures are fetched, in minutes.
HorizonMin = Annotated[
    int,
    Query(
        ge=10,
        le=360,
        description="Tidshorisont i minutter — hvor langt fram avganger hentes.",
    ),
]

# ── Risk-tier helpers ──────────────────────────────────────────────────────
# Order risk tiers worst-first. Lower rank = more severe.
_TIER_RANK = {"high": 0, "medium": 1, "low": 2}


def _tier_from_rates(cancel_rate: float, trouble_rate: float) -> str | None:
    """Tier implied by the rates drawn as LED meters.

    Thresholds are anchored to the meters' "full" points (CANCEL_RATE_FULL =
    0.10, TROUBLE_RATE_FULL = 0.30 in static/app.js) so the tier word can never
    sit lower than the bars suggest. Keep these in sync with those constants.
    """
    if cancel_rate >= 0.10 or trouble_rate >= 0.30:  # a meter is full
        return "high"
    if cancel_rate >= 0.05 or trouble_rate >= 0.15:  # a meter >= ~half
        return "medium"
    return None


def _worse(*tiers: str | None) -> str | None:
    """Return the most severe of the given tiers, ignoring None."""
    cands = [t for t in tiers if t]
    if not cands:
        return None
    return min(cands, key=lambda t: _TIER_RANK.get(t, 99))


# ── Event clustering / supersession ─────────────────────────────────────────
# Sibling messages of one incident (e.g. a cancellation plus its "take the next
# train" advice) are issued seconds apart, so a tight onset window groups them
# without chaining unrelated incidents that merely share a busy trunk line.
SIBLING_ONSET_MIN = 5
# An all-clear may arrive well after the incident it resolves; allow this gap
# between their onsets when deciding what it supersedes.
RESOLVE_ONSET_MIN = 120

# An "all clear" / normalisation message. Used (with reportType=general) to
# detect that an event is being resolved. Substring match across no/en phrasing.
_ALL_CLEAR_RX = re.compile(
    r"(normal|som normalt|opph[øo]rt|igjen|gjenoppr|tilbake til normal|"
    r"cleared|resolved|back to normal|running again)",
    re.IGNORECASE,
)


def _parse_onset(estimate: object) -> datetime | None:
    """Parse the KIX estimate's `onset` ISO timestamp; None if absent/invalid."""
    if not isinstance(estimate, dict):
        return None
    raw = estimate.get("onset")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_all_clear(sit: dict) -> bool:
    """A general (informational) message whose text signals normalisation."""
    if (sit.get("report_type") or "").lower() != "general":
        return False
    text = f"{sit.get('summary') or ''} {sit.get('description') or ''}"
    return bool(_ALL_CLEAR_RX.search(text))


def _forward_recovered(lines: set[str], by_line: dict) -> bool:
    """True when the given lines show no medium+ disruption in the forward window."""
    relevant = [l for l in lines if l in by_line]
    fwd_scheduled = sum(by_line[l]["future_scheduled"] for l in relevant)
    if not fwd_scheduled:
        return True  # nothing scheduled ahead → nothing left to disrupt
    fwd_cancelled = sum(by_line[l]["future_cancelled"] for l in relevant)
    fwd_delayed = sum(by_line[l]["future_delayed_gt_3min"] for l in relevant)
    return _tier_from_rates(
        fwd_cancelled / fwd_scheduled,
        (fwd_cancelled + fwd_delayed) / fwd_scheduled,
    ) is None


def _resolve_superseded(situations: list[dict], by_line: dict) -> list[dict]:
    """Drop situations an all-clear has resolved (supersession), decoupled from
    clustering.

    An all-clear is "confirmed" when live forward data shows its own lines have
    recovered. A confirmed all-clear hides itself and any situation whose lines
    are a *subset* of its lines (so a trunk-line all-clear can't sweep away
    unrelated incidents), gated by onset proximity and the incident's own
    forward recovery.
    """
    confirmed = []
    for s in situations:
        if not _is_all_clear(s):
            continue
        lines = set(s.get("paavirker_linjer") or [])
        if lines and _forward_recovered(lines, by_line):
            confirmed.append((id(s), lines, _parse_onset(s.get("estimate"))))
    if not confirmed:
        return situations

    confirmed_ids = {cid for cid, _, _ in confirmed}
    tol = RESOLVE_ONSET_MIN * 60
    keep = []
    for s in situations:
        if id(s) in confirmed_ids:
            continue  # the confirmed all-clear itself is resolved info — hide it
        s_lines = set(s.get("paavirker_linjer") or [])
        s_onset = _parse_onset(s.get("estimate"))
        drop = False
        for _, ac_lines, ac_onset in confirmed:
            if not s_lines or not s_lines.issubset(ac_lines):
                continue
            if s_onset and ac_onset and abs((s_onset - ac_onset).total_seconds()) > tol:
                continue
            if not _forward_recovered(s_lines, by_line):
                continue
            drop = True
            break
        if not drop:
            keep.append(s)
    return keep


def _cluster_situations(situations: list[dict]) -> list[dict]:
    """Tag each situation with an `event_id` grouping sibling messages.

    Conservative on purpose: merge only identical summaries, or messages that
    overlap on lines AND share a reportType AND were issued within a tight onset
    window — the signature of one incident's sibling messages. This avoids
    chaining unrelated incidents that merely share a busy trunk line.
    """
    n = len(situations)
    if n == 0:
        return situations

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    info = []
    for s in situations:
        info.append((
            set(s.get("paavirker_linjer") or []),
            _parse_onset(s.get("estimate")),
            (s.get("summary") or "").strip().casefold(),
            (s.get("report_type") or "").lower(),
        ))

    tol = SIBLING_ONSET_MIN * 60
    for i in range(n):
        li, oi, si, ri = info[i]
        for j in range(i + 1, n):
            lj, oj, sj, rj = info[j]
            if si and si == sj:  # identical summary text
                union(i, j)
            elif (
                li & lj and ri == rj and oi and oj
                and abs((oi - oj).total_seconds()) <= tol
            ):  # sibling: shared lines + same type + issued together
                union(i, j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)
    for members in clusters.values():
        event_id = min(
            (situations[i].get("situation_number") or situations[i].get("id") or "")
            for i in members
        )
        for i in members:
            situations[i]["event_id"] = event_id
    return situations


def _cluster_and_resolve(situations: list[dict], by_line: dict) -> list[dict]:
    """Supersession then clustering: hide what an all-clear resolved, then group
    the survivors' sibling messages and tag them with an event_id."""
    return _cluster_situations(_resolve_superseded(situations, by_line))


def _recompute_affected(analysis: dict) -> None:
    """Re-derive passenger_estimate's affected-line aggregates after clustering.

    `analyse()` builds affected_lines / affected_passengers from the full SX set
    before clustering. Once resolved events are hidden, those aggregates are
    stale (they still count the hidden corridor), so the prose summary would
    report more lines/passengers than the cards show. Rebuild them from the
    surviving situations.
    """
    pax = analysis.get("passenger_estimate")
    if not isinstance(pax, dict):
        return
    line_sits: dict[str, set[str]] = defaultdict(set)
    for s in analysis.get("situations", []):
        num = s.get("situation_number") or s.get("id") or ""
        for l in s.get("paavirker_linjer") or []:
            line_sits[l].add(num)
    affected_pax = 0
    for row in pax.get("by_line", []):
        sits_here = line_sits.get(row["linje"])
        row["affected"] = bool(sits_here)
        row["affecting_situations"] = sorted(sits_here) if sits_here else []
        if sits_here:
            affected_pax += row.get("passengers_realised", 0)
    pax["affected_lines"] = sorted(line_sits.keys())
    pax["affected_passengers"] = int(affected_pax)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        yield


API_DESCRIPTION = """
Sanntidsanalyse av togtrafikk for norske stasjoner (standard Oslo S), bygget på
[Entur Journey Planner v3](https://developer.entur.org/pages-journeyplanner-journeyplanner).

API-et henter avganger fram og tilbake i tid, slår sammen avvik (SIRI-situasjoner)
og KIX-estimater, og returnerer en samlet `Analysis`: risikonivå, innstillings- og
forsinkelsesrater, passasjer-/kapasitetsmodell, tidslinje og aktive situasjoner.

Alle analyse-endepunkt deler samme svarformat og tar `horizon_min` som styrer hvor
langt fram avgangene hentes (standard 90 minutter). Stasjons-ID-er er NSR stop place-ID-er
slik Journey Planner emitterer dem — se `/api/v1/stations` for de vanligste.
""".strip()

TAGS_METADATA = [
    {"name": "analysis", "description": "Samlet trafikkanalyse for en stasjon eller en strekning."},
    {"name": "reference", "description": "Oppslagsdata: stasjonsliste og helsesjekk."},
]

app = FastAPI(
    title="togpuls",
    version="1.0.0",
    description=API_DESCRIPTION,
    summary="Sanntids togtrafikkanalyse basert på Entur Journey Planner v3.",
    openapi_tags=TAGS_METADATA,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    contact={"name": "Entur", "url": "https://entur.org"},
    license_info={"name": "NLOD", "url": "https://data.norge.no/nlod/no/2.0"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/about", "/sw.js") or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


async def _compute_analysis(
    stop_place_id: str,
    horizon_min: int,
    to_stop_place_id: str | None = None,
) -> Analysis:
    client: httpx.AsyncClient = app.state.http_client
    now = datetime.now().astimezone()
    past_start = (now - timedelta(minutes=TIMELINE_SPAN_MIN)).isoformat()

    try:
        future_task = query_stop_place_departures(
            stop_place_id=stop_place_id,
            num_departures_per_quay=80,
            time_range_seconds=horizon_min * 60,
            client=client,
        )
        past_task = query_stop_place_departures(
            stop_place_id=stop_place_id,
            num_departures_per_quay=80,
            time_range_seconds=TIMELINE_SPAN_MIN * 60,
            start_time=past_start,
            client=client,
        )
        future_response, past_response = await asyncio.gather(future_task, past_task)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {exc}") from exc
    except RuntimeError as exc:
        # _post raises RuntimeError on GraphQL errors
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not future_response.get("stopPlace"):
        raise HTTPException(
            status_code=404,
            detail=(
                f"No stopPlace returned for id={stop_place_id!r}. "
                "Check the ID (Oslo S is NSR:StopPlace:337)."
            ),
        )

    situation_ids = collect_situation_ids(future_response) | collect_situation_ids(
        past_response
    )
    estimates = await fetch_estimates(situation_ids, client)

    to_name = COMMON_STATIONS.get(to_stop_place_id) if to_stop_place_id else None
    analysis = analyse(
        future_response,
        now=now,
        horizon_min=horizon_min,
        to_stop_place_id=to_stop_place_id,
        to_name=to_name,
        past_response=past_response,
        look_back_min=TIMELINE_SPAN_MIN,
        estimates=estimates,
    )
    analysis["timeline"] = build_timeline(
        past_response, future_response,
        now=now,
        span_before_min=TIMELINE_SPAN_MIN,
        span_after_min=TIMELINE_SPAN_MIN,
        bucket_min=TIMELINE_BUCKET_MIN,
        to_stop_place_id=to_stop_place_id,
    )

    # Tier reconciliation and fallback enrichment.
    #
    # The left chip (tier word) and the two LED meters (cancel_rate /
    # trouble_rate) must never disagree: a viewer reads near-full bars as
    # "serious", so the tier can never read lower than the bars imply.
    #
    # For situations WITHOUT a KIX estimate: derive cancel_rate / trouble_rate
    # and the tier from train_movements.by_line, so meters and tier both render
    # from current data.
    #
    # For situations WITH a KIX estimate: floor the KIX alert_tier to whatever
    # the rates actually drawn as bars imply (KIX's own rates), and to any
    # worse live data. KIX tier is a historical baseline; it must not show as
    # lower risk than its own bars — or than what is happening right now.
    #
    # Informational messages (SIRI reportType=general, e.g. an "all clear")
    # inherit corridor deviation rates from the incident they describe, so they
    # are kept as plain low/info UNLESS KIX *and* live forward data agree the
    # lines are still actively disrupted — only then are they treated like an
    # incident. This is handled per-situation in the loop below.
    # (_tier_from_rates / _worse are module-level helpers.)
    by_line = {
        lm["linje"]: lm
        for lm in analysis.get("train_movements", {}).get("by_line", [])
    }
    for sit in analysis.get("situations", []):
        report_type = (sit.get("report_type") or "").lower()
        affected = [l for l in sit.get("paavirker_linjer", []) if l in by_line]

        # Window-total live rates (past + future), used to floor incident tiers.
        scheduled = sum(by_line[l]["scheduled"] for l in affected)
        rt_cancel = rt_trouble = None
        rt_tier = None
        if scheduled:
            cancelled = sum(by_line[l]["cancelled"] for l in affected)
            delayed = sum(by_line[l]["delayed_gt_3min"] for l in affected)
            rt_cancel = cancelled / scheduled
            rt_trouble = (cancelled + delayed) / scheduled
            rt_tier = _tier_from_rates(rt_cancel, rt_trouble)

        # Forward-only live rates (now → horizon). A line that has recovered
        # shows no forward disruption even if its window total is still high.
        fwd_scheduled = sum(by_line[l]["future_scheduled"] for l in affected)
        fwd_tier = None
        if fwd_scheduled:
            fwd_cancelled = sum(by_line[l]["future_cancelled"] for l in affected)
            fwd_delayed = sum(by_line[l]["future_delayed_gt_3min"] for l in affected)
            fwd_tier = _tier_from_rates(
                fwd_cancelled / fwd_scheduled,
                (fwd_cancelled + fwd_delayed) / fwd_scheduled,
            )

        est = sit.get("estimate")
        alert = est.get("alert") if isinstance(est, dict) else None
        if not isinstance(alert, dict):
            alert = None

        # Tier implied by KIX's own rates — the ones drawn as bars.
        kix_tier = None
        if alert is not None:
            kc, kt = alert.get("cancel_rate"), alert.get("trouble_rate")
            if isinstance(kc, (int, float)) and isinstance(kt, (int, float)):
                kix_tier = _tier_from_rates(kc, kt)

        # Informational messages (reportType=general) inherit corridor deviation
        # rates from the incident they describe — e.g. an "all clear" like
        # "Normal hastighet" carries the same KIX rates as the cancellation it
        # resolves. Keep these as plain low/info UNLESS KIX *and* live forward
        # data agree the lines are still actively disrupted; only then treat the
        # message like an incident. KIX or live alone is not enough.
        if report_type == "general" and not (kix_tier and fwd_tier):
            if alert is not None:
                for k in ("cancel_rate", "trouble_rate", "alert_tier"):
                    alert.pop(k, None)
            continue

        if est is None:
            # No KIX estimate: build the alert from live data so meters and
            # tier both render from current movements.
            if not scheduled:
                continue
            new_alert: dict = {"cancel_rate": rt_cancel, "trouble_rate": rt_trouble}
            if rt_tier:
                new_alert["alert_tier"] = rt_tier
            sit["estimate"] = {"alert": new_alert}
            continue

        if not isinstance(est, dict):
            continue
        # Incident (or a confirmed general): floor the tier to its own drawn
        # rates and to any worse live data, so the tier word never reads lower
        # than the bars.
        if alert is None:
            alert = {}
        cur_tier = (alert.get("alert_tier") or "").lower() or None
        new_tier = _worse(cur_tier, kix_tier, rt_tier)
        if new_tier and new_tier != cur_tier:
            alert["alert_tier"] = new_tier
            est["alert"] = alert

    # Cluster the (tier-reconciled) situations into events, drop events an
    # all-clear has resolved, and tag survivors with an event_id.
    analysis["situations"] = _cluster_and_resolve(
        analysis.get("situations", []), by_line
    )
    # Keep affected-line / passenger aggregates in sync with the survivors.
    _recompute_affected(analysis)

    return analysis


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/about", include_in_schema=False)
async def about() -> FileResponse:
    return FileResponse(STATIC_DIR / "about.html")


@app.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    # Served from the root so its scope covers the entire site, not just /static/.
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get(
    "/api/v1/health",
    tags=["reference"],
    summary="Helsesjekk",
    description="Returnerer `{\"ok\": true}` når tjenesten kjører. Brukes til liveness/readiness.",
    response_description="Tjenesten er oppe.",
)
async def health() -> dict:
    return {"ok": True}


@app.get(
    "/api/v1/stations",
    tags=["reference"],
    summary="List vanlige stasjoner",
    description=(
        "De vanligste stasjonene med NSR stop place-ID og navn. ID-ene her er "
        "garantert kompatible med analyse-endepunktene (Entur-geocoderens søsken-ID-er er det ikke)."
    ),
    response_description="Liste av `{id, name}`.",
)
async def stations() -> list[dict]:
    return [{"id": k, "name": v} for k, v in COMMON_STATIONS.items()]


@app.get(
    "/api/v1/analysis",
    tags=["analysis"],
    summary="Analyse for Oslo S (standard)",
    description=(
        "Samlet trafikkanalyse for standardstasjonen Oslo S "
        f"(`{DEFAULT_STOP_PLACE_ID}`). Snarvei for `/api/v1/analysis/{{stop_place_id}}`."
    ),
    response_description="Samlet `Analysis` for stasjonen.",
)
async def analysis_default(horizon_min: HorizonMin = DEFAULT_HORIZON_MIN) -> Analysis:
    return await _cache.get_or_compute(
        (DEFAULT_STOP_PLACE_ID, None, horizon_min),
        lambda: _compute_analysis(DEFAULT_STOP_PLACE_ID, horizon_min),
    )


@app.get(
    "/api/v1/analysis/{stop_place_id}/to/{to_stop_place_id}",
    tags=["analysis"],
    summary="Strekningsanalyse (fra → til)",
    description=(
        "Analyse for `stop_place_id` filtrert til avganger som betjener strekningen "
        "mot `to_stop_place_id`. Begge er NSR stop place-ID-er (se `/api/v1/stations`)."
    ),
    response_description="Samlet `Analysis` begrenset til strekningen.",
)
async def analysis_corridor(
    stop_place_id: str,
    to_stop_place_id: str,
    horizon_min: HorizonMin = DEFAULT_HORIZON_MIN,
) -> Analysis:
    return await _cache.get_or_compute(
        (stop_place_id, to_stop_place_id, horizon_min),
        lambda: _compute_analysis(stop_place_id, horizon_min, to_stop_place_id),
    )


@app.get(
    "/api/v1/analysis/{stop_place_id}",
    tags=["analysis"],
    summary="Analyse for en stasjon",
    description=(
        "Samlet trafikkanalyse for én stasjon, angitt med NSR stop place-ID "
        "(f.eks. Oslo S = `NSR:StopPlace:337`; se `/api/v1/stations`)."
    ),
    response_description="Samlet `Analysis` for stasjonen.",
)
async def analysis_for(stop_place_id: str, horizon_min: HorizonMin = DEFAULT_HORIZON_MIN) -> Analysis:
    return await _cache.get_or_compute(
        (stop_place_id, None, horizon_min),
        lambda: _compute_analysis(stop_place_id, horizon_min),
    )
