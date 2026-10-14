import json
from copy import deepcopy
from uuid import uuid4

import pytest
import requests

import scripts.extract_weather as extractor


def make_response(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response.encoding = "utf-8"
    response._content = json.dumps(payload).encode("utf-8")
    return response


def test_live_http_is_blocked():
    with pytest.raises(AssertionError, match="HTTP real bloqueado"):
        requests.get("https://example.invalid")


def test_city_timeout_does_not_block_other_cities(
    monkeypatch,
    tmp_path,
    locations,
    config,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    monkeypatch.setattr(extractor, "PROJECT_ROOT", tmp_path)

    calls = []
    waits = []
    by_coordinates = {
        (item["latitude"], item["longitude"]): item
        for item in locations
    }

    def fake_get(endpoint, *, params, timeout):
        location = by_coordinates[
            (params["latitude"], params["longitude"])
        ]
        calls.append({
            "location_id": location["location_id"],
            "params": deepcopy(params),
            "timeout": timeout,
        })

        if location["location_id"] == "br_sp_sorocaba":
            raise requests.exceptions.Timeout("Timeout simulado")

        return make_response(payload_factory(location))

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(extractor, "sleep", waits.append)

    batch = extractor.collect_batch(config, locations, cycle_date)
    batch_path = extractor.save_batch_report(batch)

    assert batch["batch_status"] == "partial_success"
    assert batch["successful_location_count"] == 4
    assert batch["location_count"] == 5

    reports = {
        result["report"]["location_id"]: result["report"]
        for result in batch["results"]
    }
    failed = reports["br_sp_sorocaba"]

    assert failed["run_status"] == "failed"
    assert failed["raw_path"] is None
    assert failed["error_category"] == "timeout"
    assert len(failed["attempts"]) == 3
    assert waits == [1, 2]

    assert [
        attempt["attempt_no"] for attempt in failed["attempts"]
    ] == [1, 2, 3]

    assert len({
        attempt["attempt_id"] for attempt in failed["attempts"]
    }) == 3

    for attempt in failed["attempts"]:
        assert attempt["run_id"] == failed["run_id"]
        assert attempt["error_category"] == "timeout"
        assert attempt["http_status"] is None
        assert attempt["duration_ms"] >= 0
        assert attempt["started_at"]
        assert attempt["ended_at"]

    city_calls = [
        call for call in calls
        if call["location_id"] == "br_sp_sorocaba"
    ]
    assert len(city_calls) == 3
    assert all(
        call["params"] == failed["request_params"]
        for call in city_calls
    )
    assert all(call["timeout"] == (10, 30) for call in calls)

    for location_id, report in reports.items():
        if location_id != "br_sp_sorocaba":
            assert report["run_status"] == "validated"
            assert report["validation"]["record_count"] == 32

    assert len({report["run_id"] for report in reports.values()}) == 5
    assert all(
        report["batch_id"] == batch["batch_id"]
        for report in reports.values()
    )

    saved_batch = json.loads(
        (tmp_path / batch_path).read_text(encoding="utf-8")
    )
    assert saved_batch["batch_status"] == "partial_success"

    for result in batch["results"]:
        saved_report = json.loads(
            (tmp_path / result["report_path"]).read_text(
                encoding="utf-8"
            )
        )
        assert saved_report == result["report"]


@pytest.mark.parametrize("first_failure", ["timeout", "connection", 503])
def test_retry_recovers_and_preserves_parameters(
    monkeypatch, first_failure
):
    calls = []
    waits = []
    params = {"latitude": -22.90556, "timezone": "GMT"}
    original_params = deepcopy(params)
    run_id = str(uuid4())

    def fake_get(endpoint, *, params, timeout):
        calls.append(deepcopy(params))

        if len(calls) == 1:
            if first_failure == "timeout":
                raise requests.exceptions.Timeout()
            if first_failure == "connection":
                raise requests.exceptions.ConnectionError()
            return make_response({"error": True}, status=503)

        return make_response({"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(extractor, "sleep", waits.append)

    response, attempts = extractor.fetch_with_retries(
        "https://example.invalid", params, (10, 30), run_id
    )

    assert response.status_code == 200
    assert len(attempts) == 2
    assert attempts[0]["error_category"] is not None
    assert attempts[1]["error_category"] is None
    assert waits == [1]
    assert calls == [original_params, original_params]
    assert params == original_params
    assert all(item["run_id"] == run_id for item in attempts)
    assert len({item["attempt_id"] for item in attempts}) == 2


@pytest.mark.parametrize("status", [400, 429])
def test_non_retryable_http_status_stops_immediately(
    monkeypatch, status
):
    calls = []
    waits = []

    def fake_get(endpoint, *, params, timeout):
        calls.append(status)
        return make_response({"error": True}, status=status)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(extractor, "sleep", waits.append)

    response, attempts = extractor.fetch_with_retries(
        "https://example.invalid",
        {"timezone": "GMT"},
        (10, 30),
        str(uuid4()),
    )

    assert response.status_code == status
    assert len(attempts) == 1
    assert attempts[0]["http_status"] == status
    assert attempts[0]["error_category"] == "http_error"
    assert calls == [status]
    assert waits == []


@pytest.mark.parametrize("max_attempts", [0, 4, True])
def test_invalid_retry_limit_is_rejected(max_attempts):
    with pytest.raises(ValueError):
        extractor.fetch_with_retries(
            "https://example.invalid",
            {},
            (10, 30),
            str(uuid4()),
            max_attempts=max_attempts,
        )