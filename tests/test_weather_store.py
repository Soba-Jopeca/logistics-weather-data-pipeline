import json
from datetime import datetime, timezone

import pytest
import requests

import scripts.extract_weather as extractor
import scripts.weather_interface as interface
from scripts.weather_store import build_load_package
from scripts.load_weather_batch import parse_args
from scripts.weather_queries import _validate_as_of
from scripts.weather_store import WeatherStoreError, _parse_instant


def test_timestamp_parser_normalizes_to_utc():
    assert _parse_instant("2026-10-13T14:00:00-03:00", "test") == datetime(
        2026, 10, 13, 17, 0, tzinfo=timezone.utc
    )


@pytest.mark.parametrize("value", ["", None, "2026-10-13T14:00:00"])
def test_timestamp_parser_rejects_missing_or_naive_values(value):
    with pytest.raises(WeatherStoreError):
        _parse_instant(value, "test")


def test_query_as_of_requires_timezone():
    with pytest.raises(WeatherStoreError, match="timezone-aware"):
        _validate_as_of(datetime(2026, 10, 13, 17))


def test_query_as_of_defaults_to_aware_utc():
    assert _validate_as_of(None).utcoffset().total_seconds() == 0


def test_loader_requires_exactly_one_mode():
    with pytest.raises(SystemExit):
        parse_args([])
    with pytest.raises(SystemExit):
        parse_args(["--migrate", "--batch-id", "00000000-0000-0000-0000-000000000000"])


def test_complete_offline_raw_batch_becomes_normalized_load_package(
    tmp_path,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
    monkeypatch,
):
    root = tmp_path
    preparation = interface.prepare_extraction(
        cycle_date=cycle_date,
        config={
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "timeout": (10, 30),
        },
        locations=locations,
        project_root=root,
        orchestration_context={
            "dag_id": "logistics_weather_extract",
            "airflow_run_id": "manual__weather_store_test",
        },
    )
    location_by_coordinates = {
        (location["latitude"], location["longitude"]): location
        for location in locations
    }

    def fake_get(endpoint, *, params, timeout):
        location = location_by_coordinates[
            (params["latitude"], params["longitude"])
        ]
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = json.dumps(payload_factory(location)).encode("utf-8")
        return response

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(extractor, "sleep", lambda seconds: None)
    interface.execute_extraction(
        project_root=root,
        manifest_path=preparation["manifest_path"],
        manifest_sha256=preparation["manifest_sha256"],
    )

    package = build_load_package(preparation["batch_id"], project_root=root)

    assert package["batch"]["batch_id"] == preparation["batch_id"]
    assert len(package["runs"]) == 5
    assert len(package["forecasts"]) == 160
    assert len(package["publications"]) == 20
    assert all(
        len(artifact["sha256"]) == 64
        for artifact in package["artifacts"]
    )
