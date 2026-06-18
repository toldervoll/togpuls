// Tiny i18n helper. Loaded before app.js so its globals (`t`, `tp`,
// `intlLocale`, `currentLang`, `setLang`) are available there.
//
// Initial language is set by the inline script in index.html <head>
// (reads localStorage, falls back to navigator.language). This file just
// reads `<html lang>` and applies translations.

"use strict";

const I18N_LANG_KEY = "togpuls-lang";

const I18N_STRINGS = {
  no: {
    // <title>
    "title": "togpuls — Oslo S",

    // Brand / live indicator
    "brand_name": "togpuls",
    "live": "live",
    "live_announce": "Sanntid – oppdaterer hvert 30. sekund",
    "gauge_aria_past": "Gjennomført {pct} prosent siste 90 min",
    "gauge_aria_future": "Forventet {pct} prosent neste 90 min",
    "console_station_window": "Stasjon: {station} · vindu: ±90 min",

    // Header
    "route_label": "Rute",
    "from_label": "Fra",
    "to_label": "Til",
    "swap_direction": "Bytt retning",
    "all_directions": "Alle retninger",
    "apply": "Vis",
    "theme_toggle": "Bytt tema",
    "theme_to_light": "Bytt til lys modus",
    "theme_to_dark": "Bytt til mørk modus",
    "lang_toggle": "Switch to English",
    "lang_toggle_label": "EN",
    "never": "aldri",
    "loading": "laster…",
    "stale": "utdatert",
    "updated_at": "oppdatert {time}",

    // Timeline
    "timeline_window": "±90 min",
    "axis_neg90": "−90 min",
    "axis_neg60": "−60",
    "axis_neg30": "−30",
    "axis_now": "nå",
    "axis_pos30": "+30",
    "axis_pos60": "+60",
    "axis_pos90": "+90",
    "time_now": "nå",
    "time_ago": "{n} min siden",
    "time_in": "om {n} min",
    "tt_none": "ingen tog",
    "tt_planned": "{scheduled} planlagt",
    "tt_ran": "{realised} av {scheduled} kjørt",
    "tt_cancelled": "{n} kansellert",
    "tt_delayed": "{n} forsinket >3 min",
    "tt_more": "+{n} flere",

    // Big stats
    "big_scope_label": "Tidsrom for statistikk",
    "scope_past": "Historikk",
    "scope_future": "Fremtid",
    "scope_combined": "±90 min",
    "big_util_past": "gjennomført",
    "big_util_future": "forventet",
    "big_scheduled": "planlagt",
    "big_realised": "kjørt",
    "big_cancelled": "kansellert",
    "big_delayed": "forsinket >3 min",
    "big_p90": "p90-forsinkelse (min)",

    // Situations
    "situations_title": "Situasjoner",
    "no_data": "ingen data",
    "view_label": "Situasjonsvisning",
    "view_grouped": "Gruppert",
    "view_perline": "Per linje",
    "no_active_situations": "Ingen aktive SIRI-SX-situasjoner.",
    "sit_count_simple": "({n})",
    "sit_count_unique": "({unique} unike, {total} totalt)",
    "sit_summary_top": "{parts} — øverst: {text}",
    "sit_lines_prefix": "Linjer: {lines}",
    "sit_hist_cancel_rate":    "Kansellert",
    "sit_hist_trouble_rate":   "Avvik",
    "sit_hist_trouble_lift":   "Forhøyet risiko",
    "sit_hist_delay_p50":      "Forsinkelse p50",
    "sit_hist_delay_p90":      "Forsinkelse p90",
    "sit_hist_exp_disruption": "Forv. taptid",
    "sit_hist_n_situations":   "Hist. tilfeller",
    "sit_hist_reopen_spread":  "Åpner (p80/p90)",
    "sit_hist_impact_spread":  "Konsekvens (p80/p90)",
    "sit_est_eta": "Anslått over om ~{dur}",
    "sit_est_overdue": "Over anslått tid",
    "tier_label.low": "LAV",
    "tier_label.medium": "MIDDELS",
    "tier_label.high": "HØY",
    "rate_cancel": "Kanselleringer: {pct}",
    "rate_trouble": "Avvik: {pct}",
    "dur_min": "{n} min",
    "dur_h": "{h} t",
    "dur_hm": "{h} t {m} min",
    "sev_label.hoy": "HØY",
    "sev_label.middels": "MIDDELS",
    "sev_label.lav": "LAV",
    "sev_label.ukjent": "UKJENT",
    "sev_label.ingen": "ingen",
    "sev_count.hoy": "{n} høy",
    "sev_count.middels": "{n} middels",
    "sev_count.lav": "{n} lav",

    // Platforms
    "platforms_title": "Spor",
    "plat_meta_disrupted": "({n} med avvik)",
    "plat_none_disrupted": "Ingen spor med avvik.",
    "tbl_platform": "Spor",
    "tbl_scheduled": "Planlagt",
    "tbl_realised": "Kjørt",
    "tbl_cancelled": "Kansellert",
    "tbl_delayed": "Forsinket",
    "tbl_lines": "Linjer",
    "line_status_cancelled": "{lines} kansellert",
    "line_status_delayed": "{lines} forsinket",
    "plat_count": "{n} spor",
    "plat_busiest": "travleste: Spor {label} ({n} avganger)",
    "plat_with_canc": "{count} med kanselleringer ({total} totalt)",
    "plat_no_canc": "ingen kanselleringer",
    "plat_delayed_lines.one": "{count} linje forsinket ({deps} avganger)",
    "plat_delayed_lines.other": "{count} linjer forsinket ({deps} avganger)",
    "plat_no_delays": "ingen forsinkelser",

    // Passenger estimate
    "pax_title": "Passasjerestimat",
    "pax_modelled": "(modellert)",
    "pax_main": "~{n} passasjerer i vinduet",
    "pax_affected_sentence": "↳ ~{n} på {lines} med avvik",
    "pax_displaced_sentence": "↳ ~{n} rammet av kanselleringer",
    "pax_subset_note": "(delmengde av totalen ovenfor)",
    "pax_hypothetical_note": "(hypotetisk; ikke med i totalen over)",
    "pax_tbl_line": "Linje",
    "pax_tbl_passengers": "Pax kjørt",
    "pax_tbl_cancelled": "Kansellert",
    "pax_tbl_displaced": "Pax forskyvet",
    "pax_tbl_situations": "Situasjoner",
    "pax_coverage": "{known}/{total} kjørte avganger ({pct} %) hadde reelt belegg; resten bruker standard belegg={lf}",
    "pax_note": (
      "estimated_passengers: kjørte avganger × belegg per avgang " +
      "(faktisk OTP occupancyStatus når tilgjengelig, ellers standard belegg). " +
      "affected_passengers: samme kjørte passasjerer, begrenset til linjer med " +
      "≥1 aktiv SX — alltid ≤ estimert. " +
      "displaced_passengers: kansellerte avganger × kapasitet × standard belegg " +
      "(passasjerer hvis tog ble kansellert; uavhengig av estimert)."
    ),

    // Pluralised line/situation counts (used standalone)
    "lines_count.one": "{count} linje",
    "lines_count.other": "{count} linjer",

    // Summary sentence — single template, all params filled
    "default_stop": "stoppestedet",
    "where_to_from": "fra {from} til {to}",
    "where_through": "gjennom {from}",
    "count_all": "alle {n}",
    "count_of": "{n} av {total}",
    "summary_trains_base": (
      "Siste {min} min kjørte {pcount} planlagte tog {where}; " +
      "neste {min} min forventes {fcount} å kjøre"
    ),
    "summary_past_base": "Siste {min} min kjørte {count} planlagte tog {where}",
    "summary_future_base": (
      "Neste {min} min forventes {count} planlagte tog å kjøre {where}"
    ),
    "summary_issue_cancelled": "{n} kansellert",
    "summary_issue_delayed": "{n} forsinket mer enn 3 min",
    "summary_all_clear": (
      "Alt i rute {where}: {past} tog kjørt som planlagt siste {min} min, " +
      "og alle {future} planlagte forventes å kjøre de neste {min} min."
    ),
    "summary_all_clear_past": (
      "Alt i rute {where}: alle {past} planlagte tog kjørte som normalt siste {min} min."
    ),
    "summary_all_clear_future": (
      "Alt i rute {where}: alle {future} planlagte tog forventes å kjøre de neste {min} min."
    ),
    "summary_no_traffic_past": "Ingen trafikk {where} siste {min} min.",
    "summary_no_traffic_future": "Ingen trafikk {where} de neste {min} min.",
    "summary_sit_minor.one": "Én mindre situasjon påvirker {lines}.",
    "summary_sit_minor.other": "{count} mindre situasjoner påvirker {lines}.",
    "summary_no_trains_corridor": "Ingen tog på strekningen {corridor} de neste {min} min.",
    "summary_no_traffic_station": "Ingen trafikk planlagt på {from} de neste {min} min.",
    "summary_sit_sev_wrap": " ({parts} alvorlighet)",
    "summary_sit.one": (
      "{count} aktiv situasjon{sev} påvirker {lines}; " +
      "~{aff} passasjerer reiser akkurat nå på forstyrrede linjer"
    ),
    "summary_sit.other": (
      "{count} aktive situasjoner{sev} påvirker {lines}; " +
      "~{aff} passasjerer reiser akkurat nå på forstyrrede linjer"
    ),
    "summary_sit_displaced": ", og ~{n} til fikk toget sitt kansellert og må finne et alternativ",

    "footer": "togpuls · data: Entur Journey Planner v3 · oppdatering hver 30 s · buffer 20 s",
  },

  en: {
    "title": "togpuls — Oslo S",

    "brand_name": "togpuls",
    "live": "live",
    "live_announce": "Live — refreshing every 30 seconds",
    "gauge_aria_past": "Completed {pct} percent in the last 90 min",
    "gauge_aria_future": "Expected {pct} percent over the next 90 min",
    "console_station_window": "Station: {station} · window: ±90 min",

    "route_label": "Route",
    "from_label": "From",
    "to_label": "To",
    "swap_direction": "Swap direction",
    "all_directions": "All directions",
    "apply": "Show",
    "theme_toggle": "Toggle theme",
    "theme_to_light": "Switch to light mode",
    "theme_to_dark": "Switch to dark mode",
    "lang_toggle": "Bytt til norsk",
    "lang_toggle_label": "NO",
    "never": "never",
    "loading": "loading…",
    "stale": "stale",
    "updated_at": "updated {time}",

    "timeline_window": "±90 min",
    "axis_neg90": "−90 min",
    "axis_neg60": "−60",
    "axis_neg30": "−30",
    "axis_now": "now",
    "axis_pos30": "+30",
    "axis_pos60": "+60",
    "axis_pos90": "+90",
    "time_now": "now",
    "time_ago": "{n} min ago",
    "time_in": "in {n} min",
    "tt_none": "no trains",
    "tt_planned": "{scheduled} scheduled",
    "tt_ran": "{realised} of {scheduled} ran",
    "tt_cancelled": "{n} cancelled",
    "tt_delayed": "{n} delayed >3 min",
    "tt_more": "+{n} more",

    "big_scope_label": "Statistics time scope",
    "scope_past": "History",
    "scope_future": "Future",
    "scope_combined": "±90 min",
    "big_util_past": "completed",
    "big_util_future": "expected",
    "big_scheduled": "scheduled",
    "big_realised": "completed",
    "big_cancelled": "cancelled",
    "big_delayed": "delayed >3 min",
    "big_p90": "p90 delay (min)",

    "situations_title": "Situations",
    "no_data": "no data",
    "view_label": "Situation view",
    "view_grouped": "Grouped",
    "view_perline": "Per line",
    "no_active_situations": "No active SIRI-SX situations.",
    "sit_count_simple": "({n})",
    "sit_count_unique": "({unique} unique, {total} total)",
    "sit_summary_top": "{parts} — top: {text}",
    "sit_lines_prefix": "Lines: {lines}",
    "sit_hist_cancel_rate":    "Cancellation",
    "sit_hist_trouble_rate":   "Disruption",
    "sit_hist_trouble_lift":   "Trouble lift",
    "sit_hist_delay_p50":      "Delay p50",
    "sit_hist_delay_p90":      "Delay p90",
    "sit_hist_exp_disruption": "Exp. lost time",
    "sit_hist_n_situations":   "Hist. incidents",
    "sit_hist_reopen_spread":  "Reopens (p80/p90)",
    "sit_hist_impact_spread":  "Impact (p80/p90)",
    "sit_est_eta": "Est. clear in ~{dur}",
    "sit_est_overdue": "Past estimated end",
    "tier_label.low": "LOW",
    "tier_label.medium": "MEDIUM",
    "tier_label.high": "HIGH",
    "rate_cancel": "Cancellations: {pct}",
    "rate_trouble": "Disruptions: {pct}",
    "dur_min": "{n} min",
    "dur_h": "{h}h",
    "dur_hm": "{h}h {m}m",
    "sev_label.hoy": "HIGH",
    "sev_label.middels": "MEDIUM",
    "sev_label.lav": "LOW",
    "sev_label.ukjent": "UNKNOWN",
    "sev_label.ingen": "none",
    "sev_count.hoy": "{n} high",
    "sev_count.middels": "{n} medium",
    "sev_count.lav": "{n} low",

    "platforms_title": "Platforms",
    "plat_meta_disrupted": "({n} disrupted)",
    "plat_none_disrupted": "No platforms with disruptions.",
    "tbl_platform": "Platform",
    "tbl_scheduled": "Scheduled",
    "tbl_realised": "Completed",
    "tbl_cancelled": "Cancelled",
    "tbl_delayed": "Delayed",
    "tbl_lines": "Lines",
    "line_status_cancelled": "{lines} cancelled",
    "line_status_delayed": "{lines} delayed",
    "plat_count": "{n} platforms",
    "plat_busiest": "busiest: Platform {label} ({n} departures)",
    "plat_with_canc": "{count} with cancellations ({total} total)",
    "plat_no_canc": "no cancellations",
    "plat_delayed_lines.one": "{count} line delayed ({deps} departures)",
    "plat_delayed_lines.other": "{count} lines delayed ({deps} departures)",
    "plat_no_delays": "no delays",

    "pax_title": "Passenger estimate",
    "pax_modelled": "(modelled)",
    "pax_main": "~{n} passengers in window",
    "pax_affected_sentence": "↳ ~{n} on {lines} with disruptions",
    "pax_displaced_sentence": "↳ ~{n} affected by cancellations",
    "pax_subset_note": "(subset of the total above)",
    "pax_hypothetical_note": "(hypothetical; not included in the total above)",
    "pax_tbl_line": "Line",
    "pax_tbl_passengers": "Pax completed",
    "pax_tbl_cancelled": "Cancelled",
    "pax_tbl_displaced": "Pax displaced",
    "pax_tbl_situations": "Situations",
    "pax_coverage": "{known}/{total} completed departures ({pct} %) had real occupancy data; rest use default load factor={lf}",
    "pax_note": (
      "estimated_passengers: completed departures × occupancy per departure " +
      "(actual OTP occupancyStatus when available, otherwise default load factor). " +
      "affected_passengers: same completed passengers, restricted to lines with " +
      "≥1 active SX — always ≤ estimated. " +
      "displaced_passengers: cancelled departures × capacity × default load factor " +
      "(passengers if a train was cancelled; independent of estimated)."
    ),

    "lines_count.one": "{count} line",
    "lines_count.other": "{count} lines",

    "default_stop": "the stop",
    "where_to_from": "from {from} to {to}",
    "where_through": "through {from}",
    "count_all": "all {n}",
    "count_of": "{n} of {total}",
    "summary_trains_base": (
      "In the last {min} min, {pcount} scheduled trains ran {where}; " +
      "over the next {min} min, {fcount} are expected to run"
    ),
    "summary_past_base": "In the last {min} min, {count} scheduled trains ran {where}",
    "summary_future_base": (
      "Over the next {min} min, {count} scheduled trains are expected to run {where}"
    ),
    "summary_issue_cancelled": "{n} cancelled",
    "summary_issue_delayed": "{n} delayed by more than 3 min",
    "summary_all_clear": (
      "All on schedule {where}: {past} trains ran as planned in the last {min} min, " +
      "and all {future} scheduled are expected to run over the next {min} min."
    ),
    "summary_all_clear_past": (
      "All on schedule {where}: all {past} scheduled trains ran as planned in the last {min} min."
    ),
    "summary_all_clear_future": (
      "All on schedule {where}: all {future} scheduled trains are expected to run over the next {min} min."
    ),
    "summary_no_traffic_past": "No traffic {where} in the last {min} min.",
    "summary_no_traffic_future": "No traffic {where} in the next {min} min.",
    "summary_sit_minor.one": "One minor situation affects {lines}.",
    "summary_sit_minor.other": "{count} minor situations affect {lines}.",
    "summary_no_trains_corridor": "No trains on the {corridor} corridor in the next {min} min.",
    "summary_no_traffic_station": "No traffic scheduled at {from} in the next {min} min.",
    "summary_sit_sev_wrap": " ({parts} severity)",
    "summary_sit.one": (
      "{count} active situation{sev} affects {lines}; " +
      "~{aff} passengers are currently riding on disrupted lines"
    ),
    "summary_sit.other": (
      "{count} active situations{sev} affect {lines}; " +
      "~{aff} passengers are currently riding on disrupted lines"
    ),
    "summary_sit_displaced": ", and ~{n} more had their train cancelled and need to find an alternative",

    "footer": "togpuls · data: Entur Journey Planner v3 · refresh every 30 s · buffer 20 s",
  },
};

