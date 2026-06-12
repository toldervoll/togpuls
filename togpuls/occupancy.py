"""SIRI Nordic-profile occupancy → load-factor mapping.

Each estimated call returns an `occupancyStatus` enum from the SIRI-VM stream
flowing through OTP. We translate it into a per-call load factor (passengers
per available seat) using the band midpoints implied by the Nordic profile
descriptions.

Values > 1.0 mean standing-room above seat capacity, which is realistic during
peak hours on commuter rail.

`None` means "no real data — let the caller fall back to a default load factor."
"""

OCCUPANCY_LOAD_FACTOR: dict[str, float | None] = {
    "noData": None,
    "empty": 0.10,
    "manySeatsAvailable": 0.30,       # > 50% of seats available -> < 50% filled
    "fewSeatsAvailable": 0.70,        # < 50% available -> > 50% filled
    "standingRoomOnly": 0.95,         # < 10% seats available
    "crushedStandingRoomOnly": 1.10,  # standing crowded
    "full": 1.15,
    "notAcceptingPassengers": 1.20,
}
