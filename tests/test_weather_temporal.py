"""C1: casos temporais puros; nenhuma execução de DAG ou HTTP."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from scripts.weather_slots import canonical_slot_bytes
from scripts.weather_temporal import (
    DailyAdmissionError, DailySlot, FirstTransportGuard, LOCATION_IDS,
    evaluate_admission, evaluate_freshness, resolve_daily_slot,
)
from helpers.weather_temporal import SequenceClock, local_time


@pytest.fixture
def slot():
    return resolve_daily_slot(source="cli", cycle_date="2026-10-13")


@pytest.mark.parametrize("instant,reason", [
    (local_time(13, 44, 59, 999999), "too_early"),
    (local_time(13, 45), None),
    (local_time(14), None),
    (local_time(14, 0, 0, 1), "start_expired"),
    (local_time(14, 15), "start_expired"),
    (local_time(14, 30), "start_expired"),
])
def test_t03_admission_boundaries(slot, instant, reason):
    result = evaluate_admission(slot, instant)
    assert result["reason"] == reason
    assert result["eligible"] is (reason is None)


def test_t04_guard_revalidates_at_first_transport(slot):
    assert evaluate_admission(slot, local_time(13, 59))["eligible"]
    clock = SequenceClock(local_time(14, 0, 1), local_time(13, 59))
    guard = FirstTransportGuard(slot, clock)
    with pytest.raises(DailyAdmissionError, match="start_expired"):
        guard()
    # Uma rejeição não pode ser desfeita por relógio posterior retrocedido.
    with pytest.raises(DailyAdmissionError):
        guard()
    assert guard.started_at is None
    assert clock.calls == 1


def test_guard_does_not_readmit_each_city_or_retry(slot):
    clock = SequenceClock(local_time(14))
    guard = FirstTransportGuard(slot, clock)
    for _ in range(15):
        guard()
    assert guard.started_at == "2026-10-13T17:00:00Z"
    assert clock.calls == 1
    assert not issubclass(DailyAdmissionError, ValueError)


@pytest.mark.parametrize("day", [date(2026, 11, 1), date(2027, 1, 1)])
def test_t05_cycle_comes_from_interval_end(day):
    zone = ZoneInfo("America/Sao_Paulo")
    end = datetime.combine(day, datetime.min.time(), tzinfo=zone).replace(hour=13, minute=45)
    previous = day - timedelta(days=1)
    start = datetime.combine(previous, datetime.min.time(), tzinfo=zone).replace(hour=13, minute=45)
    slot = resolve_daily_slot(source="scheduled", data_interval_start=start,
                              data_interval_end=end)
    assert slot.cycle_date == day
    assert evaluate_admission(slot, end + timedelta(days=1))["reason"] == "start_expired"
    assert slot.cycle_date == day


@pytest.mark.parametrize("arguments", [
    {"source": "backfill", "cycle_date": "2026-10-13"},
    {"source": "cli", "cycle_date": datetime(2026, 10, 13)},
    {"source": "cli", "cycle_date": "20261013"},
    {"source": "manual", "cycle_date": "2026-10-13", "data_interval_end": local_time(13, 45)},
    {"source": "scheduled", "data_interval_start": datetime(2026, 10, 12, 13, 45),
     "data_interval_end": local_time(13, 45)},
    {"source": "scheduled", "data_interval_start": local_time(13, 45) - timedelta(days=1),
     "data_interval_end": local_time(13, 46)},
    {"source": "scheduled", "cycle_date": "2026-10-12",
     "data_interval_start": local_time(13, 45) - timedelta(days=1),
     "data_interval_end": local_time(13, 45)},
])
def test_t06_invalid_context_is_rejected(arguments):
    with pytest.raises(ValueError):
        resolve_daily_slot(**arguments)


def test_identity_is_compact_and_equivalent_in_utc(slot):
    expected = (b'{"pipeline":"logistics-weather-data-pipeline",'
                b'"purpose":"daily-logistics-decision",'
                b'"scheduled_slot_utc":"2026-10-13T16:45:00Z"}')
    assert canonical_slot_bytes(slot) == expected
    alternate = DailySlot(date(2026, 10, 13), local_time(13, 45).astimezone(
        ZoneInfo("America/Sao_Paulo")))
    assert canonical_slot_bytes(alternate) == expected


@pytest.mark.parametrize("age,eligible", [(2700, True), (3600, True), (3600.000001, False), (-1, False)])
def test_t14_freshness_boundaries(age, eligible):
    consumed = local_time(14, 30)
    cities = {city: consumed - timedelta(seconds=age) for city in LOCATION_IDS}
    result = evaluate_freshness(cities, consumed)
    assert result["eligible"] is eligible
    assert set(result["ages_seconds"]) == LOCATION_IDS


def test_t15_oldest_city_and_later_consumption_control_freshness():
    cities = {city: local_time(13, 50) for city in LOCATION_IDS}
    cities["br_sp_campinas"] = local_time(13, 46)
    assert evaluate_freshness(cities, local_time(14, 40))["oldest_age_seconds"] == 3240
    result = evaluate_freshness(cities, local_time(14, 47))
    assert not result["eligible"]
    assert result["oldest_age_seconds"] == 3660
    assert result["reasons"] == ["stale_collection"]
    assert cities["br_sp_campinas"] == local_time(13, 46)


@pytest.mark.parametrize("bad", [None, "invalid", datetime(2026, 10, 13, 13, 45)])
def test_invalid_city_timestamp_is_not_ignored(bad):
    cities = {city: local_time(13, 50) for city in LOCATION_IDS}
    cities["br_sp_campinas"] = bad
    result = evaluate_freshness(cities, local_time(14, 30))
    assert not result["eligible"]
    assert result["reasons"] == ["invalid_timestamp"]
    assert result["ages_seconds"]["br_sp_campinas"] is None


def test_readiness_and_consumption_are_separate_instants(slot):
    assert slot.readiness_cutoff == local_time(14, 15)
    assert slot.intended_consumption == local_time(14, 30)
    assert slot.admission_end == local_time(14)
