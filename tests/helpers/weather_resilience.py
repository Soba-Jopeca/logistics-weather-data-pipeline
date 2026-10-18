"""Suporte aos testes P09-T01; sem execução operacional."""

import hashlib
from pathlib import Path
import socket
from contextlib import ExitStack, contextmanager
from unittest.mock import patch
import os
import sys
from contextvars import ContextVar
import io
import json
import stat
from urllib.parse import parse_qs, urlsplit

import requests
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.response import HTTPResponse

# Capturado durante a coleta dos testes, antes da fixture block_live_http.
_ORIGINAL_SESSION_REQUEST = requests.sessions.Session.request

def file_inventory(root):
    """Inventaria arquivos sem criar ou modificar conteúdo."""
    root = Path(root).resolve()

    if not root.is_dir():
        raise ValueError("A raiz do inventário deve existir.")

    inventory = {}

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise AssertionError(
                f"Link simbólico não permitido na fixture: {path}"
            )

        if not path.is_file():
            continue

        content = path.read_bytes()
        reference = path.relative_to(root).as_posix()

        inventory[reference] = {
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    return inventory


def assert_existing_files_preserved(before, after):
    """Exige preservação dos arquivos anteriores; admite novos."""
    missing = sorted(set(before) - set(after))
    changed = sorted(
        reference
        for reference in set(before) & set(after)
        if before[reference] != after[reference]
    )

    assert not missing, f"Arquivos removidos: {missing}"
    assert not changed, f"Arquivos alterados: {changed}"
@contextmanager
def blocked_external_network():
    """Bloqueia rede e reprova qualquer tentativa durante o cenário."""
    attempts = []

    def denied(operation):
        def block(*args, **kwargs):
            attempts.append(operation)
            raise AssertionError(
                f"Acesso à rede proibido no teste: {operation}"
            )

        return block

    operations = [
        (socket, "getaddrinfo"),
        (socket, "create_connection"),
        (socket.socket, "connect"),
        (socket.socket, "connect_ex"),
        (socket.socket, "sendto"),
    ]

    if hasattr(socket.socket, "sendmsg"):
        operations.append((socket.socket, "sendmsg"))

    with ExitStack() as stack:
        for target, name in operations:
            stack.enter_context(
                patch.object(target, name, denied(name))
            )

        try:
            yield attempts
        finally:
            if attempts:
                raise AssertionError(
                    "O cenário tentou acessar a rede: "
                    + ", ".join(attempts)
                )
_WRITE_SCOPE = ContextVar("weather_test_write_scope", default=None)
_WRITE_AUDIT_INSTALLED = False


def _check_write_path(path):
    scope = _WRITE_SCOPE.get()

    if scope is None:
        return

    if isinstance(path, int):
        try:
            is_pipe = stat.S_ISFIFO(os.fstat(path).st_mode)
        except OSError:
            is_pipe = False

        if is_pipe:
            return

        scope["violations"].append("abertura por descritor")
        raise AssertionError(
            "Somente descritores de pipe são permitidos pelo teste."
        )

    target = Path(os.fsdecode(path)).resolve()

    try:
        target.relative_to(scope["root"])
    except ValueError:
        scope["violations"].append(str(target))
        raise AssertionError(
            f"Escrita fora da raiz temporária: {target}"
        ) from None


def _write_audit(event, args):
    if _WRITE_SCOPE.get() is None:
        return

    if event == "open":
        path, mode, flags = args

        writing_mode = isinstance(mode, str) and any(
            marker in mode for marker in ("w", "a", "x", "+")
        )
        writing_flags = isinstance(flags, int) and bool(
            flags
            & (
                os.O_WRONLY
                | os.O_RDWR
                | os.O_APPEND
                | os.O_CREAT
                | os.O_TRUNC
            )
        )

        if writing_mode or writing_flags:
            _check_write_path(path)

    elif event in {
        "os.mkdir",
        "os.remove",
        "os.rmdir",
        "os.chmod",
        "os.chown",
        "os.utime",
        "os.truncate",
    }:
        _check_write_path(args[0])

    elif event in {"os.rename", "os.link", "os.symlink"}:
        _check_write_path(args[0])
        _check_write_path(args[1])


@contextmanager
def restricted_writes(root):
    """Restringe operações Python auditadas à raiz temporária."""
    global _WRITE_AUDIT_INSTALLED

    root = Path(root).resolve()

    if not root.is_dir():
        raise ValueError("A raiz temporária deve existir.")

    if _WRITE_SCOPE.get() is not None:
        raise AssertionError("Proteções de escrita não devem ser aninhadas.")

    if not _WRITE_AUDIT_INSTALLED:
        sys.addaudithook(_write_audit)
        _WRITE_AUDIT_INSTALLED = True

    scope = {
        "root": root,
        "violations": [],
    }
    token = _WRITE_SCOPE.set(scope)

    try:
        yield scope["violations"]
    finally:
        _WRITE_SCOPE.reset(token)

        if scope["violations"]:
            raise AssertionError(
                "Violação da proteção de escrita: "
                + ", ".join(scope["violations"])
            )
@contextmanager
def simulated_weather_transport(
    locations,
    payload_factory,
    *,
    outcome_for=None,
):
    """Simula respostas e falhas abaixo do adaptador Requests."""
    from urllib3.exceptions import (
        MaxRetryError,
        NewConnectionError,
        ReadTimeoutError,
    )

    by_coordinates = {
        (location["latitude"], location["longitude"]): location
        for location in locations
    }
    calls = []
    city_counts = {}

    def fake_urlopen(pool, method, url, **kwargs):
        timeout = kwargs["timeout"]

        assert timeout.connect_timeout == 10
        assert timeout.read_timeout == 30

        query = parse_qs(urlsplit(url).query)
        coordinates = (
            float(query["latitude"][0]),
            float(query["longitude"][0]),
        )
        location = by_coordinates[coordinates]
        location_id = location["location_id"]

        number = city_counts.get(location_id, 0) + 1
        city_counts[location_id] = number

        call = {
            "location_id": location_id,
            "city_call_number": number,
            "method": method,
            "query": query,
            "connect_timeout": timeout.connect_timeout,
            "read_timeout": timeout.read_timeout,
        }
        calls.append(call)

        outcome = (
            outcome_for(location, number)
            if outcome_for is not None
            else None
        )

        if outcome == "timeout":
            call["outcome"] = "timeout"
            raise ReadTimeoutError(
                pool, url, "Timeout sintético P09-T01"
            )

        if outcome == "connection":
            call["outcome"] = "connection"
            reason = NewConnectionError(
                None, "Conexão sintética indisponível P09-T01"
            )
            raise MaxRetryError(pool, url, reason)

        if outcome is None:
            status = 200
            payload = payload_factory(location)
        elif isinstance(outcome, tuple) and len(outcome) == 2:
            status, payload = outcome
            assert type(status) is int
            assert 100 <= status <= 599
        else:
            raise AssertionError(
                "Resultado de transporte sintético inválido."
            )

        call["outcome"] = f"http_{status}"

        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

        return HTTPResponse(
            body=io.BytesIO(body),
            status=status,
            headers={"Content-Type": "application/json"},
            preload_content=False,
        )

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(HTTPSConnectionPool, "urlopen", fake_urlopen)
        )
        stack.enter_context(
            patch.object(
                requests.sessions.Session,
                "request",
                _ORIGINAL_SESSION_REQUEST,
            )
        )
        stack.enter_context(
            patch.dict(os.environ, {"NO_PROXY": "*", "no_proxy": "*"})
        )

        yield calls

