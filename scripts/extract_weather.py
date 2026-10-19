import json
import math
import sys
import os
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
from time import perf_counter
from copy import deepcopy
from time import sleep
from scripts.weather_window import build_cycle_window, evaluate_coverage
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).parent.parent


def required_env(name):
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(f"Configuração obrigatória ausente: {name}")

    return value.strip()
def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai previsões meteorológicas por ciclo de planejamento."
    )

    parser.add_argument(
        "--cycle-date",
        required=True,
        type=date.fromisoformat,
        metavar="AAAA-MM-DD",
        help="Data local do ciclo de planejamento, por exemplo: 2026-10-13.",
    )

    return parser.parse_args()
def load_locations():
    path = PROJECT_ROOT / "config" / "locations.json"
    locations = json.loads(path.read_text(encoding="utf-8-sig"))
    return validate_locations(locations)


def validate_locations(locations):
    if not isinstance(locations, list) or not locations:
        raise ValueError("O cadastro deve ser uma lista não vazia.")

    seen_ids = set()

    for location in locations:
        if not isinstance(location, dict):
            raise ValueError("Cada localidade deve ser um objeto.")

        for field in ("location_id", "name", "timezone"):
            value = location.get(field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Campo obrigatório inválido: {field}")

            if value != value.strip():
                raise ValueError(f"Espaços extras no campo: {field}")

        location_id = location["location_id"]

        if location_id in seen_ids:
            raise ValueError(f"Identificador duplicado: {location_id}")

        seen_ids.add(location_id)

        for field, minimum, maximum in (
            ("latitude", -90, 90),
            ("longitude", -180, 180),
        ):
            value = location.get(field)

            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not minimum <= value <= maximum
            ):
                raise ValueError(
                    f"{location_id}: coordenada inválida em {field}."
                )

        try:
            ZoneInfo(location["timezone"])
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(
                f"{location_id}: timezone inválido ou indisponível."
            ) from error

    return locations

def load_api_config():
    env_path = PROJECT_ROOT / ".env"

    if env_path.is_file():
        load_dotenv(
            env_path,
            encoding="utf-8-sig",
            override=False,
        )

    return {
        "endpoint": required_env("WEATHER_ENDPOINT"),
        "timeout": (10, 30),
    }

def build_request_params(location, window):
    if location["timezone"] != window["timezone"]:
        raise ValueError("O fuso da localidade difere do fuso do ciclo.")

    start_utc = window["window_start_utc"]
    last_utc = window["window_end_utc"] - timedelta(hours=1)

    return {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "timezone": "GMT",
        "start_hour": start_utc.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": last_utc.strftime("%Y-%m-%dT%H:%M"),
        "timeformat": "unixtime",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }

def validate_payload_structure(payload):
    if not isinstance(payload, dict):
        raise ValueError("A resposta JSON deve ser um objeto.")

    if payload.get("error"):
        raise ValueError("A API retornou um objeto de erro.")

    hourly = payload.get("hourly")
    units = payload.get("hourly_units")

    if not isinstance(hourly, dict):
        raise ValueError("Campo hourly ausente ou inválido.")

    if not isinstance(units, dict):
        raise ValueError("Campo hourly_units ausente ou inválido.")

    expected_units = {
        "time": "unixtime",
        "temperature_2m": "°C",
        "precipitation": "mm",
        "wind_speed_10m": "km/h",
    }

    sizes = {}

    for field, expected_unit in expected_units.items():
        values = hourly.get(field)

        if not isinstance(values, list) or not values:
            raise ValueError(f"Série ausente, vazia ou inválida: {field}")

        if units.get(field) != expected_unit:
            raise ValueError(f"Unidade inesperada em {field}.")

        sizes[field] = len(values)

    if len(set(sizes.values())) != 1:
        raise ValueError(f"Séries com tamanhos diferentes: {sizes}")

    if payload.get("timezone") != "GMT":
        raise ValueError("A resposta deve usar o fuso GMT solicitado.")

    offset = payload.get("utc_offset_seconds")

    if type(offset) is not int or offset != 0:
        raise ValueError("A resposta solicitada em GMT deve ter offset zero.")

    return hourly

