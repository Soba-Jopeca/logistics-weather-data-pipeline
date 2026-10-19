"""C1: exclusividade em fixtures temporárias; não valida volume operacional."""

from copy import deepcopy
import multiprocessing
from uuid import uuid4

import pytest

import scripts.weather_slots as slots
from scripts.weather_manifest import persist_immutable_document
from helpers.weather_resilience import (
    blocked_external_network, file_inventory, restricted_writes,
)
from helpers.weather_temporal import claim_worker, local_time, make_claim


@pytest.fixture(autouse=True)
def isolated_control_operations(tmp_path):
    with blocked_external_network(), restricted_writes(tmp_path):
        yield


def test_identical_claim_never_reacquires_ownership(tmp_path, locations):
    slot, candidate, _ = make_claim(locations)
    first = slots.acquire_slot(root=tmp_path, candidate=candidate)
    before = file_inventory(tmp_path)
    second = slots.acquire_slot(root=tmp_path, candidate=candidate)
    assert first["created"] is True
    assert second["created"] is False
    assert second["document"] == candidate
    assert slots.inspect_slot(root=tmp_path, slot=slot)["state"] == "claimed"
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize("source", ["cli", "manual", "scheduled"])
def test_t08_sources_share_slot_namespace(tmp_path, locations, source):
    slot, original, _ = make_claim(locations)
    other_slot, other, _ = make_claim(locations, source=source)
    slots.acquire_slot(root=tmp_path, candidate=original)
    before = file_inventory(tmp_path)
    result = slots.acquire_slot(root=tmp_path, candidate=other)
    assert slots.slot_reference(slot) == slots.slot_reference(other_slot)
    assert not result["created"]
    assert result["document"]["batch_id"] == original["batch_id"]
    assert file_inventory(tmp_path) == before


def test_t19_config_conflict_preserves_claim(tmp_path, locations):
    _, candidate, _ = make_claim(locations)
    slots.acquire_slot(root=tmp_path, candidate=candidate)
    before = file_inventory(tmp_path)
    changed = deepcopy(candidate)
    changed["input_sha256"] = "f" * 64
    result = slots.acquire_slot(root=tmp_path, candidate=changed)
    assert not result["created"]
    assert result["state"] == "conflict"
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize("field,value", [
    ("schema_version", "2"), ("policy_version", "daily-v2"),
    ("claimed_at", "2026-10-13T17:00:00.000001Z"),
    ("slot_sha256", "f" * 64), ("manifest_path", "../manifest.json"),
])
def test_invalid_claim_cannot_reserve_slot(tmp_path, locations, field, value):
    _, candidate, _ = make_claim(locations)
    candidate[field] = value
    with pytest.raises(ValueError):
        slots.acquire_slot(root=tmp_path, candidate=candidate)
    assert file_inventory(tmp_path) == {}


def test_corruption_blocks_without_repair(tmp_path, locations):
    slot, candidate, _ = make_claim(locations)
    acquired = slots.acquire_slot(root=tmp_path, candidate=candidate)
    path = tmp_path / acquired["path"]
    path.write_bytes(b'{"broken":')
    before = file_inventory(tmp_path)
    with pytest.raises(slots.SlotControlError):
        slots.acquire_slot(root=tmp_path, candidate=candidate)
    with pytest.raises(slots.SlotControlError):
        slots.inspect_slot(root=tmp_path, slot=slot)
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize("operation", ["link", "fsync"])
def test_t18_filesystem_failure_does_not_fallback(tmp_path, locations, monkeypatch, operation):
    _, candidate, _ = make_claim(locations)

    def fail(*args, **kwargs):
        raise OSError("synthetic failure")

    monkeypatch.setattr(slots.os, operation, fail)
    with pytest.raises(OSError):
        slots.acquire_slot(root=tmp_path, candidate=candidate)
    assert file_inventory(tmp_path) == {}


def test_t10_dispatch_is_single_use_even_before_started(tmp_path, locations):
    _, candidate, manifest = make_claim(locations)
    claim = slots.acquire_slot(root=tmp_path, candidate=candidate)
    reference = persist_immutable_document(tmp_path, candidate["manifest_path"], manifest)
    arguments = {
        "root": tmp_path,
        "claim_reference": {"path": claim["path"], "sha256": claim["sha256"]},
        "manifest_reference": reference, "dispatch_id": str(uuid4()),
        "now": local_time(13, 46),
    }
    slots.claim_dispatch(**arguments)
    before = file_inventory(tmp_path)
    with pytest.raises(slots.SlotControlError, match="Dispatch existente"):
        slots.claim_dispatch(**arguments)
    assert file_inventory(tmp_path) == before
    assert not (tmp_path / "data/orchestration/executions").exists()


def _receive(pipe, event):
    assert pipe.poll(20), f"Evento ausente: {event}"
    message = pipe.recv()
    assert message["event"] == event
    return message


def _finish(process):
    process.join(5)
    if process.is_alive():
        process.terminate()
        process.join(5)
    if process.is_alive():
        process.kill()
        process.join(5)
    assert not process.is_alive()


def test_t07_two_processes_have_one_owner(tmp_path, locations):
    context = multiprocessing.get_context("spawn")
    candidates = [make_claim(locations)[1] for _ in range(2)]
    workers = []
    try:
        for candidate in candidates:
            parent, child = context.Pipe()
            process = context.Process(target=claim_worker, args=(tmp_path, candidate, child))
            process.start()
            child.close()
            workers.append((process, parent))
        for _, pipe in workers:
            _receive(pipe, "ready")
        for _, pipe in workers:
            pipe.send("go")
        results = [_receive(pipe, "result") for _, pipe in workers]
        assert sum(result["created"] for result in results) == 1
        assert len({result["batch_id"] for result in results}) == 1
        for process, _ in workers:
            process.join(5)
            assert process.exitcode == 0
    finally:
        for process, pipe in workers:
            _finish(process)
            pipe.close()


def test_t09_interruption_after_link_keeps_reservation(tmp_path, locations):
    slot, candidate, _ = make_claim(locations)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=claim_worker, args=(tmp_path, candidate, child, True))
    process.start()
    child.close()
    try:
        _receive(parent, "ready")
        parent.send("go")
        _receive(parent, "linked")
        process.terminate()
        process.join(5)
        assert process.exitcode is not None and process.exitcode != 0
        before = file_inventory(tmp_path)
        result = slots.acquire_slot(root=tmp_path, candidate=candidate)
        assert not result["created"]
        assert result["document"] == candidate
        assert file_inventory(tmp_path) == before
        assert slots.inspect_slot(root=tmp_path, slot=slot)["state"] == "claimed"
    finally:
        _finish(process)
        parent.close()
