"""TypedDicts for the togpuls CLI output JSON."""

from __future__ import annotations

from typing import Any, TypedDict


class Window(TypedDict):
    fra: str
    til: str
    minutter: int


class StopPlaceInfo(TypedDict, total=False):
    id: str
    name: str
    window: Window
    to_id: str
    to_name: str


class Situation(TypedDict, total=False):
    id: str
    situation_number: str
    summary: str
    description: str
    severity: str
    severity_raw: str
    report_type: str
    valid_from: str
    valid_to: str
    paavirker_linjer: list[str]
    paavirker_quays: list[str]
    estimate: Any
    # Cluster id grouping messages that describe the same underlying event
    # (assigned in api/app.py). Several SX messages — e.g. a cancellation and
    # its "take the next train" advice — share one event_id.
    event_id: str
    # Cause from KIX (category code, e.g. "infrastruktur/signal") and a fallback
    # cause phrase extracted from the SIRI description. Frontend renders a label.
    cause_code: str
    cause_text: str


class LineMovement(TypedDict):
    linje: str
    transport_mode: str
    scheduled: int
    realised: int
    cancelled: int
    delayed_gt_3min: int
    # Forward-only counts (now → horizon), used to tell an actively-disrupting
    # line apart from one that has already recovered.
    future_scheduled: int
    future_cancelled: int
    future_delayed_gt_3min: int


class MovementStats(TypedDict):
    scheduled: int
    realised: int  # 0 in the future scope — nothing has run yet
    cancelled: int
    delayed_gt_3min: int
    median_delay_min: float | None
    p90_delay_min: float | None


class TrainMovements(TypedDict):
    # Flat fields = combined ±window (kept for CLI output and summary text)
    scheduled: int
    realised: int  # past only — a train can only have run after its time
    cancelled: int  # cancellations are announced ahead, known both ways
    delayed_gt_3min: int  # observed (past) or predicted (future)
    past_scheduled: int
    future_scheduled: int
    future_cancelled: int
    median_delay_min: float | None
    p90_delay_min: float | None
    # Per-scope blocks for the history/future/combined toggle
    past: MovementStats
    future: MovementStats
    by_line: list[LineMovement]


class CapacityVsNormal(TypedDict):
    realised_per_hour: float
    scheduled_per_hour: float
    kapasitetsutnyttelse: float
    note: str


class LinePassengers(TypedDict, total=False):
    linje: str
    transport_mode: str
    scheduled_calls: int
    realised_calls: int
    cancelled_calls: int
    passengers_realised: int
    passengers_displaced: int
    occupancy_known_realised: int
    occupancy_unknown_realised: int
    affected: bool
    affecting_situations: list[str]


class PassengerEstimate(TypedDict, total=False):
    estimated_passengers: int
    assumptions: dict[str, int]
    load_factor: float
    note: str
    occupancy_known_realised: int
    occupancy_unknown_realised: int
    affected_passengers: int
    displaced_passengers: int
    affected_lines: list[str]
    by_line: list[LinePassengers]


class PlatformUsage(TypedDict, total=False):
    quay_id: str
    quay_name: str
    public_code: str | None
    scheduled: int
    realised: int
    cancelled: int
    delayed: int
    lines: list[str]
    cancelled_lines: list[str]
    delayed_lines: list[str]


class TimelineDeparture(TypedDict):
    line: str
    destination: str
    aimed: str
    delay_min: int  # rounded; 0 when on time or under 1 min
    cancelled: bool


class TimelineBucket(TypedDict):
    bucket_start: str
    minutes_offset: int  # signed: negative = past, 0 = boundary, positive = future
    is_future: bool
    scheduled: int
    realised: int
    cancelled: int
    delayed: int  # realised with delay > DELAY_THRESHOLD_MIN
    departures: list[TimelineDeparture]


class Analysis(TypedDict, total=False):
    stop_place: StopPlaceInfo
    situations: list[Situation]
    train_movements: TrainMovements
    capacity_vs_normal: CapacityVsNormal
    passenger_estimate: PassengerEstimate
    platform_utilization: list[PlatformUsage]
    timeline: list[TimelineBucket]
