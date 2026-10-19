"""C2: prontidão persistida e replay conservador (sem rede real)."""

import json

import pytest
import requests

from helpers.weather_resilience import blocked_external_network, restricted_writes
from helpers.weather_temporal import SequenceClock, local_time
from scripts.weather_daily import (
    prepare_daily_extraction, execute_daily_extraction, reconcile_daily_extraction, evaluate_for_consumption,
)
from scripts.weather_slots import SlotControlError


@pytest.fixture
def daily_result(tmp_path, monkeypatch, locations, config, cycle_date,
                 payload_factory, fixed_clock):
    by_coordinates = {(x["latitude"], x["longitude"]): x for x in locations}
    scenario = {"kind": "complete", "calls": 0}

    def fake_get(endpoint, *, params, timeout):
        scenario["calls"] += 1
        city = by_coordinates[(params["latitude"], params["longitude"])]
        payload = payload_factory(city)
        if scenario["kind"] == "null":
            payload["hourly"]["temperature_2m"][0] = None
        if scenario["kind"] == "partial":
            for series in payload["hourly"].values():
                series.pop()
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode("utf-8")
        return response

    monkeypatch.setattr(requests, "get", fake_get)

    def build(kind="complete"):
        scenario["kind"] = kind
        prepared = prepare_daily_extraction(project_root=tmp_path,
            config=config, locations=locations, cycle_date=cycle_date,
            clock=lambda: local_time(13, 45))
        execute_daily_extraction(project_root=tmp_path, prepared=prepared, clock=lambda: local_time(14))
        return {**prepared, "mode": "new_collection"}

    with blocked_external_network(), restricted_writes(tmp_path):
        yield build, scenario


@pytest.mark.parametrize("confirmed,accepted", [
    (local_time(14, 14, 59, 999999), True), (local_time(14, 15), True),
    (local_time(14, 15, 0, 1), False),
])
def test_t12_confirmation_boundary(daily_result, tmp_path, cycle_date, confirmed, accepted):
    build, calls = daily_result
    prepared = build()
    clock = SequenceClock(local_time(14, 14), local_time(14, 14), local_time(14, 14), confirmed, confirmed)
    if accepted:
        result = reconcile_daily_extraction(project_root=tmp_path, prepared=prepared, clock=clock)
        assert result["eligible"]
    else:
        with pytest.raises(SlotControlError):
            reconcile_daily_extraction(project_root=tmp_path, prepared=prepared, clock=clock)
    replay = evaluate_for_consumption(project_root=tmp_path, cycle_date=cycle_date,
                                      consumed_at=local_time(14, 30))
    assert replay["eligible"] is accepted
    assert calls["calls"] == 5


@pytest.mark.parametrize("kind", ["null", "partial"])
def test_t16_quality_never_promotes_technical_status(daily_result, tmp_path, kind):
    build, _ = daily_result
    prepared = build(kind)
    result = reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                                       clock=lambda: local_time(14, 10))
    assert not result["eligible"]
    if kind == "null":
        assert result["batch_status"] == "success"


def test_t13_late_reconciliation_remains_ineligible(daily_result, tmp_path, cycle_date):
    build, _ = daily_result
    prepared = build()
    with pytest.raises(SlotControlError):
        reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                                   clock=lambda: local_time(14, 16))
    assert not evaluate_for_consumption(project_root=tmp_path, cycle_date=cycle_date,
                                       consumed_at=local_time(14, 30))["eligible"]


@pytest.mark.parametrize("target", ["assessment.json", "readiness.json", "readiness-confirmed.json"])
def test_t18_persistence_failure_never_authorizes_replay(
        daily_result, tmp_path, cycle_date, monkeypatch, target):
    import scripts.weather_daily as daily
    build, calls = daily_result
    prepared = build()
    original = daily.persist_immutable_document

    def fail(root, path, document):
        if path.endswith("/" + target):
            raise OSError("synthetic filesystem failure")
        return original(root, path, document)

    monkeypatch.setattr(daily, "persist_immutable_document", fail)
    with pytest.raises(OSError):
        reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                                   clock=lambda: local_time(14, 10))
    assert not evaluate_for_consumption(project_root=tmp_path, cycle_date=cycle_date,
                                       consumed_at=local_time(14, 30))["eligible"]
    assert calls["calls"] == 5


def test_t11_replay_preserves_bytes_and_reassesses_freshness(daily_result, tmp_path, cycle_date):
    from helpers.weather_resilience import file_inventory
    build, calls = daily_result
    prepared = build()
    reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                               clock=lambda: local_time(14, 10))
    before = file_inventory(tmp_path)
    for hour, minute, accepted in [(14, 30, True), (15, 0, True), (15, 1, False)]:
        replay = evaluate_for_consumption(project_root=tmp_path, cycle_date=cycle_date,
                                          consumed_at=local_time(hour, minute))
        assert replay["eligible"] is accepted
    assert file_inventory(tmp_path) == before
    assert calls["calls"] == 5


