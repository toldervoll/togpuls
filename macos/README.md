# Togpuls — macOS menylinje-app

En liten menylinje-app som viser neste togavganger, avvik og situasjoner fra
Togpuls rett i menylinjen. Poller hvert 30. sekund — samme rytme som selve
dashbordet.

Den støtter to visninger, byttes fra menyen:

- **Stasjon (alle avganger)** — alle avganger fra valgt stasjon
- **Korridor (fra → til)** — kun avganger som går mot en valgt destinasjon

Tittelen viser risikoprikk + neste avgang og status, f.eks. `🟡 L1 16:24 +6`
(linje L1 kl. 16:24, 6 min forsinket). Prikken gjenspeiler situasjonsbildet
(🟢 lav / 🟡 middels / 🔴 høy risiko).

## Kom i gang

```bash
cd macos
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python togpuls_bar.py
```

Appen dukker opp i menylinjen øverst til høyre. Velg **Avslutt** i menyen for
å stoppe den.

## Konfigurasjon

Settes med miljøvariabler (alle valgfrie):

| Variabel | Standard | Forklaring |
|----------|----------|------------|
| `TOGPULS_BASE_URL`   | `https://togpuls.kengu.no` | API-host |
| `TOGPULS_STOP_PLACE` | `NSR:StopPlace:337` (Oslo S) | «Fra»-stasjon |
| `TOGPULS_TO_PLACE`   | _(tom)_ | «Til»-stasjon — settes for korridor, tom = alle avganger |
| `TOGPULS_HORIZON`    | `60` | Tidsvindu framover i minutter |
| `TOGPULS_POLL_SEC`   | `30` | Oppdateringsintervall |

Eksempel — korridor Oslo S → Lillestrøm, 90 min vindu:

```bash
TOGPULS_TO_PLACE=NSR:StopPlace:451 TOGPULS_HORIZON=90 python togpuls_bar.py
```

Fra- og til-stasjon kan også byttes direkte fra menyen (undermenyene **Fra**
og **Til**), som fylles fra `/api/v1/stations`. Velg `Alle avganger` under
**Til** for å gå tilbake til stasjonsvisning.

## Hva vises i menyen

- **Neste avganger** — tid, linje, destinasjon og status (i rute / +N min / innstilt)
- **Avvik** — antall innstilte og forsinkede (>3 min) i tidsvinduet
- **Situasjoner** — antall, hvor mange med høy risiko, og de viktigste først
- Tidspunkt for siste oppdatering

Data hentes fra `GET /api/v1/analysis/{from}[/to/{to}]?horizon_min=…` (åpent API,
ingen autentisering). HTTP gjøres med `urllib` fra standardbiblioteket, så den
eneste avhengigheten er `rumps` (selve menylinje-rammeverket).

## Bygg en standalone .app

For en dobbeltklikkbar app uten terminal/venv:

```bash
cd macos
python3 -m venv .venv && source .venv/bin/activate   # bruk Homebrew/python.org Python
pip install -r requirements.txt py2app
python setup.py py2app
```

Resultatet havner i `dist/Togpuls.app`. `LSUIElement=True` gjør den til en ren
menylinje-app uten dock-ikon. Flytt den til `/Applications` og legg den evt. til
i *Systeminnstillinger → Generelt → Oppstartsobjekter* for autostart.

> **NB:** Bygg med Homebrew- eller python.org-Python. Xcode/CommandLineTools sin
> Python 3.9 har ikke et signerbart framework, og py2app feiler på codesign-steget.
