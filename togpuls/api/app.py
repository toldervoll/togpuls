"""FastAPI app exposing the togpuls analysis as HTTP."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
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
}

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

_cache = TTLCache(ttl_seconds=CACHE_TTL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        yield


app = FastAPI(title="togpuls", lifespan=lifespan)

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
    if path == "/" or path == "/sw.js" or path.startswith("/static"):
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

    # Real-time tier derivation and fallback enrichment.
    #
    # For situations WITHOUT a KIX estimate: derive cancel_rate / trouble_rate
    # and a real-time alert_tier from train_movements.by_line so the LED meters
    # and tier label both render from current data.
    #
    # For situations WITH a KIX estimate: elevate the KIX alert_tier when the
    # real-time cancel_rate is worse than the historical norm implies. KIX tier
    # is a historical baseline; active cancellations on affected lines should
    # never show as lower risk than what is actually happening.
    _TIER_RANK = {"high": 0, "medium": 1, "low": 2}

    def _realtime_tier(cancel_rate: float) -> str | None:
        if cancel_rate >= 0.3:
            return "high"
        if cancel_rate > 0:
            return "medium"
        return None

    by_line = {
        lm["linje"]: lm
        for lm in analysis.get("train_movements", {}).get("by_line", [])
    }
    for sit in analysis.get("situations", []):
        affected = [l for l in sit.get("paavirker_linjer", []) if l in by_line]
        scheduled = sum(by_line[l]["scheduled"] for l in affected)
        if not scheduled:
            continue
        cancelled = sum(by_line[l]["cancelled"] for l in affected)
        delayed = sum(by_line[l]["delayed_gt_3min"] for l in affected)
        cancel_rate = cancelled / scheduled
        trouble_rate = (cancelled + delayed) / scheduled
        rt_tier = _realtime_tier(cancel_rate)

        if sit.get("estimate") is None:
            alert: dict = {"cancel_rate": cancel_rate, "trouble_rate": trouble_rate}
            if rt_tier:
                alert["alert_tier"] = rt_tier
            sit["estimate"] = {"alert": alert}
        elif rt_tier:
            # Elevate KIX tier if real-time data is worse.
            alert = (sit["estimate"] or {}).get("alert") or {}
            cur_tier = (alert.get("alert_tier") or "").lower()
            if _TIER_RANK.get(rt_tier, 99) < _TIER_RANK.get(cur_tier, 99):
                alert["alert_tier"] = rt_tier

    return analysis


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    # Served from the root so its scope covers the entire site, not just /static/.
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/api/v1/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/api/v1/stations")
async def stations() -> list[dict]:
    return [{"id": k, "name": v} for k, v in COMMON_STATIONS.items()]


@app.get("/api/v1/analysis")
async def analysis_default(horizon_min: int = DEFAULT_HORIZON_MIN) -> Analysis:
    return await _cache.get_or_compute(
        (DEFAULT_STOP_PLACE_ID, None, horizon_min),
        lambda: _compute_analysis(DEFAULT_STOP_PLACE_ID, horizon_min),
    )


@app.get("/api/v1/analysis/{stop_place_id}/to/{to_stop_place_id}")
async def analysis_corridor(
    stop_place_id: str,
    to_stop_place_id: str,
    horizon_min: int = DEFAULT_HORIZON_MIN,
) -> Analysis:
    return await _cache.get_or_compute(
        (stop_place_id, to_stop_place_id, horizon_min),
        lambda: _compute_analysis(stop_place_id, horizon_min, to_stop_place_id),
    )


@app.get("/api/v1/analysis/{stop_place_id}")
async def analysis_for(stop_place_id: str, horizon_min: int = DEFAULT_HORIZON_MIN) -> Analysis:
    return await _cache.get_or_compute(
        (stop_place_id, None, horizon_min),
        lambda: _compute_analysis(stop_place_id, horizon_min),
    )
