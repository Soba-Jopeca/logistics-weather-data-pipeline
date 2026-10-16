import hashlib
import json
from copy import deepcopy
from uuid import uuid4

import pytest
import requests

import scripts.extract_weather as extractor


def test_supplied_ids_and_explicit_root_are_preserved(
    monkeypatch,
    tmp_path,
    locations,
    config,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    original_root = extractor.PROJECT_ROOT
    explicit_root = tmp_path / "execution"

    batch_id = str(uuid4())
    run_ids = {
        location["location_id"]: str(uuid4())
        for location in locations
    }

    original_config = deepcopy(config)
    original_locations = deepcopy(locations)
    original_run_ids = deepcopy(run_ids)

    by_coordinates = {
        (location["latitude"], location["longitude"]): location
        for location in locations
    }
    calls = []

    def fake_get(endpoint, *, params, timeout):
        location = by_coordinates[
            (params["latitude"], params["longitude"])
        ]
        calls.append(location["location_id"])

        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = json.dumps(
            payload_factory(location)
        ).encode("utf-8")
        return response

    monkeypatch.setattr(requests, "get", fake_get)

    batch = extractor.collect_batch(
        config,
        locations,
        cycle_date,
        batch_id=batch_id,
        run_ids=run_ids,
        project_root=explicit_root,
    )

    batch_path = extractor.save_batch_report(
        batch,
        project_root=explicit_root,
    )

    assert batch["batch_id"] == batch_id
    assert batch["batch_status"] == "success"
    assert len(calls) == 5
    assert extractor.PROJECT_ROOT == original_root

    assert config == original_config
    assert locations == original_locations
    assert run_ids == original_run_ids

    saved_batch = json.loads(
        (explicit_root / batch_path).read_text(encoding="utf-8")
    )
    assert saved_batch["batch_id"] == batch_id

    for result in batch["results"]:
        report = result["report"]
        location_id = report["location_id"]

        assert report["run_id"] == run_ids[location_id]
        assert report["batch_id"] == batch_id

        saved_report = json.loads(
            (explicit_root / result["report_path"]).read_text(
                encoding="utf-8"
            )
        )
        assert saved_report == report

        raw_bytes = (explicit_root / report["raw_path"]).read_bytes()
        assert hashlib.sha256(raw_bytes).hexdigest() == report["raw_sha256"]

        assert all(
            record["run_id"] == run_ids[location_id]
            for record in result["records"]
        )

        assert all(
            attempt["run_id"] == run_ids[location_id]
            for attempt in report["attempts"]
        )


@pytest.mark.parametrize(
    "invalid_case",
    ["missing_city", "extra_city", "duplicate_id", "invalid_uuid"],
)
def test_invalid_run_map_is_rejected_before_http(
    monkeypatch,
    locations,
    config,
    cycle_date,
    invalid_case,
):
    run_ids = {
        location["location_id"]: str(uuid4())
        for location in locations
    }
    location_ids = list(run_ids)

    if invalid_case == "missing_city":
        del run_ids[location_ids[0]]
    elif invalid_case == "extra_city":
        run_ids["unexpected_city"] = str(uuid4())
    elif invalid_case == "duplicate_id":
        run_ids[location_ids[1]] = run_ids[location_ids[0]]
    else:
        run_ids[location_ids[0]] = "invalid-uuid"

    calls = []

    def forbidden_http(*args, **kwargs):
        calls.append(True)
        raise AssertionError("HTTP nao deveria ser chamado")

    monkeypatch.setattr(requests, "get", forbidden_http)

    with pytest.raises(ValueError):
        extractor.collect_batch(
            config,
            locations,
            cycle_date,
            batch_id=str(uuid4()),
            run_ids=run_ids,
        )

    assert calls == []