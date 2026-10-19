import json
from datetime import datetime, timezone

import pytest
import requests

import scripts.extract_weather as extractor


@pytest.mark.parametrize(
    "scenario, collected_hour, collected_minute, collected_day,"
    " expected_status, expected_exit, required_count",
    [
        ("complete", 17, 0, 13, "success", 0, 32),
        ("null", 17, 0, 13, "success", 1, 32),
        ("late", 21, 7, 13, "success", 1, 29),
        ("missing", 17, 0, 13, "failed", 1, 32),
        ("ended", 3, 0, 15, "failed", 1, 0),
    ],
)
def test_main_persists_batch_and_returns_expected_exit_code(
    monkeypatch,
    tmp_path,
    locations,
    config,
    cycle_date,
    payload_factory,
    scenario,
    collected_hour,
    collected_minute,
    collected_day,
    expected_status,
    expected_exit,
    required_count,
):
    class ScenarioClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = cls(
                2026, 10, collected_day,
                collected_hour, collected_minute,
                tzinfo=timezone.utc,
            )
            if tz is None:
                raise AssertionError("Timezone obrigatorio no teste")
            return instant.astimezone(tz)

    monkeypatch.setattr(extractor, "datetime", ScenarioClock)
    monkeypatch.setattr(extractor, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(extractor, "load_locations", lambda: locations)
    monkeypatch.setattr(extractor, "load_api_config", lambda: config)
    monkeypatch.setattr(
        "sys.argv",
        ["extract_weather", "--cycle-date", cycle_date.isoformat()],
    )

    by_coordinates = {
        (item["latitude"], item["longitude"]): item
        for item in locations
    }
    visited = []

    def fake_get(endpoint, *, params, timeout):
        location = by_coordinates[
            (params["latitude"], params["longitude"])
        ]
        visited.append(location["location_id"])
        payload = payload_factory(location)

        if scenario == "null":
            payload["hourly"]["temperature_2m"][0] = None
        elif scenario == "late":
            for values in payload["hourly"].values():
                del values[:3]
        elif scenario == "missing":
            for values in payload["hourly"].values():
                values.pop()

        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = json.dumps(payload).encode("utf-8")
        return response

    monkeypatch.setattr(requests, "get", fake_get)

    exit_code = extractor.main()

    assert exit_code == expected_exit
    if scenario in ("late", "ended"):
        assert visited == []
        assert not (tmp_path / "data/raw").exists()
        return
    assert visited == [item["location_id"] for item in locations]

    batch_files = list((tmp_path / "data/raw/batches").glob("*.json"))
    assert len(batch_files) == 1
    batch = json.loads(batch_files[0].read_text(encoding="utf-8"))

    assert batch["batch_status"] == expected_status
    assert batch["cycle_date_local"] == "2026-10-13"
    assert len(batch["results"]) == 5

    total = 0

    for result in batch["results"]:
        report = result["report"]
        validation = report["validation"]

        assert validation["coverage"]["required_count"] == required_count
        assert report["cycle"]["cycle_date_local"] == "2026-10-13"
        assert "published_at" not in report

        total += validation["record_count"]

        if scenario == "null":
            assert report["run_status"] == "validated_with_nulls"
            assert validation["null_counts"]["temperature_2m"] == 1

            raw = json.loads(
                (tmp_path / report["raw_path"]).read_bytes()
            )
            assert raw["hourly"]["temperature_2m"][0] is None

        elif scenario in ("missing", "ended"):
            assert report["run_status"] == "incomplete"
            assert validation["coverage"]["coverage_complete"] is False

        else:
            assert report["run_status"] == "validated"
            assert validation["coverage"]["coverage_complete"] is True

    if scenario == "late":
        assert total == 145
    elif scenario == "missing":
        assert total == 155
    else:
        assert total == 160


@pytest.mark.parametrize(
    "arguments",
    [
        ["extract_weather"],
        ["extract_weather", "--cycle-date", "data-invalida"],
    ],
)
def test_invalid_cli_arguments_stop_before_http(monkeypatch, arguments):
    monkeypatch.setattr("sys.argv", arguments)

    with pytest.raises(SystemExit) as error:
        extractor.main()

    assert error.value.code == 2