#!/usr/bin/env python3
"""Togpuls menylinje-app for macOS.

Viser neste togavganger, avvik og situasjoner fra Togpuls-API-et i
menylinjen. Støtter både én stasjon (alle avganger) og en korridor
(fra → til). Poller hvert 30. sekund — samme rytme som dashbordet.

Konfigurasjon via miljøvariabler (alle valgfrie):
    TOGPULS_BASE_URL   standard https://togpuls.kengu.no
    TOGPULS_STOP_PLACE standard NSR:StopPlace:337 (Oslo S) — «fra»
    TOGPULS_TO_PLACE   standard tom (= alle avganger); sett for korridor
    TOGPULS_HORIZON    standard 90 (minutter framover)
    TOGPULS_POLL_SEC   standard 30
"""

import json
import os
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

import rumps
from Foundation import NSObject

BASE_URL = os.environ.get("TOGPULS_BASE_URL", "https://togpuls.kengu.no").rstrip("/")
FROM_PLACE = os.environ.get("TOGPULS_STOP_PLACE", "NSR:StopPlace:337")
TO_PLACE = os.environ.get("TOGPULS_TO_PLACE", "") or None
HORIZON_MIN = int(os.environ.get("TOGPULS_HORIZON", "90"))
POLL_SEC = int(os.environ.get("TOGPULS_POLL_SEC", "30"))

TIER_DOT = {"high": "🔴", "medium": "🟡", "low": "🟢"}
TIER_RANK = {"high": 3, "medium": 2, "low": 1}
# Effektiv alvorsrang, jf. SEVERITY_RANK + effSevRank() i static/app.js:
# alert-tier overstyrer SIRI-severity. Lav rang = verre.
SEVERITY_RANK = {"hoy": 0, "middels": 1, "lav": 2, "ukjent": 3}
RANK_DOT = {0: "🔴", 1: "🟡", 2: "🟢"}  # ellers ▪︎ (ukjent)
ALL_LABEL = "Alle avganger"

# Dashbordet speiler ruten i URL-hash: #<fra>-<til> (kun tallet i NSR-id-en),
# #<fra> for kun fra-stasjon, og ingen hash for Oslo S uten retning (jf.
# syncUrl() i static/app.js). Vi bygger samme hash for «Åpne dashbord».
STOP_PLACE_PREFIX = "NSR:StopPlace:"
DASHBOARD_DEFAULT_FROM = "NSR:StopPlace:337"  # Oslo S — URL holdes ren her

# Zero-width space — gjør ellers like menytitler unike så rumps ikke slår dem sammen.
ZWS = "​"


class _RouteObserver(NSObject):
    """KVO-observatør på WKWebView.URL. Dashbordet bruker replaceState (fyrer
    ikke hashchange/popstate), men URL-property-en oppdateres og er
    KVO-observerbar — så her fanger vi rute-endringer gjort inne i webviewen."""

    def observeValueForKeyPath_ofObject_change_context_(self, keyPath, obj, change, context):
        app = getattr(rumps.App, "*app_instance", None)
        if app is None or not getattr(app, "_route_ready", False):
            return  # ignorer forbigående URL-er under første innlasting
        url = obj.URL()
        frag = url.fragment() if url is not None else None
        app._apply_webview_route(frag)

    def webView_didFinishNavigation_(self, webView, navigation):
        # Først etter at siden er ferdig lastet stoler vi på URL-endringer.
        app = getattr(rumps.App, "*app_instance", None)
        if app is not None:
            app._route_ready = True


