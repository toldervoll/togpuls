# Deploy til DigitalOcean App Platform

togpuls er én stateless FastAPI-container uten database. Den henter data fra
Entur Journey Planner v3 ved forespørsel (TTL-cache 20 s) og serverer
frontend fra `static/`.

## Forutsetninger

- Repoet ligger på GitHub og DigitalOcean har tilgang
  (App Platform → Settings → GitHub).
- Filplassering: `Dockerfile`, `requirements.txt` og `deploy/` ligger i
  pakkemappen `togpuls/`. Stier i `app.yaml` er relative til **repo-rot**
  (mappen over pakken). Bygg-konteksten er repo-rot.

## Førstegangsoppsett

1. Rediger `deploy/app.yaml`: sett riktig `repo: <github-bruker>/togpuls`.
2. Opprett appen:

   ```sh
   doctl apps create --spec togpuls/deploy/app.yaml
   ```

   Alternativt i UI: Create App → velg repoet → «Edit App Spec» → lim inn
   innholdet i `app.yaml`.
3. Vent på bygg. Appen får en `*.ondigitalocean.app`-URL med TLS.

## Senere deploys

`deploy_on_push: true` gjør at push til `main` bygger og deployer automatisk.
Spec-endringer: `doctl apps update <app-id> --spec togpuls/deploy/app.yaml`.

## Verifisering

- `GET /api/v1/health` → `{"ok": true}` (samme endepunkt brukes som
  health check av App Platform).
- `GET /` skal vise widgeten.
- `GET /api/v1/analysis` skal returnere analyse for Oslo S.

## Kostnad og skalering

- `basic-xxs` (512 MB, delt vCPU, ~5 USD/mnd) er nok: appen holder ingen
  state og trafikken begrenses av klient-polling (30 s) + serverside-cache.
- Ved behov: bump `instance_size_slug`, ikke `instance_count`
  (cachen er per instans).

## Miljøvariabler

| Variabel | Default | Beskrivelse |
|---|---|---|
| `TOGPULS_HOST` | `0.0.0.0` | Bind-adresse |
| `TOGPULS_PORT` | `8000` | Port (må matche `http_port` i spec) |
| `JOURNEY_PLANNER_URL` | Entur prod | Overstyr Journey Planner-endepunkt |

Entur-API-et krever ingen nøkkel, men `ET-Client-Name`-headeren er satt til
`entur-togpuls` i `clients/journey_planner.py`. Endre den hvis appen får
nytt navn/eierskap.

## Lokal docker-test

```sh
# fra repo-rot
docker build -f togpuls/Dockerfile -t togpuls .
docker run --rm -p 8000:8000 togpuls
open http://localhost:8000
```
