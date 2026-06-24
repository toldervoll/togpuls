# macOS menylinje-app (togpuls_bar.py)

Liten `rumps`-app som viser neste togavganger i menylinja. Bygges til en
standalone `.app` med py2app.

## Bygg og kjør

- `make macos-run` — kjør fra kildekode. Rask test, men Dock-ikonet vises som
  Python og varslinger kan være tause (ingen ordentlig bundle).
- `make macos-app` — bygg `macos/dist/Togpuls.app`. Bruk denne for å vurdere
  ikon, varslinger og endelig oppførsel. `open macos/dist/Togpuls.app`.

## Synlighet i menylinja (notch)

macOS skjuler status items når menylinja går tom for plass (særlig med notch).
Det finnes ikke noe API som tvinger et plass-skjult ikon tilbake. Tiltakene i
appen:

- Smal tittel. Holdes kort (`🟢L1 5m`, ikke `🟢 L1 5 min`) — brede items ofres
  først. Settes i `_status_lines`.
- `autosaveName` + `isVisible` settes lazy i `_configure_status_item()`, kalt
  fra `refresh`. NSStatusItem finnes først etter at `run()` har startet, og
  ligger på `self._nsapp.nsstatusitem`.
- Reservveier inn til menyen når ikonet er skjult: Dock-meny, app-menyen og
  global hurtigtast (under).
- «Vis i statusmenyen» er en av/på-bryter (hake) i alle tre menyene. Valget
  huskes via NSUserDefaults-nøkkelen `ShowStatusItem` (lest i `__init__`,
  brukt i `_configure_status_item`). Tilbakemelding kun når det er nyttig: PÅ +
  fortsatt skjult etter ~1s → modal (`rumps.alert`, `_toggle_on_modal_once`)
  som peker på reserveveiene. PÅ + faktisk synlig → ingen melding. AV → ingen
  melding (bevisst valg). Ingen notifikasjoner — appen bruker ikke
  UserNotifications/rumps-varsler i det hele tatt.
- Deteksjon av skjult ikon: `_status_item_hidden()` er en heuristikk (macOS
  har ingen offisiell API; `isVisible` er bare intensjon). Den ser på
  status-knappens vindu — `occlusionState` uten `Visible`-biten, eller
  `frame.origin.x <= 0`. Brukes kun av modalen ved på-slåing.

## Dock-ikon og Dock-meny

`_enable_dock_and_hotkey()` (kalt fra `__main__` før `run()`):

- Setter aktiveringspolicy til Regular, så appen får Dock-ikon (og plass i
  ⌘+Tab). `LSUIElement: False` i `setup.py` gir det samme i den bygde appen.
- Bytter `rumps.rumps.NSApp` til en subklasse `_DockNSApp` som implementerer
  `applicationDockMenu_`. Reassign av modul-globalen virker fordi `run()`
  slår opp `NSApp` ved kalltid. Dock-menyen bygges i `build_dock_menu()`.
- Setter app-ikonet ved kjøretid via `setApplicationIconImage_`, så ikonet
  vises også fra kildekode. Den bygde appen bruker uansett `iconfile`.

## Menyer og handlinger

`_action_menuitems()` er den felles lista med handlinger («Åpne i vindu» =
embedded webview, «Åpne på nett» = ekstern nettleser, «Oppdater nå» =
`refresh_now` (henter menydata + relaster webviewen; 30s-timeren reloader
ikke webviewen), Fra/Til, «Vis i statusmenyen»). Den brukes tre steder, med
ferske MenuItem-er hver gang (en NSMenuItem kan bare ligge i én meny):

- Statusmenyen (NSStatusItem): statuslinjer øverst + handlingene under.
- Dock-menyen: `build_dock_menu()`.
- Hoved-menylinja (`setMainMenu_` i `_configure_app_menu()`, fylt av
  `_populate_app_menu(status_lines)` hver refresh) har to oppføringer:
  1. «Togpuls» (CFBundleName): kun handlinger + «Avslutt Togpuls».
  2. En status-meny der tittelen er status-ikon + tekst (`self.title`) og
     nedtrekket er statuslinjene — duplikat av NSStatusItem-menyen, men uten
     handlinger. Gjør avgangsinfoen tilgjengelig i menylinja når status-ikonet
     er skjult bak notchen.
  NSStatusItem-menyen beholder statuslinjer + handlinger som før.

`_status_menuitems(status_lines)` er felles bygger for statuslinjene
(avganger/situasjoner), brukt i både statusmenyen og app-menyen. Header-linja
bytter retning i korridor-modus.

## Global hurtigtast

⌃⌥⌘T popper statusmenyen opp sentrert på skjermen (`popup_menu_centered`, bruker
`nsmenu.size()` + hovedskjermens midtpunkt), også når tray-ikonet er skjult. Bruker Carbon `RegisterEventHotKey` via ctypes —
krever INGEN Tilgjengelighet-tillatelse (i motsetning til NSEvent-globale
monitorer). Overstyr med `TOGPULS_HOTKEY_KEYCODE` / `TOGPULS_HOTKEY_MODS`.
Carbon-modifikatorbitene er IKKE de samme som Cocoa/NSEvent. Sett alltid
eksplisitte ctypes-signaturer (`restype`/`argtypes`) — ellers trunkeres
64-bits pekere til 32 bit og appen krasjer. Registreringen feiler stille om
Carbon mangler; appen kjører videre uten hurtigtast.

