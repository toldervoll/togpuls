"""Static per-vehicle capacity assumptions for passenger estimation.

These are rough averages — a passenger estimate is a modelled figure, not a
measurement. The output JSON includes this table inline so consumers always
see the assumptions behind any number derived from it.
"""

CAPACITY_PER_VEHICLE: dict[str, int] = {
    "rail": 350,
    "metro": 200,
    "tram": 120,
    "bus": 50,
    "water": 0,
    "coach": 50,
    "funicular": 60,
    "cableway": 40,
    "air": 0,
}

DEFAULT_LOAD_FACTOR = 0.6
