import hashlib
import json
from uuid import uuid4

import pytest
import requests

import scripts.extract_weather as extractor
import scripts.weather_interface as interface


@pytest.fixture
def prepared_execution(tmp_path, locations, cycle_date):
    reference = interface.prepare_extraction(
        cycle_date=cycle_date,
        config={
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "timeout": (10, 30),
        },
        locations=locations,
        project_root=tmp_path,
        orchestration_context={
            "dag_id": "logistics_weather_extract",
            "airflow_run_id": "manual__execution_test",
        },
    )
    return tmp_path, locations, reference


def execution_arguments(root, reference):
    return {
        "project_root": root,
        "manifest_path": reference["manifest_path"],
        "manifest_sha256": reference["manifest_sha256"],
    }


def snapshot_files(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "scenario, expected_status, expected_calls",
    [
        ("complete", "success", 5),
        ("null", "success", 5),
        ("city_timeout", "partial_success", 7),
        ("all_timeout", "failed", 15),
    ],
)
def test_execution_and_replay_preserve_results_without_network(
    monkeypatch,
    prepared_execution,
    payload_factory,
    fixed_clock,
    scenario,
    expected_status,
    expected_calls,
):
    root, locations, reference = prepared_execution
    by_coordinates = {
        (item["latitude"], item["longitude"]): item
        for item in locations
    }
    calls = []

    def fake_get(endpoint, *, params, timeout):
        location = by_coordinates[
            (params["latitude"], params["longitude"])
        ]
        calls.append(location["location_id"])

        if scenario == "all_timeout" or (
            scenario == "city_timeout"
            and location["location_id"] == "br_sp_sorocaba"
        ):
            raise requests.exceptions.Timeout()

        payload = payload_factory(location)

        if scenario == "null":
            payload["hourly"]["temperature_2m"][0] = None

        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = json.dumps(payload).encode("utf-8")
        return response

    arguments = execution_arguments(root, reference)

    with monkeypatch.context() as patch:
        patch.setattr(requests, "get", fake_get)
        patch.setattr(extractor, "sleep", lambda seconds: None)
        first = interface.execute_extraction(**arguments)

    assert first["mode"] == "new_collection"
    assert first["batch_status"] == expected_status
    assert first["batch_id"] == reference["batch_id"]
    assert len(calls) == expected_calls
    assert len(json.dumps(first).encode("utf-8")) < 8192

    if scenario == "null":
        assert first["null_count"] == 5

    original_files = snapshot_files(root)

    # A simulação HTTP já foi retirada.
    # Qualquer chamada real agora falha pelo conftest.
    replay = interface.execute_extraction(**arguments)

    assert replay["mode"] == "replay"
    assert {
        key: value for key, value in replay.items() if key != "mode"
    } == {
        key: value for key, value in first.items() if key != "mode"
    }
    assert snapshot_files(root) == original_files


@pytest.mark.parametrize("state", ["started", "raw", "report"])
def test_ambiguous_state_blocks_collection_and_records_incident(
    prepared_execution, state
):
    root, locations, reference = prepared_execution
    manifest = json.loads(
        (root / reference["manifest_path"]).read_bytes()
    )

    if state == "started":
        interface.claim_extraction(
            project_root=root,
            batch_id=reference["batch_id"],
            manifest_sha256=reference["manifest_sha256"],
        )
    else:
        run_id = next(iter(manifest["runs"].values()))["run_id"]

        if state == "raw":
            extractor.save_raw_bytes(
                b"{}", run_id, project_root=root
            )
        else:
            extractor.save_run_report(
                {"run_id": run_id},
                project_root=root,
            )

    original_files = snapshot_files(root)

    with pytest.raises(ValueError, match="Incidente:"):
        interface.execute_extraction(
            **execution_arguments(root, reference)
        )

    for path, content in original_files.items():
        assert (root / path).read_bytes() == content

    incidents = list(
        (root / "data/orchestration/incidents").glob("*.json")
    )
    assert len(incidents) == 1
    incident = json.loads(incidents[0].read_bytes())
    assert incident["category"] == "ambiguous_state"
    assert incident["automatic_collection_blocked"] is True


