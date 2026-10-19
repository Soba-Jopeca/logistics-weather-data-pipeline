"""Produtores suportados, sem execução de funções TaskFlow."""

import ast
import json
from datetime import timedelta
from pathlib import Path

import pytest
import requests

import scripts.weather_daily as daily
from helpers.weather_resilience import blocked_external_network, file_inventory, restricted_writes
from helpers.weather_temporal import SequenceClock, local_time
from scripts.weather_temporal import DailyAdmissionError


@pytest.fixture
def inputs(tmp_path, config, locations, cycle_date):
    with blocked_external_network(), restricted_writes(tmp_path):
        yield dict(project_root=tmp_path, config=config, locations=locations,
                   cycle_date=cycle_date)


@pytest.mark.parametrize("source", ["cli", "manual", "scheduled"])
def test_t08_all_producers_same_slot_and_conflict(inputs, source):
    original = daily.prepare_daily_extraction(**inputs, clock=lambda: local_time(13, 45))
    kwargs = dict(inputs)
    if source != "cli":
        kwargs["orchestration_context"] = {
            "dag_id": "logistics_weather_extract", "airflow_run_id": source + "__test"}
    if source == "scheduled":
        kwargs.update(data_interval_start=local_time(13, 45)-timedelta(days=1),
                      data_interval_end=local_time(13, 45))
    before = file_inventory(inputs["project_root"])
    with pytest.raises((ValueError, OSError)):
        daily.prepare_daily_extraction(**kwargs, source=source, clock=lambda: local_time(13, 46))
    assert file_inventory(inputs["project_root"]) == before
    assert original["batch_id"]


def test_t04_revalidation_at_transport_no_http(inputs, monkeypatch):
    prepared = daily.prepare_daily_extraction(**inputs, clock=lambda: local_time(13, 45))
    calls = []
    monkeypatch.setattr(requests, "get", lambda *a, **k: calls.append(1))
    with pytest.raises(DailyAdmissionError):
        daily.execute_daily_extraction(project_root=inputs["project_root"], prepared=prepared,
            clock=SequenceClock(local_time(14), local_time(14, 0, 0, 1)))
    assert calls == []
    assert not (inputs["project_root"] / "data/raw").exists()
    with pytest.raises(ValueError):
        daily.execute_daily_extraction(project_root=inputs["project_root"], prepared=prepared,
                                       clock=lambda: local_time(14))


def test_t09_interruption_after_claim_before_manifest(inputs, monkeypatch):
    def interrupted(*args, **kwargs):
        raise OSError("synthetic interruption")
    monkeypatch.setattr(daily, "persist_immutable_document", interrupted)
    with pytest.raises(OSError):
        daily.prepare_daily_extraction(**inputs, clock=lambda: local_time(13, 45))
    before = file_inventory(inputs["project_root"])
    with pytest.raises(OSError):
        daily.prepare_daily_extraction(**inputs, clock=lambda: local_time(13, 46))
    assert file_inventory(inputs["project_root"]) == before
    assert len(list((inputs["project_root"] / "data/orchestration/slots").glob("*/claim.json"))) == 1


def test_t10_started_without_completion_blocks(inputs):
    from scripts.weather_interface import claim_extraction
    prepared = daily.prepare_daily_extraction(**inputs, clock=lambda: local_time(13, 45))
    claim_extraction(project_root=inputs["project_root"], batch_id=prepared["batch_id"],
                     manifest_sha256=prepared["manifest_sha256"])
    with pytest.raises(ValueError):
        daily.execute_daily_extraction(project_root=inputs["project_root"], prepared=prepared,
                                       clock=lambda: local_time(13, 46))
    assert not (inputs["project_root"] / "data/raw").exists()


def test_t11_producer_replay_uses_original_manifest(inputs, monkeypatch, payload_factory, fixed_clock):
    by_coord = {(x["latitude"], x["longitude"]): x for x in inputs["locations"]}
    calls = []
    def fake_get(endpoint, *, params, timeout):
        calls.append(params)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload_factory(by_coord[(params["latitude"], params["longitude"])])).encode()
        return response
    monkeypatch.setattr(requests, "get", fake_get)
    prepared = daily.prepare_daily_extraction(**inputs, clock=lambda: local_time(13, 45))
    extracted = daily.execute_daily_extraction(project_root=inputs["project_root"], prepared=prepared,
                                              clock=lambda: local_time(14))
    assert daily.reconcile_daily_extraction(project_root=inputs["project_root"], prepared=extracted,
                                            clock=lambda: local_time(14, 10))["eligible"]
    before = file_inventory(inputs["project_root"])
    replay = daily.prepare_daily_extraction(**inputs, source="manual",
        orchestration_context={"dag_id": "logistics_weather_extract", "airflow_run_id": "manual__replay"},
        clock=lambda: local_time(15))
    assert replay["manifest_path"] == prepared["manifest_path"]
    result = daily.execute_daily_extraction(project_root=inputs["project_root"], prepared=replay,
                                            clock=lambda: local_time(15))
    assert result["mode"] == "replay"
    assert not daily.reconcile_daily_extraction(project_root=inputs["project_root"], prepared=result,
                                                clock=lambda: local_time(15, 1))["eligible"]
    assert len(calls) == 5
    assert file_inventory(inputs["project_root"]) == before