## Dashbord-vindu (innebygd webview)

`open_window()` åpner et NSWindow med en `WKWebView` som laster dashbordet med
gjeldende rute (`_dashboard_url()`). Pålitelig vei inn som ikke avhenger av
menylinja. Vinduet gjenbrukes (`setReleasedWhenClosed_(False)`). Tilgjengelig
fra «Åpne i vindu» i statusmenyen og Dock-menyen, og ved klikk på Dock-ikonet
(`applicationShouldHandleReopen_hasVisibleWindows_` på `_DockNSApp`). Krever
`pyobjc-framework-WebKit` i `macos/requirements.txt` — endring der trigger
re-install av venv ved neste `make macos-app`.

Fra/Til holdes i synk begge veier:

- Meny → webview: `_sync_webview()` (kalt fra `refresh`) setter `location.hash`
  når ruten endres. Dashbordets `hashchange`-lytter (app.js) re-applikerer
  ruten uten full reload. `_route_hash()` er felles kilde for fragmentet.
- Webview → meny: dashbordet bruker `replaceState` (ingen hashchange/popstate),
  så `_RouteObserver` (KVO på `WKWebView.URL`) fanger endringen og
  `_apply_webview_route()` speiler den til `from_id`/`to_id` + `refresh`.
  `_route_from_hash()` er motsatt av `_route_hash()`. KVO ignoreres til
  `webView_didFinishNavigation_` har satt `_route_ready` (unngår forbigående
  URL-er under første last).

Begge veier er no-op når ruten er uendret, så det blir ingen ekko-loop og
30-sekunders-pollingen trigger ingen unødvendig oppdatering.

## App-ikon

`macos/assets/Togpuls.icns` er rendret fra `togpuls/static/icons/icon.svg`
(multi-størrelse, opp til 1024px). Koblet inn via `iconfile` i `setup.py`.

## Deling og distribusjon

Distribusjonen står på tre ben: GitHub Releases med DMG, et Homebrew
Cask-tap, og ad-hoc-signering. Det er ingen Apple Developer-konto i
spill, så ingen Developer ID og ingen notarisering — vi jobber rundt
Gatekeeper med `xattr`.

### DMG-en (`make macos-dmg`)

Bygger `macos/dist/Togpuls-<versjon>.dmg`. Avhenger av `create-dmg`
(`brew install create-dmg`). DMG-vinduet har Togpuls-ikonet og en
Applications-symlenke, pluss en `Installer.command` som brukeren
dobbeltklikker etter at app-en er dratt over. Scriptet kjører `xattr
-dr com.apple.quarantine` på app-en og starter den. Bakgrunnsbildet
genereres av `macos/installer/render_dmg_background.py` (Pillow) første
gang `macos-dmg` kjøres, og caches deretter.

App-en signeres ad-hoc (`codesign --sign -`) før DMG-en pakkes —
påkrevd for at arm64-binærer i det hele tatt skal kjøre, gir ingen
Gatekeeper-godkjenning.

### Release-workflowen

`.github/workflows/release.yml` kjører på tag-push (`v*`) eller manuelt.
Den skriver tag-versjonen til `VERSION`, kjører `make macos-dmg` på en
`macos-14`-runner, regner ut SHA256 og oppretter en GitHub Release med
DMG-en som asset. Releasen sin beskrivelse inneholder installasjons-
stegene og SHA256-en — sistnevnte brukes til å oppdatere Cask-en.

### Homebrew Cask

Cask-fila ligger i et separat repo, `kengu/homebrew-togpuls`, og brukes
slik:

    brew tap kengu/togpuls
    brew install --cask togpuls

Cask-en peker på DMG-en i siste release. En `postflight`-blokk fjerner
quarantine fra `Togpuls.app` etter install, så brew-veien gir ingen
Gatekeeper-dialoger. Når en ny release publiseres må `Casks/togpuls.rb`
oppdateres med ny `version` og `sha256` — manuelt for nå, kan
automatiseres med en bump-action senere.

### Versjon

Én kilde: `VERSION` i repo-rot. Leses av `macos/setup.py`
(`CFBundleVersion` / `CFBundleShortVersionString`) og av Makefile
(`MACOS_DMG`-navnet). Release-workflowen overskriver fila med tag-
versjonen før bygg, så lokale bygg og CI-bygg er aldri uenige.

### Direktelink-fallback

For brukere som henter DMG-en fra GitHub uten Homebrew: dra app-en til
Applications, dobbeltklikk `Installer.command` i DMG-vinduet. Den
manuelle nødløsningen er `xattr -dr com.apple.quarantine
/Applications/Togpuls.app` etterfulgt av å åpne app-en.