@contextmanager
def recorded_retry_delays():
    """Registra esperas de retry sem aguardar tempo real."""
    delays = []

    def record_delay(seconds):
        delays.append(seconds)

    with patch("scripts.extract_weather.sleep", record_delay):
        yield delays
def make_synthetic_payload(location, cycle_date):
    """Cria dados meteorológicos sintéticos para o subprocesso."""
    from scripts.weather_window import build_cycle_window

    window = build_cycle_window(cycle_date, location["timezone"])
    timestamps = [
        int(instant.timestamp())
        for instant in window["expected_times_utc"]
    ]
    count = len(timestamps)

    return {
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly_units": {
            "time": "unixtime",
            "temperature_2m": "°C",
            "precipitation": "mm",
            "wind_speed_10m": "km/h",
        },
        "hourly": {
            "time": timestamps,
            "temperature_2m": [20.0] * count,
            "precipitation": [0.0] * count,
            "wind_speed_10m": [5.0] * count,
        },
    }
def _emit_worker_event(document):
    print(
        "P09_EVENT " + json.dumps(document, ensure_ascii=True),
        flush=True,
    )


def _run_interruption_worker(
    fixture_root,
    manifest_path,
    manifest_sha256,
    mode,
    stage,
):
    from datetime import date, datetime, timedelta

    import scripts.extract_weather as extractor
    import scripts.weather_interface as interface
    from scripts.weather_manifest import load_verified_manifest
    from scripts.weather_window import build_cycle_window

    fixture_root = Path(fixture_root).resolve()
    project_root = fixture_root / "project"
    control_root = fixture_root / "control"

    if not project_root.is_dir() or not control_root.is_dir():
        raise AssertionError("Fixture do subprocesso não preparada.")

    with restricted_writes(fixture_root), blocked_external_network():
        manifest = load_verified_manifest(
            project_root=project_root,
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
        )
        locations = manifest["locations"]
        cycle_date = date.fromisoformat(manifest["cycle_date_local"])
        window = build_cycle_window(
            cycle_date, locations[0]["timezone"]
        )
        frozen_time = window["window_start_utc"] - timedelta(hours=2)
        journal_path = control_root / "transport.jsonl"

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    raise AssertionError("Relógio exige timezone.")

                return cls.fromtimestamp(frozen_time.timestamp(), tz)

        def payload_factory(location):
            return make_synthetic_payload(location, cycle_date)

        def record_transport(location, number):
            entry = {
                "location_id": location["location_id"],
                "city_call_number": number,
                "run_id": manifest["runs"][
                    location["location_id"]
                ]["run_id"],
            }

            with journal_path.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps(entry) + "\n")
                journal.flush()
                os.fsync(journal.fileno())

            return None

        arguments = {
            "project_root": project_root,
            "manifest_path": manifest_path,
            "manifest_sha256": manifest_sha256,
        }

        with patch.object(extractor, "datetime", FixedDateTime):
            with simulated_weather_transport(
                locations,
                payload_factory,
                outcome_for=record_transport,
            ) as calls:
                if mode == "interrupt":
                    original_claim = interface.claim_extraction
                    original_raw = extractor.save_raw_bytes

                    def signal_ready():
                        _emit_worker_event({
                            "event": "ready",
                            "stage": stage,
                            "pid": os.getpid(),
                            "batch_id": manifest["batch_id"],
                            "transport_call_count": len(calls),
                            "inventory": file_inventory(project_root),
                        })

                        # O controlador mantém o pipe aberto e encerra
                        # este processo após receber a sinalização.
                        sys.stdin.readline()
                        raise AssertionError(
                            "Canal de controle terminou sem interrupção."
                        )

                    def instrumented_claim(*args, **kwargs):
                        result = original_claim(*args, **kwargs)

                        if stage == "after_started":
                            signal_ready()

                        return result

                    def instrumented_raw(*args, **kwargs):
                        result = original_raw(*args, **kwargs)

                        if stage == "after_raw":
                            signal_ready()

                        return result

                    with patch.object(
                        interface,
                        "claim_extraction",
                        instrumented_claim,
                    ), patch.object(
                        extractor,
                        "save_raw_bytes",
                        instrumented_raw,
                    ):
                        interface.execute_extraction(**arguments)

                    raise AssertionError(
                        "Execução terminou sem atingir a interrupção."
                    )

                before = file_inventory(project_root)

                try:
                    interface.execute_extraction(**arguments)
                except ValueError as error:
                    error_message = str(error)
                else:
                    raise AssertionError(
                        "A inspeção deveria bloquear a coleta."
                    )

                after = file_inventory(project_root)
                assert calls == []
                assert_existing_files_preserved(before, after)

                added = sorted(set(after) - set(before))
                assert len(added) == 1
                assert added[0].startswith(
                    "data/orchestration/incidents/"
                )

                incident = json.loads(
                    (project_root / added[0]).read_bytes()
                )
                assert incident["category"] == "ambiguous_state"
                assert incident["batch_id"] == manifest["batch_id"]

                _emit_worker_event({
                    "event": "inspection",
                    "pid": os.getpid(),
                    "batch_id": manifest["batch_id"],
                    "transport_call_count": len(calls),
                    "error": error_message,
                    "incident": incident,
                    "before": before,
                    "after": after,
                    "added_files": added,
                })


def _worker_main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument(
        "--mode",
        choices=("interrupt", "inspect"),
        required=True,
    )
    parser.add_argument(
        "--stage",
        choices=("after_started", "after_raw"),
        required=True,
    )
    arguments = parser.parse_args()

    _run_interruption_worker(
        fixture_root=arguments.fixture_root,
        manifest_path=arguments.manifest_path,
        manifest_sha256=arguments.manifest_sha256,
        mode=arguments.mode,
        stage=arguments.stage,
    )


if __name__ == "__main__":
    _worker_main()