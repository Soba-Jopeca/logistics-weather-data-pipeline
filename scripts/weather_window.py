from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def build_cycle_window(cycle_date: date, timezone_name: str) -> dict:
    local_timezone = ZoneInfo(timezone_name)

    start_local = datetime.combine(
        cycle_date,
        time(hour=16),
        tzinfo=local_timezone,
    )

    end_local = datetime.combine(
        cycle_date + timedelta(days=2),
        time.min,
        tzinfo=local_timezone,
    )

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    expected_times_utc = []
    current = start_utc

    while current < end_utc:
        expected_times_utc.append(current)
        current += timedelta(hours=1)

    return {
        "cycle_date_local": cycle_date.isoformat(),
        "timezone": timezone_name,
        "window_start_utc": start_utc,
        "window_end_utc": end_utc,
        "expected_times_utc": expected_times_utc,
    }
def required_times_for_collection(
    window: dict,
    collected_at: datetime,
) -> list[datetime]:
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at deve conter informação de fuso.")

    collected_at_utc = collected_at.astimezone(timezone.utc)

    return [
        forecast_time
        for forecast_time in window["expected_times_utc"]
        if forecast_time >= collected_at_utc
    ]

def evaluate_coverage(
    window: dict,
    collected_at: datetime,
    forecast_times: list[datetime],
) -> dict:
    required = required_times_for_collection(window, collected_at)

    received = set(forecast_times)
    allowed = set(window["expected_times_utc"])

    outside_window = received - allowed
    missing = [instant for instant in required if instant not in received]

    return {
        "required_count": len(required),
        "received_count": len(forecast_times),
        "missing_times_utc": [
            instant.isoformat() for instant in missing
        ],
        "outside_window_times_utc": [
            instant.isoformat() for instant in sorted(outside_window)
        ],
        "coverage_complete": (
            bool(required)
            and not missing
            and not outside_window
        ),
    }