class TogpulsBar(rumps.App):
    def __init__(self):
        super().__init__("🚆 …", quit_button=None)
        self.from_id = FROM_PLACE
        self.from_name = "Oslo S"
        self.to_id = TO_PLACE
        self.to_name = None
        self.stations = self._load_stations()
        self._name_lookup()
        # Husket valg: skal status-ikonet vises? Standard True.
        from Foundation import NSUserDefaults
        d = NSUserDefaults.standardUserDefaults()
        self._status_visible = (
            True if d.objectForKey_("ShowStatusItem") is None
            else bool(d.boolForKey_("ShowStatusItem"))
        )
        self.timer = rumps.Timer(self.refresh, POLL_SEC)
        self.timer.start()
        self.refresh(None)

    # ---- HTTP ----------------------------------------------------------

    @staticmethod
    def _get(path, params=None, timeout=12):
        url = f"{BASE_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"User-Agent": "togpuls-macos-bar/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)

    def _load_stations(self):
        try:
            return self._get("/api/v1/stations", timeout=10)
        except Exception:
            return []

    def _name_lookup(self):
        """Sett lesbare navn fra stasjonslista hvis vi bare har id-er."""
        by_id = {s.get("id"): s.get("name") for s in self.stations}
        self.from_name = by_id.get(self.from_id, self.from_name)
        if self.to_id:
            self.to_name = by_id.get(self.to_id, self.to_id)

    # ---- meny: fra / til -----------------------------------------------

    def _from_submenu(self):
        sub = rumps.MenuItem(f"Fra: {self.from_name}")
        for st in self.stations:
            sid, name = st.get("id"), st.get("name")
            if not sid:
                continue
            item = rumps.MenuItem(name, callback=self._set_from(sid, name))
            item.state = 1 if sid == self.from_id else 0
            sub.add(item)
        return sub

    def _to_submenu(self):
        label = self.to_name or ALL_LABEL
        sub = rumps.MenuItem(f"Til: {label}")
        alle = rumps.MenuItem(ALL_LABEL, callback=self._set_to(None, None))
        alle.state = 1 if not self.to_id else 0
        sub.add(alle)
        for st in self.stations:
            sid, name = st.get("id"), st.get("name")
            if not sid or sid == self.from_id:
                continue
            item = rumps.MenuItem(name, callback=self._set_to(sid, name))
            item.state = 1 if sid == self.to_id else 0
            sub.add(item)
        return sub

    def _set_from(self, sid, name):
        def cb(_):
            self.from_id, self.from_name = sid, name
            if self.to_id == sid:  # fra == til gir ikke mening
                self.to_id, self.to_name = None, None
            self.refresh(None)

        return cb

    def _set_to(self, sid, name):
        def cb(_):
            self.to_id, self.to_name = sid, name
            self.refresh(None)

        return cb

    def _configure_status_item(self):
        """Sett autosaveName og bruk det huskede synlighetsvalget. NSStatusItem
        finnes først etter at run() har startet, så vi gjør dette lazy."""
        item = getattr(getattr(self, "_nsapp", None), "nsstatusitem", None)
        if item is None or getattr(self, "_si_configured", False):
            return
        item.setAutosaveName_("TogpulsBar")  # husk plassering mellom omstarter
        item.setVisible_(self._status_visible)
        self._si_configured = True

    def _status_item_hidden(self):
        """Heuristikk for om menylinje-ikonet faktisk ikke vises (macOS har
        ingen offisiell API for dette). isVisible rapporterer kun intensjon.
        Vi ser på status-knappens vindu: occlusionState mister Visible-biten,
        og systemet parkerer skjulte ikoner på x ≤ 0 / utenfor skjerm."""
        item = getattr(getattr(self, "_nsapp", None), "nsstatusitem", None)
        if item is None:
            return False
        button = item.button()
        if button is None:
            return True
        win = button.window()
        if win is None or win.screen() is None:
            return True
        from AppKit import NSWindowOcclusionStateVisible
        if not (win.occlusionState() & NSWindowOcclusionStateVisible):
            return True
        return win.frame().origin.x <= 0

    def toggle_status_item(self, sender):
        """Av/på-bryter for menylinje-ikonet. Valget huskes mellom omstarter.
        Når vi slår PÅ men ikonet likevel ikke dukker opp (full menylinje),
        sier vi fra via en modal. Å slå AV gir ingen melding — det var et
        bevisst valg."""
        self._status_visible = not self._status_visible
        item = getattr(getattr(self, "_nsapp", None), "nsstatusitem", None)
        if item is not None:
            item.setVisible_(self._status_visible)
        from Foundation import NSUserDefaults
        NSUserDefaults.standardUserDefaults().setBool_forKey_(
            self._status_visible, "ShowStatusItem"
        )
        sender.state = 1 if self._status_visible else 0
        if self._status_visible:
            # Sjekk etter at layouten har satt seg; varsle BARE hvis fortsatt
            # skjult (ingen melding når det faktisk dukker opp).
            self._recheck_timer = rumps.Timer(self._toggle_on_modal_once, 1)
            self._recheck_timer.start()

    def _toggle_on_modal_once(self, timer):
        timer.stop()
        if not self._status_item_hidden():
            return  # ikonet dukket opp — ingen melding nødvendig
        try:
            rumps.alert(
                title="Togpuls",
                message=("Menylinja er trolig full, så ikonet vises ikke. Du når "
                         "Togpuls via status-menyen i menylinja, Dock-ikonet "
                         "eller hurtigtasten ⌃⌥⌘T."),
                ok="OK",
            )
        except Exception:
            pass

    def open_window(self, _=None):
        """Åpne (eller hent fram) et vindu med dashbordet i en innebygd
        WKWebView. Uavhengig av menylinja — fungerer alltid."""
        from AppKit import (
            NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable, NSWindowStyleMaskMiniaturizable,
            NSBackingStoreBuffered, NSApplication,
        )
        from Foundation import NSURL, NSURLRequest
        from WebKit import (
            WKWebView, WKWebViewConfiguration,
            WKUserScript, WKUserContentController,
        )

        nsapp = NSApplication.sharedApplication()
        if getattr(self, "_window", None) is not None:
            self._window.makeKeyAndOrderFront_(None)
            nsapp.activateIgnoringOtherApps_(True)
            return

        rect = ((0.0, 0.0), (480.0, 760.0))
        style = (
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable | NSWindowStyleMaskMiniaturizable
        )
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, NSBackingStoreBuffered, False
        )
        win.setTitle_("Togpuls")
        win.setReleasedWhenClosed_(False)  # gjenbruk vinduet ved ny åpning
        win.center()

        # Konfigurér webviewen med en lite JS som settes på window før siden
        # lastes. Dashbordet bruker dette flagget til å skjule «Last ned for
        # Mac»-hero-en — den er meningsløs når brukeren allerede er inne i
        # app-en. WKUserScriptInjectionTimeAtDocumentStart = 0.
        config = WKWebViewConfiguration.alloc().init()
        controller = WKUserContentController.alloc().init()
        controller.addUserScript_(
            WKUserScript.alloc().initWithSource_injectionTime_forMainFrameOnly_(
                "window.__togpulsApp = true;", 0, True,
            )
        )
        config.setUserContentController_(controller)
        web = WKWebView.alloc().initWithFrame_configuration_(rect, config)
        web.setAutoresizingMask_(2 | 16)  # bredde + høyde følger vinduet
        win.setContentView_(web)
        # Observer URL-endringer i webviewen (Fra/Til endret inne i dashbordet).
        self._route_ready = False
        self._route_observer = _RouteObserver.alloc().init()
        web.setNavigationDelegate_(self._route_observer)
        web.addObserver_forKeyPath_options_context_(
            self._route_observer, "URL", 0, None
        )
        web.loadRequest_(
            NSURLRequest.requestWithURL_(NSURL.URLWithString_(self._dashboard_url()))
        )

        win.makeKeyAndOrderFront_(None)
        nsapp.activateIgnoringOtherApps_(True)
        self._window = win
        self._webview = web
        self._synced_hash = self._route_hash()  # lastet allerede med riktig rute

    def _sync_webview(self):
        """Speil gjeldende Fra/Til til den åpne webviewen ved å sette
        location.hash. Dashbordets hashchange-lytter re-applikerer ruten uten
        full reload. No-op hvis ruten er uendret eller vinduet aldri er åpnet."""
        web = getattr(self, "_webview", None)
        if web is None:
            return
        h = self._route_hash()
        if h == getattr(self, "_synced_hash", None):
            return
        web.evaluateJavaScript_completionHandler_(
            f"window.location.hash = {json.dumps(h)};", None
        )
        self._synced_hash = h

    def _route_from_hash(self, frag):
        """Motsatt av _route_hash: gjør et URL-fragment om til (from_id, to_id)
        med fulle NSR-id-er. Tomt fragment = Oslo S, alle avganger."""
        def full(n):
            n = (n or "").strip()
            if not n:
                return None
            return n if n.startswith(STOP_PLACE_PREFIX) else STOP_PLACE_PREFIX + n

        frag = (frag or "").strip()
        if not frag:
            return DASHBOARD_DEFAULT_FROM, None
        parts = frag.split("-")
        frm = full(parts[0]) or DASHBOARD_DEFAULT_FROM
        to = full(parts[1]) if len(parts) > 1 else None
        return frm, to

    def _apply_webview_route(self, frag):
        """Speil en rute valgt inne i webviewen tilbake til menyene og API-et.
        No-op hvis ruten er uendret — bryter ellers ekko-loopen mot
        _sync_webview."""
        frm, to = self._route_from_hash(frag)
        if frm == self.from_id and to == self.to_id:
            return
        self.from_id, self.to_id = frm, to
        by_id = {s.get("id"): s.get("name") for s in self.stations}
        self.from_name = by_id.get(frm, frm)
        self.to_name = by_id.get(to, to) if to else None
        self._synced_hash = self._route_hash()  # vi er alt i synk; ikke ekko
        self.refresh(None)

    def popup_menu_centered(self, _=None):
        """Vis statusmenyen sentrert på skjermen, uavhengig av om menylinje-
        ikonet er synlig. Brukes av den globale hurtigtasten."""
        from AppKit import NSScreen
        nsmenu = getattr(self.menu, "_menu", None)
        if nsmenu is None:
            return
        loc = (0.0, 0.0)
        screen = NSScreen.mainScreen()
        if screen is not None:
            f = screen.frame()
            sz = nsmenu.size()  # menyens dimensjoner, for å sentrere den
            cx = f.origin.x + f.size.width / 2.0
            cy = f.origin.y + f.size.height / 2.0
            # Lokasjonen er menyens øvre venstre hjørne (skjermkoordinater,
            # origo nederst), så menyen faller nedover fra punktet.
            loc = (cx - sz.width / 2.0, cy + sz.height / 2.0)
        nsmenu.popUpMenuPositioningItem_atLocation_inView_(None, loc, None)

    def _action_menuitems(self):
        """Felles handlingsvalg, gjenbrukt i statusmenyen, Dock-menyen og
        app-menyen. Lager ferske MenuItem-er hver gang — en NSMenuItem kan
        bare ligge i én meny om gangen."""
        vis = rumps.MenuItem("Vis i statusmenyen", callback=self.toggle_status_item)
        vis.state = 1 if getattr(self, "_status_visible", True) else 0
        return [
            rumps.MenuItem("Åpne i vindu", callback=self.open_window),
            rumps.MenuItem("Åpne på nett", callback=self.open_dashboard),
            rumps.MenuItem("Oppdater nå", callback=self.refresh_now),
            self._from_submenu(),
            self._to_submenu(),
            vis,
        ]

    def refresh_now(self, _=None):
        """Manuell oppdatering: hent menydata på nytt og relast dashbordet i
        webviewen (om det er åpent). 30-sekunders-timeren reloader ikke
        webviewen — dashbordet poller selv."""
        self.refresh(None)
        web = getattr(self, "_webview", None)
        if web is not None:
            web.reload()

    def build_dock_menu(self):
        """Bygg en fersk NSMenu for Dock-ikonet. macOS legger selv til
        standardvalg (Vis, Avslutt) under disse."""
        from AppKit import NSMenu
        menu = NSMenu.alloc().init()
        self._dock_items = self._action_menuitems()  # hold ref mot GC
        for mi in self._dock_items:
            menu.addItem_(mi._menuitem)
        return menu

    def _configure_app_menu(self):
        """Opprett hoved-menylinja én gang. To oppføringer:
        1) app-menyen «Togpuls» (CFBundleName) — handlinger.
        2) en status-meny der tittelen er status-ikon + tekst og nedtrekket er
           statuslinjene (duplikat av NSStatusItem, uten handlinger).
        Innholdet fylles inn av _populate_app_menu hver refresh."""
        if getattr(self, "_app_menu", None) is not None:
            return
        if getattr(self, "_nsapp", None) is None:
            return  # NSApplication er ikke klar før run() har startet
        from AppKit import NSApplication, NSMenu, NSMenuItem
        main = NSMenu.alloc().init()

        app_item = NSMenuItem.alloc().init()
        main.addItem_(app_item)
        app_menu = NSMenu.alloc().init()
        main.setSubmenu_forItem_(app_menu, app_item)

        status_item = NSMenuItem.alloc().init()
        main.addItem_(status_item)
        status_menu = NSMenu.alloc().init()
        main.setSubmenu_forItem_(status_menu, status_item)

        NSApplication.sharedApplication().setMainMenu_(main)
        self._app_menu = app_menu
        self._app_status_menuitem = status_item
        self._app_status_menu = status_menu

    def _populate_app_menu(self, status_lines):
        if getattr(self, "_app_menu", None) is None:
            return
        from AppKit import NSMenuItem

        # 1) «Togpuls»-menyen: kun handlinger + Avslutt.
        menu = self._app_menu
        menu.removeAllItems()
        self._app_items = self._action_menuitems()  # hold ref mot GC
        for mi in self._app_items:
            menu.addItem_(mi._menuitem)
        menu.addItem_(NSMenuItem.separatorItem())
        quit_item = rumps.MenuItem("Avslutt Togpuls", callback=rumps.quit_application)
        menu.addItem_(quit_item._menuitem)
        self._app_items.append(quit_item)

        # 2) Status-menyen: tittel = status-tekst, innhold = statuslinjene.
        self._app_status_menuitem.setTitle_(self.title or "Togpuls")
        smenu = self._app_status_menu
        smenu.removeAllItems()
        self._app_status_items = self._status_menuitems(status_lines)
        for mi in self._app_status_items:
            smenu.addItem_(mi._menuitem)
        # Vis statuslinjene i full farge (ikke dempet pga. manglende action).
        smenu.setAutoenablesItems_(False)

    def swap_direction(self, _):
        """Bytt fra- og til-stasjon, som swap-pilen i dashbordet."""
        if not self.to_id:
            return
        self.from_id, self.to_id = self.to_id, self.from_id
        self.from_name, self.to_name = self.to_name, self.from_name
        self.refresh(None)

    def open_dashboard(self, _):
        webbrowser.open(self._dashboard_url())

    def _route_hash(self):
        """Fragmentet (uten #) som speiler valgt rute, likt syncUrl() i app.js.
        Tom streng = Oslo S uten retning (alle avganger)."""
        def short(sid):
            return sid[len(STOP_PLACE_PREFIX):] if sid and sid.startswith(
                STOP_PLACE_PREFIX) else sid

        if self.to_id:
            return f"{short(self.from_id)}-{short(self.to_id)}"
        if self.from_id and self.from_id != DASHBOARD_DEFAULT_FROM:
            return f"{short(self.from_id)}"
        return ""

    def _dashboard_url(self):
        """Speil valgt stasjonspar i URL-hash, likt syncUrl() i app.js."""
        h = self._route_hash()
        return f"{BASE_URL}/#{h}" if h else BASE_URL

    # ---- datahenting + rendering --------------------------------------

    def refresh(self, _):
        self._configure_status_item()
        self._configure_app_menu()
        frm = urllib.parse.quote(self.from_id)
        if self.to_id:
            path = f"/api/v1/analysis/{frm}/to/{urllib.parse.quote(self.to_id)}"
        else:
            path = f"/api/v1/analysis/{frm}"
        try:
            data = self._get(path, params={"horizon_min": HORIZON_MIN})
            status_lines = self._status_lines(data)
        except Exception as exc:
            self.title = "🚆"
            self._headline = "🚆 Kunne ikke nå Togpuls"
            status_lines = [
                "Kunne ikke nå Togpuls",
                str(exc)[:60],
                "",
                f"Prøvde {datetime.now():%H:%M:%S}",
            ]
        self._rebuild_menu(status_lines)
        self._populate_app_menu(status_lines)
        self._sync_webview()

    def _status_menuitems(self, status_lines):
        """Felles bygger for statuslinjene (avganger/situasjoner), gjenbrukt i
        statusmenyen og app-menyen. Øverst vises «status nå» (farget ball +
        neste tog + tidspunkt), så menyen gir samme info som menylinje-ikonet
        når det er skjult. ZWS gjør ellers like titler unike så rumps ikke slår
        dem sammen. Header-linja bytter retning i korridor-modus."""
        headline = getattr(self, "_headline", "")
        prefix = [headline, ""] if headline else []
        lines = prefix + list(status_lines)
        items = [rumps.MenuItem((text or " ") + ZWS * i)
                 for i, text in enumerate(lines)]
        if self.to_id and len(items) > len(prefix):
            items[len(prefix)].set_callback(self.swap_direction)  # header-linja
        return items

    def _rebuild_menu(self, status_lines):
        items = self._status_menuitems(status_lines)
        items += [None]
        items += self._action_menuitems()
        items += [
            None,
            rumps.MenuItem("Avslutt", callback=rumps.quit_application),
        ]
        self.menu.clear()
        self.menu.update(items)
        # Statuslinjene har ingen action; med auto-enabling (standard) tegner
        # macOS dem dempet/grå (lav kontrast, vanskelig å lese). Skru det av så
        # alle linjer vises i full labelColor — tilpasser seg lys/mørk modus.
        self.menu._menu.setAutoenablesItems_(False)

    def _status_lines(self, d):
        tm = d.get("train_movements", {}) or {}
        sits = d.get("situations", []) or []
        sp = d.get("stop_place", {}) or {}

        deps = self._next_departures(d)
        cancelled = tm.get("cancelled", 0)
        delayed = tm.get("delayed_gt_3min", 0)
        worst = self._worst_tier(sits)

        # Tittel: neste avgang om N min + status, med risikoprikk fra
        # situasjonsbildet. Minutter til avgang, ikke klokkeslett.
        dot = TIER_DOT.get(worst, "🟢")
        if deps:
            nxt = deps[0]
            mins = self._mins_until(nxt)
            when = "nå" if not mins else f"{mins}m"
            self.title = f"{dot}{nxt['line']} {when}{self._mark(nxt)}"
            when_txt = "nå" if not mins else f"om {mins} min"
            self._headline = (
                f"{dot} {nxt['line']} kl {self._hhmm(nxt)} · {when_txt}{self._mark(nxt)}"
            )
        else:
            self.title = f"{dot}–"
            self._headline = f"{dot} Ingen avganger i tidsvinduet"

        # Header
        win = (sp.get("window") or {}).get("minutter", HORIZON_MIN)
        if sp.get("to_name"):
            head = f"{sp.get('name', self.from_name)} → {sp['to_name']} ⇄"
        else:
            head = f"{sp.get('name', self.from_name)} · alle avganger"
        lines = [f"{head} · neste {win} min", ""]

        # Neste avganger
        lines.append("Neste avganger")
        if deps:
            for dep in deps[:6]:
                dest = (dep.get("destination") or "")[:16]
                lines.append(
                    f"   {self._hhmm(dep)} {dep['line']} → {dest}{self._status(dep)}"
                )
        else:
            lines.append("   ingen i tidsvinduet")

        # Avvik — telling (autoritativ, fra train_movements) + liste
        lines.append("")
        lines.append(f"Avvik: {cancelled} innstilt · {delayed} forsinket >3 min")
        avvik = self._deviations(d)
        for dep in avvik[:6]:
            dest = (dep.get("destination") or "")[:16]
            lines.append(
                f"   {self._hhmm(dep)} {dep['line']} → {dest}{self._status(dep)}"
            )
        if len(avvik) > 6:
            lines.append("   … og flere")

        # Situasjoner — grupper søsken-meldinger per hendelse, som dashbordet
        groups = self._group_situations(sits)
        high = sum(1 for g in groups if g["rank"] == 0)
        lines.append("")
        lines.append(f"Situasjoner: {len(groups)} ({high} høy risiko)")
        for g in groups[:5]:
            mark = RANK_DOT.get(g["rank"], "▪︎")
            lines.append(f"   {mark} {self._group_text(g)}")

        lines.append("")
        lines.append(f"Sist oppdatert {datetime.now():%H:%M:%S}")
        return lines

    # ---- avganger ------------------------------------------------------

    def _next_departures(self, d):
        """Alle departures fra tidslinjen, kommende først, sortert på tid."""
        now = datetime.now().astimezone()
        deps = []
        for bucket in d.get("timeline", []) or []:
            for dep in bucket.get("departures") or []:
                when = self._parse(dep.get("aimed"))
                if when is None or when < now:
                    continue
                dep["_when"] = when
                deps.append(dep)
        deps.sort(key=lambda x: x["_when"])
        return deps

    def _deviations(self, d):
        """Innstilte og forsinkede (>3 min) avganger i analysevinduet, verste
        først. Dedupliseres på (linje, destinasjon, tid) — backend gjør det
        samme — og avgrenses til window for å speile train_movements."""
        win = (d.get("stop_place") or {}).get("window") or {}
        fra, til = self._parse(win.get("fra")), self._parse(win.get("til"))
        seen, out = set(), []
        for bucket in d.get("timeline", []) or []:
            for dep in bucket.get("departures") or []:
                when = self._parse(dep.get("aimed"))
                if when is None or (fra and til and not fra <= when <= til):
                    continue
                key = (dep.get("line"), dep.get("destination"), dep.get("aimed"))
                if key in seen:
                    continue
                seen.add(key)
                delayed = dep.get("delayed")
                if delayed is None:  # older API without the flag — derive it
                    delayed = (dep.get("delay_min") or 0) > 3
                if not dep.get("cancelled") and not delayed:
                    continue
                dep["_when"] = when
                out.append(dep)
        out.sort(key=lambda x: (not x.get("cancelled"), -(x.get("delay_min") or 0)))
        return out

    @staticmethod
    def _parse(iso):
        if not iso:
            return None
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            return None

    @staticmethod
    def _hhmm(dep):
        w = dep.get("_when")
        return f"{w:%H:%M}" if w else "--:--"

    @staticmethod
    def _mins_until(dep):
        """Hele minutter til (planlagt) avgang; 0 hvis nå/passert."""
        w = dep.get("_when")
        if not w:
            return None
        return max(0, round((w - datetime.now().astimezone()).total_seconds() / 60))

    @staticmethod
    def _mark(dep):
        if dep.get("cancelled"):
            return " ✖"
        if (dep.get("delay_min") or 0) >= 3:
            return f" +{dep['delay_min']}"
        return ""

    @staticmethod
    def _status(dep):
        if dep.get("cancelled"):
            return "  · INNSTILT"
        delay = dep.get("delay_min") or 0
        if delay >= 1:
            return f"  · +{delay} min"
        return ""

    # ---- situasjoner ---------------------------------------------------

    def _group_situations(self, sits):
        """Slå sammen søsken-meldinger til hendelser, jf. groupSituations() i
        app.js: nøkkel = event_id (ellers tekst), forén berørte linjer, og la
        verste medlem (lavest effektiv rang) representere hendelsen."""
        groups = {}
        for s in sits:
            text = (s.get("summary") or s.get("description") or "").strip() or "(uten tekst)"
            key = s.get("event_id") or text
            g = groups.get(key)
            if g is None:
                g = {"text": text, "lines": set(), "count": 0, "rank": 99,
                     "cause_code": "", "cause_text": ""}
                groups[key] = g
            g["count"] += 1
            for line in s.get("paavirker_linjer") or []:
                g["lines"].add(line)
            r = self._eff_rank(s)
            if r < g["rank"]:
                g["rank"] = r
                g["text"] = text
                g["cause_code"] = s.get("cause_code") or ""
                g["cause_text"] = s.get("cause_text") or ""
            elif not g["cause_code"] and not g["cause_text"]:
                g["cause_code"] = s.get("cause_code") or ""
                g["cause_text"] = s.get("cause_text") or ""
        return sorted(groups.values(), key=lambda g: (g["rank"], -g["count"]))

    def _eff_rank(self, s):
        """Effektiv alvorsrang: alert-tier overstyrer SIRI-severity."""
        tier = (self._tier(s) or "").lower()
        if tier == "high":
            sev = "hoy"
        elif tier == "medium":
            sev = "middels"
        else:
            sev = (s.get("severity") or "ukjent").lower()
        return SEVERITY_RANK.get(sev, 3)

    @staticmethod
    def _group_text(g):
        """Én linje: (berørte linjer) tekst · årsak [×antall]."""
        parts = []
        linjer = sorted(g["lines"])
        if linjer:
            shown = ", ".join(linjer[:4])
            if len(linjer) > 4:
                shown += f" +{len(linjer) - 4}"
            parts.append(f"({shown})")
        if g["text"]:
            parts.append(g["text"][:44])
        text = " ".join(parts)
        cause = (g["cause_text"] or "").strip() or (g["cause_code"] or "").strip()
        if cause:
            text += f" · {cause[:40]}"
        if g["count"] > 1:
            text += f" ×{g['count']}"
        return text

    @staticmethod
    def _tier(situation):
        return ((situation.get("estimate") or {}).get("alert") or {}).get("alert_tier")

    def _worst_tier(self, situations):
        worst = None
        for s in situations:
            t = self._tier(s)
            if t and TIER_RANK.get(t, 0) > TIER_RANK.get(worst, 0):
                worst = t
        return worst


