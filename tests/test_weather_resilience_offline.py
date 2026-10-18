import socket

import pytest
import json

import scripts.weather_interface as interface
from helpers.weather_resilience import simulated_weather_transport

from helpers.weather_resilience import (
    assert_existing_files_preserved,
    blocked_external_network,
    file_inventory,
    restricted_writes,
)
from scripts.weather_manifest import persist_immutable_document
from helpers.weather_resilience import recorded_retry_delays


def test_inventory_detects_changes(tmp_path):
    path = tmp_path / "example.json"
    path.write_bytes(b'{"value": 1}')

    before = file_inventory(tmp_path)

    assert before["example.json"]["size_bytes"] == 12

    path.write_bytes(b'{"value": 2}')
    after = file_inventory(tmp_path)

    with pytest.raises(AssertionError, match="Arquivos alterados"):
        assert_existing_files_preserved(before, after)


def test_write_barrier_allows_immutable_persistence(tmp_path):
    with restricted_writes(tmp_path):
        result = persist_immutable_document(
            tmp_path,
            "fixture.json",
            {"test": True},
        )

    inventory = file_inventory(tmp_path)

    assert inventory["fixture.json"]["sha256"] == result["sha256"]


def test_write_barrier_blocks_outside_root(tmp_path):
    allowed_root = tmp_path / "scenario"
    allowed_root.mkdir()

    forbidden_path = tmp_path / "outside.json"

    with pytest.raises(
        AssertionError,
        match="Violação da proteção de escrita",
    ):
        with restricted_writes(allowed_root):
            forbidden_path.write_text("blocked", encoding="utf-8")

    assert not forbidden_path.exists()


def test_network_barrier_blocks_dns():
    with pytest.raises(
        AssertionError,
        match="O cenário tentou acessar a rede",
    ):
        with blocked_external_network():
            socket.getaddrinfo("example.invalid", 443)


def test_network_barrier_detects_swallowed_exception():
    with pytest.raises(
        AssertionError,
        match="O cenário tentou acessar a rede",
    ):
        with blocked_external_network():
            with pytest.raises(
                AssertionError,
                match="Acesso à rede proibido",
            ):
                socket.getaddrinfo("example.invalid", 443)
