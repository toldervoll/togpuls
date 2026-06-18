"""TypedDicts for the togpuls CLI output JSON."""

from __future__ import annotations

from typing import TypedDict


class DisruptionEstimate(TypedDict, total=False):
    point_min_from_now: int
    p50_min_from_now: int
    p80_min_from_now: int
    p90_min_from_now: int
    overdue: bool


class DisruptionAlertProfile(TypedDict, total=False):
    grain: str
    matched_category: str
    matched_line: str
    matched_hour: int
    alert_tier: str
    alert_score: float
    cancel_rate: float
    trouble_rate: float
    trouble_lift: float | None
    exp_disruption_min: float
    delay_p50: int | None
    delay_p90: int | None
    n_situations: int
    n_boardings: int


class DisruptionEnrichment(TypedDict, total=False):
    category: str
    onset: str
    minutes_since_onset: int
    reopened: bool
    reopened_at: str | None
    minutes_since_reopen: int | None
    num_affected_stops: int
    declared_window_min: int | None
    reopen: DisruptionEstimate
    impact: DisruptionEstimate
    alert: DisruptionAlertProfile | None


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
    disruption: DisruptionEnrichment


class LineMovement(TypedDict):
    linje: str
    transport_mode: str
    scheduled: int
    realised: int
    cancelled: int
    delayed_gt_3min: int


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
