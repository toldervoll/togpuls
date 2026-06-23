"""togpuls — Oslo S situation analyser CLI.

Fetches estimated calls for all quays at a stop place (default: Oslo S,
NSR:StopPlace:337) in one Journey Planner v3 request, then derives:
  - SIRI-SX situations affecting the stop
  - Train movements (scheduled / realised / cancelled / delays)
  - Capacity vs scheduled (live ratio)
  - Modelled passenger throughput
  - Platform / quay utilization
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

import httpx

from togpuls.analysis import analyse, collect_situation_ids
from togpuls.clients.disruptions import fetch_estimates
from togpuls.clients.journey_planner import query_stop_place_departures
from togpuls.models import Analysis

DEFAULT_STOP_PLACE_ID = "NSR:StopPlace:337"  # Oslo S


async def run(
    stop_place_id: str,
    horizon_min: int,
    at: str | None,
    to_stop_place_id: str | None = None,
) -> Analysis:
    now = (
        datetime.fromisoformat(at)
        if at
        else datetime.now().astimezone()
    )

    via = f" → {to_stop_place_id}" if to_stop_place_id else ""
    print(
        f"Querying Journey Planner for {stop_place_id}{via} (window {horizon_min} min)...",
        file=sys.stderr,
    )
    time_range_seconds = horizon_min * 60
    response = await query_stop_place_departures(
        stop_place_id=stop_place_id,
        num_departures_per_quay=80,
        time_range_seconds=time_range_seconds,
    )

    if not response.get("stopPlace"):
        raise SystemExit(
            f"No stopPlace returned for id={stop_place_id!r}. "
            "Check the ID (Oslo S is NSR:StopPlace:337)."
        )

    async with httpx.AsyncClient() as client:
        estimates = await fetch_estimates(
            collect_situation_ids(response),
            client,
            from_stop=stop_place_id,
            to_stop=to_stop_place_id,
        )

    return analyse(
        response,
        now=now,
        horizon_min=horizon_min,
        to_stop_place_id=to_stop_place_id,
        estimates=estimates,
    )


def format_text(a: Analysis) -> str:
    sp = a["stop_place"]
    tm = a["train_movements"]
    cap = a["capacity_vs_normal"]
    pax = a["passenger_estimate"]
    plats = a["platform_utilization"]
    sits = a["situations"]

    lines = []
    to_id = sp.get("to_id")
    to_name = sp.get("to_name")
    if to_id:
        suffix = f"{to_name} ({to_id})" if to_name else to_id
        lines.append(f"{sp['name']} ({sp['id']}) → {suffix}")
    else:
        lines.append(f"{sp['name']} ({sp['id']})")
    lines.append(f"  Window: {sp['window']['fra']} -> {sp['window']['til']}  ({sp['window']['minutter']} min)")
    lines.append("")
    lines.append("Train movements")
    lines.append(
        f"  scheduled={tm['scheduled']} realised={tm['realised']} "
        f"cancelled={tm['cancelled']} delayed(>3m)={tm['delayed_gt_3min']}"
    )
    lines.append(
        f"  median delay={tm['median_delay_min']} p90={tm['p90_delay_min']} min"
    )
    lines.append("")
    lines.append("Capacity vs scheduled")
    lines.append(
        f"  realised/h={cap['realised_per_hour']} scheduled/h={cap['scheduled_per_hour']} "
        f"utilisation={cap['kapasitetsutnyttelse']}"
    )
    lines.append(f"  ({cap['note']})")
    lines.append("")
    lines.append("Passenger estimate")
    known = pax.get("occupancy_known_realised", 0)
    unknown = pax.get("occupancy_unknown_realised", 0)
    total_real = known + unknown
    if total_real > 0:
        cov_pct = round(100 * known / total_real)
        cov_txt = f"  ({known}/{total_real} realised calls = {cov_pct}% real occupancy, rest fallback @ {pax['load_factor']})"
    else:
        cov_txt = f"  (no realised calls; load_factor fallback only)"
    lines.append(f"  ~{pax['estimated_passengers']} passengers")
    lines.append(cov_txt)
    aff = pax.get("affected_passengers", 0)
    aff_lines = pax.get("affected_lines", [])
    disp = pax.get("displaced_passengers", 0)
    if aff_lines:
        sample = ", ".join(aff_lines[:5])
        more = f" +{len(aff_lines) - 5} more" if len(aff_lines) > 5 else ""
        lines.append(
            f"  On disrupted lines: ~{aff} passengers across {len(aff_lines)} line(s): {sample}{more}"
        )
    else:
        lines.append("  On disrupted lines: 0 (no active SX touches any line)")
    if disp > 0:
        lines.append(f"  Displaced by cancellations: ~{disp} passengers (had to find alternatives)")
    affected_rows = [r for r in pax.get("by_line", []) if r.get("affected")]
    if affected_rows:
        lines.append("  Top affected lines:")
        for r in affected_rows[:5]:
            affecting = r.get("affecting_situations", [])
            sit_txt = f"  [{len(affecting)} SX]" if affecting else ""
            lines.append(
                f"    {r['linje']:>5}  real={r['realised_calls']:>3} pax={r['passengers_realised']:>5}  "
                f"canc={r['cancelled_calls']:>2} displ={r['passengers_displaced']:>5}{sit_txt}"
            )
    lines.append("")
    lines.append(f"Platforms (top 10 of {len(plats)})")
    for p in plats[:10]:
        canc_lines = ",".join(p.get("cancelled_lines") or []) or "-"
        lines.append(
            f"  {p['public_code'] or '-':>4}  {p['quay_id']:30}  "
            f"sched={p['scheduled']:>3} real={p['realised']:>3} "
            f"canc={p['cancelled']:>2}  cancelled_lines={canc_lines}"
        )
    lines.append("")
    lines.append(f"Situations: {len(sits)}")
    for s in sits[:10]:
        lines.append(
            f"  [{s.get('severity','?'):>7}] {s.get('summary') or s.get('description') or '(no text)'}"
        )
        if s.get("paavirker_linjer"):
            lines.append(f"           lines: {', '.join(s['paavirker_linjer'])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(prog="togpuls", description="Oslo S situation analyser")
    parser.add_argument("--stop-place-id", default=DEFAULT_STOP_PLACE_ID,
                        help=f"NSR stop place id (default: {DEFAULT_STOP_PLACE_ID} = Oslo S)")
    parser.add_argument("--to-stop-place-id", default=None,
                        help="Optional downstream NSR stop place id; restricts the "
                             "analysis to service journeys that call at both the "
                             "FROM and TO stops, in that order")
    parser.add_argument("--horizon-min", type=int, default=90,
                        help="Look-ahead window in minutes (default: 90)")
    parser.add_argument("--at", default=None,
                        help="ISO-8601 timestamp to anchor the window (default: now)")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    result = asyncio.run(
        run(args.stop_place_id, args.horizon_min, args.at, args.to_stop_place_id)
    )

    if args.format == "json":
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