def test_f06_intact_replay_preserves_ids_and_files(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    project_root = tmp_path / "project"
    project_root.mkdir()

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": "synthetic_f06",
            },
        )

        manifest_path = project_root / reference["manifest_path"]
        manifest = json.loads(manifest_path.read_bytes())

        arguments = {
            "project_root": project_root,
            "manifest_path": reference["manifest_path"],
            "manifest_sha256": reference["manifest_sha256"],
        }

        with simulated_weather_transport(
            locations, payload_factory
        ) as calls:
            first = interface.execute_extraction(**arguments)

            assert first["mode"] == "new_collection"
            assert first["batch_status"] == "success"
            assert first["record_count"] == 160
            assert first["successful_location_count"] == 5
            assert len(calls) == 5

            before_replay = file_inventory(project_root)
            calls_before_replay = len(calls)

            replay = interface.execute_extraction(**arguments)

            after_replay = file_inventory(project_root)

            assert replay["mode"] == "replay"
            assert len(calls) == calls_before_replay
            assert after_replay == before_replay

        assert {
            key: value
            for key, value in first.items()
            if key != "mode"
        } == {
            key: value
            for key, value in replay.items()
            if key != "mode"
        }

        summary = json.loads(
            (project_root / first["batch_report_path"]).read_bytes()
        )

        expected_run_ids = {
            location_id: run["run_id"]
            for location_id, run in manifest["runs"].items()
        }
        actual_run_ids = {
            result["report"]["location_id"]: result["report"]["run_id"]
            for result in summary["results"]
        }
        assert actual_run_ids == expected_run_ids

        attempt_ids = [
            attempt["attempt_id"]
            for result in summary["results"]
            for attempt in result["report"]["attempts"]
        ]
        assert len(attempt_ids) == len(set(attempt_ids)) == 5

        manifest_entry = after_replay[reference["manifest_path"]]
        assert manifest_entry["sha256"] == reference["manifest_sha256"]

        evidence = {
            "scenario": "F06",
            "batch_id": reference["batch_id"],
            "run_ids": actual_run_ids,
            "attempt_ids": attempt_ids,
            "first_result": first,
            "replay_result": replay,
            "initial_transport_calls": calls_before_replay,
            "additional_replay_calls": len(calls) - calls_before_replay,
            "transport_calls": calls,
            "before_replay": before_replay,
            "after_replay": after_replay,
        }

        (tmp_path / "F06-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
@pytest.mark.parametrize("state", ["started", "orphan_raw"])
def test_f08_ambiguous_state_blocks_without_overwriting(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    state,
):
    from scripts.extract_weather import save_raw_bytes

    project_root = tmp_path / "project"
    project_root.mkdir()

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": f"synthetic_f08_{state}",
            },
        )

        manifest = json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        )
        run_id = next(iter(manifest["runs"].values()))["run_id"]

        if state == "started":
            interface.claim_extraction(
                project_root=project_root,
                batch_id=reference["batch_id"],
                manifest_sha256=reference["manifest_sha256"],
            )
        else:
            save_raw_bytes(
                b'{"synthetic_orphan": true}',
                run_id,
                project_root=project_root,
            )

        before = file_inventory(project_root)

        with simulated_weather_transport(
            locations, payload_factory
        ) as calls:
            with pytest.raises(ValueError, match="Incidente:") as error:
                interface.execute_extraction(
                    project_root=project_root,
                    manifest_path=reference["manifest_path"],
                    manifest_sha256=reference["manifest_sha256"],
                )

            assert calls == []

        after = file_inventory(project_root)
        assert_existing_files_preserved(before, after)

        added = sorted(set(after) - set(before))
        assert len(added) == 1
        assert added[0].startswith("data/orchestration/incidents/")

        incident = json.loads(
            (project_root / added[0]).read_bytes()
        )
        assert incident["category"] == "ambiguous_state"
        assert incident["batch_id"] == reference["batch_id"]
        assert incident["automatic_collection_blocked"] is True

        execution_root = (
            project_root
            / "data/orchestration/executions"
            / reference["batch_id"]
        )
        assert not (execution_root / "completed.json").exists()

        if state == "orphan_raw":
            assert not (execution_root / "started.json").exists()

        evidence = {
            "scenario": "F08",
            "variant": state,
            "batch_id": reference["batch_id"],
            "run_ids": {
                location_id: run["run_id"]
                for location_id, run in manifest["runs"].items()
            },
            "transport_calls": calls,
            "transport_call_count": len(calls),
            "error": str(error.value),
            "incident": incident,
            "before": before,
            "after": after,
            "added_files": added,
        }

        (tmp_path / f"F08-{state}-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
@pytest.mark.parametrize("artifact", ["raw", "report", "completion"])
def test_f09_corruption_blocks_replay_without_repair(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
    artifact,
):
    project_root = tmp_path / "project"
    project_root.mkdir()

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": f"synthetic_f09_{artifact}",
            },
        )
        arguments = {
            "project_root": project_root,
            "manifest_path": reference["manifest_path"],
            "manifest_sha256": reference["manifest_sha256"],
        }

        with simulated_weather_transport(
            locations, payload_factory
        ) as calls:
            result = interface.execute_extraction(**arguments)

            assert result["batch_status"] == "success"
            assert len(calls) == 5

            summary = json.loads(
                (project_root / result["batch_report_path"]).read_bytes()
            )
            first = summary["results"][0]

            if artifact == "raw":
                target_reference = first["report"]["raw_path"]
                old = b'"temperature_2m": [20.0'
                new = b'"temperature_2m": [21.0'
            elif artifact == "report":
                target_reference = first["report_path"]
                old = b'"record_count": 32'
                new = b'"record_count": 31'
            else:
                target_reference = result["completion_path"]
                old = b'"record_count": 160'
                new = b'"record_count": 161'

            target = project_root / target_reference
            original = target.read_bytes()
            assert old in original

            corrupted = original.replace(old, new, 1)
            assert len(corrupted) == len(original)
            assert sum(
                left != right
                for left, right in zip(original, corrupted)
            ) == 1

            intact_inventory = file_inventory(project_root)
            target.write_bytes(corrupted)
            before_attempt = file_inventory(project_root)
            calls_before_attempt = len(calls)

            with pytest.raises(ValueError, match="Incidente:") as error:
                interface.execute_extraction(**arguments)

            after_attempt = file_inventory(project_root)

            assert len(calls) == calls_before_attempt
            assert target.read_bytes() == corrupted
            assert_existing_files_preserved(
                before_attempt, after_attempt
            )

        added = sorted(set(after_attempt) - set(before_attempt))
        assert len(added) == 1
        assert added[0].startswith("data/orchestration/incidents/")

        incident = json.loads(
            (project_root / added[0]).read_bytes()
        )
        assert incident["category"] == "artifact_integrity"
        assert incident["batch_id"] == reference["batch_id"]
        assert incident["automatic_collection_blocked"] is True

        evidence = {
            "scenario": "F09",
            "variant": artifact,
            "batch_id": reference["batch_id"],
            "target_reference": target_reference,
            "changed_bytes": 1,
            "initial_transport_calls": calls_before_attempt,
            "additional_replay_calls": len(calls) - calls_before_attempt,
            "transport_calls": calls,
            "error": str(error.value),
            "incident": incident,
            "intact_inventory": intact_inventory,
            "before_attempt": before_attempt,
            "after_attempt": after_attempt,
            "added_files": added,
        }

        (tmp_path / f"F09-{artifact}-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
@pytest.mark.parametrize("variant", ["wrong_hash", "changed_bytes"])
def test_f10_manifest_integrity_blocks_before_collection(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    variant,
):
    import hashlib

    project_root = tmp_path / "project"
    project_root.mkdir()

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": f"synthetic_f10_{variant}",
            },
        )

        manifest_path = project_root / reference["manifest_path"]
        original_bytes = manifest_path.read_bytes()
        intact_inventory = file_inventory(project_root)

        supplied_hash = reference["manifest_sha256"]

        if variant == "wrong_hash":
            supplied_hash = hashlib.sha256(
                b"synthetic_incorrect_hash"
            ).hexdigest()
            assert supplied_hash != reference["manifest_sha256"]
        else:
            # Continua sendo JSON válido, mas os bytes e o hash mudaram.
            manifest_path.write_bytes(original_bytes + b"\n")

        before_attempt = file_inventory(project_root)

        with simulated_weather_transport(
            locations, payload_factory
        ) as calls:
            with pytest.raises(ValueError, match="Incidente:") as error:
                interface.execute_extraction(
                    project_root=project_root,
                    manifest_path=reference["manifest_path"],
                    manifest_sha256=supplied_hash,
                )

            assert calls == []

        after_attempt = file_inventory(project_root)
        assert_existing_files_preserved(
            before_attempt, after_attempt
        )

        added = sorted(set(after_attempt) - set(before_attempt))
        assert len(added) == 1
        assert added[0].startswith("data/orchestration/incidents/")

        incident = json.loads(
            (project_root / added[0]).read_bytes()
        )
        assert incident["category"] == "manifest_integrity"
        assert incident["batch_id"] is None
        assert incident["automatic_collection_blocked"] is True

        execution_root = (
            project_root
            / "data/orchestration/executions"
            / reference["batch_id"]
        )
        assert not (execution_root / "started.json").exists()
        assert not (execution_root / "completed.json").exists()
        assert not (project_root / "data/raw").exists()

        evidence = {
            "scenario": "F10",
            "variant": variant,
            "expected_batch_id": reference["batch_id"],
            "manifest_path": reference["manifest_path"],
            "original_manifest_sha256": reference["manifest_sha256"],
            "supplied_manifest_sha256": supplied_hash,
            "transport_calls": calls,
            "transport_call_count": len(calls),
            "error": str(error.value),
            "incident": incident,
            "intact_inventory": intact_inventory,
            "before_attempt": before_attempt,
            "after_attempt": after_attempt,
            "added_files": added,
        }

        (tmp_path / f"F10-{variant}-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
def test_f12_context_identity_and_slot_uniqueness_gap(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
):
    project_root = tmp_path / "project"
    project_root.mkdir()

    context_a = {
        "dag_id": "offline_resilience",
        "airflow_run_id": "synthetic_f12_a",
    }
    context_b = {
        "dag_id": "offline_resilience",
        "airflow_run_id": "synthetic_f12_b",
    }

    with restricted_writes(tmp_path), blocked_external_network():
        with simulated_weather_transport(
            locations, payload_factory
        ) as calls:
            first = interface.prepare_extraction(
                cycle_date=cycle_date,
                config=config,
                locations=locations,
                project_root=project_root,
                orchestration_context=context_a,
            )
            before_repeat = file_inventory(project_root)

            repeated = interface.prepare_extraction(
                cycle_date=cycle_date,
                config=config,
                locations=locations,
                project_root=project_root,
                orchestration_context=context_a,
            )
            after_repeat = file_inventory(project_root)

            assert repeated == first
            assert after_repeat == before_repeat

            second = interface.prepare_extraction(
                cycle_date=cycle_date,
                config=config,
                locations=locations,
                project_root=project_root,
                orchestration_context=context_b,
            )
            after_new_context = file_inventory(project_root)

            assert calls == []

        assert second["batch_id"] != first["batch_id"]
        assert second["manifest_path"] != first["manifest_path"]
        assert second["cycle_date"] == first["cycle_date"]

        first_manifest = json.loads(
            (project_root / first["manifest_path"]).read_bytes()
        )
        second_manifest = json.loads(
            (project_root / second["manifest_path"]).read_bytes()
        )

        first_run_ids = {
            location_id: run["run_id"]
            for location_id, run in first_manifest["runs"].items()
        }
        second_run_ids = {
            location_id: run["run_id"]
            for location_id, run in second_manifest["runs"].items()
        }

        assert set(first_run_ids.values()).isdisjoint(
            second_run_ids.values()
        )
        assert first_manifest["config"] == second_manifest["config"]
        assert first_manifest["locations"] == second_manifest["locations"]

        for location_id in first_run_ids:
            assert (
                first_manifest["runs"][location_id]["request_params"]
                == second_manifest["runs"][location_id]["request_params"]
            )
            assert (
                first_manifest["runs"][location_id]["cycle"]
                == second_manifest["runs"][location_id]["cycle"]
            )

        assert_existing_files_preserved(
            after_repeat, after_new_context
        )
        added = sorted(set(after_new_context) - set(after_repeat))
        assert added == [second["manifest_path"]]

        assert not (project_root / "data/raw").exists()
        assert not (
            project_root / "data/orchestration/executions"
        ).exists()

        evidence = {
            "scenario": "F12",
            "first_context": context_a,
            "second_context": context_b,
            "first_reference": first,
            "repeated_reference": repeated,
            "second_reference": second,
            "first_run_ids": first_run_ids,
            "second_run_ids": second_run_ids,
            "transport_call_count": len(calls),
            "before_repeat": before_repeat,
            "after_repeat": after_repeat,
            "after_new_context": after_new_context,
            "added_files": added,
            "limitation": (
                "Contextos distintos criam identidades distintas para "
                "o mesmo ciclo. Unicidade de slot não está implementada "
                "nem comprovada por este teste."
            ),
        }

        (tmp_path / "F12-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
@pytest.mark.parametrize(
    "failure, expected_category",
    [
        ("timeout", "timeout"),
        ("connection", "connection_error"),
    ],
)
def test_f01_http_failure_is_limited_and_other_cities_continue(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
    failure,
    expected_category,
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    failed_city = "br_sp_sorocaba"

    def outcome_for(location, number):
        if location["location_id"] == failed_city:
            return failure
        return None

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": f"synthetic_f01_{failure}",
            },
        )
        manifest = json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        )
        before = file_inventory(project_root)

        with recorded_retry_delays() as delays:
            with simulated_weather_transport(
                locations,
                payload_factory,
                outcome_for=outcome_for,
            ) as calls:
                result = interface.execute_extraction(
                    project_root=project_root,
                    manifest_path=reference["manifest_path"],
                    manifest_sha256=reference["manifest_sha256"],
                )

        assert result["batch_status"] == "partial_success"
        assert result["successful_location_count"] == 4
        assert result["record_count"] == 128
        assert len(calls) == 7
        assert delays == [1, 2]

        expected_order = []
        for location in locations:
            location_id = location["location_id"]
            expected_order.extend(
                [location_id] * (3 if location_id == failed_city else 1)
            )

        assert [call["location_id"] for call in calls] == expected_order

        summary = json.loads(
            (project_root / result["batch_report_path"]).read_bytes()
        )
        reports = {
            row["report"]["location_id"]: row["report"]
            for row in summary["results"]
        }
        failed = reports[failed_city]

        assert failed["run_status"] == "failed"
        assert failed["raw_path"] is None
        assert failed["raw_sha256"] is None
        assert failed["collected_at"] is None
        assert len(failed["attempts"]) == 3

        assert [
            attempt["attempt_no"] for attempt in failed["attempts"]
        ] == [1, 2, 3]
        assert all(
            attempt["error_category"] == expected_category
            and attempt["http_status"] is None
            for attempt in failed["attempts"]
        )

        attempt_ids = []
        for location_id, report in reports.items():
            assert report["run_id"] == (
                manifest["runs"][location_id]["run_id"]
            )

            expected_attempts = 3 if location_id == failed_city else 1
            assert len(report["attempts"]) == expected_attempts

            if location_id != failed_city:
                assert report["run_status"] == "validated"

            for attempt in report["attempts"]:
                assert attempt["run_id"] == report["run_id"]
                attempt_ids.append(attempt["attempt_id"])

        assert len(attempt_ids) == len(set(attempt_ids)) == 7

        for call in calls:
            expected_params = manifest["runs"][
                call["location_id"]
            ]["request_params"]
            assert call["query"] == {
                key: [str(value)]
                for key, value in expected_params.items()
            }

        failed_run_id = failed["run_id"]
        assert not (
            project_root / f"data/raw/weather_{failed_run_id}.json"
        ).exists()
        assert len(
            list((project_root / "data/raw").glob("weather_*.json"))
        ) == 4

        after = file_inventory(project_root)
        assert_existing_files_preserved(before, after)

        evidence = {
            "scenario": "F01",
            "variant": failure,
            "reference": reference,
            "result": result,
            "failed_city": failed_city,
            "failed_report": failed,
            "attempt_ids": attempt_ids,
            "transport_call_count": len(calls),
            "transport_calls": calls,
            "retry_delays": delays,
            "before": before,
            "after": after,
        }

        (tmp_path / f"F01-{failure}-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
def test_f02_transient_failure_recovers_without_restarting_batch(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    recovering_city = "br_sp_sorocaba"

    def outcome_for(location, number):
        if location["location_id"] != recovering_city:
            return None

        if number == 1:
            return "timeout"

        if number == 2:
            return 503, {"reason": "Falha transitória sintética"}

        return None

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": "synthetic_f02",
            },
        )
        manifest = json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        )
        before = file_inventory(project_root)

        with recorded_retry_delays() as delays:
            with simulated_weather_transport(
                locations,
                payload_factory,
                outcome_for=outcome_for,
            ) as calls:
                result = interface.execute_extraction(
                    project_root=project_root,
                    manifest_path=reference["manifest_path"],
                    manifest_sha256=reference["manifest_sha256"],
                )

        assert result["batch_status"] == "success"
        assert result["successful_location_count"] == 5
        assert result["record_count"] == 160
        assert len(calls) == 7
        assert delays == [1, 2]

        expected_order = []
        for location in locations:
            location_id = location["location_id"]
            expected_order.extend(
                [location_id]
                * (3 if location_id == recovering_city else 1)
            )

        assert [call["location_id"] for call in calls] == expected_order

        summary = json.loads(
            (project_root / result["batch_report_path"]).read_bytes()
        )
        reports = {
            row["report"]["location_id"]: row["report"]
            for row in summary["results"]
        }
        recovered = reports[recovering_city]
        attempts = recovered["attempts"]

        assert recovered["run_status"] == "validated"
        assert [item["attempt_no"] for item in attempts] == [1, 2, 3]
        assert [item["http_status"] for item in attempts] == [
            None, 503, 200
        ]
        assert [item["error_category"] for item in attempts] == [
            "timeout", "http_error", None
        ]

        attempt_ids = []
        for location_id, report in reports.items():
            assert report["run_status"] == "validated"
            assert report["run_id"] == (
                manifest["runs"][location_id]["run_id"]
            )
            assert len(report["attempts"]) == (
                3 if location_id == recovering_city else 1
            )

            for attempt in report["attempts"]:
                assert attempt["run_id"] == report["run_id"]
                attempt_ids.append(attempt["attempt_id"])

        assert len(attempt_ids) == len(set(attempt_ids)) == 7

        for call in calls:
            expected_params = manifest["runs"][
                call["location_id"]
            ]["request_params"]
            assert call["query"] == {
                key: [str(value)]
                for key, value in expected_params.items()
            }

        after = file_inventory(project_root)
        assert_existing_files_preserved(before, after)

        assert len(
            list((project_root / "data/raw").glob("weather_*.json"))
        ) == 5

        for report in reports.values():
            assert after[report["raw_path"]]["sha256"] == (
                report["raw_sha256"]
            )

        evidence = {
            "scenario": "F02",
            "reference": reference,
            "result": result,
            "recovering_city": recovering_city,
            "recovered_report": recovered,
            "attempt_ids": attempt_ids,
            "transport_call_count": len(calls),
            "transport_calls": calls,
            "retry_delays": delays,
            "before": before,
            "after": after,
        }

        (tmp_path / "F02-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
def test_f03_http_200_with_missing_hour_remains_incomplete(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    from datetime import datetime, timezone

    project_root = tmp_path / "project"
    project_root.mkdir()
    incomplete_city = "br_sp_sorocaba"
    removed_times = []

    def outcome_for(location, number):
        if location["location_id"] != incomplete_city:
            return None

        payload = payload_factory(location)
        hourly = payload["hourly"]
        removed_times.append(hourly["time"].pop())

        for field in (
            "temperature_2m",
            "precipitation",
            "wind_speed_10m",
        ):
            hourly[field].pop()

        return 200, payload

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": "synthetic_f03",
            },
        )
        manifest = json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        )
        before = file_inventory(project_root)

        with recorded_retry_delays() as delays:
            with simulated_weather_transport(
                locations,
                payload_factory,
                outcome_for=outcome_for,
            ) as calls:
                result = interface.execute_extraction(
                    project_root=project_root,
                    manifest_path=reference["manifest_path"],
                    manifest_sha256=reference["manifest_sha256"],
                )

                assert result["batch_status"] == "partial_success"
                assert result["successful_location_count"] == 4
                assert result["record_count"] == 159
                assert len(calls) == 5
                assert delays == []
                assert len(removed_times) == 1

                summary = json.loads(
                    (project_root / result["batch_report_path"]).read_bytes()
                )
                reports = {
                    row["report"]["location_id"]: row["report"]
                    for row in summary["results"]
                }
                report = reports[incomplete_city]
                coverage = report["validation"]["coverage"]

                missing_time = datetime.fromtimestamp(
                    removed_times[0], timezone.utc
                ).isoformat()

                assert report["run_status"] == "incomplete"
                assert report["validation"]["record_count"] == 31
                assert coverage["required_count"] == 32
                assert coverage["received_count"] == 31
                assert coverage["coverage_complete"] is False
                assert coverage["missing_times_utc"] == [missing_time]
                assert coverage["outside_window_times_utc"] == []

                for location_id, item in reports.items():
                    assert item["run_id"] == (
                        manifest["runs"][location_id]["run_id"]
                    )
                    assert len(item["attempts"]) == 1
                    assert item["attempts"][0]["http_status"] == 200
                    assert item["attempts"][0]["error_category"] is None

                    if location_id != incomplete_city:
                        assert item["run_status"] == "validated"

                raw = json.loads(
                    (project_root / report["raw_path"]).read_bytes()
                )
                assert len(raw["hourly"]["time"]) == 31
                assert removed_times[0] not in raw["hourly"]["time"]

                before_reconciliation = file_inventory(project_root)
                verified = interface.verify_batch_artifacts(
                    project_root=project_root,
                    manifest=manifest,
                )
                after_reconciliation = file_inventory(project_root)

                assert verified["batch_status"] == "partial_success"
                assert verified["record_count"] == 159
                assert verified["successful_location_count"] == 4
                assert after_reconciliation == before_reconciliation
                assert len(calls) == 5

        after = file_inventory(project_root)
        assert_existing_files_preserved(before, after)
        assert after[report["raw_path"]]["sha256"] == report["raw_sha256"]

        evidence = {
            "scenario": "F03",
            "reference": reference,
            "result": result,
            "incomplete_report": report,
            "missing_time_utc": missing_time,
            "verified": verified,
            "transport_call_count": len(calls),
            "transport_calls": calls,
            "retry_delays": delays,
            "before": before,
            "after": after,
            "before_reconciliation": before_reconciliation,
            "after_reconciliation": after_reconciliation,
            "limitation": (
                "Integridade parcial verificada pelo núcleo. "
                "Não comprova aprovação analítica ou estado de task Airflow."
            ),
        }

        (tmp_path / "F03-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
@pytest.mark.parametrize(
    "variant, expected_records, expected_calls",
    [
        ("timeout", 128, 7),
        ("incomplete", 159, 5),
    ],
)
def test_f07_partial_replay_preserves_partiality(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
    variant,
    expected_records,
    expected_calls,
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    partial_city = "br_sp_sorocaba"

    def outcome_for(location, number):
        if location["location_id"] != partial_city:
            return None

        if variant == "timeout":
            return "timeout"

        payload = payload_factory(location)

        for values in payload["hourly"].values():
            values.pop()

        return 200, payload

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": f"synthetic_f07_{variant}",
            },
        )
        arguments = {
            "project_root": project_root,
            "manifest_path": reference["manifest_path"],
            "manifest_sha256": reference["manifest_sha256"],
        }

        with recorded_retry_delays() as delays:
            with simulated_weather_transport(
                locations,
                payload_factory,
                outcome_for=outcome_for,
            ) as calls:
                first = interface.execute_extraction(**arguments)

                assert first["mode"] == "new_collection"
                assert first["batch_status"] == "partial_success"
                assert first["successful_location_count"] == 4
                assert first["record_count"] == expected_records
                assert len(calls) == expected_calls

                before_replay = file_inventory(project_root)
                initial_call_count = len(calls)
                delays_before_replay = list(delays)

                replay = interface.execute_extraction(**arguments)

                after_replay = file_inventory(project_root)

                assert replay["mode"] == "replay"
                assert replay["batch_status"] == "partial_success"
                assert replay["successful_location_count"] == 4
                assert replay["record_count"] == expected_records
                assert len(calls) == initial_call_count
                assert delays == delays_before_replay
                assert after_replay == before_replay

        assert {
            key: value
            for key, value in first.items()
            if key != "mode"
        } == {
            key: value
            for key, value in replay.items()
            if key != "mode"
        }

        summary = json.loads(
            (project_root / replay["batch_report_path"]).read_bytes()
        )
        reports = {
            row["report"]["location_id"]: row["report"]
            for row in summary["results"]
        }
        expected_city_status = (
            "failed" if variant == "timeout" else "incomplete"
        )
        assert reports[partial_city]["run_status"] == expected_city_status
        assert summary["batch_status"] == "partial_success"

        attempt_ids = [
            attempt["attempt_id"]
            for report in reports.values()
            for attempt in report["attempts"]
        ]
        assert len(attempt_ids) == len(set(attempt_ids)) == expected_calls
        assert delays == ([1, 2] if variant == "timeout" else [])

        evidence = {
            "scenario": "F07",
            "variant": variant,
            "reference": reference,
            "first_result": first,
            "replay_result": replay,
            "partial_report": reports[partial_city],
            "run_ids": {
                location_id: report["run_id"]
                for location_id, report in reports.items()
            },
            "attempt_ids": attempt_ids,
            "initial_transport_calls": initial_call_count,
            "additional_replay_calls": len(calls) - initial_call_count,
            "transport_calls": calls,
            "retry_delays": delays,
            "before_replay": before_replay,
            "after_replay": after_replay,
            "limitation": (
                "Replay do núcleo preserva parcialidade. "
                "Não comprova estado de task ou aprovação analítica."
            ),
        }

        (tmp_path / f"F07-{variant}-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

def test_f04_report_write_failure_preserves_raw_and_blocks_restart(
    tmp_path,
    monkeypatch,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    from pathlib import Path

    project_root = tmp_path / "project"
    project_root.mkdir()
    failed_city = "br_sp_sorocaba"
    original_open = Path.open
    write_failures = []

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": "synthetic_f04",
            },
        )
        manifest = json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        )
        failed_run_id = manifest["runs"][failed_city]["run_id"]
        raw_reference = f"data/raw/weather_{failed_run_id}.json"
        report_reference = f"data/raw/runs/{failed_run_id}.json"
        report_path = project_root / report_reference
        arguments = {
            "project_root": project_root,
            "manifest_path": reference["manifest_path"],
            "manifest_sha256": reference["manifest_sha256"],
        }
        before = file_inventory(project_root)

        def failing_open(path, mode="r", *args, **kwargs):
            if path == report_path and mode == "xb":
                assert (project_root / raw_reference).is_file()
                write_failures.append(
                    file_inventory(project_root)[raw_reference]
                )
                raise PermissionError(
                    "Falha sintética na escrita do relatório F04"
                )

            return original_open(path, mode, *args, **kwargs)

        with simulated_weather_transport(
            locations, payload_factory
        ) as calls:
            with monkeypatch.context() as fault:
                fault.setattr(Path, "open", failing_open)

                with pytest.raises(
                    ValueError, match="Incidente:"
                ) as first_error:
                    interface.execute_extraction(**arguments)

            assert len(calls) == 5
            assert len(write_failures) == 1

            after_failure = file_inventory(project_root)
            assert_existing_files_preserved(before, after_failure)
            assert after_failure[raw_reference] == write_failures[0]
            assert not report_path.exists()

            summary_reference = (
                f"data/raw/batches/{reference['batch_id']}.json"
            )
            summary = json.loads(
                (project_root / summary_reference).read_bytes()
            )
            assert summary["batch_status"] == "partial_success"
            assert summary["successful_location_count"] == 4

            failed_result = next(
                row for row in summary["results"]
                if row["report"]["location_id"] == failed_city
            )
            assert failed_result["report_path"] is None
            assert failed_result["report"]["run_id"] == failed_run_id
            assert failed_result["report"]["error_category"] == (
                "run_execution_error"
            )
            assert failed_result["report"]["error_message"] == (
                "Falha sintética na escrita do relatório F04"
            )

            assert len(
                list((project_root / "data/raw").glob("weather_*.json"))
            ) == 5
            assert len(
                list((project_root / "data/raw/runs").glob("*.json"))
            ) == 4

            incidents_before = [
                name for name in after_failure
                if name.startswith("data/orchestration/incidents/")
            ]
            assert len(incidents_before) == 1
            first_incident = json.loads(
                (project_root / incidents_before[0]).read_bytes()
            )
            assert first_incident["category"] == "execution_error"

            execution_root = (
                project_root
                / "data/orchestration/executions"
                / reference["batch_id"]
            )
            assert (execution_root / "started.json").exists()
            assert not (execution_root / "completed.json").exists()

            calls_before_restart = len(calls)

            with pytest.raises(
                ValueError, match="Incidente:"
            ) as restart_error:
                interface.execute_extraction(**arguments)

            assert len(calls) == calls_before_restart

        after_restart = file_inventory(project_root)
        assert_existing_files_preserved(
            after_failure, after_restart
        )
        added = sorted(set(after_restart) - set(after_failure))
        assert len(added) == 1
        assert added[0].startswith("data/orchestration/incidents/")

        restart_incident = json.loads(
            (project_root / added[0]).read_bytes()
        )
        assert restart_incident["category"] == "ambiguous_state"
        assert not (execution_root / "completed.json").exists()

        evidence = {
            "scenario": "F04",
            "reference": reference,
            "failed_run_id": failed_run_id,
            "raw_reference": raw_reference,
            "missing_report_reference": report_reference,
            "raw_at_failure": write_failures[0],
            "failed_result": failed_result,
            "first_error": str(first_error.value),
            "restart_error": str(restart_error.value),
            "first_incident": first_incident,
            "restart_incident": restart_incident,
            "transport_calls": calls,
            "initial_transport_calls": calls_before_restart,
            "additional_restart_calls": len(calls) - calls_before_restart,
            "before": before,
            "after_failure": after_failure,
            "after_restart": after_restart,
            "limitation": (
                "A escrita do relatório foi impedida antes de abrir "
                "o arquivo. Não simula gravação parcial ou falha física "
                "de disco. O relatório ausente não contém auditoria "
                "persistida das tentativas dessa cidade."
            ),
        }

        (tmp_path / "F04-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
@pytest.mark.parametrize(
    "damage",
    ["summary_counter", "summary_run_id", "summary_report_reference"],
)
def test_f11_reconciliation_rejects_divergence_without_repair(
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
    damage,
):
    from uuid import uuid4

    project_root = tmp_path / "project"
    project_root.mkdir()

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": f"synthetic_f11_{damage}",
            },
        )
        manifest = json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        )

        with simulated_weather_transport(
            locations, payload_factory
        ) as calls:
            result = interface.execute_extraction(
                project_root=project_root,
                manifest_path=reference["manifest_path"],
                manifest_sha256=reference["manifest_sha256"],
            )

            assert result["batch_status"] == "success"
            assert len(calls) == 5

            summary_path = project_root / result["batch_report_path"]
            summary = json.loads(summary_path.read_bytes())
            intact_inventory = file_inventory(project_root)

            if damage == "summary_counter":
                summary["successful_location_count"] = 4
            elif damage == "summary_run_id":
                summary["results"][0]["report"]["run_id"] = str(uuid4())
            else:
                summary["results"][0]["report_path"] = (
                    summary["results"][1]["report_path"]
                )

            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            before_reconciliation = file_inventory(project_root)
            calls_before_reconciliation = len(calls)

            with pytest.raises(ValueError) as error:
                interface.verify_batch_artifacts(
                    project_root=project_root,
                    manifest=manifest,
                )

            after_reconciliation = file_inventory(project_root)

            assert len(calls) == calls_before_reconciliation
            assert after_reconciliation == before_reconciliation
            assert json.loads(summary_path.read_bytes()) == summary
            assert intact_inventory != before_reconciliation

        assert not list(
            (project_root / "data/orchestration/incidents").glob("*.json")
        )

        evidence = {
            "scenario": "F11",
            "variant": damage,
            "reference": reference,
            "summary_reference": result["batch_report_path"],
            "initial_transport_calls": calls_before_reconciliation,
            "additional_reconciliation_calls": (
                len(calls) - calls_before_reconciliation
            ),
            "transport_calls": calls,
            "error_type": type(error.value).__name__,
            "error": str(error.value),
            "incident_created": False,
            "intact_inventory": intact_inventory,
            "before_reconciliation": before_reconciliation,
            "after_reconciliation": after_reconciliation,
            "limitation": (
                "Somente verify_batch_artifacts foi executado. "
                "Não comprova estado de task ou DAG Airflow."
            ),
        }

        (tmp_path / f"F11-{damage}-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )