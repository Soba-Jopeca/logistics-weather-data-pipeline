import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest

from scripts.weather_interface import prepare_extraction


@pytest.fixture
def preparation_inputs(tmp_path, locations, cycle_date):
    return {
        "cycle_date": cycle_date,
        "config": {
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "timeout": (10, 30),
        },
        "locations": deepcopy(locations),
        "project_root": tmp_path,
        "orchestration_context": {
            "dag_id": "logistics_weather_extract",
            "airflow_run_id": "manual__teste",
        },
    }


def test_repeated_preparation_reuses_ids_and_manifest(preparation_inputs):
    first = prepare_extraction(**preparation_inputs)
    root = preparation_inputs["project_root"]
    original_bytes = (root / first["manifest_path"]).read_bytes()

    second = prepare_extraction(**preparation_inputs)

    assert second == first
    assert (root / first["manifest_path"]).read_bytes() == original_bytes
    assert hashlib.sha256(original_bytes).hexdigest() == (
        first["manifest_sha256"]
    )

    manifest = json.loads(original_bytes)

    assert manifest["batch_id"] == first["batch_id"]
    assert len({run["run_id"] for run in manifest["runs"].values()}) == 5
    assert len(json.dumps(first).encode("utf-8")) < 8192


def test_supplied_ids_are_preserved(preparation_inputs):
    batch_id = str(uuid4())
    run_ids = {
        location["location_id"]: str(uuid4())
        for location in preparation_inputs["locations"]
    }

    result = prepare_extraction(
        **preparation_inputs,
        batch_id=batch_id,
        run_ids=run_ids,
    )

    manifest = json.loads(
        (
            preparation_inputs["project_root"]
            / result["manifest_path"]
        ).read_bytes()
    )

    assert result["batch_id"] == batch_id
    assert {
        location_id: run["run_id"]
        for location_id, run in manifest["runs"].items()
    } == run_ids


@pytest.mark.parametrize("change", ["cycle", "location", "batch", "run"])
def test_same_context_blocks_conflicting_preparation(
    preparation_inputs, change
):
    first = prepare_extraction(**preparation_inputs)
    path = (
        preparation_inputs["project_root"]
        / first["manifest_path"]
    )
    original_bytes = path.read_bytes()

    altered = deepcopy(preparation_inputs)

    if change == "cycle":
        altered["cycle_date"] += timedelta(days=1)
    elif change == "location":
        altered["locations"][0]["latitude"] += 0.01
    elif change == "batch":
        altered["batch_id"] = str(uuid4())
    else:
        altered["run_ids"] = {
            location["location_id"]: str(uuid4())
            for location in altered["locations"]
        }

    with pytest.raises(ValueError):
        prepare_extraction(**altered)

    assert path.read_bytes() == original_bytes


def test_new_orchestration_context_creates_new_identity(preparation_inputs):
    first = prepare_extraction(**preparation_inputs)

    preparation_inputs["orchestration_context"]["airflow_run_id"] = (
        "manual__outra_rodada"
    )
    second = prepare_extraction(**preparation_inputs)

    assert second["batch_id"] != first["batch_id"]
    assert second["manifest_path"] != first["manifest_path"]


def test_cli_preparation_without_identity_creates_new_batch(
    preparation_inputs,
):
    preparation_inputs["orchestration_context"] = None

    first = prepare_extraction(**preparation_inputs)
    second = prepare_extraction(**preparation_inputs)

    assert first["batch_id"] != second["batch_id"]


def test_cli_preparation_with_batch_id_reuses_manifest(preparation_inputs):
    preparation_inputs["orchestration_context"] = None
    preparation_inputs["batch_id"] = str(uuid4())

    first = prepare_extraction(**preparation_inputs)
    second = prepare_extraction(**preparation_inputs)

    assert second == first

