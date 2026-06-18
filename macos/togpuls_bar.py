#!/usr/bin/env python3
"""Togpuls menylinje-app for macOS.

Viser neste togavganger, avvik og situasjoner fra Togpuls-API-et i
menylinjen. Støtter både én stasjon (alle avganger) og en korridor
(fra → til). Poller hvert 30. sekund — samme rytme som dashbordet.

Konfigurasjon via miljøvariabler (alle valgfrie):
    TOGPULS_BASE_URL   standard https://togpuls.kengu.no
    TOGPULS_STOP_PLACE standard NSR:StopPlace:337 (Oslo S) — «fra»
    TOGPULS_TO_PLACE   standard tom (= alle avganger); sett for korridor
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
FROM_PLACE = os.environ.get("TOGPULS_STOP_PLACE", "NSR:StopPlace:337")
TO_PLACE = os.environ.get("TOGPULS_TO_PLACE", "") or None
HORIZON_MIN = int(os.environ.get("TOGPULS_HORIZON", "60"))
POLL_SEC = int(os.environ.get("TOGPULS_POLL_SEC", "30"))

TIER_DOT = {"high": "🔴", "medium": "🟡", "low": "🟢"}
TIER_RANK = {"high": 3, "medium": 2, "low": 1}
ALL_LABEL = "Alle avganger"

# Zero-width space — gjør ellers like menytitler unike så rumps ikke slår dem sammen.
ZWS = "​"


class TogpulsBar(rumps.App):
    def __init__(self):
        super().__init__("🚆 …", quit_button=None)
        self.from_id = FROM_PLACE
        self.from_name = "Oslo S"
        self.to_id = TO_PLACE
        self.to_name = None
        self.stations = self._load_stations()
        self._name_lookup()
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

    def open_dashboard(self, _):
        webbrowser.open(BASE_URL)

    # ---- datahenting + rendering --------------------------------------

    def refresh(self, _):
        frm = urllib.parse.quote(self.from_id)
        if self.to_id:
            path = f"/api/v1/analysis/{frm}/to/{urllib.parse.quote(self.to_id)}"
        else:
            path = f"/api/v1/analysis/{frm}"
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
            items.append(rumps.MenuItem((text or " ") + ZWS * i))
        items += [
            None,
            rumps.MenuItem("Åpne dashbord", callback=self.open_dashboard),
            self._from_submenu(),
            self._to_submenu(),
            rumps.MenuItem("Oppdater nå", callback=self.refresh),
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

        # Tittel: neste avgang + status, med risikoprikk fra situasjonsbildet.
        dot = TIER_DOT.get(worst, "🟢")
        if deps:
            nxt = deps[0]
            self.title = f"{dot} {nxt['line']} {self._hhmm(nxt)}{self._mark(nxt)}"
        else:
            self.title = f"{dot} 🚆 –"

        # Header
        win = (sp.get("window") or {}).get("minutter", HORIZON_MIN)
        if sp.get("to_name"):
            head = f"{sp.get('name', self.from_name)} → {sp['to_name']}"
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

        # Avvik (oppsummert)
        lines.append("")
        lines.append(f"Avvik: {cancelled} innstilt · {delayed} forsinket >3 min")

        # Situasjoner — prioriter høy risiko
        ranked = sorted(sits, key=lambda s: TIER_RANK.get(self._tier(s), 0), reverse=True)
        high = sum(1 for s in sits if self._tier(s) == "high")
        lines.append("")
        lines.append(f"Situasjoner: {len(sits)} ({high} høy risiko)")
        for s in ranked[:5]:
            mark = TIER_DOT.get(self._tier(s), "▪︎")
            lines.append(f"   {mark} {self._situation_text(s)}")

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

    @staticmethod
    def _situation_text(s):
        """Én linje: (berørte linjer) situasjon · årsak.

        Årsak er cause_text når den finnes, ellers cause_code-kategorien."""
        parts = []
        linjer = s.get("paavirker_linjer") or []
        if linjer:
            shown = ", ".join(linjer[:4])
            if len(linjer) > 4:
                shown += f" +{len(linjer) - 4}"
            parts.append(f"({shown})")
        summary = (s.get("summary") or "").strip()[:44]
        if summary:
            parts.append(summary)
        text = " ".join(parts)
        cause = (s.get("cause_text") or "").strip() or (s.get("cause_code") or "").strip()
        if cause:
            text += f" · {cause[:40]}"
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


if __name__ == "__main__":
    if os.environ.get("TOGPULS_SELFTEST") == "1":
        _selftest()
    else:
        TogpulsBar().run()
