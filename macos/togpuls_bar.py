#!/usr/bin/env python3
"""Togpuls menylinje-app for macOS.

Viser sanntidsstatus for togavganger fra Togpuls-API-et i menylinjen, og
en nedtrekksmeny med detaljer. Poller hvert 30. sekund — samme rytme som
selve dashbordet.

Konfigurasjon via miljøvariabler:
    TOGPULS_BASE_URL   standard https://togpuls.kengu.no
    TOGPULS_STOP_PLACE standard NSR:StopPlace:337 (Oslo S)
    TOGPULS_HORIZON    standard 60 (minutter framover)
    TOGPULS_POLL_SEC   standard 30
"""

import json
import os
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

import rumps

BASE_URL = os.environ.get("TOGPULS_BASE_URL", "https://togpuls.kengu.no").rstrip("/")
STOP_PLACE = os.environ.get("TOGPULS_STOP_PLACE", "NSR:StopPlace:337")
HORIZON_MIN = int(os.environ.get("TOGPULS_HORIZON", "60"))
POLL_SEC = int(os.environ.get("TOGPULS_POLL_SEC", "30"))

TIER_DOT = {"high": "🔴", "medium": "🟡", "low": "🟢"}
TIER_RANK = {"high": 3, "medium": 2, "low": 1}

# Zero-width space — gjør ellers like menytitler unike så rumps ikke slår dem sammen.
ZWS = "​"


class TogpulsBar(rumps.App):
    def __init__(self):
        super().__init__("🚆 …", quit_button=None)
        self.stop_place = STOP_PLACE
        self.station_name = "Oslo S"
        self.stations = self._load_stations()
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

    # ---- stasjoner -----------------------------------------------------

    def _load_stations(self):
        try:
            return self._get("/api/v1/stations", timeout=10)
        except Exception:
            return []

    def _station_submenu(self):
        sub = rumps.MenuItem("Stasjon")
        for st in self.stations:
            sid, name = st.get("id"), st.get("name")
            if not sid:
                continue
            item = rumps.MenuItem(name, callback=self._make_station_cb(sid, name))
            item.state = 1 if sid == self.stop_place else 0
            sub.add(item)
        return sub

    def _make_station_cb(self, sid, name):
        def cb(_):
            self.stop_place = sid
            self.station_name = name
            self.refresh(None)

        return cb

    def open_dashboard(self, _):
        webbrowser.open(BASE_URL)

    # ---- datahenting + rendering --------------------------------------

    def refresh(self, _):
        path = f"/api/v1/analysis/{urllib.parse.quote(self.stop_place)}"
        try:
            data = self._get(path, params={"horizon_min": HORIZON_MIN})
            status_lines = self._status_lines(data)
        except Exception as exc:
            self.title = "🚆 –"
            status_lines = [
                "Kunne ikke nå Togpuls",
                str(exc)[:60],
                "",
                f"Prøvde {datetime.now():%H:%M:%S}",
            ]
        self._rebuild_menu(status_lines)

    def _rebuild_menu(self, status_lines):
        items = []
        for i, text in enumerate(status_lines):
            # Unik nøkkel via usynlige tegn; tom streng blir et mellomrom.
            items.append(rumps.MenuItem((text or " ") + ZWS * i))
        items += [
            None,
            rumps.MenuItem("Åpne dashbord", callback=self.open_dashboard),
            self._station_submenu(),
            rumps.MenuItem("Oppdater nå", callback=self.refresh),
            None,
            rumps.MenuItem("Avslutt", callback=rumps.quit_application),
        ]
        self.menu.clear()
        self.menu.update(items)

    def _status_lines(self, d):
        tm = d.get("train_movements", {}) or {}
        sits = d.get("situations", []) or []
        pe = d.get("passenger_estimate", {}) or {}
        sp = d.get("stop_place", {}) or {}

        worst = self._worst_tier(sits)
        cancelled = tm.get("cancelled", 0)
        delayed = tm.get("delayed_gt_3min", 0)
        self.title = f"{TIER_DOT.get(worst, '🟢')} {cancelled}✖ {delayed}⏱"

        name = sp.get("name", self.station_name)
        win = (sp.get("window") or {}).get("minutter", HORIZON_MIN)
        lines = [f"{name} · neste {win} min", ""]

        lines.append(f"Avganger: {tm.get('realised', 0)}/{tm.get('scheduled', 0)} kjørt")
        lines.append(f"Innstilt: {cancelled}   ·   Forsinket >3 min: {delayed}")
        p50, p90 = tm.get("median_delay_min"), tm.get("p90_delay_min")
        if p50 is not None:
            lines.append(f"Forsinkelse median {p50} min · p90 {p90} min")

        by_line = tm.get("by_line", []) or []
        ranked = sorted(
            by_line,
            key=lambda l: l.get("cancelled", 0) * 2 + l.get("delayed_gt_3min", 0),
            reverse=True,
        )
        hot = [l for l in ranked if l.get("cancelled") or l.get("delayed_gt_3min")][:5]
        if hot:
            lines.append("")
            lines.append("Mest berørte linjer:")
            for l in hot:
                lines.append(
                    f"   {str(l.get('linje', '?')):<5} "
                    f"{l.get('cancelled', 0)}✖ {l.get('delayed_gt_3min', 0)}⏱"
                )

        high = [s for s in sits if self._tier(s) == "high"]
        lines.append("")
        lines.append(f"Situasjoner: {len(sits)} ({len(high)} høy risiko)")
        for s in high[:4]:
            lines.append(f"   🔴 {(s.get('summary') or '').strip()[:48]}")

        affected = pe.get("affected_passengers")
        if affected:
            displaced = pe.get("displaced_passengers", 0)
            alines = ", ".join(pe.get("affected_lines", []) or [])
            lines.append("")
            lines.append(f"Berørte reisende: ~{affected:,}".replace(",", " "))
            if displaced:
                lines.append(f"   kan ikke reise: ~{displaced:,}".replace(",", " "))
            if alines:
                lines.append(f"   linjer: {alines}")

        lines.append("")
        lines.append(f"Sist oppdatert {datetime.now():%H:%M:%S}")
        return lines

    # ---- hjelpere ------------------------------------------------------

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
    """Henter live-data og skriver statuslinjene til stdout. Brukes til å
    verifisere at den buntede appen når API-et. Aktiveres med TOGPULS_SELFTEST=1."""
    app = TogpulsBar.__new__(TogpulsBar)
    app.station_name = "Oslo S"
    app.title = ""
    path = "/api/v1/analysis/" + urllib.parse.quote(STOP_PLACE)
    data = app._get(path, params={"horizon_min": HORIZON_MIN})
    print("TITTEL:", app.title or "(satt i _status_lines)")
    print("\n".join(app._status_lines(data)))


if __name__ == "__main__":
    if os.environ.get("TOGPULS_SELFTEST") == "1":
        _selftest()
    else:
        TogpulsBar().run()
