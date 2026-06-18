# Deploying to DigitalOcean App Platform

togpuls is a single stateless FastAPI container with no database. It fetches
data from Entur Journey Planner v3 on request (20 s TTL cache) and serves
the frontend from `static/`.

## Prerequisites

- The repo is on GitHub and DigitalOcean has access
  (App Platform → Settings → GitHub).
- File locations: `requirements.txt` lives in the repo root; `Dockerfile`
  and `deploy/` live in the package directory `togpuls/`. Paths in
  `app.yaml` are relative to the **repo root**. The build context is the
  repo root.

## First-time setup

1. Edit `deploy/app.yaml`: verify `repo: kengu/togpuls`.
2. Create the app:

   ```sh
   doctl apps create --spec togpuls/deploy/app.yaml
   ```

   Alternatively in the UI: Create App → pick the repo → "Edit App Spec" →
   paste the contents of `app.yaml`.
3. Wait for the build. The app gets a `*.ondigitalocean.app` URL with TLS.

## Subsequent deploys

`deploy_on_push: true` means a push to `main` builds and deploys
automatically. Spec changes:
`doctl apps update <app-id> --spec togpuls/deploy/app.yaml`.

## Verification

- `GET /api/v1/health` → `{"ok": true}` (the same endpoint is used as the
  App Platform health check).
- `GET /` should show the widget.
- `GET /api/v1/analysis` should return the Oslo S analysis.

## Cost and scaling

- `basic-xxs` (512 MB, shared vCPU, ~5 USD/month) is enough: the app holds
  no state and traffic is bounded by client polling (30 s) + the
  server-side cache.
- If needed: bump `instance_size_slug`, not `instance_count`
  (the cache is per instance).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TOGPULS_HOST` | `0.0.0.0` | Bind address |
| `TOGPULS_PORT` | `8000` | Port (must match `http_port` in the spec) |
| `JOURNEY_PLANNER_URL` | Entur prod | Override the Journey Planner endpoint |

The Entur API requires no key, but the `ET-Client-Name` header is set to
`kengu-togpuls` in `clients/journey_planner.py`. Change it if the app gets
a new name or owner.

## Local docker test

```sh
# from the repo root
docker build -f togpuls/Dockerfile -t togpuls .
docker run --rm -p 8000:8000 togpuls
open http://localhost:8000
```