def test_t16_corruption_blocks(daily_result, tmp_path, cycle_date):
    build, _ = daily_result
    prepared = build()
    reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                               clock=lambda: local_time(14, 10))
    next((tmp_path / "data/raw").glob("weather_*.json")).write_bytes(b"broken")
    assert not evaluate_for_consumption(project_root=tmp_path, cycle_date=cycle_date,
                                       consumed_at=local_time(14, 30))["eligible"]


def test_t17_t20_no_fallback_to_another_cycle(daily_result, tmp_path, cycle_date):
    from datetime import timedelta
    from helpers.weather_resilience import file_inventory
    build, _ = daily_result
    prepared = build()
    reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                               clock=lambda: local_time(14, 10))
    before = file_inventory(tmp_path)
    result = evaluate_for_consumption(project_root=tmp_path,
        cycle_date=cycle_date + timedelta(days=1), consumed_at=local_time(14, 30) + timedelta(days=1))
    assert result == {"eligible": False, "reasons": ["unavailable"]}
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize("fault", ["missing", "corrupt", "wrong_hash", "future", "bad_schema"])
def test_t12_confirmation_is_required_and_bound(daily_result, tmp_path, cycle_date, fault):
    from scripts.weather_manifest import encode_document
    build, _ = daily_result
    prepared = build()
    reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                               clock=lambda: local_time(14, 10))
    path = next((tmp_path / "data/orchestration/slots").glob("*/readiness-confirmed.json"))
    doc = json.loads(path.read_bytes())
    if fault == "missing":
        path.unlink()
    elif fault == "corrupt":
        path.write_bytes(b"broken")
    else:
        if fault == "wrong_hash":
            doc["readiness"]["sha256"] = "0" * 64
        if fault == "future":
            doc["confirmed_at"] = local_time(14, 16).isoformat()
        if fault == "bad_schema":
            doc["schema_version"] = "2"
        path.write_bytes(encode_document(doc))
    assert not evaluate_for_consumption(project_root=tmp_path, cycle_date=cycle_date,
                                       consumed_at=local_time(14, 30))["eligible"]
    replay = reconcile_daily_extraction(project_root=tmp_path,
        prepared={**prepared, "mode": "replay"}, clock=lambda: local_time(14, 30))
    assert not replay["eligible"]


def test_t15_delayed_witness_does_not_freeze_consumption_time(daily_result, tmp_path):
    build, _ = daily_result
    prepared = build()
    result = reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
        clock=SequenceClock(local_time(14, 10), local_time(14, 10), local_time(14, 10),
                            local_time(14, 10), local_time(15, 1)))
    assert not result["eligible"]
    assert "stale_collection" in result["reasons"]
    assert result["provisional"] is False


def test_t16_corrupt_dispatch_cannot_be_ignored(daily_result, tmp_path, cycle_date):
    build, _ = daily_result
    prepared = build()
    reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                               clock=lambda: local_time(14, 10))
    next((tmp_path / "data/orchestration/slots").glob("*/dispatch.json")).write_bytes(b"broken")
    assert not evaluate_for_consumption(project_root=tmp_path, cycle_date=cycle_date,
                                       consumed_at=local_time(14, 30))["eligible"]


def test_t12_late_receipt_must_remain_ineligible_on_replay(
        tmp_path, monkeypatch, locations, config, cycle_date, payload_factory, fixed_clock):
    by_coordinates = {(x["latitude"], x["longitude"]): x for x in locations}

    def fake_get(endpoint, *, params, timeout):
        city = by_coordinates[(params["latitude"], params["longitude"])]
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload_factory(city)).encode("utf-8")
        return response

    monkeypatch.setattr(requests, "get", fake_get)
    with blocked_external_network(), restricted_writes(tmp_path):
        prepared = prepare_daily_extraction(
            project_root=tmp_path, config=config, locations=locations,
            cycle_date=cycle_date, clock=lambda: local_time(13, 45))
        # Montar a conclusão técnica com transporte simulado, sem DAG/tasks.
        execute_daily_extraction(project_root=tmp_path, prepared=prepared, clock=lambda: local_time(14))
        prepared["mode"] = "new_collection"
        with pytest.raises(SlotControlError):
            reconcile_daily_extraction(project_root=tmp_path, prepared=prepared,
                clock=SequenceClock(local_time(14, 14), local_time(14, 14),
                                    local_time(14, 15), local_time(14, 15, 0, 1)))
        replay = evaluate_for_consumption(project_root=tmp_path,
            cycle_date=cycle_date, consumed_at=local_time(14, 30))
        assert replay["eligible"] is False
