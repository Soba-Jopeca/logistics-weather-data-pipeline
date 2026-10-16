import json
from copy import deepcopy
from uuid import uuid4

import pytest
import requests

import scripts.extract_weather as extractor
from scripts.weather_interface import verify_batch_artifacts
from scripts.weather_manifest import build_manifest_document


@pytest.fixture
def persisted_batch(
    monkeypatch,
    tmp_path,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    config = {
        "endpoint": "https://api.open-meteo.com/v1/forecast",
        "timeout": (10, 30),
    }
    batch_id = str(uuid4())
    run_ids = {
        location["location_id"]: str(uuid4())
        for location in locations
    }

    manifest = build_manifest_document(
        cycle_date=cycle_date,
        config=config,
        locations=locations,
        batch_id=batch_id,
        run_ids=run_ids,
    )

    by_coordinates = {
        (location["latitude"], location["longitude"]): location
        for location in locations
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

    with monkeypatch.context() as patch:
        patch.setattr(requests, "get", fake_get)

        batch = extractor.collect_batch(
            config,
            locations,
            cycle_date,
            batch_id=batch_id,
            run_ids=run_ids,
            project_root=tmp_path,
        )
        extractor.save_batch_report(batch, project_root=tmp_path)

    return tmp_path, manifest, batch


def test_intact_batch_is_reconciled_without_http(persisted_batch):
    root, manifest, batch = persisted_batch
    original = deepcopy(batch)

    result = verify_batch_artifacts(
        project_root=root,
        manifest=manifest,
    )

    assert result["batch_status"] == "success"
    assert result["successful_location_count"] == 5
    assert result["record_count"] == 160
    assert result["null_count"] == 0
    assert len(result["artifact_hashes"]) == 11
    assert batch == original


@pytest.mark.parametrize(
    "damage",
    [
        "raw_bytes",
        "missing_report",
        "report_identity",
        "summary_count",
        "validation",
    ],
)
def test_damaged_batch_is_rejected_without_repair(persisted_batch, damage):
    root, manifest, batch = persisted_batch
    report = batch["results"][0]["report"]

    summary_path = (
        root / "data/raw/batches" / f"{batch['batch_id']}.json"
    )
    report_path = root / batch["results"][0]["report_path"]
    raw_path = root / report["raw_path"]

    if damage == "raw_bytes":
        changed_path = raw_path
        changed_path.write_bytes(b'{"altered": true}')

    elif damage == "missing_report":
        report_path.unlink()
        with pytest.raises(OSError):
            verify_batch_artifacts(project_root=root, manifest=manifest)
        assert not report_path.exists()
        return

    elif damage == "report_identity":
        changed_path = report_path
        altered = json.loads(changed_path.read_bytes())
        altered["location_id"] = "outra-cidade"
        changed_path.write_text(json.dumps(altered), encoding="utf-8")

    elif damage == "summary_count":
        changed_path = summary_path
        altered = json.loads(changed_path.read_bytes())
        altered["successful_location_count"] = 4
        changed_path.write_text(json.dumps(altered), encoding="utf-8")

    else:
        changed_path = report_path
        altered = json.loads(changed_path.read_bytes())
        altered["validation"]["record_count"] = 31
        changed_path.write_text(json.dumps(altered), encoding="utf-8")

        summary = json.loads(summary_path.read_bytes())
        summary["results"][0]["report"] = altered
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

    changed_bytes = changed_path.read_bytes()

    with pytest.raises(ValueError):
        verify_batch_artifacts(project_root=root, manifest=manifest)

    assert changed_path.read_bytes() == changed_bytes