def parse_forecast_times(payload):
    hourly = payload.get("hourly")

    if not isinstance(hourly, dict):
        raise ValueError("Campo hourly ausente ou inválido.")

    values = hourly.get("time")

    if not isinstance(values, list) or not values:
        raise ValueError("Série de horários ausente, vazia ou inválida.")

    times = []

    for value in values:
        if type(value) is not int:
            raise ValueError("Unix timestamp deve ser um número inteiro.")

        try:
            parsed = datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OverflowError, OSError) as error:
            raise ValueError("Unix timestamp fora do intervalo válido.") from error

        times.append(parsed)

    for previous, current in zip(times, times[1:]):
        if current - previous != timedelta(hours=1):
            raise ValueError(
                "Horários fora de ordem, duplicados ou não consecutivos."
            )

    return times

def validate_weather_values(hourly):
    null_counts = {}

    for field in ("temperature_2m", "precipitation", "wind_speed_10m"):
        null_counts[field] = 0

        for value in hourly[field]:
            if value is None:
                null_counts[field] += 1
                continue

            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"Valor numérico inválido em {field}.")

            if field in ("precipitation", "wind_speed_10m") and value < 0:
                raise ValueError(f"Valor negativo inválido em {field}.")

    return null_counts

def normalize_forecasts(hourly, forecast_times, run_id, location_id):
    fields = ("temperature_2m", "precipitation", "wind_speed_10m")

    if any(len(hourly[field]) != len(forecast_times) for field in fields):
        raise ValueError("Quantidade de valores diferente dos horários.")

    records = []

    for index, forecast_time in enumerate(forecast_times):
        records.append({
            "run_id": run_id,
            "location_id": location_id,
            "forecast_time_utc": forecast_time.isoformat(),
            "temperature_2m_c": hourly["temperature_2m"][index],
            "precipitation_mm": hourly["precipitation"][index],
            "wind_speed_10m_kmh": hourly["wind_speed_10m"][index],
        })

    return records

def fetch_forecast_response(endpoint, params, timeout=(10, 30), *, before_first_transport=None):
    if before_first_transport is not None:
        before_first_transport()
    return requests.get(
        endpoint,
        params=params,
        timeout=timeout,
    )


def save_raw_bytes(raw_bytes, run_id, *, project_root=None):
    # Validar o identificador antes de utilizá-lo no caminho.
    from uuid import UUID

    canonical_run_id = str(UUID(run_id))

    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    output_path = raw_dir / f"weather_{canonical_run_id}.json"
    expected_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        with output_path.open("xb") as file:
            file.write(raw_bytes)
    except FileExistsError:
        existing_bytes = output_path.read_bytes()

        if existing_bytes != raw_bytes:
            raise ValueError(
                f"Conflito de Raw para run_id={canonical_run_id}. "
                "O arquivo original foi preservado."
            )

    saved_bytes = output_path.read_bytes()

    if saved_bytes != raw_bytes:
        raise OSError("Os bytes gravados diferem do conteúdo recebido.")

    return {
        "raw_path": output_path.relative_to(root).as_posix(),
        "raw_sha256": expected_hash,
    }

def execute_attempt(endpoint, params, timeout, run_id, attempt_no, *, before_first_transport=None):
    attempt = {
        "attempt_id": str(uuid4()),
        "run_id": run_id,
        "attempt_no": attempt_no,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "duration_ms": None,
        "http_status": None,
        "error_category": None,
        "error_message": None,
    }

    response = None
    timer = perf_counter()

    try:
        options = ({"before_first_transport": before_first_transport}
                   if before_first_transport is not None else {})
        response = fetch_forecast_response(endpoint, params, timeout, **options)
        attempt["http_status"] = response.status_code

        if not 200 <= response.status_code < 300:
            attempt["error_category"] = "http_error"
            attempt["error_message"] = f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        attempt["error_category"] = "timeout"
        attempt["error_message"] = "Tempo de espera HTTP excedido."

    except requests.exceptions.ConnectionError:
        attempt["error_category"] = "connection_error"
        attempt["error_message"] = "Falha de conexão com a fonte."

    except requests.exceptions.RequestException as error:
        attempt["error_category"] = "request_error"
        attempt["error_message"] = type(error).__name__

    finally:
        attempt["ended_at"] = datetime.now(timezone.utc).isoformat()
        attempt["duration_ms"] = round(
            (perf_counter() - timer) * 1000,
            3,
        )

    return response, attempt