def _selftest():
    """Henter live-data og skriver statuslinjene til stdout. Aktiveres med
    TOGPULS_SELFTEST=1 — brukes til å verifisere at appen når API-et."""
    app = TogpulsBar.__new__(TogpulsBar)
    app.from_id, app.from_name = FROM_PLACE, "Oslo S"
    app.to_id, app.to_name = TO_PLACE, None
    app.title = ""
    frm = urllib.parse.quote(app.from_id)
    if app.to_id:
        path = f"/api/v1/analysis/{frm}/to/{urllib.parse.quote(app.to_id)}"
    else:
        path = f"/api/v1/analysis/{frm}"
    data = app._get(path, params={"horizon_min": HORIZON_MIN})
    lines = app._status_lines(data)
    print("TITTEL:", app.title)
    print("\n".join(lines))


# ---- global hurtigtast (Carbon RegisterEventHotKey) --------------------
# Carbon-hotkeys krever INGEN Tilgjengelighet-tillatelse, i motsetning til
# NSEvent-globale monitorer. Standard: ⌃⌥⌘T. Overstyr keycode/modifiers med
# TOGPULS_HOTKEY_KEYCODE / TOGPULS_HOTKEY_MODS om ønskelig.
import ctypes
import ctypes.util

# Carbon-modifikatorer (ikke de samme bitene som Cocoa/NSEvent).
_CARBON_CMD, _CARBON_OPT, _CARBON_CTRL, _CARBON_SHIFT = 0x0100, 0x0800, 0x1000, 0x0200
_DEFAULT_KEYCODE = int(os.environ.get("TOGPULS_HOTKEY_KEYCODE", "17"))  # kVK_ANSI_T
_DEFAULT_MODS = int(
    os.environ.get("TOGPULS_HOTKEY_MODS", str(_CARBON_CTRL | _CARBON_OPT | _CARBON_CMD))
)

