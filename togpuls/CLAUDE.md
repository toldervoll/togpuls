# togpuls

Sanntidsanalyse av togtrafikk ved norske stasjoner (default Oslo S), basert på
Entur Journey Planner v3. FastAPI-backend + vanilla JS-frontend i én container.

## Kjøring

```sh
# fra repo-rot (mappen over denne pakken)
uvicorn togpuls.api.app:app --reload      # utvikling, http://localhost:8000
python -m togpuls.serve                    # som i prod
python -m togpuls.main                     # CLI-analyse til stdout
docker build -f togpuls/Dockerfile -t togpuls . && docker run --rm -p 8000:8000 togpuls
```

Avhengigheter: `pip install -r requirements.txt` (fastapi, httpx, uvicorn).
Ingen database, ingen byggsteg for frontend.

## Arkitektur

| Fil/mappe | Ansvar |
|---|---|
| `api/app.py` | FastAPI-app, ruter, `COMMON_STATIONS`, CORS, no-cache for static |
| `api/cache.py` | `TTLCache` (20 s) — dedupliserer samtidige forespørsler per nøkkel |
| `clients/journey_planner.py` | HTTP mot Journey Planner v3 (GraphQL), `ET-Client-Name` |
| `queries/stop_place_query.py` | GraphQL-spørringen |
| `analysis.py` | All domenelogikk: situasjoner, kanselleringer, forsinkelser, timeline |
| `capacity.py`, `occupancy.py` | Kapasitets- og passasjermodell |
| `models.py` | TypedDicts for analyseresultatet |
| `static/` | Frontend: `index.html`, `app.js`, `styles.css` — poller API hvert 30 s |
| `design/` | Designspesifikasjoner og mockups (HTML) — fasit ved UI-arbeid |
| `deploy/` | DigitalOcean App Platform: `app.yaml` + `DEPLOY.md` |

API-ruter: `/` (widget), `/api/v1/health`, `/api/v1/stations`,
`/api/v1/analysis[/{stop}[/to/{to}]]?horizon_min=90`.

## Konvensjoner

- Krever Python ≥ 3.12: `models.py` bruker `typing.TypedDict` som
  respons-typer, og pydantic/FastAPI avviser dem på eldre versjoner
  (da kreves `typing_extensions.TypedDict`). Dockerfile bruker 3.12-slim.
- `from __future__ import annotations` i alle moduler, typehints overalt.
- Stasjons-IDer er NSR stop place-IDer slik Journey Planner emitterer dem i
  `serviceJourney.quays[].stopPlace.id`. Geocoder-IDer er IKKE kompatible —
  ikke bytt kilde (se kommentar ved `COMMON_STATIONS`).
- Frontend er rammeverksfri: ikke innfør React/byggsteg. `app.js` finner
  elementer via id-er i `index.html`; endrer du markup, oppdater app.js i
  samme commit.
- Lys/mørk tema styres av `data-theme` på `<html>` + CSS-variabler i
  `styles.css`. Tema persisteres i localStorage før stylesheet lastes
  (inline script i `index.html`) — ikke flytt dette.
- UI-endringer: sjekk `design/` for gjeldende spesifikasjon først
  (nå: `design/header-spec.md` + `design/header-mockup.html`).

## Verifisering

Det finnes ingen testsuite ennå. Minimum før en endring anses ferdig:

1. `python -m compileall togpuls` går rent (fra repo-rot: gjelder pakken).
2. Start appen og sjekk `GET /api/v1/health` og `GET /api/v1/analysis`.
3. UI-endringer: test lys + mørk modus og 375 px-, 700 px- og
   1200 px-viewport.

## Fallgruver

- Upstream-feil fra Entur skal bli HTTP 502 (`httpx.HTTPError` /
  `RuntimeError` fanges i `_compute_analysis`) — ikke la dem boble som 500.
- `TTLCache` er per prosess. Kjør én instans; skaler vertikalt.
- Tidshåndtering bruker lokal tidssone (`datetime.now().astimezone()`).
  Containeren kjører UTC; Journey Planner returnerer offsets, så det er OK,
  men vær varsom med naive datetimes i ny kode.
