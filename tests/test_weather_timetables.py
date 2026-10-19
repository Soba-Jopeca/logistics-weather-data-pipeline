"""Cálculo de timetables 2.9.2; nenhum scheduler, task ou DAG run."""

from datetime import timedelta

import pytest

from helpers.weather_resilience import blocked_external_network
from scripts.weather_temporal import evaluate_admission, resolve_daily_slot


def _types():
    import airflow
    import pendulum
    from airflow.timetables.base import DataInterval, TimeRestriction
    from airflow.timetables.interval import CronDataIntervalTimetable
    from airflow.timetables.trigger import CronTriggerTimetable
    assert airflow.__version__ == "2.9.2"
    return pendulum, DataInterval, TimeRestriction, CronDataIntervalTimetable, CronTriggerTimetable


def test_t01_timetable_semantics():
    with blocked_external_network():
        p, _, restriction, interval_type, trigger_type = _types()
        zone = "America/Sao_Paulo"
        start = p.datetime(2026, 10, 12, 13, 45, tz=zone)
        rules = restriction(earliest=start, latest=None, catchup=True)
        interval = interval_type("45 13 * * *", timezone=zone)
        trigger = trigger_type("45 13 * * *", timezone=zone)
        data_info = interval.next_dagrun_info(last_automated_data_interval=None, restriction=rules)
        trigger_info = trigger.next_dagrun_info(last_automated_data_interval=None, restriction=rules)
        assert data_info.logical_date == start
        assert data_info.data_interval.end == start + timedelta(days=1)
        assert data_info.run_after == data_info.data_interval.end
        assert trigger_info.logical_date == start
        assert trigger_info.data_interval.start == trigger_info.data_interval.end == start
        slot = resolve_daily_slot(source="scheduled", data_interval_start=data_info.data_interval.start,
                                  data_interval_end=data_info.data_interval.end)
        assert slot.cycle_date.isoformat() == "2026-10-13"
        with pytest.raises(ValueError):
            resolve_daily_slot(source="scheduled", data_interval_start=trigger_info.data_interval.start,
                               data_interval_end=trigger_info.data_interval.end)
        assert interval.deserialize(interval.serialize()).serialize() == interval.serialize()
        assert trigger.deserialize(trigger.serialize()).serialize() == trigger.serialize()


@pytest.mark.parametrize("hour,minute,expected_day,admitted", [
    (13, 44, 12, False), (13, 45, 13, True), (14, 0, 13, True), (14, 1, 13, False),
])
@pytest.mark.parametrize("history", [False, True])
def test_t02_scheduler_resume_candidates(monkeypatch, hour, minute, expected_day, admitted, history):
    with blocked_external_network():
        p, data_interval, restriction, interval_type, trigger_type = _types()
        import airflow.timetables.interval as module
        import airflow.timetables.trigger as trigger_module
        zone = "America/Sao_Paulo"
        now = p.datetime(2026, 10, 13, hour, minute, tz=zone)
        monkeypatch.setattr(module, "utcnow", lambda: now)
        monkeypatch.setattr(trigger_module.timezone, "utcnow", lambda: now)
        start = p.datetime(2026, 10, 10, 13, 45, tz=zone)
        previous = data_interval(start, start + timedelta(days=1)) if history else None
        rules = restriction(earliest=start, latest=None, catchup=False)
        for cls in (interval_type, trigger_type):
            timetable = cls("45 13 * * *", timezone=zone)
            info = timetable.next_dagrun_info(last_automated_data_interval=previous, restriction=rules)
            assert info.data_interval.end.in_timezone(zone).day == expected_day
            if cls is interval_type:
                slot = resolve_daily_slot(source="scheduled", data_interval_start=info.data_interval.start,
                                          data_interval_end=info.data_interval.end)
                assert evaluate_admission(slot, now)["eligible"] is admitted


def test_t02_previous_completed_interval_prevents_same_candidate(monkeypatch):
    with blocked_external_network():
        p, data_interval, restriction, interval_type, _ = _types()
        import airflow.timetables.interval as module
        end = p.datetime(2026, 10, 13, 13, 45, tz="America/Sao_Paulo")
        monkeypatch.setattr(module, "utcnow", lambda: end + timedelta(hours=1))
        info = interval_type("45 13 * * *", timezone="America/Sao_Paulo").next_dagrun_info(
            last_automated_data_interval=data_interval(end-timedelta(days=1), end),
            restriction=restriction(earliest=end-timedelta(days=3), latest=None, catchup=False))
        assert info.data_interval.end == end + timedelta(days=1)
        slot = resolve_daily_slot(source="scheduled", data_interval_start=info.data_interval.start,
                                  data_interval_end=info.data_interval.end)
        assert evaluate_admission(slot, end + timedelta(hours=1))["reason"] == "too_early"