function _normalizeLang(l) {
  return l === "no" || l === "en" ? l : null;
}

function currentLang() {
  return _normalizeLang(document.documentElement.lang) || "no";
}

function _dict() {
  return I18N_STRINGS[currentLang()] || I18N_STRINGS.no;
}

function _fmt(s, params) {
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (_, k) => (params[k] !== undefined ? params[k] : `{${k}}`));
}

function t(key, params) {
  const d = _dict();
  let s = d[key];
  if (s === undefined) s = I18N_STRINGS.no[key];
  if (s === undefined) return key;
  return _fmt(s, params);
}

function tp(key, count, params) {
  const rules = new Intl.PluralRules(intlLocale());
  const cat = rules.select(count);
  const full = `${key}.${cat}`;
  const dict = _dict();
  const fallback = dict[`${key}.other`] !== undefined ? `${key}.other` : key;
  const useKey = dict[full] !== undefined ? full : fallback;
  return t(useKey, { count, ...(params || {}) });
}

function intlLocale() {
  return currentLang() === "no" ? "nb-NO" : "en-GB";
}

function applyStaticTranslations() {
  for (const el of document.querySelectorAll("[data-i18n]")) {
    el.textContent = t(el.getAttribute("data-i18n"));
  }
  for (const el of document.querySelectorAll("[data-i18n-attr]")) {
    const spec = el.getAttribute("data-i18n-attr");
    for (const pair of spec.split(",")) {
      const colon = pair.indexOf(":");
      if (colon < 0) continue;
      const attr = pair.slice(0, colon).trim();
      const key = pair.slice(colon + 1).trim();
      el.setAttribute(attr, t(key));
    }
  }
  document.title = t("title");
}

function setLang(lang) {
  const normalised = _normalizeLang(lang);
  if (!normalised || normalised === currentLang()) return;
  document.documentElement.lang = normalised;
  try { localStorage.setItem(I18N_LANG_KEY, normalised); } catch (e) {}
  applyStaticTranslations();
  document.dispatchEvent(new CustomEvent("i18n:change"));
}

// Apply on load. The inline head script has already set <html lang>.
applyStaticTranslations();
