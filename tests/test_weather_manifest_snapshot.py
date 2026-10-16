from copy import deepcopy
from uuid import uuid4

import pytest

from scripts.weather_manifest import (
    build_manifest_document,
    encode_document,
)


@pytest.fixture
def manifest_inputs(locations, cycle_date):
    return {
        "cycle_date": cycle_date,
        "config": {
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "timeout": (10, 30),
        },
        "locations": deepcopy(locations),
        "batch_id": str(uuid4()),
        "run_ids": {
            location["location_id"]: str(uuid4())
            for location in locations
        },
        "orchestration_context": {
            "dag_id": "logistics_weather_extract",
            "airflow_run_id": "manual__teste",
        },
    }


def test_same_inputs_produce_identical_manifest(manifest_inputs):
    first = build_manifest_document(**manifest_inputs)
    second = build_manifest_document(**manifest_inputs)

    assert encode_document(first) == encode_document(second)
    assert first["batch_id"] == manifest_inputs["batch_id"]
    assert len(first["locations"]) == 5
    assert len(first["runs"]) == 5

    for location_id, run in first["runs"].items():
        assert run["run_id"] == manifest_inputs["run_ids"][location_id]
        assert run["request_params"]["timezone"] == "GMT"
        assert run["request_params"]["timeformat"] == "unixtime"
        assert run["request_params"]["start_hour"] == "2026-10-13T19:00"
        assert run["request_params"]["end_hour"] == "2026-10-15T02:00"
        assert run["cycle"]["cycle_date_local"] == "2026-10-13"


def test_manifest_does_not_share_mutable_inputs(manifest_inputs):
    original = deepcopy(manifest_inputs)
    manifest = build_manifest_document(**manifest_inputs)

    assert manifest_inputs == original

    manifest_inputs["locations"][0]["name"] = "Alterado"
    manifest_inputs["run_ids"].clear()
    manifest_inputs["orchestration_context"]["dag_id"] = "outro"

    assert manifest["locations"][0]["name"] == original["locations"][0]["name"]
    assert len(manifest["runs"]) == 5
    assert manifest["orchestration_context"]["dag_id"] == (
        "logistics_weather_extract"
    )


@pytest.mark.parametrize(
    "invalid_case",
    [
        "endpoint",
        "timeout",
        "extra_config",
        "missing_run",
        "duplicate_run",
        "unknown_context",
        "incomplete_context",
    ],
)
def test_invalid_snapshot_is_rejected(manifest_inputs, invalid_case):
    if invalid_case == "endpoint":
        manifest_inputs["config"]["endpoint"] = "https://example.invalid"
    elif invalid_case == "timeout":
        manifest_inputs["config"]["timeout"] = (1, 2)
    elif invalid_case == "extra_config":
        manifest_inputs["config"]["secret"] = "nao-persistir"
    elif invalid_case == "missing_run":
        manifest_inputs["run_ids"].pop(next(iter(manifest_inputs["run_ids"])))
    elif invalid_case == "duplicate_run":
        ids = list(manifest_inputs["run_ids"])
        manifest_inputs["run_ids"][ids[1]] = (
            manifest_inputs["run_ids"][ids[0]]
        )
    elif invalid_case == "unknown_context":
        manifest_inputs["orchestration_context"]["password"] = "nao-persistir"
    else:
        del manifest_inputs["orchestration_context"]["airflow_run_id"]

    with pytest.raises(ValueError):
        build_manifest_document(**manifest_inputs)