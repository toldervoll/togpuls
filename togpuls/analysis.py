"""Turn a Journey Planner stopPlace response into the four-block analysis."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from togpuls.capacity import CAPACITY_PER_VEHICLE, DEFAULT_LOAD_FACTOR
from togpuls.occupancy import OCCUPANCY_LOAD_FACTOR
from togpuls.models import (
    Analysis,
    CapacityVsNormal,
    LineMovement,
    LinePassengers,
    MovementStats,
    PassengerEstimate,
    PlatformUsage,
    Situation,
    StopPlaceInfo,
    TrainMovements,
    Window,
)

SEVERITY_MAP: dict[str, str] = {
    "normal": "lav",
    "slight": "lav",
    "noImpact": "lav",
    "severe": "middels",
    "verySevere": "hoy",
    "undefined": "ukjent",
}

DELAY_THRESHOLD_MIN = 3.0


def _minutes_between(iso_a: str | None, iso_b: str | None) -> float | None:
    if not iso_a or not iso_b:
        return None
    try:
        a = datetime.fromisoformat(iso_a)
        b = datetime.fromisoformat(iso_b)
        return (b - a).total_seconds() / 60
    except (ValueError, TypeError):
        return None


def _delay_percentiles(delays: list[float]) -> tuple[float | None, float | None]:
    """(median, p90) of a delay list, or (None, None) when empty."""
    if not delays:
        return None, None
    s = sorted(delays)
    p90_idx = max(0, int(len(s) * 0.9) - 1)
    return round(statistics.median(s), 2), round(s[p90_idx], 2)


def _first_text(field) -> str:
    """Pick the first non-empty `value` from a SIRI text field (list or dict)."""
    if isinstance(field, list):
        for item in field:
            if isinstance(item, dict) and item.get("value"):
                return item["value"]
        return ""
    if isinstance(field, dict):
        return field.get("value", "") or ""
    return ""


def collect_situation_ids(response: dict) -> set[str]:
    """All SIRI situation keys in a stopPlace response.

    Keyed the same way the accumulator in `analyse()` keys them
    (`situationNumber`, falling back to `id`) so estimates fetched up front
    line up with the entries built later. Used by callers to fetch disruption
    estimates concurrently before `analyse()` runs.
    """
    ids: set[str] = set()
    quays = (response.get("stopPlace") or {}).get("quays") or []
    for quay in quays:
        for call in quay.get("estimatedCalls") or []:
            for sit in call.get("situations") or []:
                key = sit.get("situationNumber") or sit.get("id")
                if key:
                    ids.add(key)
    return ids


def _call_aimed(call: dict) -> str | None:
    return call.get("aimedDepartureTime") or call.get("aimedArrivalTime")


def _call_expected(call: dict) -> str | None:
    return call.get("expectedDepartureTime") or call.get("expectedArrivalTime")


def _in_window(
    call: dict, now: datetime, horizon_min: int, look_back_min: int = 0
) -> bool:
    aimed = _call_aimed(call)
    if not aimed:
        return False
    try:
        ts = datetime.fromisoformat(aimed)
    except (ValueError, TypeError):
        return False
    return now - timedelta(minutes=look_back_min) <= ts <= now + timedelta(minutes=horizon_min)


def _passes_through(sj: dict, from_id: str, to_id: str) -> bool:
    """Does this service journey call at from_id and later at to_id?"""
    quays = sj.get("quays") or []
    from_idx = -1
    for i, q in enumerate(quays):
        sp = (q or {}).get("stopPlace") or {}
        if sp.get("id") == from_id:
            from_idx = i
            break
    if from_idx < 0:
        return False
    for q in quays[from_idx + 1 :]:
        sp = (q or {}).get("stopPlace") or {}
        if sp.get("id") == to_id:
            return True
    return False


def analyse(
    response: dict,
    now: datetime,
    horizon_min: int,
    to_stop_place_id: str | None = None,
    to_name: str | None = None,
    past_response: dict | None = None,
    look_back_min: int = 0,
    estimates: dict[str, object] | None = None,
) -> Analysis:
    estimates = estimates or {}
    stop_place = response.get("stopPlace") or {}
    quays = stop_place.get("quays") or []
    from_id = stop_place.get("id", "")

    window: Window = {
        "fra": (now - timedelta(minutes=look_back_min)).isoformat(),
        "til": (now + timedelta(minutes=horizon_min)).isoformat(),
        "minutter": horizon_min,
    }
    sp_info: StopPlaceInfo = {
        "id": from_id,
        "name": stop_place.get("name", ""),
        "window": window,
    }
    if to_stop_place_id:
        sp_info["to_id"] = to_stop_place_id
        sp_info["to_name"] = to_name or ""

    # Single pass — accumulators, split past/future at `now`
    total_scheduled = 0
    total_realised = 0
    total_cancelled = 0
    total_delayed = 0
    past_scheduled = 0
    past_cancelled = 0
    past_delayed = 0
    future_scheduled = 0
    future_cancelled = 0
    future_delayed = 0
    delays_past: list[float] = []
    delays_future: list[float] = []

    by_line_acc: dict[str, dict] = defaultdict(
        lambda: {
            "scheduled": 0, "realised": 0, "cancelled": 0, "delayed": 0,
            "transport_mode": "",
            "pax_realised": 0.0, "pax_displaced": 0.0,
            "occupancy_known_realised": 0, "occupancy_unknown_realised": 0,
        }
    )
    platforms: list[PlatformUsage] = []
    plat_acc: dict[str, dict] = {}  # keyed by visible track number
    passengers_modelled = 0.0
    occupancy_known_realised_total = 0
    occupancy_unknown_realised_total = 0

    # situationNumber -> aggregated record
    sit_acc: dict[str, dict] = {}
    # line_code -> set of situationNumbers touching that line
    line_situations: dict[str, set[str]] = defaultdict(set)

    # Collect quays from both responses; use a seen set to skip duplicate calls
    # (boundary calls that appear in both past and future queries).
    seen_calls: set[tuple] = set()
    all_quays = list(quays)
    if past_response:
        all_quays += (past_response.get("stopPlace") or {}).get("quays") or []

    for quay in all_quays:
        q_scheduled = 0
        q_realised = 0
        q_cancelled = 0
        q_delayed = 0
        q_lines: set[str] = set()
        q_cancelled_lines: set[str] = set()
        q_delayed_lines: set[str] = set()

        for call in quay.get("estimatedCalls") or []:
            if not _in_window(call, now, horizon_min, look_back_min):
                continue
            aimed = _call_aimed(call)
            line_key = ((call.get("serviceJourney") or {}).get("id") or "")
            dedup_key = (quay.get("id", ""), aimed, line_key)
            if dedup_key in seen_calls:
                continue
            seen_calls.add(dedup_key)
            sj = call.get("serviceJourney") or {}
            if to_stop_place_id and not _passes_through(sj, from_id, to_stop_place_id):
                continue

            # Past = aimed time has passed; only past trains can have "run".
            try:
                is_past = datetime.fromisoformat(aimed) <= now
            except (ValueError, TypeError):
                is_past = False

            cancelled = bool(call.get("cancellation"))
            line = sj.get("line") or {}
            line_code = line.get("publicCode") or line.get("id") or "?"
            mode = line.get("transportMode", "") or ""
            capacity = CAPACITY_PER_VEHICLE.get(mode, 0)

            # Per-call load factor: real occupancy when available, else default.
            occupancy_status = call.get("occupancyStatus") or "noData"
            real_lf = OCCUPANCY_LOAD_FACTOR.get(occupancy_status)
            effective_lf = real_lf if real_lf is not None else DEFAULT_LOAD_FACTOR
            realised_pax = capacity * effective_lf          # actual if not cancelled
            displaced_pax = capacity * DEFAULT_LOAD_FACTOR  # hypothetical "would have been"

            total_scheduled += 1
            q_scheduled += 1
            if is_past:
                past_scheduled += 1
            else:
                future_scheduled += 1
            q_lines.add(line_code)
            line_bucket = by_line_acc[line_code]
            line_bucket["scheduled"] += 1
            if not line_bucket["transport_mode"]:
                line_bucket["transport_mode"] = mode

            if cancelled:
                # Cancellations are announced ahead — counted across the window.
                total_cancelled += 1
                q_cancelled += 1
                q_cancelled_lines.add(line_code)
                line_bucket["cancelled"] += 1
                line_bucket["pax_displaced"] += displaced_pax
                if is_past:
                    past_cancelled += 1
                else:
                    future_cancelled += 1
            else:
                # Delays are known for both halves (observed or predicted).
                delay = _minutes_between(_call_aimed(call), _call_expected(call))
                if delay is not None:
                    if delay > DELAY_THRESHOLD_MIN:
                        total_delayed += 1
                        line_bucket["delayed"] += 1
                        q_delayed += 1
                        q_delayed_lines.add(line_code)
                        if is_past:
                            past_delayed += 1
                        else:
                            future_delayed += 1
                    (delays_past if is_past else delays_future).append(delay)

                # Realised ("kjørt") only exists once the departure has passed.
                if is_past:
                    total_realised += 1
                    q_realised += 1
                    line_bucket["realised"] += 1
                    line_bucket["pax_realised"] += realised_pax
                    passengers_modelled += realised_pax
                    if real_lf is not None:
                        line_bucket["occupancy_known_realised"] += 1
                        occupancy_known_realised_total += 1
                    else:
                        line_bucket["occupancy_unknown_realised"] += 1
                        occupancy_unknown_realised_total += 1

            # situations attached to this call
            for sit in call.get("situations") or []:
                key = sit.get("situationNumber") or sit.get("id")
                if not key:
                    continue
                entry = sit_acc.get(key)
                if entry is None:
                    validity = sit.get("validityPeriod") or {}
                    severity_raw = sit.get("severity", "undefined") or "undefined"
                    entry = {
                        "id": sit.get("id", ""),
                        "situation_number": sit.get("situationNumber", ""),
                        "summary": _first_text(sit.get("summary")),
                        "description": _first_text(sit.get("description")),
                        "severity_raw": severity_raw,
                        "severity": SEVERITY_MAP.get(severity_raw, "ukjent"),
                        "report_type": sit.get("reportType", "") or "",
                        "valid_from": validity.get("startTime", "") or "",
                        "valid_to": validity.get("endTime", "") or "",
                        "estimate": estimates.get(key),
                        "_lines": set(),
                        "_quays": set(),
                    }
                    sit_acc[key] = entry
                entry["_lines"].add(line_code)
                if quay.get("id"):
                    entry["_quays"].add(quay["id"])
                line_situations[line_code].add(key)

        # Merge by visible track number: the same physical track appears as
        # multiple quay objects (sub-quays, and once per past/future response).
        plat_key = quay.get("publicCode") or quay.get("name") or quay.get("id", "")
        acc = plat_acc.get(plat_key)
        if acc is None:
            acc = {
                "quay_id": quay.get("id", ""),
                "quay_name": quay.get("name", ""),
                "public_code": quay.get("publicCode"),
                "scheduled": 0,
                "realised": 0,
                "cancelled": 0,
                "delayed": 0,
                "_lines": set(),
                "_cancelled_lines": set(),
                "_delayed_lines": set(),
            }
            plat_acc[plat_key] = acc
        acc["scheduled"] += q_scheduled
        acc["realised"] += q_realised
        acc["cancelled"] += q_cancelled
        acc["delayed"] += q_delayed
        acc["_lines"] |= q_lines
        acc["_cancelled_lines"] |= q_cancelled_lines
        acc["_delayed_lines"] |= q_delayed_lines

    for acc in plat_acc.values():
        platforms.append({
            "quay_id": acc["quay_id"],
            "quay_name": acc["quay_name"],
            "public_code": acc["public_code"],
            "scheduled": acc["scheduled"],
            "realised": acc["realised"],
            "cancelled": acc["cancelled"],
            "delayed": acc["delayed"],
            "lines": sorted(acc["_lines"]),
            "cancelled_lines": sorted(acc["_cancelled_lines"]),
            "delayed_lines": sorted(acc["_delayed_lines"]),
        })

    # Sort platforms by cancellations asc, then busiest-first as a tiebreak
    platforms.sort(key=lambda p: (p["cancelled"], -p["scheduled"]))

    # Build by_line list
    by_line: list[LineMovement] = []
    for code, b in sorted(by_line_acc.items(), key=lambda kv: kv[1]["scheduled"], reverse=True):
        by_line.append({
            "linje": code,
            "transport_mode": b["transport_mode"],
            "scheduled": b["scheduled"],
            "realised": b["realised"],
            "cancelled": b["cancelled"],
            "delayed_gt_3min": b["delayed"],
        })

    median_past, p90_past = _delay_percentiles(delays_past)
    median_future, p90_future = _delay_percentiles(delays_future)
    median_delay, p90_delay = _delay_percentiles(delays_past + delays_future)

    past_stats: MovementStats = {
        "scheduled": past_scheduled,
        "realised": total_realised,
        "cancelled": past_cancelled,
        "delayed_gt_3min": past_delayed,
        "median_delay_min": median_past,
        "p90_delay_min": p90_past,
    }
    future_stats: MovementStats = {
        "scheduled": future_scheduled,
        "realised": 0,
        "cancelled": future_cancelled,
        "delayed_gt_3min": future_delayed,
        "median_delay_min": median_future,
        "p90_delay_min": p90_future,
    }

    train_movements: TrainMovements = {
        "scheduled": total_scheduled,
        "realised": total_realised,
        "cancelled": total_cancelled,
        "delayed_gt_3min": total_delayed,
        "past_scheduled": past_scheduled,
        "future_scheduled": future_scheduled,
        "future_cancelled": future_cancelled,
        "median_delay_min": median_delay,
        "p90_delay_min": p90_delay,
        "past": past_stats,
        "future": future_stats,
        "by_line": by_line,
    }

    horizon_hours = horizon_min / 60 if horizon_min else 1
    look_back_hours = look_back_min / 60 if look_back_min else horizon_hours
    window_hours = (look_back_min + horizon_min) / 60 or 1
    capacity_vs_normal: CapacityVsNormal = {
        "realised_per_hour": round(total_realised / look_back_hours, 1),
        "scheduled_per_hour": round(total_scheduled / window_hours, 1),
        # Historic completion: how much of the past plan actually ran.
        "kapasitetsutnyttelse": (
            round(total_realised / past_scheduled, 3) if past_scheduled else 0.0
        ),
        "note": (
            "kapasitetsutnyttelse = realised / past_scheduled (observed history). "
            "Not a 4-week historical mean — add persistence for that."
        ),
    }

    passenger_by_line: list[LinePassengers] = []
    affected_passengers_total = 0.0
    displaced_passengers_total = 0.0
    for code, b in by_line_acc.items():
        ps_real = b["pax_realised"]
        ps_disp = b["pax_displaced"]
        is_affected = code in line_situations
        if is_affected:
            affected_passengers_total += ps_real
        displaced_passengers_total += ps_disp
        passenger_by_line.append({
            "linje": code,
            "transport_mode": b["transport_mode"],
            "scheduled_calls": b["scheduled"],
            "realised_calls": b["realised"],
            "cancelled_calls": b["cancelled"],
            "passengers_realised": int(ps_real),
            "passengers_displaced": int(ps_disp),
            "occupancy_known_realised": b["occupancy_known_realised"],
            "occupancy_unknown_realised": b["occupancy_unknown_realised"],
            "affected": is_affected,
            "affecting_situations": sorted(line_situations.get(code, set())),
        })
    passenger_by_line.sort(
        key=lambda r: (not r["affected"], -r["passengers_realised"])
    )

    passenger_estimate: PassengerEstimate = {
        "estimated_passengers": int(passengers_modelled),
        "assumptions": dict(CAPACITY_PER_VEHICLE),
        "load_factor": DEFAULT_LOAD_FACTOR,
        "occupancy_known_realised": occupancy_known_realised_total,
        "occupancy_unknown_realised": occupancy_unknown_realised_total,
        "affected_passengers": int(affected_passengers_total),
        "displaced_passengers": int(displaced_passengers_total),
        "affected_lines": sorted(line_situations.keys()),
        "by_line": passenger_by_line,
        "note": (
            "estimated_passengers: kjørte avganger × belegg per avgang "
            "(faktisk OTP occupancyStatus når tilgjengelig, ellers standard belegg). "
            "affected_passengers: samme kjørte passasjerer, begrenset til linjer med "
            "≥1 aktiv SX — alltid ≤ estimert. "
            "displaced_passengers: kansellerte avganger × kapasitet × standard belegg "
            "(passasjerer hvis tog ble kansellert; uavhengig av estimert)."
        ),
    }

    situations: list[Situation] = []
    for key, entry in sit_acc.items():
        lines = sorted(entry.pop("_lines"))
        quay_ids = sorted(entry.pop("_quays"))
        sit_out: Situation = {
            "id": entry["id"],
            "situation_number": entry["situation_number"],
            "summary": entry["summary"],
            "description": entry["description"],
            "severity": entry["severity"],
            "severity_raw": entry["severity_raw"],
            "report_type": entry["report_type"],
            "valid_from": entry["valid_from"],
            "valid_to": entry["valid_to"],
            "paavirker_linjer": lines,
            "paavirker_quays": quay_ids,
        }
        situations.append(sit_out)
    severity_rank = {"hoy": 0, "middels": 1, "lav": 2, "ukjent": 3}
    situations.sort(key=lambda s: severity_rank.get(s.get("severity", "ukjent"), 3))

    return {
        "stop_place": sp_info,
        "situations": situations,
        "train_movements": train_movements,
        "capacity_vs_normal": capacity_vs_normal,
        "passenger_estimate": passenger_estimate,
        "platform_utilization": platforms,
    }


def build_timeline(
    past_response: dict,
    future_response: dict,
    now: datetime,
    span_before_min: int = 90,
    span_after_min: int = 90,
    bucket_min: int = 5,
    to_stop_place_id: str | None = None,
) -> list[dict]:
    """Bucket calls in [now-span_before, now+span_after] into bucket_min slots.

    Past calls come from `past_response` (queried with startTime = now-span_before,
    timeRange = span_before_min). Future calls come from `future_response`
    (queried at now over span_after_min). Buckets are returned oldest-first;
    missing buckets are filled with zeros.

    Each bucket carries a signed `minutes_offset`: negative for past, 0 at
    the current bucket boundary, positive for future. `is_future` is True
    for buckets at or after the now-boundary.

    If `to_stop_place_id` is set, only counts calls whose service journey
    continues from the response's stop place to that downstream stop place.
    """
    if bucket_min <= 0:
        return []
    n_before = span_before_min // bucket_min
    n_after = span_after_min // bucket_min
    n_total = n_before + n_after
    if n_total == 0:
        return []
    window_start = now - timedelta(minutes=span_before_min)
    window_span = span_before_min + span_after_min

    buckets = []
    for i in range(n_total):
        b_start = window_start + timedelta(minutes=i * bucket_min)
        offset_from_now = (i - n_before) * bucket_min
        buckets.append({
            "bucket_start": b_start.isoformat(),
            "minutes_offset": offset_from_now,
            "is_future": i >= n_before,
            "scheduled": 0,
            "realised": 0,
            "cancelled": 0,
            "delayed": 0,
            "departures": [],
        })

    for resp in (past_response, future_response):
        if not resp:
            continue
        stop_place = resp.get("stopPlace") or {}
        from_id = stop_place.get("id", "")
        for quay in stop_place.get("quays") or []:
            for call in quay.get("estimatedCalls") or []:
                aimed = _call_aimed(call)
                if not aimed:
                    continue
                try:
                    ts = datetime.fromisoformat(aimed)
                except (ValueError, TypeError):
                    continue
                offset_min = (ts - window_start).total_seconds() / 60
                if offset_min < 0 or offset_min >= window_span:
                    continue
                if to_stop_place_id:
                    sj = call.get("serviceJourney") or {}
                    if not _passes_through(sj, from_id, to_stop_place_id):
                        continue
                idx = int(offset_min // bucket_min)
                if idx < 0 or idx >= n_total:
                    continue
                b = buckets[idx]
                b["scheduled"] += 1
                cancelled = bool(call.get("cancellation"))
                delay = _minutes_between(aimed, _call_expected(call))
                delayed = (
                    not cancelled
                    and delay is not None
                    and delay > DELAY_THRESHOLD_MIN
                )
                if cancelled:
                    b["cancelled"] += 1
                else:
                    b["realised"] += 1
                    if delayed:
                        b["delayed"] += 1
                line = (call.get("serviceJourney") or {}).get("line") or {}
                dest = call.get("destinationDisplay") or {}
                b["departures"].append({
                    "line": line.get("publicCode") or line.get("id") or "?",
                    "destination": dest.get("frontText") or "",
                    "aimed": aimed,
                    "delay_min": round(delay) if delay is not None and delay >= 1 else 0,
                    "cancelled": cancelled,
                })
    for b in buckets:
        b["departures"].sort(key=lambda d: d["aimed"])
    return buckets
