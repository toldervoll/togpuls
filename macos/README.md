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

Enklest via `make` fra repo-roten:

```bash
make macos-run     # kjør fra kildekode
make macos-app     # bygg standalone macos/dist/Togpuls.app
make macos-clean   # fjern venv + byggeartefakter
```

Appen dukker opp i menylinjen øverst til høyre. Velg **Avslutt** i menyen for
å stoppe den.

> `make`-targetene lager en egen venv i `macos/.venv` med et framework-Python
> (standard `python3.12`). Overstyr med f.eks. `make macos-app MACOS_PY=python3.13`.

Manuelt, uten `make`:

```bash
cd macos
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python togpuls_bar.py
```

## Konfigurasjon

Settes med miljøvariabler (alle valgfrie):

| Variabel | Standard | Forklaring |
|----------|----------|------------|
| `TOGPULS_BASE_URL`   | `https://togpuls.kengu.no` | API-host |
| `TOGPULS_STOP_PLACE` | `NSR:StopPlace:337` (Oslo S) | «Fra»-stasjon |
| `TOGPULS_TO_PLACE`   | _(tom)_ | «Til»-stasjon — settes for korridor, tom = alle avganger |
| `TOGPULS_HORIZON`    | `90` | Tidsvindu framover i minutter |
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
- **Avvik** — antall innstilte og forsinkede (>3 min), med en liste over de
  faktiske avgangene (innstilte først, så verste forsinkelser)
- **Situasjoner** — antall, hvor mange med høy risiko, og de viktigste først,
  med berørte linjer og årsak per situasjon
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
menylinje-app uten dock-ikon. Flytt den til `/Applications`.

> **NB:** Bygg med Homebrew- eller python.org-Python. Xcode/CommandLineTools sin
> Python 3.9 har ikke et signerbart framework, og py2app feiler på codesign-steget.

## Autostart ved innlogging

To måter — velg én.

### A) Som .app via Oppstartsobjekter (enklest)

Bygg `.app`-en, flytt den til `/Applications`, og legg den til som
oppstartsobjekt. Via grensesnittet:

*Systeminnstillinger → Generelt → Oppstartsobjekter → Åpne ved innlogging → «+»*
og velg `Togpuls.app`.

Eller fra terminalen:

```bash
make macos-app
cp -R macos/dist/Togpuls.app /Applications/
osascript -e 'tell application "System Events" to make login item \
  at end with properties {path:"/Applications/Togpuls.app", hidden:true}'
```

Fjern igjen med:

```bash
osascript -e 'tell application "System Events" to delete login item "Togpuls"'
```

### B) Fra kildekode via launchd (uten .app)

Kjører menylinje-appen rett fra venv-et, og starter den på nytt om den
stopper (`KeepAlive`). Lag `~/Library/LaunchAgents/no.kengu.togpuls.menubar.plist`
— bytt ut `<REPO>` med den absolutte stien til dette repoet:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>            <string>no.kengu.togpuls.menubar</string>
  <key>ProgramArguments</key>
  <array>
    <string><REPO>/macos/.venv/bin/python</string>
    <string><REPO>/macos/togpuls_bar.py</string>
  </array>
  <key>RunAtLoad</key>        <true/>
  <key>KeepAlive</key>        <true/>
  <!-- valgfri konfig, f.eks. korridor: -->
  <key>EnvironmentVariables</key>
  <dict>
    <key>TOGPULS_TO_PLACE</key><string>NSR:StopPlace:451</string>
  </dict>
</dict>
</plist>
```

Aktiver (og start nå):

```bash
launchctl load -w ~/Library/LaunchAgents/no.kengu.togpuls.menubar.plist
```

Slå av og fjern:

```bash
launchctl unload -w ~/Library/LaunchAgents/no.kengu.togpuls.menubar.plist
rm ~/Library/LaunchAgents/no.kengu.togpuls.menubar.plist
```

Forutsetter at venv-et finnes (`make macos-run` eller `make configure` én gang).
Konfigurer ellers via `EnvironmentVariables` i plist-en — ikke skallets miljø,
siden launchd ikke leser `~/.zshrc`.
