import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from time import monotonic

import pytest

import scripts.weather_interface as interface
from helpers.weather_resilience import (
    assert_existing_files_preserved,
    blocked_external_network,
    file_inventory,
    restricted_writes,
)


PROJECT_ROOT = Path(__file__).parent.parent
WORKER_PATH = Path(__file__).parent / "helpers/weather_resilience.py"


def start_worker(fixture_root, reference, mode, stage):
    control_root = fixture_root / "control"

    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(PROJECT_ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "TEMP": str(control_root),
        "TMP": str(control_root),
    }

    for name in ("SYSTEMROOT", "WINDIR"):
        if name in os.environ:
            environment[name] = os.environ[name]

    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            str(WORKER_PATH),
            "--fixture-root", str(fixture_root),
            "--manifest-path", reference["manifest_path"],
            "--manifest-sha256", reference["manifest_sha256"],
            "--mode", mode,
            "--stage", stage,
        ],
        cwd=fixture_root,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )

    messages = queue.Queue()

    def read_output():
        try:
            for line in process.stdout:
                messages.put(line)
        finally:
            messages.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    return process, reader, messages


def await_worker_event(messages, expected_event, timeout=45):
    deadline = monotonic() + timeout
    output = []

    while True:
        remaining = deadline - monotonic()

        if remaining <= 0:
            raise AssertionError(
                f"Timeout aguardando {expected_event}: {output}"
            )

        try:
            line = messages.get(timeout=remaining)
        except queue.Empty:
            raise AssertionError(
                f"Timeout aguardando {expected_event}: {output}"
            ) from None

        if line is None:
            raise AssertionError(
                f"Filho terminou antes de {expected_event}: {output}"
            )

        output.append(line.rstrip())

        if line.startswith("P09_EVENT "):
            event = json.loads(line[len("P09_EVENT "):])

            assert event["event"] == expected_event
            return event


def finish_worker(process, reader):
    if process.poll() is None:
        process.terminate()

    try:
        return_code = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        return_code = process.wait(timeout=10)

    reader.join(timeout=5)
    assert not reader.is_alive(), "Leitor do subprocesso não terminou."
    assert process.poll() is not None, "Subprocesso ainda ativo."

    process.stdin.close()
    process.stdout.close()

    return return_code


def read_transport_journal(path):
    if not path.exists():
        return []

    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize(
    "stage, expected_calls",
    [
        ("after_started", 0),
        ("after_raw", 1),
    ],
)
def test_f05_interruption_blocks_new_collection_in_fresh_process(
    tmp_path,
    config,
    locations,
    cycle_date,
    stage,
    expected_calls,
):
    project_root = tmp_path / "project"
    control_root = tmp_path / "control"
    project_root.mkdir()
    control_root.mkdir()

    with restricted_writes(tmp_path), blocked_external_network():
        reference = interface.prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context={
                "dag_id": "offline_resilience",
                "airflow_run_id": f"synthetic_f05_{stage}",
            },
        )
        manifest = json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        )
        before = file_inventory(project_root)

        process, reader, messages = start_worker(
            tmp_path, reference, "interrupt", stage
        )

        try:
            ready = await_worker_event(messages, "ready")

            assert ready["pid"] == process.pid
            assert ready["stage"] == stage
            assert ready["batch_id"] == reference["batch_id"]
            assert ready["transport_call_count"] == expected_calls
            assert process.poll() is None
        finally:
            interrupted_return_code = finish_worker(process, reader)

        assert interrupted_return_code != 0
        assert process.poll() is not None

        after_interruption = file_inventory(project_root)
        assert after_interruption == ready["inventory"]
        assert_existing_files_preserved(before, after_interruption)

        execution_reference = (
            f"data/orchestration/executions/{reference['batch_id']}"
        )
        started_reference = f"{execution_reference}/started.json"
        completed_reference = f"{execution_reference}/completed.json"

        assert started_reference in after_interruption
        assert completed_reference not in after_interruption

        expected_new_files = {started_reference}

        if stage == "after_raw":
            first_city = locations[0]["location_id"]
            first_run = manifest["runs"][first_city]["run_id"]
            expected_new_files.add(
                f"data/raw/weather_{first_run}.json"
            )

        assert set(after_interruption) - set(before) == expected_new_files

        journal_path = control_root / "transport.jsonl"
        journal_before = read_transport_journal(journal_path)
        assert len(journal_before) == expected_calls

        for entry in journal_before:
            assert entry["run_id"] == (
                manifest["runs"][entry["location_id"]]["run_id"]
            )

        inspector, inspection_reader, inspection_messages = start_worker(
            tmp_path, reference, "inspect", stage
        )

        try:
            inspection = await_worker_event(
                inspection_messages, "inspection"
            )
            inspection_return_code = inspector.wait(timeout=10)
            assert inspection_return_code == 0
        finally:
            finish_worker(inspector, inspection_reader)

        assert inspector.poll() == 0
        assert inspection["transport_call_count"] == 0
        assert inspection["batch_id"] == reference["batch_id"]

        journal_after = read_transport_journal(journal_path)
        assert journal_after == journal_before

        after_inspection = file_inventory(project_root)
        assert inspection["before"] == after_interruption
        assert inspection["after"] == after_inspection
        assert_existing_files_preserved(
            after_interruption, after_inspection
        )

        added = sorted(set(after_inspection) - set(after_interruption))
        assert len(added) == 1
        assert added[0].startswith("data/orchestration/incidents/")
        assert completed_reference not in after_inspection

        assert json.loads(
            (project_root / reference["manifest_path"]).read_bytes()
        ) == manifest

        evidence = {
            "scenario": "F05",
            "variant": stage,
            "reference": reference,
            "run_ids": {
                location_id: run["run_id"]
                for location_id, run in manifest["runs"].items()
            },
            "ready_event": ready,
            "interrupted_pid": process.pid,
            "interrupted_return_code": interrupted_return_code,
            "inspector_pid": inspector.pid,
            "inspection_return_code": inspection_return_code,
            "processes_finished": (
                process.poll() is not None
                and inspector.poll() is not None
            ),
            "inspection": inspection,
            "transport_calls_before_inspection": journal_before,
            "transport_calls_after_inspection": journal_after,
            "additional_inspection_calls": 0,
            "before": before,
            "after_interruption": after_interruption,
            "after_inspection": after_inspection,
            "limitation": (
                "Interrupção de processo em fixture sintética. "
                "Não comprova durabilidade em queda de energia ou "
                "falha física. Tentativas sem relatório persistido "
                "não possuem auditoria contratual completa."
            ),
        }

        (tmp_path / f"F05-{stage}-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )