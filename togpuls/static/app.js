const POLL_MS = 30_000;
const DEFAULT_FROM_STOP_PLACE_ID = "NSR:StopPlace:337"; // Oslo S
const SEVERITIES = ["hoy", "middels", "lav", "ukjent"];
const SEVERITY_RANK = { hoy: 0, middels: 1, lav: 2, ukjent: 3 };

function severityLabel(sev) {
  return t(`sev_label.${sev}`);
}

let situationView = "grouped"; // or "per-line"
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

function buildPerLineSituations(sits) {
  const byLine = new Map();
  for (const s of sits) {
    const text = s.summary || s.description || "(no text)";
    for (const line of s.paavirker_linjer || []) {
      let e = byLine.get(line);
      if (!e) {
        e = { line, severity: s.severity || "ukjent", texts: new Set() };
        byLine.set(line, e);
      }
      e.texts.add(text);
      const cur = SEVERITY_RANK[e.severity] ?? 99;
      const inc = SEVERITY_RANK[s.severity] ?? 99;
      if (inc < cur) e.severity = s.severity;
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

function groupSituations(sits) {
  const groups = new Map();
  for (const s of sits) {
    const text = s.summary || s.description || "(no text)";
    const key = text;
    let g = groups.get(key);
    if (!g) {
      g = {
        text,
        severity: s.severity || "ukjent",
        lines: new Set(),
        quays: new Set(),
        count: 0,
      };
      groups.set(key, g);
    }
    g.count += 1;
    for (const l of s.paavirker_linjer || []) g.lines.add(l);
    for (const q of s.paavirker_quays || []) g.quays.add(q);
    const cur = SEVERITY_RANK[g.severity] ?? 99;
    const inc = SEVERITY_RANK[s.severity] ?? 99;
    if (inc < cur) g.severity = s.severity;
  }
  return Array.from(groups.values())
    .map((g) => ({
      ...g,
      lines: Array.from(g.lines).sort(),
      quays: Array.from(g.quays).sort(),
    }))
    .sort((a, b) => {
      const sa = SEVERITY_RANK[a.severity] ?? 99;
      const sb = SEVERITY_RANK[b.severity] ?? 99;
      if (sa !== sb) return sa - sb;
      return b.count - a.count;
    });
}

const $ = (id) => document.getElementById(id);

function fmtPct(x) {
  if (x === null || x === undefined || isNaN(x)) return "—";
  return Math.round(x * 100) + " %";
}

function fmtNum(x) {
  if (x === null || x === undefined) return "—";
  return new Intl.NumberFormat(intlLocale()).format(x);
}

function formatLineStatus(cancelledLines, delayedLines) {
  const c = cancelledLines || [];
  const d = delayedLines || [];
  const parts = [];
  if (c.length) parts.push(t("line_status_cancelled", { lines: c.join(", ") }));
  if (d.length) parts.push(t("line_status_delayed", { lines: d.join(", ") }));
  return parts.join(", ") || "—";
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString(intlLocale(), { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function setStale(stale) {
  $("stale-badge").classList.toggle("hidden", !stale);
}

function setLoading(loading) {
  const badge = $("loading-badge");
  if (badge) badge.classList.toggle("hidden", !loading);
}

function setApplyDirty(dirty) {
  const btn = $("apply-btn");
  if (btn) btn.setAttribute("data-dirty", dirty ? "true" : "false");
}

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
      const sevHigh = groups.filter((g) => g.severity === "hoy").length;
      const sevMid = groups.filter((g) => g.severity === "middels").length;
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
        <span class="sit-sev sev-${sev}"></span>
        <div class="sit-body">
          <div class="sit-text"></div>
          <div class="sit-lines"></div>
        </div>
        ${countBadge}`;
      li.querySelector(".sit-sev").textContent = severityLabel(sev);
      li.querySelector(".sit-text").textContent = r.line;
      li.querySelector(".sit-lines").textContent = r.texts.join(" · ");
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
        <span class="sit-sev sev-${sev}"></span>
        <div class="sit-body">
          <div class="sit-text"></div>
          <div class="sit-lines"></div>
        </div>
        ${countBadge}`;
      li.querySelector(".sit-sev").textContent = severityLabel(sev);
      li.querySelector(".sit-text").textContent = g.text;
      li.querySelector(".sit-lines").textContent = lines ? t("sit_lines_prefix", { lines }) : "";
      ul.appendChild(li);
    }
  }
}

function renderTimeline(buckets) {
  const host = $("timeline-bars");
  const meta = $("timeline-meta");
  if (!host) return; // stale HTML — section not present
  host.innerHTML = "";
  if (!buckets.length) {
    if (meta) meta.textContent = t("timeline_no_data");
    return;
  }
  const max = Math.max(...buckets.map((b) => b.scheduled), 1);
  let pastSched = 0, pastReal = 0, pastCanc = 0;
  let futSched = 0, futReal = 0, futCanc = 0;
  let nowMarkerInserted = false;
  for (const b of buckets) {
    const isFuture = b.is_future === true ||
      (b.is_future == null && (b.minutes_offset ?? 0) >= 0);
    if (isFuture) {
      futSched += b.scheduled; futReal += b.realised; futCanc += b.cancelled;
      if (!nowMarkerInserted) {
        const marker = document.createElement("div");
        marker.className = "now-marker";
        marker.title = t("time_now");
        host.appendChild(marker);
        nowMarkerInserted = true;
      }
    } else {
      pastSched += b.scheduled; pastReal += b.realised; pastCanc += b.cancelled;
    }

    const bar = document.createElement("div");
    bar.className =
      "bar" +
      (b.scheduled === 0 ? " empty" : "") +
      (isFuture ? " future" : " past");
    const realPct = (b.realised / max) * 100;
    const cancPct = (b.cancelled / max) * 100;
    if (b.cancelled > 0) {
      const seg = document.createElement("div");
      seg.className = "seg seg-cancelled";
      seg.style.height = cancPct + "%";
      bar.appendChild(seg);
    }
    if (b.realised > 0) {
      const seg = document.createElement("div");
      seg.className = "seg seg-realised";
      seg.style.height = realPct + "%";
      bar.appendChild(seg);
    }
    const time = fmtTime(b.bucket_start);
    const off = b.minutes_offset ?? 0;
    const when = off === 0
      ? t("time_now")
      : off < 0 ? t("time_ago", { n: -off }) : t("time_in", { n: off });
    const verb = isFuture
      ? t("bar_future_tooltip", { realised: b.realised, cancelled: b.cancelled, scheduled: b.scheduled })
      : t("bar_past_tooltip", { realised: b.realised, cancelled: b.cancelled, scheduled: b.scheduled });
    bar.title = `${time} (${when}): ${verb}`;
    host.appendChild(bar);
  }
  // If the response was entirely past (no future buckets), still emit the
  // marker at the end so the user sees the "now" boundary.
  if (!nowMarkerInserted) {
    const marker = document.createElement("div");
    marker.className = "now-marker";
    marker.title = t("time_now");
    host.appendChild(marker);
  }
  meta.textContent = t("timeline_meta", {
    past: pastSched,
    future: futSched,
    fcancelled: futCanc,
  });
}

function buildSummary(d) {
  const tm = d.train_movements || {};
  const cap = d.capacity_vs_normal || {};
  const pax = d.passenger_estimate || {};
  const sits = d.situations || [];
  const win = (d.stop_place && d.stop_place.window) || {};
  const winMin = win.minutter ?? 0;
  const fromName = (d.stop_place && d.stop_place.name) || t("default_stop");
  const toName = d.stop_place && d.stop_place.to_name;
  const corridor = toName ? `${fromName} → ${toName}` : fromName;
  const util = Math.round((cap.kapasitetsutnyttelse || 0) * 100);

  const sentences = [];
  if (tm.scheduled > 0) {
    const where = toName
      ? t("where_to_from", { from: fromName, to: toName })
      : t("where_through", { from: fromName });
    sentences.push(t("summary_trains", {
      min: winMin,
      realised: fmtNum(tm.realised),
      scheduled: fmtNum(tm.scheduled),
      where,
      util,
      cancelled: fmtNum(tm.cancelled),
      delayed: fmtNum(tm.delayed_gt_3min),
    }));
  } else if (toName) {
    sentences.push(t("summary_no_trains_corridor", { corridor, min: winMin }));
  } else {
    sentences.push(t("summary_no_traffic_station", { from: fromName, min: winMin }));
  }

  if (sits.length > 0) {
    const affLines = pax.affected_lines || [];
    const aff = fmtNum(pax.affected_passengers || 0);
    const disp = pax.displaced_passengers || 0;
    const sevHigh = sits.filter((s) => s.severity === "hoy").length;
    const sevMid = sits.filter((s) => s.severity === "middels").length;
    const sevParts = [];
    if (sevHigh) sevParts.push(t("sev_count.hoy", { n: sevHigh }));
    if (sevMid) sevParts.push(t("sev_count.middels", { n: sevMid }));
    const sevTxt = sevParts.length
      ? t("summary_sit_sev_wrap", { parts: sevParts.join(", ") })
      : "";
    let s = tp("summary_sit", sits.length, {
      count: sits.length,
      sev: sevTxt,
      lines: tp("lines_count", affLines.length),
      aff,
    });
    if (disp > 0) {
      s += t("summary_sit_displaced", { n: fmtNum(disp) });
    }
    sentences.push(s + ".");
  } else {
    sentences.push(t("no_active_situations"));
  }

  return sentences.join(" ");
}

function render(d) {
  lastData = d;
  // Header: the route picker is now the only stop label, no h1 to update.
  const w = d.stop_place?.window || {};
  $("window").textContent = `${fmtTime(w.fra)}–${fmtTime(w.til)}`;
  const durEl = $("window-dur");
  if (durEl) durEl.textContent = w.minutter != null ? `${w.minutter} min` : "—";
  const now = new Date().toLocaleTimeString(intlLocale(), { hour: "2-digit", minute: "2-digit" });
  $("updated").textContent = t("updated_at", { time: now });

  // Big stat
  const tm = d.train_movements || {};
  const cap = d.capacity_vs_normal || {};
  $("util-pct").textContent = fmtPct(cap.kapasitetsutnyttelse);
  $("summary-text").textContent = buildSummary(d);
  renderTimeline(d.timeline || []);
  $("cnt-scheduled").textContent = fmtNum(tm.scheduled);
  $("cnt-realised").textContent = fmtNum(tm.realised);
  $("cnt-cancelled").textContent = fmtNum(tm.cancelled);
  $("cnt-delayed").textContent = fmtNum(tm.delayed_gt_3min);
  $("cnt-p90").textContent = tm.p90_delay_min == null ? "—" : tm.p90_delay_min;

  // Situations
  renderSituations(d.situations || []);

  // Spor (topp 10)
  const allPlats = d.platform_utilization || [];
  const plats = allPlats.slice(0, 10);
  $("plat-meta").textContent = t("platforms_topx_of_y", { x: plats.length, y: allPlats.length });
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
    tr.children[5].textContent = formatLineStatus(p.cancelled_lines, p.delayed_lines);
    tb.appendChild(tr);
  }

  // Passenger box
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
      paxTbody.appendChild(tr);
    }
  } else {
    paxTbl.classList.add("hidden");
  }
}

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
    render(d);
    setStale(false);
  } catch (e) {
    setStale(true);
    console.error("refresh failed", e);
  } finally {
    setLoading(false);
    refreshTimer = setTimeout(refresh, POLL_MS);
  }
}

async function initRoutePicker() {
  const fromSel = $("from-select");
  const toSel = $("to-select");
  const applyBtn = $("apply-btn");
  if (!fromSel || !toSel || !applyBtn) return;

  try {
    const savedFrom = localStorage.getItem("togpuls-from");
    if (savedFrom) currentFrom = savedFrom;
    const savedTo = localStorage.getItem("togpuls-to");
    if (savedTo) currentTo = savedTo;
  } catch (e) {}

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

  // If saved FROM isn't in the list, fall back to default.
  if (![...fromSel.options].some((o) => o.value === currentFrom)) {
    currentFrom = DEFAULT_FROM_STOP_PLACE_ID;
  }
  fromSel.value = currentFrom;
  toSel.value = currentTo;
  setApplyDirty(false);

  function updateDirty() {
    // Picking the same station for both makes no sense — clear TO.
    if (toSel.value && toSel.value === fromSel.value) {
      toSel.value = "";
    }
    const dirty =
      (fromSel.value || DEFAULT_FROM_STOP_PLACE_ID) !== currentFrom ||
      toSel.value !== currentTo;
    setApplyDirty(dirty);
  }
  fromSel.addEventListener("change", updateDirty);
  toSel.addEventListener("change", updateDirty);

  applyBtn.addEventListener("click", () => {
    currentFrom = fromSel.value || DEFAULT_FROM_STOP_PLACE_ID;
    currentTo = toSel.value;
    try {
      localStorage.setItem("togpuls-from", currentFrom);
      if (currentTo) localStorage.setItem("togpuls-to", currentTo);
      else localStorage.removeItem("togpuls-to");
    } catch (e) {}
    setApplyDirty(false);
    refresh();
  });
}

function currentTheme() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit === "light" || explicit === "dark") return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function updateThemeToggleLabel() {
  const icon = $("theme-toggle-icon");
  const btn = $("theme-toggle");
  if (!icon) return;
  const theme = currentTheme();
  icon.textContent = theme === "dark" ? "☀" : "☾";
  if (btn) {
    const label = theme === "dark" ? t("theme_to_light") : t("theme_to_dark");
    btn.setAttribute("aria-label", label);
    btn.setAttribute("title", label);
  }
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
  // Track system changes when no explicit choice has been saved.
  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      const saved = localStorage.getItem("togpuls-theme");
      if (saved !== "light" && saved !== "dark") updateThemeToggleLabel();
    });
  } catch (e) {}
}

function initSituationToggle() {
  const root = document.getElementById("sit-view-toggle");
  if (!root) return;
  root.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-view]");
    if (!btn) return;
    // Prevent the parent <details> from toggling open/closed.
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

function initLangToggle() {
  const btn = $("lang-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => {
    setLang(currentLang() === "no" ? "en" : "no");
  });
}

// Re-render dynamic content when the language changes.
document.addEventListener("i18n:change", () => {
  updateThemeToggleLabel();
  if (lastData) render(lastData);
});

initThemeToggle();
initLangToggle();
initSituationToggle();
initRoutePicker().then(refresh);

// Register the service worker so the page is installable and works offline.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.error("sw register failed", err);
    });
  });
}
