"""GraphQL query for all-quay departures at a stop place.

Fans out over every quay (platform) at the given StopPlace in a single
request, returning aimed/expected/cancellation/situations per call.
"""

STOP_PLACE_DEPARTURES_QUERY = """
query OsloSDepartures(
  $id: String!,
  $n: Int!,
  $timeRange: Int!,
  $startTime: DateTime
) {
  stopPlace(id: $id) {
    id
    name
    quays {
      id
      name
      publicCode
      estimatedCalls(
        numberOfDepartures: $n,
        timeRange: $timeRange,
        startTime: $startTime,
        includeCancelledTrips: true
      ) {
        aimedDepartureTime
        expectedDepartureTime
        aimedArrivalTime
        expectedArrivalTime
        cancellation
        realtimeState
        date
        occupancyStatus
        serviceJourney {
          id
          line {
            id
            publicCode
            name
            transportMode
          }
          quays {
            stopPlace {
              id
            }
          }
        }
        situations {
          id
          situationNumber
          summary { value }
          description { value }
          severity
          reportType
          validityPeriod {
            startTime
            endTime
          }
        }
      }
    }
  }
}
"""


def stop_place_variables(
    stop_place_id: str,
    num_departures_per_quay: int = 80,
    time_range_seconds: int = 5400,
    start_time: str | None = None,
) -> dict:
    v = {
        "id": stop_place_id,
        "n": num_departures_per_quay,
        "timeRange": time_range_seconds,
    }
    if start_time is not None:
        v["startTime"] = start_time
    return v