# Holder referanser i live så ikke GC river dem bort under kjøring.
_hotkey_state = {}


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


def _install_global_hotkey(on_fire):
    """Registrer en systemglobal hurtigtast. Returnerer True ved suksess.
    Feiler stille (returnerer False) hvis Carbon ikke er tilgjengelig —
    appen fungerer fint uten hurtigtasten."""
    try:
        carbon_path = ctypes.util.find_library("Carbon") or (
            "/System/Library/Frameworks/Carbon.framework/Carbon"
        )
        carbon = ctypes.CDLL(carbon_path)
    except OSError:
        return False

    # Eksplisitte signaturer er kritisk: uten restype=c_void_p trunkerer
    # ctypes 64-bits pekere til 32 bit, som gir krasj.
    carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    carbon.InstallEventHandler.restype = ctypes.c_int32
    carbon.InstallEventHandler.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ]
    carbon.RegisterEventHotKey.restype = ctypes.c_int32
    carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
    ]

    kEventClassKeyboard = 0x6B657962  # 'keyb'
    kEventHotKeyPressed = 6
    HANDLER = ctypes.CFUNCTYPE(
        ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
    )

    def _handler(next_handler, event, user_data):
        try:
            on_fire()
        except Exception:
            pass
        return 0

    handler = HANDLER(_handler)
    spec = _EventTypeSpec(kEventClassKeyboard, kEventHotKeyPressed)
    target = carbon.GetApplicationEventTarget()
    carbon.InstallEventHandler(
        target, ctypes.cast(handler, ctypes.c_void_p), 1,
        ctypes.byref(spec), None, None
    )

    hk_id = _EventHotKeyID(0x54475053, 1)  # 'TGPS'
    hk_ref = ctypes.c_void_p()
    status = carbon.RegisterEventHotKey(
        ctypes.c_uint32(_DEFAULT_KEYCODE),
        ctypes.c_uint32(_DEFAULT_MODS),
        hk_id,
        target,
        0,
        ctypes.byref(hk_ref),
    )
    if status != 0:
        return False
    _hotkey_state.update(carbon=carbon, handler=handler, spec=spec, ref=hk_ref)
    return True