def test_manifest_can_be_verified_without_changes(preparation_inputs):
    from scripts.weather_manifest import load_verified_manifest

    reference = prepare_extraction(**preparation_inputs)
    root = preparation_inputs["project_root"]
    path = root / reference["manifest_path"]
    original_bytes = path.read_bytes()

    document = load_verified_manifest(
        project_root=root,
        manifest_path=reference["manifest_path"],
        manifest_sha256=reference["manifest_sha256"],
    )

    assert document["batch_id"] == reference["batch_id"]
    assert path.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "change",
    ["old_hash", "parameters", "missing_field", "unknown_field"],
)
def test_altered_manifest_is_rejected(preparation_inputs, change):
    from scripts.weather_manifest import (
        encode_document,
        load_verified_manifest,
    )

    reference = prepare_extraction(**preparation_inputs)
    root = preparation_inputs["project_root"]
    path = root / reference["manifest_path"]
    document = json.loads(path.read_bytes())

    if change in ("old_hash", "parameters"):
        location_id = next(iter(document["runs"]))
        document["runs"][location_id]["request_params"]["latitude"] += 1
    elif change == "missing_field":
        del document["config"]
    else:
        document["unexpected"] = "campo-nao-permitido"

    altered_bytes = encode_document(document)
    path.write_bytes(altered_bytes)

    expected_hash = (
        reference["manifest_sha256"]
        if change == "old_hash"
        else hashlib.sha256(altered_bytes).hexdigest()
    )

    with pytest.raises(ValueError):
        load_verified_manifest(
            project_root=root,
            manifest_path=reference["manifest_path"],
            manifest_sha256=expected_hash,
        )

    # A leitura rejeita o problema sem sobrescrever o arquivo.
    assert path.read_bytes() == altered_bytes

def test_execution_claim_blocks_second_start(preparation_inputs):
    from scripts.weather_interface import claim_extraction

    reference = prepare_extraction(**preparation_inputs)
    root = preparation_inputs["project_root"]

    first = claim_extraction(
        project_root=root,
        batch_id=reference["batch_id"],
        manifest_sha256=reference["manifest_sha256"],
    )

    path = root / first["path"]
    original_bytes = path.read_bytes()
    claim = json.loads(original_bytes)

    assert claim["batch_id"] == reference["batch_id"]
    assert claim["manifest_sha256"] == reference["manifest_sha256"]
    assert claim["execution_token"]
    assert hashlib.sha256(original_bytes).hexdigest() == first["sha256"]

    with pytest.raises(ValueError, match="marca de início"):
        claim_extraction(
            project_root=root,
            batch_id=reference["batch_id"],
            manifest_sha256=reference["manifest_sha256"],
        )

    assert path.read_bytes() == original_bytes


def test_execution_claim_rejects_different_manifest(preparation_inputs):
    from scripts.weather_interface import claim_extraction

    reference = prepare_extraction(**preparation_inputs)
    root = preparation_inputs["project_root"]

    first = claim_extraction(
        project_root=root,
        batch_id=reference["batch_id"],
        manifest_sha256=reference["manifest_sha256"],
    )
    path = root / first["path"]
    original_bytes = path.read_bytes()

    different_hash = hashlib.sha256(b"outro-manifesto").hexdigest()

    with pytest.raises(ValueError, match="marca de início"):
        claim_extraction(
            project_root=root,
            batch_id=reference["batch_id"],
            manifest_sha256=different_hash,
        )

    assert path.read_bytes() == original_bytes

@pytest.mark.parametrize("damage", ["conflict", "invalid_json", "missing_run_id"])
def test_preparation_failure_preserves_manifest_and_records_incident(
    preparation_inputs, damage
):
    reference = prepare_extraction(**preparation_inputs)
    root = preparation_inputs["project_root"]
    path = root / reference["manifest_path"]

    if damage == "conflict":
        preparation_inputs["locations"][0]["latitude"] += 0.01

    elif damage == "invalid_json":
        path.write_bytes(b'{"incomplete":')

    else:
        document = json.loads(path.read_bytes())
        location_id = next(iter(document["runs"]))
        del document["runs"][location_id]["run_id"]
        path.write_text(json.dumps(document), encoding="utf-8")

    original_bytes = path.read_bytes()

    with pytest.raises(ValueError, match="Preparação bloqueada. Incidente:"):
        prepare_extraction(**preparation_inputs)

    assert path.read_bytes() == original_bytes

    incidents = list(
        (root / "data/orchestration/incidents").glob("*.json")
    )
    assert len(incidents) == 1

    incident = json.loads(incidents[0].read_bytes())
    assert incident["category"] == "manifest_integrity"
    assert incident["automatic_collection_blocked"] is True


def test_preparation_reports_incident_persistence_failure(
    preparation_inputs, monkeypatch
):
    import scripts.weather_interface as interface

    reference = prepare_extraction(**preparation_inputs)
    root = preparation_inputs["project_root"]
    path = root / reference["manifest_path"]
    original_bytes = path.read_bytes()

    preparation_inputs["locations"][0]["latitude"] += 0.01

    def denied_incident(**kwargs):
        raise PermissionError("Gravacao negada no teste")

    monkeypatch.setattr(
        interface,
        "record_extraction_incident",
        denied_incident,
    )

    with pytest.raises(
        ValueError,
        match="Preparação bloqueada. Não foi possível persistir",
    ):
        prepare_extraction(**preparation_inputs)

    assert path.read_bytes() == original_bytes
    assert not (root / "data/orchestration/incidents").exists()