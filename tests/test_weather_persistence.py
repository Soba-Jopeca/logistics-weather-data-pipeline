import hashlib
import json
from uuid import uuid4

import pytest
import requests

import scripts.extract_weather as extractor


def test_raw_bytes_and_hash_match(raw_root):
    content = b'{"sample": 1}'
    result = extractor.save_raw_bytes(content, str(uuid4()))

    saved_bytes = (raw_root / result["raw_path"]).read_bytes()

    assert saved_bytes == content
    assert result["raw_sha256"] == hashlib.sha256(saved_bytes).hexdigest()


def test_raw_replay_does_not_create_another_file(raw_root):
    run_id = str(uuid4())
    content = b'{"sample": 1}'

    first = extractor.save_raw_bytes(content, run_id)
    replay = extractor.save_raw_bytes(content, run_id)

    assert replay == first
    assert len(list((raw_root / "data/raw").glob("weather_*.json"))) == 1


def test_raw_conflict_preserves_original(raw_root):
    run_id = str(uuid4())
    original = b'{"sample": 1}'
    result = extractor.save_raw_bytes(original, run_id)

    with pytest.raises(ValueError, match="Conflito de Raw"):
        extractor.save_raw_bytes(b'{"sample": 2}', run_id)

    assert (raw_root / result["raw_path"]).read_bytes() == original


def test_new_run_creates_new_raw_version(raw_root):
    content = b'{"sample": 1}'

    first = extractor.save_raw_bytes(content, str(uuid4()))
    second = extractor.save_raw_bytes(content, str(uuid4()))

    assert first["raw_path"] != second["raw_path"]
    assert first["raw_sha256"] == second["raw_sha256"]
    assert len(list((raw_root / "data/raw").glob("weather_*.json"))) == 2


def test_run_report_replay_and_conflict(raw_root):
    report = {
        "run_id": str(uuid4()),
        "run_status": "failed",
        "raw_path": None,
        "attempts": [],
    }

    path = extractor.save_run_report(report)
    assert extractor.save_run_report(report) == path

    with pytest.raises(ValueError, match="Relatório conflitante"):
        extractor.save_run_report(dict(report, run_status="validated"))

    saved = json.loads((raw_root / path).read_text(encoding="utf-8"))
    assert saved == report


def test_raw_write_error_is_propagated(raw_root, monkeypatch):
    raw_dir = raw_root / "data/raw"
    raw_dir.mkdir(parents=True)
    path_type = type(raw_root)
    original_open = path_type.open

    def denied_open(path, mode="r", *args, **kwargs):
        if path.parent == raw_dir and mode == "xb":
            raise PermissionError("Gravacao negada no teste")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(path_type, "open", denied_open)

    with pytest.raises(PermissionError):
        extractor.save_raw_bytes(b"{}", str(uuid4()))

    assert list(raw_dir.glob("weather_*.json")) == []


def test_raw_write_failure_is_recorded_as_failed_run(
    monkeypatch,
    tmp_path,
    locations,
    config,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    location = locations[0]
    monkeypatch.setattr(extractor, "PROJECT_ROOT", tmp_path)

    response = requests.Response()
    response.status_code = 200
    response.encoding = "utf-8"
    response._content = json.dumps(
        payload_factory(location)
    ).encode("utf-8")

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: response,
    )

    def failed_write(*args, **kwargs):
        raise PermissionError("Gravacao Raw negada no teste")

    monkeypatch.setattr(extractor, "save_raw_bytes", failed_write)

    result = extractor.collect_location(
        config, location, cycle_date, str(uuid4())
    )
    report = result["report"]

    assert report["run_status"] == "failed"
    assert report["error_category"] == "persistence_error"
    assert report["raw_path"] is None
    assert report["raw_sha256"] is None
    assert result["records"] == []

    saved = json.loads(
        (tmp_path / result["report_path"]).read_text(encoding="utf-8")
    )
    assert saved == report


def test_run_report_write_failure_does_not_stop_other_cities(
    monkeypatch,
    tmp_path,
    locations,
    config,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    monkeypatch.setattr(extractor, "PROJECT_ROOT", tmp_path)
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

    original_save = extractor.save_run_report

    def selective_failure(report):
        if report["location_id"] == "br_sp_sorocaba":
            raise PermissionError("Relatorio negado no teste")
        return original_save(report)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(extractor, "save_run_report", selective_failure)

    batch = extractor.collect_batch(config, locations, cycle_date)

    assert batch["batch_status"] == "partial_success"
    assert batch["successful_location_count"] == 4
    assert len(batch["results"]) == 5

    failed = next(
        result for result in batch["results"]
        if result["report"]["location_id"] == "br_sp_sorocaba"
    )
    assert failed["report"]["run_status"] == "failed"
    assert failed["report"]["error_category"] == "run_execution_error"
    assert failed["report_path"] is None

    path = extractor.save_batch_report(batch)
    saved = json.loads((tmp_path / path).read_text(encoding="utf-8"))
    assert saved["batch_status"] == "partial_success"
    assert len(saved["results"]) == 5


def test_batch_write_error_is_propagated(raw_root):
    # Um arquivo ocupa o caminho onde deveria existir uma pasta.
    (raw_root / "data").write_text("bloqueio", encoding="utf-8")

    with pytest.raises(OSError):
        extractor.save_batch_report({
            "batch_id": str(uuid4()),
            "batch_status": "failed",
            "results": [],
        })