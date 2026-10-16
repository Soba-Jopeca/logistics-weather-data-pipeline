import hashlib
import json

import pytest

from scripts.weather_manifest import (
    persist_immutable_document,
    resolve_reference,
)


def test_document_is_persisted_with_matching_hash(tmp_path):
    reference = "data/orchestration/test/manifest.json"
    document = {"batch_id": "batch-teste", "city": "São Paulo"}

    result = persist_immutable_document(
        tmp_path, reference, document
    )
    saved_bytes = (tmp_path / reference).read_bytes()

    assert json.loads(saved_bytes) == document
    assert result == {
        "path": reference,
        "sha256": hashlib.sha256(saved_bytes).hexdigest(),
    }
    assert list((tmp_path / reference).parent.glob(".pending-*")) == []


def test_identical_document_is_reused(tmp_path):
    reference = "data/orchestration/test/manifest.json"
    document = {"batch_id": "batch-teste"}

    first = persist_immutable_document(
        tmp_path, reference, document
    )
    replay = persist_immutable_document(
        tmp_path, reference, document
    )

    assert replay == first
    assert len(list((tmp_path / reference).parent.iterdir())) == 1


def test_conflicting_document_preserves_original(tmp_path):
    reference = "data/orchestration/test/manifest.json"
    original = {"batch_id": "original"}

    persist_immutable_document(tmp_path, reference, original)
    original_bytes = (tmp_path / reference).read_bytes()

    with pytest.raises(ValueError, match="conflitante"):
        persist_immutable_document(
            tmp_path, reference, {"batch_id": "different"}
        )

    assert (tmp_path / reference).read_bytes() == original_bytes
    assert list((tmp_path / reference).parent.glob(".pending-*")) == []


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "../outside.json",
        "data/../../outside.json",
        "/outside.json",
        "C:/outside.json",
        r"C:\outside.json",
        r"data\manifest.json",
        "data//manifest.json",
        "data/./manifest.json",
        "data/file.json:stream",
    ],
)
def test_unsafe_reference_is_rejected(tmp_path, reference):
    with pytest.raises(ValueError):
        resolve_reference(tmp_path, reference)


def test_non_finite_metadata_is_rejected_without_publication(tmp_path):
    reference = "data/orchestration/test/manifest.json"

    with pytest.raises(ValueError):
        persist_immutable_document(
            tmp_path, reference, {"value": float("nan")}
        )

    assert not (tmp_path / reference).exists()


def test_publication_failure_leaves_no_final_document(
    tmp_path, monkeypatch
):
    reference = "data/orchestration/test/manifest.json"

    def failed_link(*args, **kwargs):
        raise OSError("Publicacao negada no teste")

    monkeypatch.setattr("scripts.weather_manifest.os.link", failed_link)

    with pytest.raises(OSError):
        persist_immutable_document(
            tmp_path, reference, {"batch_id": "batch-teste"}
        )

    assert not (tmp_path / reference).exists()
    assert list((tmp_path / reference).parent.glob(".pending-*")) == []