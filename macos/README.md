# Togpuls — macOS menylinje-app

En liten menylinje-app som viser sanntidsstatus fra Togpuls rett i menylinjen,
med detaljer i nedtrekksmenyen. Poller hvert 30. sekund — samme rytme som
selve dashbordet.

Tittelen viser en risikoprikk + innstilte/forsinkede avganger, f.eks.
`🟡 2✖ 7⏱` (gul risiko, 2 innstilt, 7 forsinket >3 min).

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
| `TOGPULS_STOP_PLACE` | `NSR:StopPlace:337` (Oslo S) | Hvilken stasjon |
| `TOGPULS_HORIZON`    | `60` | Tidsvindu framover i minutter |
| `TOGPULS_POLL_SEC`   | `30` | Oppdateringsintervall |

Eksempel — Lillestrøm, 90 min vindu:

```bash
TOGPULS_STOP_PLACE=NSR:StopPlace:451 TOGPULS_HORIZON=90 python togpuls_bar.py
```

Stasjon kan også byttes direkte fra menyen (undermenyen **Stasjon**), som
fylles fra `/api/v1/stations`.

## Hva vises i menyen

- Avganger kjørt / planlagt, innstilte, forsinkede >3 min
- Median- og p90-forsinkelse
- De mest berørte linjene
- Antall situasjoner og de med høy risiko (`alert_tier = high`)
- Estimert antall berørte og strandede reisende
- Tidspunkt for siste oppdatering

Data hentes fra `GET /api/v1/analysis/{stop_place}?horizon_min=…` (åpent API,
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

## Kjør automatisk ved innlogging (valgfritt)

Pakk inn som en `launchd`-agent, eller bygg en `.app` med
[`py2app`](https://py2app.readthedocs.io/) og legg den i
*Systeminnstillinger → Generelt → Oppstartsobjekter*.
