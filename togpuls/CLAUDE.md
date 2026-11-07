# togpuls

Real-time train traffic analysis for Norwegian stations (default Oslo S),
based on Entur Journey Planner v3. FastAPI backend + vanilla JS frontend in
a single container.

## Running

```sh
# from the repo root (the directory above this package)
uvicorn togpuls.api.app:app --reload      # development, http://localhost:8000
python -m togpuls.serve                    # as in production
python -m togpuls.main                     # CLI analysis to stdout
docker build -f togpuls/Dockerfile -t togpuls . && docker run --rm -p 8000:8000 togpuls
```

Dependencies: `pip install -r requirements.txt` (fastapi, httpx, uvicorn).
No database, no frontend build step.

## Architecture

| File/directory | Responsibility |
|---|---|
| `api/app.py` | FastAPI app, routes, `COMMON_STATIONS`, CORS, no-cache for static |
| `api/cache.py` | `TTLCache` (20 s) — deduplicates concurrent requests per key |
| `clients/journey_planner.py` | HTTP against Journey Planner v3 (GraphQL), `ET-Client-Name` |
| `clients/journey_status.py` | Best-effort read of kix-avvik `notification-api/v1/journey-status` (Vy/SJ train status for a from→to route); `None` on any failure, max 6 reads/min per stop pair |
| `queries/stop_place_query.py` | The GraphQL query |
| `analysis.py` | All domain logic: situations, cancellations, delays, timeline |
| `capacity.py`, `occupancy.py` | Capacity and passenger model |
| `models.py` | TypedDicts for the analysis result |
| `static/` | Frontend: `index.html`, `app.js`, `styles.css` — polls the API every 30 s |
| `design/` | Design specs and mockups (HTML) — source of truth for UI work |
| `deploy/` | DigitalOcean App Platform: `app.yaml` + `DEPLOY.md` |

API routes: `/` (widget), `/api/v1/health`, `/api/v1/stations`,
`/api/v1/analysis[/{stop}[/to/{to}]]?horizon_min=90`.

## Conventions

- Requires Python ≥ 3.12: `models.py` uses `typing.TypedDict` as response
  types, and pydantic/FastAPI reject them on older versions (which require
  `typing_extensions.TypedDict`). The Dockerfile uses 3.12-slim.
- `from __future__ import annotations` in every module, type hints everywhere.
- Station IDs are NSR stop place IDs as Journey Planner emits them in
  `serviceJourney.quays[].stopPlace.id`. Geocoder IDs are NOT compatible —
  do not switch the source (see the comment at `COMMON_STATIONS`).
- The frontend is framework-free: do not introduce React or a build step.
  `app.js` looks up elements by ids in `index.html`; if you change markup,
  update app.js in the same commit.
- Light/dark theme is driven by `data-theme` on `<html>` + CSS variables in
  `styles.css`. The theme is persisted to localStorage before the stylesheet
  loads (inline script in `index.html`) — do not move this.
- UI changes: check `design/` for the current spec first
  (currently `design/header-spec.md` + `design/header-mockup.html`).

## Verification

Minimum before a change is considered done (from the repo root):

1. `python -m compileall togpuls` passes cleanly.
2. `python -m unittest discover -s tests` passes (stdlib only; no pytest).
3. Start the app and check `GET /api/v1/health` and `GET /api/v1/analysis`.
4. UI changes: test light + dark mode and 375 px, 700 px and 1200 px
   viewports.

## Pitfalls

- Upstream errors from Entur must become HTTP 502 (`httpx.HTTPError` /
  `RuntimeError` are caught in `_compute_analysis`) — do not let them bubble
  up as 500.
- `TTLCache` is per process. Run one instance; scale vertically.
- Time handling uses the local timezone (`datetime.now().astimezone()`).
  The container runs UTC; Journey Planner returns offsets, so this is fine,
  but be careful with naive datetimes in new code.
