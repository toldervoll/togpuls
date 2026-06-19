# togpuls

Live situation analyser for **Oslo Sentralstasjon (Oslo S)** — the hub of the
Norwegian rail network. Ingests SIRI-SX situation messages and the live
departure board from Entur's Journey Planner v3 in a single GraphQL request,
then derives a four-block analysis: active situations, train movements
(scheduled / realised / cancelled / delays), capacity vs schedule, modelled
passenger throughput, and per-platform utilisation.

Ships as an HTTP API, a zero-build web widget, and a one-shot CLI.

## Quick start

Requires Python 3.12+ and `make`.

```bash
make configure   # one-time: creates venv, installs deps
make serve       # starts the API + widget on http://localhost:8000
```

Open <http://localhost:8000/> in a browser. The widget polls the API every
30 seconds; the API caches upstream calls for 20 seconds so concurrent
clients share one Journey Planner fetch.

## Endpoints

| Method | Path                                              | Returns                                                     |
|--------|---------------------------------------------------|-------------------------------------------------------------|
| `GET`  | `/`                                               | The widget                                                  |
| `GET`  | `/api/v1/health`                                  | `{"ok": true}`                                              |
| `GET`  | `/api/v1/analysis?horizon_min=90`                 | Analysis for Oslo S (`NSR:StopPlace:337`)                   |
| `GET`  | `/api/v1/analysis/{stop_place_id}?horizon_min=90` | Analysis for any NSR stop place                             |

Unknown stop place → `404`. Upstream GraphQL or HTTP failures → `502`.

## CLI

For ad-hoc inspection without running the server:

```bash
make cli                                              # JSON to stdout
./venv/bin/python -m togpuls.main --format text       # human summary
./venv/bin/python -m togpuls.main --horizon-min 60    # shorter window
./venv/bin/python -m togpuls.main --stop-place-id NSR:StopPlace:59872
```

The CLI emits exactly the same JSON shape as the API.

## Configuration

| Env var                | Default                                              | Purpose                                |
|------------------------|------------------------------------------------------|----------------------------------------|
| `TOGPULS_HOST`         | `0.0.0.0`                                            | uvicorn bind host                      |
| `TOGPULS_PORT`         | `8000`                                               | uvicorn bind port                      |
| `JOURNEY_PLANNER_URL`  | `https://api.entur.io/journey-planner/v3/graphql`    | Override OTP endpoint for testing      |

Example: `TOGPULS_PORT=9090 make serve`.

## Architecture

One GraphQL request to Journey Planner v3 fans out over every quay
(platform) at the stop place; the response carries aimed/expected times,
cancellation flags, and SIRI-SX situations per estimated call. The
`analyse()` function in `togpuls/analysis.py` then produces the `Analysis`
TypedDict (see `togpuls/models.py`) in a single pass over the response. The
FastAPI app in `togpuls/api/app.py` wraps that pipeline with a small async
TTL cache so polling clients don't multiply upstream load.

## Make targets

```text
make help        # list targets
make configure   # create venv, install deps (idempotent)
make serve       # run the API + widget
make cli         # run the CLI (JSON to stdout)
make clean       # remove the venv
make macos-run   # run the macOS menu bar app from source
make macos-app   # build standalone macos/dist/Togpuls.app
make macos-clean # remove the macOS venv + build artifacts
```

## macOS menu bar app

A small menu bar app (`macos/`) showing next departures, deviations and
situations live from the API. Build it with `make macos-app`, and see
[macos/README.md](macos/README.md) for details — including how to start it
automatically at login (as a Login Item, or via a launchd agent).

## Data source

Entur Journey Planner v3, called with `ET-Client-Name: kengu-togpuls`.
See <https://developer.entur.org/> for the upstream API.
