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
    "station_search": "Søk stasjon…",
    "no_matches": "Ingen treff",
    "apply": "Vis",
    "theme_toggle": "Bytt tema",
    "theme_to_light": "Bytt til lys modus",
    "theme_to_dark": "Bytt til mørk modus",
    "lang_toggle": "Switch to English",
    "lang_toggle_label": "EN",
    "never": "aldri",
    "loading": "laster…",
    "stale": "utdatert",
    "updated_at": "{time}",
    "reload": "Oppdater nå",

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
    "big_p90": "mest forsinket (min)",
    "tip_util_past": "Andel planlagte tog som faktisk kjørte i tidsvinduet.",
    "tip_util_future": "Andel kommende tog som forventes å kjøre.",
    "tip_cancelled": "Antall avganger innstilt i tidsvinduet.",
    "tip_delayed": "Antall avganger forsinket mer enn 3 minutter.",
    "tip_p90": "10 % av togene er så forsinket eller mer (90-persentilen). Fanger de verste forsinkelsene uten at enkelttilfeller drar opp snittet.",
    "tip_realised": "Antall avganger som har kjørt (kun historikk).",
    "tip_scheduled": "Antall planlagte avganger i tidsvinduet.",

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
    "sit_also_prefix": "Også: {texts}",
    "summary_cause": "Årsak: {cause}.",
    "sit_hist_cause": "Årsak",
    "sit_hist_lines": "Linjer",
    "sit_hist_hour_label": "Tidspunkt",
    "cause_label.infrastruktur/signal": "Signalfeil",
    "cause_label.drift/kapasitet": "Redusert kapasitet",
    "cause_label.drift/ruteendring": "Ruteendring",
    "sit_hist_hour":           "kl. {h}",
    "sit_hist_cancel_rate":    "Kansellert",
    "sit_hist_trouble_rate":   "Avvik",
    "sit_hist_trouble_lift":   "Forhøyet risiko",
    "sit_hist_delay_p50":      "Forsinkelse p50",
    "sit_hist_delay_p90":      "Forsinkelse p90",
    "sit_hist_exp_disruption": "Forv. taptid",
    "sit_hist_n_situations":   "Hist. tilfeller",
    "sit_hist_reopen_spread":  "Åpner (p80/p90)",
    "sit_hist_impact_spread":  "Konsekvens (p80/p90)",
    "sit_delay": "Forsinkelse {n} min",
    "sit_delay_range": "Forsinkelse {lo}-{hi} min",
    "sit_cancel_pill": "{pct} sjanse for innstilling",
    "sit_tip_dep": "Avgang {stop}{detail}",
    "sit_tip_arr": "Framme {stop}{detail}",
    "sit_tip_delay": "forsinkelse typisk +{dur}",
    "sit_tip_p90": "(p90 +{dur})",
    "sit_tip_cancel": "innstilt {pct}",
    "tier_label.low": "LAV RISIKO",
    "tier_label.medium": "MIDDELS RISIKO",
    "tier_label.high": "HØY RISIKO",
    "dur_min": "{n} min",
    "dur_h": "{h} t",
    "dur_hm": "{h} t {m} min",
    "sev_label.hoy": "HØY RISIKO",
    "sev_label.middels": "MIDDELS RISIKO",
    "sev_label.lav": "LAV RISIKO",
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

    "footer_pre": "togpuls · data: ",
    "footer_source": "Entur Journey Planner v3",
    "footer_post": "",
    "footer_about": "Om",
    "footer_github": "GitHub",
    "footer_api": "API",
    "footer_macos": "macOS-app",

    "mac_hero_title": "Togpuls i menylinjen",
    "mac_hero_sub": "Last ned macOS-appen og få neste avgang ett klikk unna.",
    "mac_hero_cta": "Last ned for Mac",
    "mac_hero_dismiss": "Lukk",

    // About page
    "about_title": "Om togpuls",
    "about_back": "Tilbake til dashbordet",
    "about_lead": "togpuls er et sanntidsbilde av togtrafikken på en norsk stasjon — hvor mye som faktisk kjører, hva som er innstilt eller forsinket, og hvilke avvik som påvirker reisende akkurat nå.",
    "about_data_h": "Datakilde",
    "about_data_b": "Alle tall kommer fra Entur Journey Planner v3 (GraphQL). Avgangene hentes 90 minutter fram og 90 minutter tilbake i tid, og avvik beriker bildet med SIRI-situasjoner og KIX-estimater. Dataene oppdateres hvert 30. sekund med en buffer på 20 sekunder.",
    "about_how_h": "Slik leses tallene",
    "about_how_b": "Måleren viser andelen planlagte avganger som er gjennomført (bakover) og forventet gjennomført (framover). Risikonivået og LED-målerne for innstillinger og forsinkelser er forankret i sanntidsdata, slik at nivåordet aldri ligger lavere enn målerne tilsier.",
    "about_api_h": "API",
    "about_api_b": "De samme dataene er åpne via et enkelt REST-API. Se den interaktive dokumentasjonen for endepunkter og svarformat.",
    "about_api_link": "Åpne API-dokumentasjon",
    "about_source_h": "Kildekode",
    "about_source_b": "togpuls er åpen kildekode — FastAPI-backend og rammeverkfri frontend, uten byggesteg.",
    "about_source_link": "Se prosjektet på GitHub",
    "about_footer_pre": "Data: ",
    "about_footer_source": "Entur Journey Planner v3",
    "about_footer_post": " · NLOD-lisens",

    // Install page
    "install_title": "Installer Togpuls på Mac",
    "install_h1": "Installer Togpuls på Mac",
    "install_lead": "Togpuls finnes som en liten menylinje-app for macOS som viser neste avgang og avvik rett øverst på skjermen. Anbefalt installasjon er via Homebrew — den eneste veien som er friksjonsfri på macOS 15 (Sequoia) og nyere.",
    "install_brew_h": "Anbefalt: Med Homebrew",
    "install_brew_b": "Fire kommandoer i Terminal. Homebrew håndterer signering-omgåelse og oppdateringer for deg — kjør de tre første for å installere, og den siste senere for å oppdatere.",
    "install_brew_need": "Krever Homebrew. Har du det ikke? Installer fra ",
    "install_brew_need_end": " først.",
    "install_brew_trust": "Steg 2 lar Homebrew bruke vårt tredjeparts-tap — én gang, gjelder også fremtidige oppdateringer.",
    "install_copy": "Kopier kommando",
    "install_dmg_h": "Alternativ: Last ned DMG",
    "install_dmg_b": "Hvis du ikke har Homebrew, kan du laste ned DMG-en og installere manuelt. Da må du gjennom et ekstra steg i Systeminnstillinger fordi appen ikke er notarisert hos Apple.",
    "install_dmg_cta": "Last ned for Mac",
    "install_step1_h": "Åpne DMG-en og dra Togpuls til Applications.",
    "install_step2_h": "Prøv å åpne Togpuls fra Programmer.",
    "install_step2_b": "Du får en dialog som sier «Apple kunne ikke fastslå om Togpuls er fri for skadevare». Klikk «Ferdig».",
    "install_step3_h": "Gå til Systeminnstillinger → Personvern og sikkerhet.",
    "install_step3_b": "Bla ned til seksjonen «Sikkerhet». Der står det «Togpuls ble blokkert» med en knapp «Åpne likevel». Klikk den, bekreft med passord eller Touch ID.",
    "install_step4_h": "Togpuls starter — ikonet dukker opp i menylinjen.",
    "install_step4_b": "Dette ekstra steget gjøres kun første gang. Heretter starter appen normalt.",
    "install_why_h": "Hvorfor det ekstra steget?",
    "install_why_b": "Apple krever at apper notariseres (sendes til Apple for skanning) for å starte uten advarsler. Notarisering forutsetter et Apple Developer Program-medlemskap, som koster ~$99/år. Togpuls er et privat sideprosjekt uten kommersielt grunnlag for den kostnaden. Apper du installerer via Homebrew slipper unna fordi Homebrew fjerner Apples «quarantine»-flagg automatisk under installasjonen — derfor er det den anbefalte veien.",
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
    "station_search": "Search station…",
    "no_matches": "No matches",
    "apply": "Show",
    "theme_toggle": "Toggle theme",
    "theme_to_light": "Switch to light mode",
    "theme_to_dark": "Switch to dark mode",
    "lang_toggle": "Bytt til norsk",
    "lang_toggle_label": "NO",
    "never": "never",
    "loading": "loading…",
    "stale": "stale",
    "updated_at": "{time}",
    "reload": "Refresh",

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
    "big_p90": "most delayed (min)",
    "tip_util_past": "Share of scheduled trains that actually ran in the window.",
    "tip_util_future": "Share of upcoming trains expected to run.",
    "tip_cancelled": "Number of departures cancelled in the window.",
    "tip_delayed": "Number of departures delayed more than 3 minutes.",
    "tip_p90": "10% of trains are this delayed or worse (the 90th percentile). Captures the worst delays without letting outliers skew the average.",
    "tip_realised": "Number of departures that have run (history only).",
    "tip_scheduled": "Number of scheduled departures in the window.",

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
    "sit_also_prefix": "Also: {texts}",
    "summary_cause": "Cause: {cause}.",
    "sit_hist_cause": "Cause",
    "sit_hist_lines": "Lines",
    "sit_hist_hour_label": "Time",
    "cause_label.infrastruktur/signal": "Signal failure",
    "cause_label.drift/kapasitet": "Reduced capacity",
    "cause_label.drift/ruteendring": "Route change",
    "sit_hist_hour":           "{h}:00",
    "sit_hist_cancel_rate":    "Cancellation",
    "sit_hist_trouble_rate":   "Disruption",
    "sit_hist_trouble_lift":   "Trouble lift",
    "sit_hist_delay_p50":      "Delay p50",
    "sit_hist_delay_p90":      "Delay p90",
    "sit_hist_exp_disruption": "Exp. lost time",
    "sit_hist_n_situations":   "Hist. incidents",
    "sit_hist_reopen_spread":  "Reopens (p80/p90)",
    "sit_hist_impact_spread":  "Impact (p80/p90)",
    "sit_delay": "Delay {n} min",
    "sit_delay_range": "Delay {lo}-{hi} min",
    "sit_cancel_pill": "{pct} chance of cancellation",
    "sit_tip_dep": "Departure {stop}{detail}",
    "sit_tip_arr": "Arrival {stop}{detail}",
    "sit_tip_delay": "delay typically +{dur}",
    "sit_tip_p90": "(p90 +{dur})",
    "sit_tip_cancel": "cancel {pct}",
    "tier_label.low": "LOW RISK",
    "tier_label.medium": "MEDIUM RISK",
    "tier_label.high": "HIGH RISK",
    "dur_min": "{n} min",
    "dur_h": "{h}h",
    "dur_hm": "{h}h {m}m",
    "sev_label.hoy": "HIGH RISK",
    "sev_label.middels": "MEDIUM RISK",
    "sev_label.lav": "LOW RISK",
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

    "footer_pre": "togpuls · data: ",
    "footer_source": "Entur Journey Planner v3",
    "footer_post": "",
    "footer_about": "About",
    "footer_github": "GitHub",
    "footer_api": "API",
    "footer_macos": "macOS app",

    "mac_hero_title": "Togpuls in the menu bar",
    "mac_hero_sub": "Download the macOS app and keep the next departure one click away.",
    "mac_hero_cta": "Download for Mac",
    "mac_hero_dismiss": "Dismiss",

    // About page
    "about_title": "About togpuls",
    "about_back": "Back to the dashboard",
    "about_lead": "togpuls is a real-time picture of train traffic at a Norwegian station — how much is actually running, what's cancelled or delayed, and which disruptions affect travellers right now.",
    "about_data_h": "Data source",
    "about_data_b": "All figures come from Entur Journey Planner v3 (GraphQL). Departures are fetched 90 minutes ahead and 90 minutes back in time, enriched with SIRI situations and KIX estimates. The data refreshes every 30 seconds with a 20-second buffer.",
    "about_how_h": "Reading the numbers",
    "about_how_b": "The gauge shows the share of scheduled departures that ran (backward) and are expected to run (forward). The risk tier and the LED meters for cancellations and delays are anchored in live data, so the tier word never sits lower than the meters imply.",
    "about_api_h": "API",
    "about_api_b": "The same data is open via a simple REST API. See the interactive documentation for endpoints and the response format.",
    "about_api_link": "Open API documentation",
    "about_source_h": "Source code",
    "about_source_b": "togpuls is open source — a FastAPI backend and a framework-free frontend, with no build step.",
    "about_source_link": "View the project on GitHub",
    "about_footer_pre": "Data: ",
    "about_footer_source": "Entur Journey Planner v3",
    "about_footer_post": " · NLOD licence",

    // Install page
    "install_title": "Install Togpuls on Mac",
    "install_h1": "Install Togpuls on Mac",
    "install_lead": "Togpuls comes as a small macOS menu bar app that shows the next departure and disruptions right at the top of your screen. The recommended way to install it is via Homebrew — the only path that is frictionless on macOS 15 (Sequoia) and later.",
    "install_brew_h": "Recommended: With Homebrew",
    "install_brew_b": "Four commands in Terminal. Homebrew handles the signing workaround and updates for you — run the first three to install, and the last one later to update.",
    "install_brew_need": "Requires Homebrew. Don't have it? Install it from ",
    "install_brew_need_end": " first.",
    "install_brew_trust": "Step 2 lets Homebrew use our third-party tap — once, also covers future updates.",
    "install_copy": "Copy command",
    "install_dmg_h": "Alternative: download the DMG",
    "install_dmg_b": "If you don't have Homebrew you can download the DMG and install manually. You then have to go through one extra step in System Settings because the app isn't notarized with Apple.",
    "install_dmg_cta": "Download for Mac",
    "install_step1_h": "Open the DMG and drag Togpuls to Applications.",
    "install_step2_h": "Try to open Togpuls from Applications.",
    "install_step2_b": "You'll get a dialog saying \"Apple could not verify that Togpuls is free of malware\". Click <em>Done</em>.",
    "install_step3_h": "Go to System Settings → Privacy & Security.",
    "install_step3_b": "Scroll down to the \"Security\" section. There it says \"Togpuls was blocked\" with an \"Open Anyway\" button. Click it, confirm with password or Touch ID.",
    "install_step4_h": "Togpuls starts — the icon appears in the menu bar.",
    "install_step4_b": "This extra step is only required the first time. From then on the app launches normally.",
    "install_why_h": "Why the extra step?",
    "install_why_b": "Apple requires apps to be notarized (sent to Apple for scanning) to launch without warnings. Notarization requires an Apple Developer Program membership, which costs ~$99/year. Togpuls is a private side project without a commercial basis for that cost. Apps installed via Homebrew skip the warning because Homebrew removes Apple's \"quarantine\" flag automatically during install — that's why it's the recommended path.",
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