def test_interrupted_execution_preserves_completed_city_and_blocks_restart(
    monkeypatch,
    prepared_execution,
    payload_factory,
    fixed_clock,
):
    root, locations, reference = prepared_execution
    calls = []
    by_coordinates = {
        (item["latitude"], item["longitude"]): item
        for item in locations
    }

    def interrupted_get(endpoint, *, params, timeout):
        calls.append(deepcopy_params(params))

        if len(calls) == 2:
            raise RuntimeError("Interrupcao simulada do processo")

        location = by_coordinates[
            (params["latitude"], params["longitude"])
        ]
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = json.dumps(
            payload_factory(location)
        ).encode("utf-8")
        return response

    arguments = execution_arguments(root, reference)

    with monkeypatch.context() as patch:
        patch.setattr(requests, "get", interrupted_get)

        with pytest.raises(RuntimeError, match="Interrupcao simulada"):
            interface.execute_extraction(**arguments)

    reports = list((root / "data/raw/runs").glob("*.json"))
    assert len(reports) == 1
    report_bytes = reports[0].read_bytes()
    report = json.loads(report_bytes)

    raw_path = root / report["raw_path"]
    raw_bytes = raw_path.read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == report["raw_sha256"]

    with pytest.raises(ValueError, match="Incidente:"):
        interface.execute_extraction(**arguments)

    assert reports[0].read_bytes() == report_bytes
    assert raw_path.read_bytes() == raw_bytes
    assert len(calls) == 2


def deepcopy_params(params):
    # Os parâmetros deste teste possuem apenas valores escalares.
    return dict(params)

@pytest.fixture
def completed_execution(
    monkeypatch,
    prepared_execution,
    payload_factory,
    fixed_clock,
):
    root, locations, reference = prepared_execution
    by_coordinates = {
        (item["latitude"], item["longitude"]): item
        for item in locations
    }

    def fake_get(endpoint, *, params, timeout):
        location = by_coordinates[
            (params["latitude"], params["longitude"])
        ]
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = json.dumps(
            payload_factory(location)
        ).encode("utf-8")
        return response

    arguments = execution_arguments(root, reference)

    with monkeypatch.context() as patch:
        patch.setattr(requests, "get", fake_get)
        result = interface.execute_extraction(**arguments)

    return root, reference, arguments, result


@pytest.mark.parametrize("artifact", ["raw", "report", "completion"])
def test_modified_final_artifact_blocks_replay(
    completed_execution, artifact
):
    root, reference, arguments, result = completed_execution

    summary = json.loads(
        (root / result["batch_report_path"]).read_bytes()
    )
    first = summary["results"][0]

    if artifact == "raw":
        path = root / first["report"]["raw_path"]
    elif artifact == "report":
        path = root / first["report_path"]
    else:
        path = root / result["completion_path"]

    path.write_bytes(b'{"altered": true}')
    altered_bytes = path.read_bytes()

    with pytest.raises(ValueError, match="Incidente:"):
        interface.execute_extraction(**arguments)

    assert path.read_bytes() == altered_bytes

    incidents = list(
        (root / "data/orchestration/incidents").glob("*.json")
    )
    assert len(incidents) == 1

    incident = json.loads(incidents[0].read_bytes())
    assert incident["category"] == "artifact_integrity"
    assert incident["batch_id"] == reference["batch_id"]


def test_manifest_hash_mismatch_blocks_execution(prepared_execution):
    root, locations, reference = prepared_execution
    arguments = execution_arguments(root, reference)
    arguments["manifest_sha256"] = hashlib.sha256(
        b"outro-conteudo"
    ).hexdigest()

    with pytest.raises(ValueError, match="Incidente:"):
        interface.execute_extraction(**arguments)

    assert not (root / "data/raw").exists()

    incidents = list(
        (root / "data/orchestration/incidents").glob("*.json")
    )
    assert len(incidents) == 1
    assert json.loads(incidents[0].read_bytes())["category"] == (
        "manifest_integrity"
    )


def test_incident_write_failure_is_explicit(
    monkeypatch, prepared_execution
):
    root, locations, reference = prepared_execution

    interface.claim_extraction(
        project_root=root,
        batch_id=reference["batch_id"],
        manifest_sha256=reference["manifest_sha256"],
    )

    def denied_incident(**kwargs):
        raise PermissionError("Disco indisponivel no teste")

    monkeypatch.setattr(
        interface,
        "record_extraction_incident",
        denied_incident,
    )

    with pytest.raises(
        ValueError,
        match="Não foi possível persistir",
    ):
        interface.execute_extraction(
            **execution_arguments(root, reference)
        )

    assert not (root / "data/orchestration/incidents").exists()