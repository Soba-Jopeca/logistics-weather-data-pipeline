from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from scripts.weather_window import (
    build_cycle_window,
    evaluate_coverage,
    required_times_for_collection,
)


@pytest.fixture
def window():
    return build_cycle_window(
        date(2026, 10, 13),
        "America/Sao_Paulo",
    )


def test_cycle_has_expected_utc_limits_and_32_hours(window):
    times = window["expected_times_utc"]

    assert window["cycle_date_local"] == "2026-10-13"
    assert window["timezone"] == "America/Sao_Paulo"
    assert window["window_start_utc"] == datetime(
        2026, 10, 13, 19, tzinfo=timezone.utc
    )
    assert window["window_end_utc"] == datetime(
        2026, 10, 15, 3, tzinfo=timezone.utc
    )
    assert len(times) == 32
    assert times[-1] == datetime(
        2026, 10, 15, 2, tzinfo=timezone.utc
    )
    assert len(set(times)) == 32
    assert all(
        current - previous == timedelta(hours=1)
        for previous, current in zip(times, times[1:])
    )


@pytest.mark.parametrize(
    "collected_at, expected_count, first_hour_utc",
    [
        ("2026-10-13T14:00:00-03:00", 32, 19),
        ("2026-10-13T16:00:00-03:00", 32, 19),
        ("2026-10-13T18:00:00-03:00", 30, 21),
        ("2026-10-13T18:07:00-03:00", 29, 22),
        ("2026-10-15T00:00:00-03:00", 0, None),
        ("2026-10-15T01:00:00-03:00", 0, None),
    ],
)
def test_required_hours_follow_collection_time(
    window, collected_at, expected_count, first_hour_utc
):
    required = required_times_for_collection(
        window,
        datetime.fromisoformat(collected_at),
    )

    assert len(required) == expected_count

    if first_hour_utc is not None:
        assert required[0] == datetime(
            2026, 10, 13, first_hour_utc, tzinfo=timezone.utc
        )

    assert len(window["expected_times_utc"]) == 32


def test_collection_without_timezone_is_rejected(window):
    with pytest.raises(ValueError):
        required_times_for_collection(
            window,
            datetime(2026, 10, 13, 18, 7),
        )


def test_midnight_keeps_explicit_cycle(window):
    collected_at = datetime(
        2026, 10, 14, 0,
        tzinfo=ZoneInfo("America/Sao_Paulo"),
    )

    required = required_times_for_collection(window, collected_at)

    assert window["cycle_date_local"] == "2026-10-13"
    assert len(required) == 24
    assert required[0] == datetime(
        2026, 10, 14, 3, tzinfo=timezone.utc
    )


def test_overlapping_cycles_keep_distinct_identity(window):
    next_window = build_cycle_window(
        date(2026, 10, 14),
        "America/Sao_Paulo",
    )

    overlap = (
        set(window["expected_times_utc"])
        & set(next_window["expected_times_utc"])
    )

    assert len(overlap) == 8
    assert window["cycle_date_local"] != next_window["cycle_date_local"]


def test_full_coverage_before_start(window):
    result = evaluate_coverage(
        window,
        datetime.fromisoformat("2026-10-13T14:00:00-03:00"),
        window["expected_times_utc"],
    )

    assert result["coverage_complete"] is True
    assert result["required_count"] == 32
    assert result["missing_times_utc"] == []


def test_missing_last_hour_is_reported(window):
    times = window["expected_times_utc"]

    result = evaluate_coverage(
        window,
        datetime.fromisoformat("2026-10-13T14:00:00-03:00"),
        times[:-1],
    )

    assert result["coverage_complete"] is False
    assert result["missing_times_utc"] == [times[-1].isoformat()]


def test_late_collection_accepts_remaining_hours(window):
    result = evaluate_coverage(
        window,
        datetime.fromisoformat("2026-10-13T18:07:00-03:00"),
        window["expected_times_utc"][3:],
    )

    assert result["required_count"] == 29
    assert result["coverage_complete"] is True


def test_ended_cycle_is_not_complete(window):
    result = evaluate_coverage(
        window,
        datetime.fromisoformat("2026-10-15T00:00:00-03:00"),
        window["expected_times_utc"],
    )

    assert result["required_count"] == 0
    assert result["coverage_complete"] is False


def test_hour_outside_window_is_reported(window):
    outside = window["window_end_utc"]

    result = evaluate_coverage(
        window,
        datetime.fromisoformat("2026-10-13T14:00:00-03:00"),
        window["expected_times_utc"] + [outside],
    )

    assert result["coverage_complete"] is False
    assert result["outside_window_times_utc"] == [outside.isoformat()]