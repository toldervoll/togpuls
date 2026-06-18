const POLL_MS = 30_000;
const DEFAULT_FROM_STOP_PLACE_ID = "NSR:StopPlace:337"; // Oslo S
const SEVERITIES = ["hoy", "middels", "lav", "ukjent"];
const SEVERITY_RANK = { hoy: 0, middels: 1, lav: 2, ukjent: 3 };
const GAUGE_CIRC = 2 * Math.PI * 50; // circumference for r=50

function severityLabel(sev) {
  return t(`sev_label.${sev}`);
}

// Render the KIX cause: a known category code → friendly label, an unknown
// code → prettified ("infrastruktur/signal" → "Infrastruktur · signal"), else
// the cause phrase pulled from the description. Returns "" when unknown.
function resolveCause(code, text) {
  if (code) {
    const key = `cause_label.${code}`;
    const label = t(key);
    if (label !== key) return label;
    return code
      .split("/")
      .map((p) => (p ? p[0].toUpperCase() + p.slice(1) : p))
      .join(" · ");
  }
  if (text) return text[0].toUpperCase() + text.slice(1);
  return "";
}

let situationView = "grouped"; // or "per-line"
let bigScope = "combined"; // "past" | "future" | "combined"
let lastSituations = [];
let lastData = null;
let currentFrom = DEFAULT_FROM_STOP_PLACE_ID;
let currentTo = ""; // empty = all directions
let refreshTimer = null;

function apiUrl() {
  const fromEnc = encodeURIComponent(currentFrom);
  if (currentTo) {
    return `/api/v1/analysis/${fromEnc}/to/${encodeURIComponent(currentTo)}`;
  }
  if (currentFrom === DEFAULT_FROM_STOP_PLACE_ID) {
    return `/api/v1/analysis`;
  }
  return `/api/v1/analysis/${fromEnc}`;
}

// ── Shareable route in the URL ─────────────────────────────────────────
// The URL hash mirrors the selected route as `#<from>-<to>` (e.g. #451-337)
// so a view can be copied and shared. Station ids are NSR stop place ids
// (NSR:StopPlace:N); we keep only the numeric N in the hash for compactness
// and re-expand on read. A hash is purely client-side, so a direct link works
// without a server route.

const STOP_PLACE_PREFIX = "NSR:StopPlace:";

function shortStopId(id) {
  return id && id.startsWith(STOP_PLACE_PREFIX) ? id.slice(STOP_PLACE_PREFIX.length) : id;
}

// Expand a hash stop id back to a full NSR id (337 → NSR:StopPlace:337).
// A value that already looks like a full id is passed through unchanged.
function fullStopId(value) {
  if (!value) return "";
  return /^\d+$/.test(value) ? STOP_PLACE_PREFIX + value : value;
}