def test_t19_configuration_conflict(inputs):
    daily.prepare_daily_extraction(**inputs, clock=lambda: local_time(13, 45))
    before = file_inventory(inputs["project_root"])
    altered = dict(inputs, config={**inputs["config"], "timeout": (11, 30)})
    with pytest.raises(ValueError):
        daily.prepare_daily_extraction(**altered, clock=lambda: local_time(13, 46))
    assert file_inventory(inputs["project_root"]) == before


@pytest.mark.parametrize("run_type,conf", [("backfill", {}), ("manual", {}),
    ("manual", {"cycle_date": "2026-10-13", "force": True}),
    ("scheduled", {"cycle_date": "2026-10-13"})])
def test_t06_airflow_context_rejected(run_type, conf):
    with pytest.raises(ValueError):
        daily.airflow_daily_request(run_type=run_type, conf=conf,
            dag_id="logistics_weather_extract", run_id="test",
            logical_date=local_time(13, 45)-timedelta(days=1),
            data_interval_start=local_time(13, 45)-timedelta(days=1),
            data_interval_end=local_time(13, 45))


@pytest.mark.parametrize("source", ["manual", "scheduled"])
def test_t08_valid_airflow_adapter_creates_bound_manifest(inputs, source):
    request = daily.airflow_daily_request(run_type=source,
        conf={"cycle_date": "2026-10-13"} if source == "manual" else {},
        dag_id="logistics_weather_extract", run_id=source + "__valid",
        logical_date=local_time(13, 45)-timedelta(days=1),
        data_interval_start=local_time(13, 45)-timedelta(days=1),
        data_interval_end=local_time(13, 45))
    prepared = daily.prepare_daily_extraction(
        **{**inputs, **request}, clock=lambda: local_time(13, 45))
    manifest = json.loads((inputs["project_root"] / prepared["manifest_path"]).read_bytes())
    assert manifest["cycle_date_local"] == "2026-10-13"
    assert manifest["orchestration_context"]["scheduled_slot"] == "2026-10-13T16:45:00Z"


def test_t08_static_supported_entrypoints_use_coordinator():
    root = Path(__file__).resolve().parents[1]
    for path, function, expected in [
        ("scripts/extract_weather.py", "main", {"prepare_daily_extraction", "execute_daily_extraction", "reconcile_daily_extraction"}),
        ("dags/weather_extract.py", "prepare_extraction", {"prepare_daily_extraction"}),
        ("dags/weather_extract.py", "extract_batch", {"execute_daily_extraction"}),
        ("dags/weather_extract.py", "reconcile_extraction", {"reconcile_daily_extraction"}),
    ]:
        tree = ast.parse((root/path).read_text())
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
        calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert expected <= calls
        assert not calls & {"execute_extraction", "collect_batch", "collect_location", "fetch_forecast_response"}


def test_t07_competing_producers_only_one_transports(inputs, payload_factory):
    import multiprocessing
    from helpers.weather_temporal import daily_worker
    payloads = {loc["location_id"]: payload_factory(loc) for loc in inputs["locations"]}
    ctx = multiprocessing.get_context("spawn")
    workers = []
    try:
        for _ in range(2):
            parent, child = ctx.Pipe()
            process = ctx.Process(target=daily_worker, args=(inputs["project_root"],
                inputs["config"], inputs["locations"], payloads, child))
            process.start()
            child.close()
            workers.append((process, parent))
        for _, pipe in workers:
            assert pipe.poll(20)
            assert pipe.recv()["event"] == "ready"
        for _, pipe in workers:
            pipe.send("go")
        results = []
        for _, pipe in workers:
            assert pipe.poll(20)
            results.append(pipe.recv())
        assert sorted(result["calls"] for result in results) == [0, 5]
        assert sum(result["state"] == "new_collection" for result in results) == 1
        for process, _ in workers:
            process.join(5)
            assert process.exitcode == 0
    finally:
        for process, pipe in workers:
            if process.is_alive():
                process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
            pipe.close()