def fetch_with_retries(endpoint, params, timeout, run_id, max_attempts=3, *, before_first_transport=None):
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts deve estar entre 1 e 3.")

    frozen_params = deepcopy(params)
    attempts = []
    response = None

    for attempt_no in range(1, max_attempts + 1):
        response, attempt = execute_attempt(
            endpoint,
            deepcopy(frozen_params),
            timeout,
            run_id,
            attempt_no,
            **({"before_first_transport": before_first_transport}
               if before_first_transport is not None else {}),
        )
        attempts.append(attempt)

        if attempt["error_category"] is None:
            return response, attempts

        retryable = (
            attempt["error_category"] in ("timeout", "connection_error")
            or attempt["http_status"] in (500, 502, 503, 504)
        )

        if not retryable or attempt_no == max_attempts:
            break

        sleep(2 ** (attempt_no - 1))

    return response, attempts

def save_run_report(report, *, project_root=None):
    from uuid import UUID

    run_id = str(UUID(report["run_id"]))

    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    report_dir = root / "data" / "raw" / "runs"
    report_dir.mkdir(parents=True, exist_ok=True)

    output_path = report_dir / f"{run_id}.json"

    content = json.dumps(
        report,
        ensure_ascii=False,
        indent=4,
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")

    try:
        with output_path.open("xb") as file:
            file.write(content)
    except FileExistsError:
        if output_path.read_bytes() != content:
            raise ValueError(
                f"Relatório conflitante para run_id={run_id}. "
                "O original foi preservado."
            )

    if output_path.read_bytes() != content:
        raise OSError("Falha na conferência do relatório gravado.")

    return output_path.relative_to(root).as_posix()

def process_forecast(payload, window, collected_at, run_id, location_id):
    hourly = validate_payload_structure(payload)
    forecast_times = parse_forecast_times(payload)
    null_counts = validate_weather_values(hourly)

    coverage = evaluate_coverage(
        window,
        collected_at,
        forecast_times,
    )

    records = normalize_forecasts(
        hourly,
        forecast_times,
        run_id,
        location_id,
    )

    validation = {
        "record_count": len(records),
        "first_forecast_time_utc": forecast_times[0].isoformat(),
        "last_forecast_time_utc": forecast_times[-1].isoformat(),
        "null_counts": null_counts,
        "coverage": coverage,
    }

    return records, validation

def collect_location(
    config,
    location,
    cycle_date,
    batch_id,
    run_id=None,
    *,
    project_root=None,
    request_params=None,
    before_first_transport=None,
):
    run_id = str(uuid4()) if run_id is None else run_id
    location_snapshot = deepcopy(location)

    window = build_cycle_window(
        cycle_date,
        location_snapshot["timezone"],
    )
    expected_params = build_request_params(location_snapshot, window)

    if request_params is None:
        params = expected_params
    else:
        if (
            not isinstance(request_params, dict)
            or request_params != expected_params
        ):
            raise ValueError(
                "Parâmetros fornecidos diferem do snapshot e do ciclo."
            )

        params = deepcopy(request_params)

    report = {
        "run_id": run_id,
        "batch_id": batch_id,
        "location_id": location_snapshot["location_id"],
        "location": location_snapshot,
        "source": "Open-Meteo",
        "endpoint": config["endpoint"],
        "request_params": deepcopy(params),
        "cycle": {
            "cycle_date_local": window["cycle_date_local"],
            "timezone": window["timezone"],
            "window_start_utc": window["window_start_utc"].isoformat(),
            "window_end_utc": window["window_end_utc"].isoformat(),
        },
        "requested_at": None,
        "collected_at": None,
        "run_status": "failed",
        "raw_path": None,
        "raw_sha256": None,
        "attempts": [],
        "validation": None,
        "error_category": None,
        "error_message": None,
    }

    records = []

    response, attempts = fetch_with_retries(
        config["endpoint"],
        params,
        config["timeout"],
        run_id,
        **({"before_first_transport": before_first_transport}
           if before_first_transport is not None else {}),
    )

    report["attempts"] = attempts
    report["requested_at"] = attempts[0]["started_at"]
    last_attempt = attempts[-1]

    try:
        # Response pode existir mesmo quando o status HTTP indica erro.
        if response is not None:
            report["collected_at"] = last_attempt["ended_at"]
            if project_root is None:
                raw_reference = save_raw_bytes(response.content, run_id)
            else:
                raw_reference = save_raw_bytes(
                    response.content,
                    run_id,
                    project_root=project_root,
                )

            report.update(raw_reference)

        if last_attempt["error_category"] is not None:
            report["error_category"] = last_attempt["error_category"]
            report["error_message"] = last_attempt["error_message"]

        else:
            collected_at = datetime.fromisoformat(report["collected_at"])
            payload = response.json()

            records, validation = process_forecast(
                payload,
                window,
                collected_at,
                run_id,
                location_snapshot["location_id"],
            )

            report["validation"] = validation

            if not validation["coverage"]["coverage_complete"]:
                report["run_status"] = "incomplete"
            elif any(validation["null_counts"].values()):
                report["run_status"] = "validated_with_nulls"
            else:
                report["run_status"] = "validated"

    except ValueError as error:
        report["error_category"] = "validation_or_raw_conflict"
        report["error_message"] = str(error)

    except OSError as error:
        report["error_category"] = "persistence_error"
        report["error_message"] = type(error).__name__

    if project_root is None:
        report_path = save_run_report(report)
    else:
        report_path = save_run_report(
            report,
            project_root=project_root,
        )

    return {
        "report": report,
        "report_path": report_path,
        "records": records,
    }

def collect_batch(
    config,
    locations,
    cycle_date,
    *,
    batch_id=None,
    run_ids=None,
    project_root=None,
    request_params_by_location=None,
    before_first_transport=None,
):
    from uuid import UUID

    if not locations:
        raise ValueError("A rodada precisa de pelo menos uma localidade.")

    config_snapshot = deepcopy(config)
    locations_snapshot = deepcopy(locations)

    location_ids = [
        location["location_id"]
        for location in locations_snapshot
    ]

    if len(set(location_ids)) != len(location_ids):
        raise ValueError("A rodada contém localidades duplicadas.")

    batch_id = (
        str(uuid4())
        if batch_id is None
        else str(UUID(batch_id))
    )

    if run_ids is None:
        frozen_run_ids = {
            location_id: str(uuid4())
            for location_id in location_ids
        }
    else:
        if not isinstance(run_ids, dict):
            raise ValueError("run_ids deve ser um mapa por localidade.")

        if set(run_ids) != set(location_ids):
            raise ValueError(
                "run_ids deve identificar exatamente as localidades da rodada."
            )

        frozen_run_ids = {
            location_id: str(UUID(run_ids[location_id]))
            for location_id in location_ids
        }

    if len(set(frozen_run_ids.values())) != len(location_ids):
        raise ValueError("Cada localidade deve possuir um run_id distinto.")

    frozen_request_params = None

    if request_params_by_location is not None:
        if (
            not isinstance(request_params_by_location, dict)
            or set(request_params_by_location) != set(location_ids)
        ):
            raise ValueError(
                "Parâmetros devem identificar exatamente as localidades."
            )

        frozen_request_params = deepcopy(request_params_by_location)

        for location in locations_snapshot:
            window = build_cycle_window(
                cycle_date,
                location["timezone"],
            )
            expected = build_request_params(location, window)

            if frozen_request_params[location["location_id"]] != expected:
                raise ValueError(
                    "Parâmetros da rodada divergem do cadastro e do ciclo."
                )

    started_at = datetime.now(timezone.utc).isoformat()
    results = []

    for location in locations_snapshot:
        run_id = frozen_run_ids[location["location_id"]]

        options = {"run_id": run_id}
        if before_first_transport is not None:
            options["before_first_transport"] = before_first_transport
        if frozen_request_params is not None:
            options["request_params"] = frozen_request_params[
                location["location_id"]
            ]

        if project_root is not None:
            options["project_root"] = project_root

        try:
            result = collect_location(
                config_snapshot,
                location,
                cycle_date,
                batch_id,
                **options,
            )
            results.append(result)

        except (ValueError, OSError) as error:
            results.append({
                "report": {
                    "run_id": run_id,
                    "batch_id": batch_id,
                    "location_id": location["location_id"],
                    "run_status": "failed",
                    "error_category": "run_execution_error",
                    "error_message": str(error),
                },
                "report_path": None,
                "records": [],
            })

    successful = sum(
        result["report"]["run_status"]
        in ("validated", "validated_with_nulls")
        for result in results
    )

    if successful == len(results):
        batch_status = "success"
    elif successful:
        batch_status = "partial_success"
    else:
        batch_status = "failed"

    return {
        "batch_id": batch_id,
        "cycle_date_local": cycle_date.isoformat(),
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "batch_status": batch_status,
        "location_count": len(results),
        "successful_location_count": successful,
        "results": results,
    }

def save_batch_report(batch, *, project_root=None):
    from uuid import UUID

    batch_id = str(UUID(batch["batch_id"]))

    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    report_dir = root / "data" / "raw" / "batches"
    report_dir.mkdir(parents=True, exist_ok=True)

    output_path = report_dir / f"{batch_id}.json"

    # Registros normalizados continuam em memória nesta etapa.
    # O resumo preserva os relatórios e seus caminhos.
    summary = {
        key: value
        for key, value in batch.items()
        if key != "results"
    }

    summary["results"] = [
        {
            "report": result["report"],
            "report_path": result["report_path"],
        }
        for result in batch["results"]
    ]

    content = json.dumps(
        summary,
        ensure_ascii=False,
        indent=4,
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")

    try:
        with output_path.open("xb") as file:
            file.write(content)
    except FileExistsError:
        if output_path.read_bytes() != content:
            raise ValueError(
                f"Resumo conflitante para batch_id={batch_id}. "
                "O original foi preservado."
            )

    if output_path.read_bytes() != content:
        raise OSError("Falha na conferência do resumo da rodada.")

    return output_path.relative_to(root).as_posix()

def main():
    from scripts.weather_daily import (
        prepare_daily_extraction, execute_daily_extraction, reconcile_daily_extraction,
    )
    from scripts.weather_temporal import DailyAdmissionError

    args = parse_args()
    try:
        reference = prepare_daily_extraction(
            cycle_date=args.cycle_date, config=load_api_config(),
            locations=load_locations(), project_root=PROJECT_ROOT,
            clock=lambda: datetime.now(timezone.utc),
        )
        result = execute_daily_extraction(
            prepared=reference, project_root=PROJECT_ROOT,
            clock=lambda: datetime.now(timezone.utc),
        )
        evaluation = reconcile_daily_extraction(
            prepared=result, project_root=PROJECT_ROOT,
            clock=lambda: datetime.now(timezone.utc),
        )
    except (DailyAdmissionError, ValueError, OSError) as error:
        print(f"Indisponível para decisão diária: {error}", file=sys.stderr)
        return 1
    print("Batch:", result["batch_id"])
    print("Ciclo:", result["cycle_date"])
    print("Modo:", result["mode"])
    print("Status técnico:", result["batch_status"])
    print("Avaliação operacional:", json.dumps(evaluation, ensure_ascii=False))
    return 0 if evaluation["eligible"] else 1
if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.exceptions.RequestException as error:
        print(
            f"FALHA HTTP ou de conexão: {type(error).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)
    except (ValueError, OSError) as error:
        print(f"FALHA: {error}", file=sys.stderr)
        sys.exit(1)