// Parse `#<from>` or `#<from>-<to>` from the URL hash. `to` is always written
// together with `from`, so a single segment unambiguously means "from only".
function readUrlRoute() {
  const raw = location.hash.replace(/^#/, "");
  if (!raw) return { from: "", to: "", hasRoute: false };
  const [from, to] = raw.split("-");
  return { from: fullStopId(from), to: fullStopId(to), hasRoute: true };
}

// Reflect the current route in the URL hash without adding history entries.
// `to` always carries `from` alongside it (#337-451) so #451 can only mean
// from=451. Oslo S with all directions is the default → keep the URL clean.
function syncUrl() {
  let hash = "";
  if (currentTo) {
    hash = `#${shortStopId(currentFrom)}-${shortStopId(currentTo)}`;
  } else if (currentFrom && currentFrom !== DEFAULT_FROM_STOP_PLACE_ID) {
    hash = `#${shortStopId(currentFrom)}`;
  }
  const base = location.pathname + location.search;
  history.replaceState(null, "", hash ? base + hash : base);
}

function buildPerLineSituations(sits) {
  const byLine = new Map();
  for (const s of sits) {
    const text = s.summary || s.description || "(no text)";
    for (const line of s.paavirker_linjer || []) {
      let e = byLine.get(line);
      if (!e) {
        e = { line, severity: s.severity || "ukjent", texts: new Set(), estimate: null,
              cause_code: "", cause_text: "" };
        byLine.set(line, e);
      }
      e.texts.add(text);
      if (e.estimate == null && s.estimate != null) e.estimate = s.estimate;
      const cur = SEVERITY_RANK[e.severity] ?? 99;
      const inc = SEVERITY_RANK[s.severity] ?? 99;
      if (inc < cur) e.severity = s.severity;
      if (!e.cause_code && !e.cause_text) { e.cause_code = s.cause_code || ""; e.cause_text = s.cause_text || ""; }
    }
  }
  return Array.from(byLine.values())
    .map((e) => ({ ...e, texts: Array.from(e.texts).sort() }))
    .sort((a, b) => {
      const sa = SEVERITY_RANK[a.severity] ?? 99;
      const sb = SEVERITY_RANK[b.severity] ?? 99;
      if (sa !== sb) return sa - sb;
      return a.line.localeCompare(b.line, "nb");
    });
}

// Effective risk rank for a situation: the alert tier wins over SIRI severity
// (mirrors riskTier() in renderSituations), so a low-severity message that the
// backend elevated still sorts and represents its event as high.
function effSevRank(s) {
  const tier = s.estimate?.alert?.alert_tier?.toLowerCase();
  const sev = tier === "high" ? "hoy"
    : tier === "medium" ? "middels"
    : (s.severity || "ukjent");
  return SEVERITY_RANK[sev] ?? 99;
}

// Group messages by event (backend event_id), falling back to identical text.
// Several SX messages about one incident — e.g. "Innstilt" + "Ta neste tog" —
// collapse into a single card represented by its worst member.
function groupSituations(sits) {
  const groups = new Map();
  for (const s of sits) {
    const text = s.summary || s.description || "(no text)";
    const key = s.event_id || text;
    let g = groups.get(key);
    if (!g) {
      g = {
        text,
        severity: s.severity || "ukjent",
        lines: new Set(),
        quays: new Set(),
        texts: new Set(),
        count: 0,
        estimate: null,
        cause_code: "",
        cause_text: "",
        rank: 99,
      };
      groups.set(key, g);
    }
    g.count += 1;
    if (text) g.texts.add(text);
    for (const l of s.paavirker_linjer || []) g.lines.add(l);
    for (const q of s.paavirker_quays || []) g.quays.add(q);
    // The worst member represents the event: its text, severity, estimate, cause.
    const r = effSevRank(s);
    if (r < g.rank) {
      g.rank = r;
      g.text = text;
      g.severity = s.severity || "ukjent";
      if (s.estimate != null) g.estimate = s.estimate;
      g.cause_code = s.cause_code || "";
      g.cause_text = s.cause_text || "";
    } else if (g.estimate == null && s.estimate != null) {
      g.estimate = s.estimate;
    }
    if (!g.cause_code && !g.cause_text) { g.cause_code = s.cause_code || ""; g.cause_text = s.cause_text || ""; }
  }
  return Array.from(groups.values())
    .map((g) => ({
      ...g,
      lines: Array.from(g.lines).sort(),
      quays: Array.from(g.quays).sort(),
      texts: Array.from(g.texts),
    }))
    .sort((a, b) => {
      if (a.rank !== b.rank) return a.rank - b.rank;
      return b.count - a.count;
    });
}

const $ = (id) => document.getElementById(id);

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function fmtPct(x) {
  if (x === null || x === undefined || isNaN(x)) return "—";
  return Math.round(x * 100) + " %";
}

function fmtNum(x) {
  if (x === null || x === undefined) return "—";
  return new Intl.NumberFormat(intlLocale()).format(x);
}

function fmtDurationMin(mins) {
  const m = Math.max(0, Math.round(mins));
  if (m < 60) return t("dur_min", { n: m });
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? t("dur_hm", { h, m: r }) : t("dur_h", { h });
}

// The disruption-estimate service returns an `impact` block predicting when
// the situation clears: point_min_from_now plus a p50/p80/p90 spread and an
// `overdue` flag. Render the point estimate as a short ETA; tolerate a missing
// or differently-shaped payload by returning "" (nothing shown).
function formatEstimate(est) {
  const impact = est && typeof est === "object" ? est.impact : null;
  if (!impact || typeof impact !== "object") return "";
  if (impact.overdue === true) return t("sit_est_overdue");
  const mins = typeof impact.point_min_from_now === "number"
    ? impact.point_min_from_now
    : (typeof impact.p50_min_from_now === "number" ? impact.p50_min_from_now : null);
  if (mins === null || mins <= 0) return "";
  return t("sit_est_eta", { dur: fmtDurationMin(mins) });
}


// Fill the .sit-estimate node in a rendered <li>, or remove it when there is
// no usable estimate.
function applyEstimate(li, est) {
  const el = li.querySelector(".sit-estimate");
  if (!el) return;
  const txt = formatEstimate(est);
  if (!txt) {
    el.remove();
    return;
  }
  el.textContent = txt;
  if (est && est.impact && est.impact.overdue === true) el.classList.add("overdue");
}

// Attach a hover tooltip to .sit-estimate showing historical profile rows
// from estimate.alert + estimate.reopen/impact. No-ops when the estimate
// only has the two rates already visible as LED meters (fallback path).
function applyHistory(li, est, lines, cause) {
  const chip = li.querySelector(".sit-estimate");
  if (!chip) return;
  const alert = est && typeof est === "object" ? est.alert : null;
  const reopen = est && typeof est === "object" ? est.reopen : null;
  const impact = est && typeof est === "object" ? est.impact : null;

  const spread = (blk) => {
    if (!blk) return null;
    const p80 = typeof blk.p80_min_from_now === "number" ? fmtDurationMin(blk.p80_min_from_now) : null;
    const p90 = typeof blk.p90_min_from_now === "number" ? fmtDurationMin(blk.p90_min_from_now) : null;
    return p80 && p90 ? `~${p80} / ~${p90}` : (p80 || p90 || null);
  };

  const rows = [
    ["sit_hist_cancel_rate",    alert && typeof alert.cancel_rate    === "number" ? fmtRate(alert.cancel_rate)    : null],
    ["sit_hist_trouble_rate",   alert && typeof alert.trouble_rate   === "number" ? fmtRate(alert.trouble_rate)   : null],
    ["sit_hist_trouble_lift",   alert && typeof alert.trouble_lift   === "number" ? fmtRate(alert.trouble_lift)   : null],
    ["sit_hist_delay_p50",      alert && typeof alert.delay_p50      === "number" ? fmtDurationMin(alert.delay_p50)      : null],
    ["sit_hist_delay_p90",      alert && typeof alert.delay_p90      === "number" ? fmtDurationMin(alert.delay_p90)      : null],
    ["sit_hist_exp_disruption", alert && typeof alert.exp_disruption_min === "number" ? fmtDurationMin(alert.exp_disruption_min) : null],
    ["sit_hist_n_situations",   alert && typeof alert.n_situations   === "number" ? String(alert.n_situations)    : null],
    ["sit_hist_reopen_spread",  spread(reopen)],
    ["sit_hist_impact_spread",  spread(impact)],
  ].filter(([, v]) => v !== null);

  // The historical match hour as a plain field (matched_hour -1 = none).
  if (alert && typeof alert.matched_hour === "number" && alert.matched_hour >= 0) {
    rows.push(["sit_hist_hour_label", t("sit_hist_hour", { h: alert.matched_hour })]);
  }

  // Cause and lines as labelled fields at the top, formatted like every other
  // row (bold label + value).
  const lineList = (lines || []).filter(Boolean);
  if (lineList.length) rows.unshift(["sit_hist_lines", lineList.join(", ")]);
  if (cause) rows.unshift(["sit_hist_cause", cause]);

  if (!rows.length) return;

  const tip = document.createElement("div");
  tip.className = "sit-hist-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  const grid = document.createElement("div");
  grid.className = "sit-hist-grid";
  for (const [key, val] of rows) {
    const label = document.createElement("span");
    label.className = "sit-hist-label";
    label.textContent = t(key);
    const value = document.createElement("span");
    value.className = "sit-hist-value";
    value.textContent = val;
    grid.appendChild(label);
    grid.appendChild(value);
  }
  tip.appendChild(grid);

  const meta = chip.closest(".sit-meta") || chip.parentElement;
  meta.appendChild(tip);
  chip.addEventListener("mouseenter", () => { tip.hidden = false; });
  meta.addEventListener("mouseleave", () => { tip.hidden = true; });
}

// ── Alert metrics (estimate.alert) ──────────────────────────────────────
// The estimate service returns an `alert` block with a risk tier and two
// base rates. The tier replaces the SIRI severity word in the left chip;
// the rates become small LED meters left of the text.
const LED_SEGMENTS = 5;
const LED_HTML = "<i></i>".repeat(LED_SEGMENTS);
// Display scale: a rate at/above this lights the whole meter. Exact value is
// always in the tooltip — the LEDs are a glanceable relative indicator.
// The backend floors the tier word to these same anchors (_tier_from_rates in
// api/app.py) so the bars and the tier can never disagree — keep them in sync.
const CANCEL_RATE_FULL = 0.1; // 10% cancellations
const TROUBLE_RATE_FULL = 0.3; // 30% trouble
const TIER_SEV = { low: "lav", medium: "middels", high: "hoy" };

function fmtRate(x) {
  if (typeof x !== "number" || isNaN(x)) return "—";
  return new Intl.NumberFormat(intlLocale(), {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(x);
}

// Light the first N LED segments proportional to rate/full; remove the meter
// entirely when the rate is missing.
function renderRateMeter(el, rate, full, kind) {
  if (!el) return;
  if (typeof rate !== "number" || isNaN(rate)) {
    el.remove();
    return;
  }
  const lit = rate > 0
    ? Math.min(LED_SEGMENTS, Math.max(1, Math.ceil((rate / full) * LED_SEGMENTS)))
    : 0;
  el.querySelectorAll(".leds i").forEach((seg, i) => seg.classList.toggle("on", i < lit));
  const label = t(kind === "cancel" ? "rate_cancel" : "rate_trouble", { pct: fmtRate(rate) });
  el.title = label;
  el.setAttribute("aria-label", label);
}

// Set the left chip (tier when available, else SIRI severity) and the two
// rate meters for a rendered situation <li>.
function applyAlert(li, sev, est) {
  const alert = est && typeof est === "object" ? est.alert : null;
  const tierRaw = alert && typeof alert.alert_tier === "string"
    ? alert.alert_tier.toLowerCase()
    : null;
  const tier = tierRaw && TIER_SEV[tierRaw] ? tierRaw : null;

  const sevEl = li.querySelector(".sit-sev");
  if (sevEl) {
    if (tier) {
      sevEl.textContent = t(`tier_label.${tier}`);
      sevEl.className = `sit-sev tier-${tier}`;
      li.classList.add(`tier-${tier}`);
    } else {
      sevEl.textContent = severityLabel(sev);
      sevEl.className = `sit-sev sev-${sev}`;
    }
  }

  const meters = li.querySelector(".sit-meters");
  if (!meters) return;
  const hasCancel = alert && typeof alert.cancel_rate === "number";
  const hasTrouble = alert && typeof alert.trouble_rate === "number";
  if (!hasCancel && !hasTrouble) {
    meters.remove();
    return;
  }
  li.querySelector(".sit-body")?.classList.add("has-meters");
  renderRateMeter(meters.querySelector(".meter-cancel"), hasCancel ? alert.cancel_rate : null, CANCEL_RATE_FULL, "cancel");
  renderRateMeter(meters.querySelector(".meter-trouble"), hasTrouble ? alert.trouble_rate : null, TROUBLE_RATE_FULL, "trouble");
}

function renderLineStatus(cell, cancelledLines, delayedLines) {
  cell.replaceChildren();
  const c = cancelledLines || [];
  const d = delayedLines || [];
  if (!c.length && !d.length) {
    cell.textContent = "—";
    return;
  }
  if (c.length) {
    const chip = document.createElement("span");
    chip.className = "plat-line-chip red";
    chip.textContent = t("line_status_cancelled", { lines: c.join(", ") });
    cell.appendChild(chip);
  }
  if (d.length) {
    const chip = document.createElement("span");
    chip.className = "plat-line-chip amber";
    chip.textContent = t("line_status_delayed", { lines: d.join(", ") });
    cell.appendChild(chip);
  }
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString(intlLocale(), { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

// ── Motion helpers ─────────────────────────────────────────────────────

const _tickRaf = new WeakMap();

function tickTo(el, numericTarget) {
  if (!el) return;
  if (prefersReducedMotion()) {
    el.textContent = fmtNum(numericTarget);
    return;
  }
  const rawPrev = (el.textContent || "").replace(/\s/g, "").replace(/[^\d]/g, "");
  const prev = parseInt(rawPrev, 10) || 0;
  if (prev === numericTarget) return;
  const start = performance.now();
  const duration = 500;
  if (_tickRaf.has(el)) cancelAnimationFrame(_tickRaf.get(el));
  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const val = Math.round(prev + (numericTarget - prev) * ease);
    el.textContent = fmtNum(val);
    if (progress < 1) _tickRaf.set(el, requestAnimationFrame(step));
    else el.textContent = fmtNum(numericTarget);
  }
  _tickRaf.set(el, requestAnimationFrame(step));
}

function setGauge(svgId, pct) {
  const gauge = $(svgId);
  const arc = gauge ? gauge.querySelector(".gauge-arc") : null;
  if (!arc || !gauge) return;
  arc.style.transition = prefersReducedMotion() ? "none" : "";
  if (pct == null) {
    // No data — bare track, no arc (a 0-length arc still paints its
    // rounded line cap as a dot)
    arc.style.strokeDashoffset = GAUGE_CIRC;
    arc.style.stroke = "transparent";
    return;
  }
  const clamped = Math.max(0, Math.min(100, pct));
  const offset = GAUGE_CIRC * (1 - clamped / 100);
  arc.style.strokeDashoffset = offset;
  arc.style.stroke = clamped >= 90
    ? "var(--signal-green)" : clamped >= 70
    ? "var(--signal-amber)" : "var(--signal-red)";
}

function pulseLive() {
  const dot = $("live-dot");
  if (!dot || prefersReducedMotion()) return;
  dot.classList.remove("pulse");
  void dot.offsetWidth; // restart animation
  dot.classList.add("pulse");
}

function applySeverityDiff(newData) {
  if (!lastData) return;
  const newSits = newData?.situations || [];
  const oldHighTexts = new Set(
    (lastData.situations || [])
      .filter((s) => s.severity === "hoy")
      .map((s) => s.summary || s.description || "")
  );
  const hasNew = newSits.some(
    (s) => s.severity === "hoy" && !oldHighTexts.has(s.summary || s.description || "")
  );
  if (!hasNew || prefersReducedMotion()) return;
  // DOM not yet updated; pulse after render on next tick
  requestAnimationFrame(() => {
    const ul = $("situations");
    if (!ul) return;
    for (const li of ul.querySelectorAll("li.sev-hoy")) {
      li.classList.remove("severity-pulse");
      void li.offsetWidth;
      li.classList.add("severity-pulse");
      li.addEventListener("animationend", () => li.classList.remove("severity-pulse"), { once: true });
    }
  });
}

// ── State helpers ──────────────────────────────────────────────────────

function setStale(stale) {
  $("stale-badge").classList.toggle("hidden", !stale);
}

function setLoading(loading) {
  const badge = $("loading-badge");
  if (badge) badge.classList.toggle("hidden", !loading);
}


// ── Render: situations ─────────────────────────────────────────────────

function renderSituations(sits) {
  lastSituations = sits;
  const ul = $("situations");
  const sitCount = $("sit-count");
  const sitSummary = $("sit-summary");
  if (!ul) return;

  const groups = groupSituations(sits);
  const totalCount = sits.length;
  if (sitCount) {
    sitCount.textContent =
      groups.length === totalCount
        ? t("sit_count_simple", { n: totalCount })
        : t("sit_count_unique", { unique: groups.length, total: totalCount });
  }
  if (sitSummary) {
    if (groups.length === 0) {
      sitSummary.textContent = t("no_active_situations");
    } else {
      const riskTier = (g) => {
        const tier = g.estimate?.alert?.alert_tier?.toLowerCase();
        if (tier === "high") return "hoy";
        if (tier === "medium") return "middels";
        return g.severity;
      };
      const sevHigh = groups.filter((g) => riskTier(g) === "hoy").length;
      const sevMid = groups.filter((g) => riskTier(g) === "middels").length;
      const sevLow = groups.length - sevHigh - sevMid;
      const sevParts = [];
      if (sevHigh) sevParts.push(t("sev_count.hoy", { n: sevHigh }));
      if (sevMid) sevParts.push(t("sev_count.middels", { n: sevMid }));
      if (sevLow) sevParts.push(t("sev_count.lav", { n: sevLow }));
      sitSummary.textContent = t("sit_summary_top", {
        parts: sevParts.join(" · "),
        text: groups[0].text,
      });
    }
  }

  ul.innerHTML = "";
  if (sits.length === 0) {
    const li = document.createElement("li");
    li.className = "sev-lav";
    li.innerHTML = `<span class="sit-sev sev-lav"></span><div class="sit-body"><div class="sit-text muted"></div></div>`;
    li.querySelector(".sit-sev").textContent = t("sev_label.ingen");
    li.querySelector(".sit-text").textContent = t("no_active_situations");
    ul.appendChild(li);
    return;
  }

  if (situationView === "per-line") {
    const rows = buildPerLineSituations(sits);
    for (const r of rows) {
      const sev = SEVERITIES.includes(r.severity) ? r.severity : "ukjent";
      const li = document.createElement("li");
      li.className = `sev-${sev}`;
      const countBadge = r.texts.length > 1 ? `<span class="sit-count-badge">×${r.texts.length}</span>` : "";
      li.innerHTML = `
        <span class="sit-sev"></span>
        <div class="sit-body">
          <div class="sit-meters">
            <span class="rate-meter meter-cancel" role="img"><svg class="rate-ico" aria-hidden="true"><use href="#x-mark"/></svg><span class="leds" aria-hidden="true">${LED_HTML}</span></span>
            <span class="rate-meter meter-trouble" role="img"><svg class="rate-ico" aria-hidden="true"><use href="#clock"/></svg><span class="leds" aria-hidden="true">${LED_HTML}</span></span>
          </div>
          <div class="sit-content">
            <div class="sit-text"></div>
            <div class="sit-meta">
              <div class="sit-estimate"></div>
              <span class="sit-cause"></span>
            </div>
            <div class="sit-lines"></div>
          </div>
        </div>
        ${countBadge}`;
      li.querySelector(".sit-text").textContent = r.line;
      li.querySelector(".sit-lines").textContent = r.texts.join(" · ");
      const rCause = resolveCause(r.cause_code, r.cause_text);
      const rCauseEl = li.querySelector(".sit-cause");
      if (rCause) rCauseEl.textContent = rCause; else rCauseEl.remove();
      applyAlert(li, sev, r.estimate);
      applyEstimate(li, r.estimate);
      applyHistory(li, r.estimate, [r.line], rCause);
      ul.appendChild(li);
    }
  } else {
    for (const g of groups) {
      const sev = SEVERITIES.includes(g.severity) ? g.severity : "ukjent";
      const li = document.createElement("li");
      li.className = `sev-${sev}`;
      const lines = g.lines.join(", ");
      const countBadge = g.count > 1 ? `<span class="sit-count-badge">×${g.count}</span>` : "";
      li.innerHTML = `
        <span class="sit-sev"></span>
        <div class="sit-body">
          <div class="sit-meters">
            <span class="rate-meter meter-cancel" role="img"><svg class="rate-ico" aria-hidden="true"><use href="#x-mark"/></svg><span class="leds" aria-hidden="true">${LED_HTML}</span></span>
            <span class="rate-meter meter-trouble" role="img"><svg class="rate-ico" aria-hidden="true"><use href="#clock"/></svg><span class="leds" aria-hidden="true">${LED_HTML}</span></span>
          </div>
          <div class="sit-content">
            <div class="sit-text"></div>
            <div class="sit-meta">
              <div class="sit-estimate"></div>
              <span class="sit-cause"></span>
            </div>
            <div class="sit-members"></div>
            <div class="sit-lines"></div>
          </div>
        </div>
        ${countBadge}`;
      li.querySelector(".sit-text").textContent = g.text;
      const others = (g.texts || []).filter((x) => x !== g.text);
      li.querySelector(".sit-members").textContent = others.length
        ? t("sit_also_prefix", { texts: others.join(" · ") })
        : "";
      li.querySelector(".sit-lines").textContent = lines ? t("sit_lines_prefix", { lines }) : "";
      const gCause = resolveCause(g.cause_code, g.cause_text);
      const gCauseEl = li.querySelector(".sit-cause");
      if (gCause) gCauseEl.textContent = gCause; else gCauseEl.remove();
      applyAlert(li, sev, g.estimate);
      applyEstimate(li, g.estimate);
      applyHistory(li, g.estimate, g.lines, gCause);
      ul.appendChild(li);
    }
  }
}

// ── Render: timeline ───────────────────────────────────────────────────

function renderTimeline(buckets) {
  const host = $("timeline-bars");
  if (!host) return;
  host.innerHTML = "";
  if (!buckets.length) return;
  const max = Math.max(...buckets.map((b) => b.scheduled), 1);
  const bucketMin = buckets.length > 1
    ? (buckets[1].minutes_offset ?? 0) - (buckets[0].minutes_offset ?? 0)
    : 5;
  let pastSched = 0, futSched = 0, futCanc = 0;
  let nowMarkerInserted = false;
  let barIdx = 0;
  for (const b of buckets) {
    const isFuture = b.is_future === true ||
      (b.is_future == null && (b.minutes_offset ?? 0) >= 0);
    if (isFuture) {
      futSched += b.scheduled; futCanc += b.cancelled;
      if (!nowMarkerInserted) {
        const marker = document.createElement("div");
        marker.className = "now-marker";
        marker.title = t("time_now");
        host.appendChild(marker);
        nowMarkerInserted = true;
      }
    } else {
      pastSched += b.scheduled;
    }

    const bar = document.createElement("div");
    bar.className =
      "bar" +
      (b.scheduled === 0 ? " empty" : "") +
      (isFuture ? " future" : " past");
    bar.style.setProperty("--i", String(barIdx++));
    const delayed = b.delayed || 0;
    const clean = Math.max(0, b.realised - delayed);
    const cancPct    = (b.cancelled / max) * 78;
    const delayedPct = (delayed      / max) * 78;
    const cleanPct   = (clean        / max) * 78;
    if (b.scheduled === 0) {
      const stub = document.createElement("div");
      stub.className = "seg seg-empty";
      bar.appendChild(stub);
    } else {
      if (clean > 0) {
        const seg = document.createElement("div");
        seg.className = "seg seg-realised";
        seg.style.height = cleanPct + "%";
        bar.appendChild(seg);
      }
      if (delayed > 0) {
        const seg = document.createElement("div");
        seg.className = "seg seg-delayed";
        seg.style.height = delayedPct + "%";
        bar.appendChild(seg);
      }
      if (b.cancelled > 0) {
        const seg = document.createElement("div");
        seg.className = "seg seg-cancelled";
        seg.style.height = cancPct + "%";
        bar.appendChild(seg);
      }
    }
    bar.addEventListener("mouseenter", () => showBarTip(host, bar, b, bucketMin, isFuture));
    bar.addEventListener("mouseleave", () => hideBarTip(host));
    host.appendChild(bar);
  }
  if (!nowMarkerInserted) {
    const marker = document.createElement("div");
    marker.className = "now-marker";
    marker.title = t("time_now");
    host.appendChild(marker);
  }
}

// ── Timeline tooltip ───────────────────────────────────────────────────

const TIP_MAX_ROWS = 6;

function _tipEl(host) {
  let tip = host.querySelector(".tl-tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "tl-tip";
    tip.setAttribute("role", "tooltip");
    tip.hidden = true;
    host.appendChild(tip);
  }
  return tip;
}

function showBarTip(host, bar, b, bucketMin, isFuture) {
  const tip = _tipEl(host);
  tip.replaceChildren();

  // Header: time range + relative time
  const start = fmtTime(b.bucket_start);
  let end = "";
  try {
    end = fmtTime(new Date(new Date(b.bucket_start).getTime() + bucketMin * 60000).toISOString());
  } catch { /* leave empty */ }
  const off = b.minutes_offset ?? 0;
  const when = off === 0
    ? t("time_now")
    : off < 0 ? t("time_ago", { n: -off }) : t("time_in", { n: off });
  const head = document.createElement("div");
  head.className = "tl-tip-head";
  head.textContent = end ? `${start}–${end} · ${when}` : `${start} · ${when}`;
  tip.appendChild(head);

  // Count line — state-aware, no zero-noise
  const counts = document.createElement("div");
  counts.className = "tl-tip-counts";
  const parts = [];
  if (b.scheduled === 0) {
    parts.push({ text: t("tt_none"), cls: "" });
  } else if (isFuture) {
    parts.push({ text: t("tt_planned", { scheduled: fmtNum(b.scheduled) }), cls: "" });
  } else {
    parts.push({ text: t("tt_ran", { realised: fmtNum(b.realised), scheduled: fmtNum(b.scheduled) }), cls: "" });
  }
  if (b.cancelled > 0) parts.push({ text: t("tt_cancelled", { n: fmtNum(b.cancelled) }), cls: "tl-tip-red" });
  if ((b.delayed || 0) > 0) parts.push({ text: t("tt_delayed", { n: fmtNum(b.delayed) }), cls: "tl-tip-amber" });
  parts.forEach((p, i) => {
    if (i > 0) counts.appendChild(document.createTextNode(" · "));
    const span = document.createElement("span");
    if (p.cls) span.className = p.cls;
    span.textContent = p.text;
    counts.appendChild(span);
  });
  tip.appendChild(counts);

  // Departure rows
  const deps = b.departures || [];
  if (deps.length) {
    const list = document.createElement("div");
    list.className = "tl-tip-deps";
    for (const d of deps.slice(0, TIP_MAX_ROWS)) {
      const row = document.createElement("div");
      row.className = "tl-tip-dep" + (d.cancelled ? " cancelled" : "");
      const line = document.createElement("span");
      line.className = "tl-tip-line";
      line.textContent = d.line;
      const dest = document.createElement("span");
      dest.className = "tl-tip-dest";
      dest.textContent = d.destination ? `→ ${d.destination}` : "";
      const time = document.createElement("span");
      time.className = "tl-tip-time";
      time.textContent = fmtTime(d.aimed);
      row.append(line, dest, time);
      if (!d.cancelled && d.delay_min > 0) {
        const delay = document.createElement("span");
        delay.className = d.delay_min > 3 ? "tl-tip-delay" : "tl-tip-delay-minor";
        delay.textContent = `+${d.delay_min} min`;
        row.appendChild(delay);
      }
      list.appendChild(row);
    }
    if (deps.length > TIP_MAX_ROWS) {
      const more = document.createElement("div");
      more.className = "tl-tip-more";
      more.textContent = t("tt_more", { n: deps.length - TIP_MAX_ROWS });
      list.appendChild(more);
    }
    tip.appendChild(list);
  }

  // Position below the bars, clamped to the host; flip above when the
  // viewport has no room beneath.
  tip.hidden = false;
  const hostRect = host.getBoundingClientRect();
  const barRect = bar.getBoundingClientRect();
  tip.classList.toggle(
    "above",
    hostRect.bottom + tip.offsetHeight + 12 > window.innerHeight &&
      hostRect.top - tip.offsetHeight - 12 >= 0
  );
  const center = barRect.left - hostRect.left + barRect.width / 2;
  const half = tip.offsetWidth / 2;
  const left = Math.max(4, Math.min(center - half, hostRect.width - tip.offsetWidth - 4));
  tip.style.left = `${left}px`;
}

function hideBarTip(host) {
  const tip = host.querySelector(".tl-tip");
  if (tip) tip.hidden = true;
}

// ── Render: summary ────────────────────────────────────────────────────

function buildSummary(d) {
  const tm = d.train_movements || {};
  const pax = d.passenger_estimate || {};
  const sits = d.situations || [];
  const win = (d.stop_place && d.stop_place.window) || {};
  const winMin = win.minutter ?? 0;
  const fromName = (d.stop_place && d.stop_place.name) || t("default_stop");
  const toName = d.stop_place && d.stop_place.to_name;
  const corridor = toName ? `${fromName} → ${toName}` : fromName;

  const cancelled = tm.cancelled || 0;
  const delayed = tm.delayed_gt_3min || 0;
  const pastS = tm.past || {};
  const futS = tm.future || {};
  const pastSched = pastS.scheduled ?? tm.past_scheduled ?? 0;
  const futSched = futS.scheduled ?? tm.future_scheduled ?? 0;
  const futExpected = futSched - (futS.cancelled || 0);
  // Count situations the way the panel shows them: collapsed into events, with
  // the tier (not raw SIRI severity) deciding high/medium — so the prose count
  // matches the cards after clustering and supersession.
  const sitGroups = groupSituations(sits);
  const groupCount = sitGroups.length;
  const groupSev = (g) => {
    const tier = g.estimate?.alert?.alert_tier?.toLowerCase();
    return tier === "high" ? "hoy" : tier === "medium" ? "middels" : (g.severity || "ukjent");
  };
  const sevHigh = sitGroups.filter((g) => groupSev(g) === "hoy").length;
  const sevMid = sitGroups.filter((g) => groupSev(g) === "middels").length;
  const minorOnly = sevHigh === 0 && sevMid === 0;

  const where = toName
    ? t("where_to_from", { from: fromName, to: toName })
    : t("where_through", { from: fromName });

  // Sentence 1: traffic — scoped to the stat toggle (past/future/±window)
  const sentences = [];
  const issueList = (c, dl) => {
    const issues = [];
    if (c > 0) issues.push(t("summary_issue_cancelled", { n: fmtNum(c) }));
    if (dl > 0) issues.push(t("summary_issue_delayed", { n: fmtNum(dl) }));
    return issues;
  };
  const pc = pastS.cancelled || 0;
  const pd = pastS.delayed_gt_3min || 0;
  const fc = futS.cancelled || 0;
  const fd = futS.delayed_gt_3min || 0;
  // "alle 23" reads nicer than "23 av 23" (but "1 av 1" beats "alle 1")
  const countPhrase = (n, total) =>
    n === total && total > 1
      ? t("count_all", { n: fmtNum(total) })
      : t("count_of", { n: fmtNum(n), total: fmtNum(total) });
  const cleanPast =
    pastSched > 0 && pc === 0 && pd === 0 && (pastS.realised || 0) === pastSched;
  const cleanFuture = futSched > 0 && fc === 0 && fd === 0;

  const pastSentence = () => {
    if (pastSched === 0) return t("summary_no_traffic_past", { where, min: winMin });
    if (cleanPast) {
      return t("summary_all_clear_past", { past: fmtNum(pastSched), where, min: winMin });
    }
    let s = t("summary_past_base", {
      min: winMin,
      count: countPhrase(pastS.realised || 0, pastSched),
      where,
    });
    const issues = issueList(pc, pd);
    if (issues.length) s += "; " + issues.join(", ");
    return s + ".";
  };
  const futureSentence = () => {
    if (futSched === 0) return t("summary_no_traffic_future", { where, min: winMin });
    if (cleanFuture) {
      return t("summary_all_clear_future", { future: fmtNum(futSched), where, min: winMin });
    }
    let s = t("summary_future_base", {
      min: winMin,
      count: countPhrase(futExpected, futSched),
      where,
    });
    const issues = issueList(fc, fd);
    if (issues.length) s += "; " + issues.join(", ");
    return s + ".";
  };

  let trafficClean;
  if (bigScope === "past") {
    trafficClean = cleanPast;
    sentences.push(pastSentence());
  } else if (bigScope === "future") {
    trafficClean = cleanFuture;
    sentences.push(futureSentence());
  } else if (tm.scheduled === 0) {
    trafficClean = false;
    sentences.push(toName
      ? t("summary_no_trains_corridor", { corridor, min: winMin })
      : t("summary_no_traffic_station", { from: fromName, min: winMin }));
  } else if (futSched === 0) {
    // Combined, but the window only holds history — avoid "0 av 0" noise
    trafficClean = cleanPast;
    sentences.push(pastSentence());
  } else if (pastSched === 0) {
    trafficClean = cleanFuture;
    sentences.push(futureSentence());
  } else {
    trafficClean = cleanPast && cleanFuture;
    if (trafficClean) {
      sentences.push(t("summary_all_clear", {
        min: winMin,
        past: fmtNum(pastSched),
        future: fmtNum(futSched),
        where,
      }));
    } else {
      let s = t("summary_trains_base", {
        min: winMin,
        pcount: countPhrase(tm.realised || 0, pastSched),
        fcount: countPhrase(futExpected, futSched),
        where,
      });
      const issues = issueList(cancelled, delayed);
      if (issues.length) s += "; " + issues.join(", ");
      sentences.push(s + ".");
    }
  }

  // Sentence 2: situations
  if (groupCount === 0) {
    // Clean traffic already implies it; only worth saying when degraded.
    if (!trafficClean && tm.scheduled > 0) {
      sentences.push(t("no_active_situations"));
    }
  } else if (trafficClean && minorOnly) {
    // Small disturbance, trains all on plan: one short note, no figures.
    const affLines = pax.affected_lines || [];
    sentences.push(tp("summary_sit_minor", groupCount, {
      count: groupCount,
      lines: tp("lines_count", affLines.length),
    }));
  } else {
    const affLines = pax.affected_lines || [];
    const aff = fmtNum(pax.affected_passengers || 0);
    const disp = pax.displaced_passengers || 0;
    const sevParts = [];
    if (sevHigh) sevParts.push(t("sev_count.hoy", { n: sevHigh }));
    if (sevMid) sevParts.push(t("sev_count.middels", { n: sevMid }));
    const sevTxt = sevParts.length
      ? t("summary_sit_sev_wrap", { parts: sevParts.join(", ") })
      : "";
    let s = tp("summary_sit", groupCount, {
      count: groupCount,
      sev: sevTxt,
      lines: tp("lines_count", affLines.length),
      aff,
    });
    if (disp > 0) {
      s += t("summary_sit_displaced", { n: fmtNum(disp) });
    }
    sentences.push(s + ".");
  }

  // Cause sentence: only when the active events share a single known cause, so
  // we never imply one cause for a mix of unrelated situations.
  if (groupCount > 0) {
    const causes = new Set(
      sitGroups.map((g) => resolveCause(g.cause_code, g.cause_text)).filter(Boolean)
    );
    if (causes.size === 1) {
      sentences.push(t("summary_cause", { cause: [...causes][0] }));
    }
  }

  return sentences.join(" ");
}

// ── Render: stat counters (scoped past/future/combined) ────────────────

function scopeStats(tm) {
  if (bigScope === "past") return tm.past || {};
  if (bigScope === "future") return tm.future || {};
  return tm; // flat fields = combined ±window
}

function setLamp(tile, cls) {
  if (!tile) return;
  tile.classList.remove("lamp-green", "lamp-amber", "lamp-red");
  if (cls) tile.classList.add(cls);
}

function renderBigCounters() {
  const tm = (lastData || {}).train_movements || {};
  const s = scopeStats(tm);
  const isFuture = bigScope === "future";
  tickTo($("cnt-scheduled"), s.scheduled ?? 0);
  tickTo($("cnt-cancelled"), s.cancelled ?? 0);
  tickTo($("cnt-delayed"),   s.delayed_gt_3min ?? 0);
  $("cnt-p90").textContent = s.p90_delay_min == null ? "—" : s.p90_delay_min;
  // "Kjørt" is meaningless for the future scope — nothing has run yet.
  if (isFuture) {
    $("cnt-realised").textContent = "—";
  } else {
    tickTo($("cnt-realised"), s.realised ?? 0);
  }

  // Contextual gauges: history shows the past ring, future the forecast
  // ring, combined both.
  const wrapPast = $("gauge-wrap-past");
  const wrapFut = $("gauge-wrap-future");
  if (wrapPast) wrapPast.classList.toggle("hidden", isFuture);
  if (wrapFut) wrapFut.classList.toggle("hidden", bigScope === "past");

  // Semantic counter colours + signal lamps per tile
  const pastSched = tm.past_scheduled || 0;
  const utilPast = pastSched > 0 ? (100 * (tm.realised || 0)) / pastSched : 0;
  const kjortGreen = !isFuture && pastSched > 0 && utilPast >= 90;
  $("cnt-cancelled").classList.toggle("neg", (s.cancelled || 0) > 0);
  $("cnt-delayed").classList.toggle("sig-amber", (s.delayed_gt_3min || 0) > 0);
  $("cnt-realised").classList.toggle("sig-green", kjortGreen);

  const tileOf = (id) => $(id)?.parentElement;
  setLamp(tileOf("cnt-cancelled"), (s.cancelled || 0) > 0 ? "lamp-red" : null);
  setLamp(tileOf("cnt-delayed"), (s.delayed_gt_3min || 0) > 0 ? "lamp-amber" : null);
  setLamp(tileOf("cnt-p90"),
    s.p90_delay_min != null && s.p90_delay_min > 3 ? "lamp-amber" : null);
  setLamp(tileOf("cnt-realised"), kjortGreen ? "lamp-green" : null);
  tileOf("cnt-realised")?.classList.toggle("na", isFuture);
}

// ── Render: main ──────────────────────────────────────────────────────

function render(d) {
  lastData = d;

  // Header meta
  const w = d.stop_place?.window || {};
  $("window").textContent = `${fmtTime(w.fra)}–${fmtTime(w.til)}`;
  const durEl = $("window-dur");
  if (durEl) durEl.textContent = w.minutter != null ? `${w.minutter} min` : "—";
  const now = new Date().toLocaleTimeString(intlLocale(), { hour: "2-digit", minute: "2-digit" });
  $("updated").textContent = t("updated_at", { time: now });

  // Big stat: dual gauges (history | forecast) + counters
  const tm = d.train_movements || {};
  const pastSched = tm.past_scheduled || 0;
  const futSched = tm.future_scheduled || 0;
  const futCanc = tm.future_cancelled || 0;
  const utilPast = pastSched > 0
    ? Math.round((100 * (tm.realised || 0)) / pastSched) : null;
  const utilFut = futSched > 0
    ? Math.round((100 * (futSched - futCanc)) / futSched) : null;
  $("util-pct-past").textContent = utilPast == null ? "—" : utilPast + " %";
  $("util-pct-future").textContent = utilFut == null ? "—" : utilFut + " %";
  setGauge("gauge-past", utilPast);
  setGauge("gauge-future", utilFut);
  const gaugePastEl = $("gauge-past");
  if (gaugePastEl) gaugePastEl.setAttribute("aria-label", t("gauge_aria_past", { pct: utilPast ?? 0 }));
  const gaugeFutEl = $("gauge-future");
  if (gaugeFutEl) gaugeFutEl.setAttribute("aria-label", t("gauge_aria_future", { pct: utilFut ?? 0 }));

  renderBigCounters();

  $("summary-text").textContent = buildSummary(d);
  renderTimeline(d.timeline || []);

  // Situations
  renderSituations(d.situations || []);

  // Drive the summary card border colour from the highest active risk tier.
  const _TIER_RANK = { high: 0, medium: 1, low: 2 };
  let topTier = null;
  for (const sit of d.situations || []) {
    const tier = sit.estimate?.alert?.alert_tier?.toLowerCase();
    if (tier && _TIER_RANK[tier] !== undefined) {
      if (topTier === null || _TIER_RANK[tier] < _TIER_RANK[topTier]) topTier = tier;
    }
  }
  const summarySection = document.querySelector("section.summary");
  if (summarySection) {
    summarySection.classList.remove("tier-high", "tier-medium", "tier-low");
    if (topTier) summarySection.classList.add(`tier-${topTier}`);
  }

  // Platforms — exception-only: rows just for disrupted platforms
  const allPlats = d.platform_utilization || [];
  const plats = allPlats
    .filter((p) => (p.cancelled || 0) > 0 || (p.delayed || 0) > 0)
    .sort((a, b) =>
      (b.cancelled || 0) - (a.cancelled || 0) ||
      (b.delayed || 0) - (a.delayed || 0) ||
      (b.scheduled || 0) - (a.scheduled || 0));
  $("plat-meta").textContent = plats.length
    ? t("plat_meta_disrupted", { n: plats.length })
    : "";
  const platSummary = $("plat-summary");
  if (platSummary) {
    const totalCanc = allPlats.reduce((s, p) => s + (p.cancelled || 0), 0);
    const platsWithCanc = allPlats.filter((p) => (p.cancelled || 0) > 0).length;
    const totalDel = allPlats.reduce((s, p) => s + (p.delayed || 0), 0);
    const delayedLineSet = new Set();
    for (const p of allPlats) for (const ln of p.delayed_lines || []) delayedLineSet.add(ln);
    const busiest = allPlats.slice().sort((a, b) => (b.scheduled || 0) - (a.scheduled || 0))[0];
    const parts = [t("plat_count", { n: allPlats.length })];
    if (busiest && busiest.scheduled > 0) {
      const label = busiest.public_code || busiest.quay_name || busiest.quay_id;
      parts.push(t("plat_busiest", { label, n: busiest.scheduled }));
    }
    if (totalCanc > 0) {
      parts.push(t("plat_with_canc", { count: platsWithCanc, total: totalCanc }));
    } else {
      parts.push(t("plat_no_canc"));
    }
    if (delayedLineSet.size > 0) {
      parts.push(tp("plat_delayed_lines", delayedLineSet.size, {
        count: delayedLineSet.size,
        deps: totalDel,
      }));
    } else {
      parts.push(t("plat_no_delays"));
    }
    platSummary.textContent = parts.join(" · ");
  }
  const platTbl = $("plat-tbl");
  if (platTbl) platTbl.classList.toggle("hidden", plats.length === 0);
  const platEmpty = $("plat-empty");
  if (platEmpty) platEmpty.classList.toggle("hidden", plats.length > 0);
  const tb = $("platforms");
  tb.innerHTML = "";
  for (const p of plats) {
    const tr = document.createElement("tr");
    const code = p.public_code || p.quay_name || p.quay_id;
    tr.innerHTML =
      `<td></td>` +
      `<td>${fmtNum(p.scheduled)}</td>` +
      `<td>${fmtNum(p.realised)}</td>` +
      `<td>${fmtNum(p.cancelled)}</td>` +
      `<td>${fmtNum(p.delayed || 0)}</td>` +
      `<td class="lines"></td>`;
    tr.children[0].textContent = code;
    renderLineStatus(tr.children[5], p.cancelled_lines, p.delayed_lines);
    // data-label for mobile card layout
    tr.children[0].dataset.label = t("tbl_platform");
    tr.children[1].dataset.label = t("tbl_scheduled");
    tr.children[2].dataset.label = t("tbl_realised");
    tr.children[3].dataset.label = t("tbl_cancelled");
    tr.children[4].dataset.label = t("tbl_delayed");
    tr.children[5].dataset.label = t("tbl_lines");
    // Semantic chip colours
    if ((p.cancelled || 0) > 0) tr.children[3].classList.add("chip-red");
    if ((p.delayed || 0) > 0)   tr.children[4].classList.add("chip-amber");
    tb.appendChild(tr);
  }

  // Passenger estimate
  const pax = d.passenger_estimate || {};
  $("pax-headline-main").textContent = t("pax_main", { n: fmtNum(pax.estimated_passengers) });
  $("pax-note").textContent = t("pax_note");
  const known = pax.occupancy_known_realised || 0;
  const unknown = pax.occupancy_unknown_realised || 0;
  const totalReal = known + unknown;
  if (totalReal > 0) {
    const pct = Math.round((100 * known) / totalReal);
    $("pax-coverage").textContent = t("pax_coverage", {
      known, total: totalReal, pct, lf: pax.load_factor,
    });
  } else {
    $("pax-coverage").textContent = "";
  }

  const affLines = pax.affected_lines || [];
  const affEl = $("pax-affected");
  if (affLines.length > 0) {
    $("pax-affected-text").textContent = t("pax_affected_sentence", {
      n: fmtNum(pax.affected_passengers),
      lines: tp("lines_count", affLines.length),
    });
    affEl.classList.remove("hidden");
  } else {
    affEl.classList.add("hidden");
  }

  const dispEl = $("pax-displaced");
  if ((pax.displaced_passengers || 0) > 0) {
    $("pax-displaced-text").textContent = t("pax_displaced_sentence", {
      n: fmtNum(pax.displaced_passengers),
    });
    dispEl.classList.remove("hidden");
  } else {
    dispEl.classList.add("hidden");
  }

  const byLine = (pax.by_line || []).filter((r) => r.affected).slice(0, 5);
  const paxTbl = $("pax-by-line");
  const paxTbody = paxTbl.querySelector("tbody");
  paxTbody.innerHTML = "";
  if (byLine.length > 0) {
    paxTbl.classList.remove("hidden");
    for (const r of byLine) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td class="line-cell"></td><td></td><td></td><td></td><td></td>`;
      tr.children[0].textContent = r.linje;
      tr.children[1].textContent = fmtNum(r.passengers_realised);
      tr.children[2].textContent = fmtNum(r.cancelled_calls);
      tr.children[3].textContent = fmtNum(r.passengers_displaced);
      tr.children[4].textContent = (r.affecting_situations || []).length;
      tr.children[0].dataset.label = t("pax_tbl_line");
      tr.children[1].dataset.label = t("pax_tbl_passengers");
      tr.children[2].dataset.label = t("pax_tbl_cancelled");
      tr.children[3].dataset.label = t("pax_tbl_displaced");
      tr.children[4].dataset.label = t("pax_tbl_situations");
      paxTbody.appendChild(tr);
    }
  } else {
    paxTbl.classList.add("hidden");
  }
}

// ── Data fetching ──────────────────────────────────────────────────────

async function refresh() {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
  setLoading(true);
  try {
    const r = await fetch(apiUrl(), { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    applySeverityDiff(d);
    render(d);
    pulseLive();
    setStale(false);
  } catch (e) {
    setStale(true);
    console.error("refresh failed", e);
  } finally {
    setLoading(false);
    refreshTimer = setTimeout(refresh, POLL_MS);
  }
}

// ── Route picker ───────────────────────────────────────────────────────

async function initRoutePicker() {
  const fromSel = $("from-select");
  const toSel = $("to-select");
  if (!fromSel || !toSel) return;

  try {
    const savedFrom = localStorage.getItem("togpuls-from");
    if (savedFrom) currentFrom = savedFrom;
    const savedTo = localStorage.getItem("togpuls-to");
    if (savedTo) currentTo = savedTo;
  } catch (e) {}

  // A route in the URL hash wins over local prefs so a shared link opens the
  // intended view. When only `from` is given, `to` is treated as cleared.
  const urlRoute = readUrlRoute();
  if (urlRoute.from) currentFrom = urlRoute.from;
  if (urlRoute.hasRoute) currentTo = urlRoute.to;

  let stations = [];
  try {
    const r = await fetch("/api/v1/stations", { cache: "no-store" });
    if (r.ok) stations = await r.json();
  } catch (e) {
    console.error("stations failed", e);
  }

  for (const s of stations) {
    const fromOpt = document.createElement("option");
    fromOpt.value = s.id; fromOpt.textContent = s.name;
    fromSel.appendChild(fromOpt);
    const toOpt = document.createElement("option");
    toOpt.value = s.id; toOpt.textContent = s.name;
    toSel.appendChild(toOpt);
  }

  if (![...fromSel.options].some((o) => o.value === currentFrom)) {
    currentFrom = DEFAULT_FROM_STOP_PLACE_ID;
  }
  if (currentTo && (currentTo === currentFrom ||
      ![...toSel.options].some((o) => o.value === currentTo))) {
    currentTo = "";
  }
  fromSel.value = currentFrom;
  toSel.value = currentTo;
  // Normalise the address bar to the resolved route (e.g. an unknown id in
  // the link falls back to defaults, and the URL should reflect that).
  syncUrl();

  const swapBtn = $("swap-btn");

  function applyRoute() {
    if (toSel.value && toSel.value === fromSel.value) {
      toSel.value = "";
    }
    if (swapBtn) swapBtn.disabled = !toSel.value;
    currentFrom = fromSel.value || DEFAULT_FROM_STOP_PLACE_ID;
    currentTo = toSel.value;
    try {
      localStorage.setItem("togpuls-from", currentFrom);
      if (currentTo) localStorage.setItem("togpuls-to", currentTo);
      else localStorage.removeItem("togpuls-to");
    } catch (e) {}
    syncUrl();
    refresh();
  }

  fromSel.addEventListener("change", applyRoute);
  toSel.addEventListener("change", applyRoute);

  // Re-apply the route when the hash is edited or a new link is opened in the
  // same tab. replaceState (used by syncUrl) does not fire this, so no loop.
  window.addEventListener("hashchange", () => {
    const r = readUrlRoute();
    const known = (sel, id) => id && [...sel.options].some((o) => o.value === id);
    fromSel.value = known(fromSel, r.from) ? r.from : DEFAULT_FROM_STOP_PLACE_ID;
    toSel.value = known(toSel, r.to) ? r.to : "";
    applyRoute();
  });

  if (swapBtn) {
    swapBtn.disabled = !toSel.value;
    swapBtn.addEventListener("click", () => {
      if (!toSel.value) return;
      const from = fromSel.value;
      fromSel.value = toSel.value;
      toSel.value = from;
      applyRoute();
    });
  }
}

// ── Theme toggle ───────────────────────────────────────────────────────

function currentTheme() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit === "light" || explicit === "dark") return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function updateThemeToggleLabel() {
  const btn = $("theme-toggle");
  if (!btn) return;
  const theme = currentTheme();
  const label = theme === "dark" ? t("theme_to_light") : t("theme_to_dark");
  btn.setAttribute("aria-label", label);
  btn.setAttribute("title", label);
  // Icons are toggled via CSS based on data-theme on <html>
}

function initThemeToggle() {
  const btn = $("theme-toggle");
  if (!btn) return;
  updateThemeToggleLabel();
  btn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("togpuls-theme", next); } catch (e) {}
    updateThemeToggleLabel();
  });
  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      const saved = localStorage.getItem("togpuls-theme");
      if (saved !== "light" && saved !== "dark") updateThemeToggleLabel();
    });
  } catch (e) {}
}

// ── Situation view toggle ──────────────────────────────────────────────

function initSituationToggle() {
  const root = document.getElementById("sit-view-toggle");
  if (!root) return;
  root.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-view]");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    if (btn.dataset.view === situationView) return;
    situationView = btn.dataset.view;
    for (const b of root.querySelectorAll("button")) {
      b.classList.toggle("active", b.dataset.view === situationView);
    }
    renderSituations(lastSituations);
  });
}

// ── Big stat scope toggle (history / future / combined) ────────────────

function initBigScopeToggle() {
  const root = $("big-scope-toggle");
  if (!root) return;
  root.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-scope]");
    if (!btn || btn.dataset.scope === bigScope) return;
    bigScope = btn.dataset.scope;
    for (const b of root.querySelectorAll("button")) {
      b.classList.toggle("active", b.dataset.scope === bigScope);
    }
    renderBigCounters();
    if (lastData) $("summary-text").textContent = buildSummary(lastData);
  });
}

// ── Lang toggle ────────────────────────────────────────────────────────

function initLangToggle() {
  const btn = $("lang-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => {
    setLang(currentLang() === "no" ? "en" : "no");
  });
}

// ── i18n:change re-render ──────────────────────────────────────────────

document.addEventListener("i18n:change", () => {
  updateThemeToggleLabel();
  if (lastData) render(lastData);
});

// ── Boot ───────────────────────────────────────────────────────────────

initThemeToggle();
initLangToggle();
initSituationToggle();
initBigScopeToggle();
initRoutePicker().then(refresh);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.error("sw register failed", err);
    });
  });
}