def _enable_dock_and_hotkey():
    """Gjør appen til en vanlig app (Dock-ikon + app-veksler), hekt en
    Dock-meny på rumps' delegat, og registrer den globale hurtigtasten."""
    from AppKit import (
        NSApplication, NSApplicationActivationPolicyRegular, NSImage,
    )
    import rumps.rumps as _rc

    nsapp = NSApplication.sharedApplication()
    nsapp.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    # Sett app-ikonet ved kjøretid, så det vises også når vi kjører fra kilde
    # (der prosessen ellers arver Pythons ikon). Den bygde .app-en bruker
    # uansett iconfile fra Info.plist.
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(here, "assets", "Togpuls.icns"),
        os.path.join(here, "..", "togpuls", "static", "icons", "icon-512.png"),
    ):
        if os.path.exists(cand):
            img = NSImage.alloc().initWithContentsOfFile_(cand)
            if img is not None:
                nsapp.setApplicationIconImage_(img)
                break

    class _DockNSApp(_rc.NSApp):
        def applicationDockMenu_(self, sender):
            app = getattr(rumps.App, "*app_instance", None)
            return app.build_dock_menu() if app is not None else None

        def applicationShouldHandleReopen_hasVisibleWindows_(self, sender, flag):
            # Klikk på Dock-ikonet åpner dashbord-vinduet.
            app = getattr(rumps.App, "*app_instance", None)
            if app is not None:
                app.open_window()
            return True

    _rc.NSApp = _DockNSApp  # run() oppretter delegaten fra denne globalen

    def _fire():
        app = getattr(rumps.App, "*app_instance", None)
        if app is not None:
            app.popup_menu_centered()

    _install_global_hotkey(_fire)


if __name__ == "__main__":
    if os.environ.get("TOGPULS_SELFTEST") == "1":
        _selftest()
    else:
        _enable_dock_and_hotkey()
        TogpulsBar().run()
