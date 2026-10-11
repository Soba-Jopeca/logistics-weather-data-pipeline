import json
import math
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def required_env(name):
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(f"Configuração obrigatória ausente: {name}")

    return value.strip()


def load_config():
    env_path = PROJECT_ROOT / ".env"

    if not env_path.is_file():
        raise ValueError("Arquivo .env não encontrado na raiz do projeto.")

    load_dotenv(
        env_path,
        encoding="utf-8-sig",
        override=False,
    )

    city = required_env("WEATHER_CITY")
    latitude = float(required_env("WEATHER_LATITUDE"))
    longitude = float(required_env("WEATHER_LONGITUDE"))
    hours = int(required_env("WEATHER_FORECAST_HOURS"))

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude deve estar entre -90 e 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude deve estar entre -180 e 180.")

    if hours != 24:
        raise ValueError(
            "Nesta etapa, a previsão deve conter 24 passos horários."
        )

    endpoint = required_env("WEATHER_ENDPOINT")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": required_env("WEATHER_HOURLY"),
        "timezone": required_env("WEATHER_TIMEZONE"),
        "forecast_hours": hours,
        "timeformat": "iso8601",
        "temperature_unit": required_env("WEATHER_TEMPERATURE_UNIT"),
        "wind_speed_unit": required_env("WEATHER_WIND_SPEED_UNIT"),
        "precipitation_unit": required_env("WEATHER_PRECIPITATION_UNIT"),
    }

    return endpoint, city, params


def fetch_forecast(endpoint, params):
    response = requests.get(
        endpoint,
        params=params,
        timeout=(10, 30),
    )

    print("HTTP:", response.status_code)
    response.raise_for_status()

    return response.json()

def main():
    # Ler a configuração.
    endpoint, city, params = load_config()
    hours = params["forecast_hours"]

    # Identificar a execução e consultar a API.
    run_id = str(uuid4())
    requested_at = datetime.now(timezone.utc).isoformat()

    payload = fetch_forecast(endpoint, params)

    collected_at = datetime.now(timezone.utc).isoformat()
    if not isinstance(payload, dict):
        raise ValueError("A resposta JSON deve ser um objeto.")

    if payload.get("error"):
        raise ValueError("A API retornou um objeto de erro.")

    print("Identificador da execução:", run_id)
    print("Pedido iniciado em UTC:", requested_at)
    print("Resposta recebida em UTC:", collected_at)

    # Validar a estrutura e o tamanho das séries.
    hourly = payload.get("hourly")

    if not isinstance(hourly, dict):
        raise ValueError("Campo hourly ausente ou inválido.")

    for field in ("time", "temperature_2m", "precipitation", "wind_speed_10m"):
        values = hourly.get(field)

        if not isinstance(values, list):
            raise ValueError(f"Série ausente ou inválida: {field}")

        if len(values) != hours:
            raise ValueError(
                f"{field}: esperados {hours} valores, recebidos {len(values)}."
            )

        print(f"{field}: {len(values)} valores")

    # Validar as unidades.
    expected_units = {
        "time": "iso8601",
        "temperature_2m": "°C",
        "precipitation": "mm",
        "wind_speed_10m": "km/h",
    }

    units = payload.get("hourly_units")

    if not isinstance(units, dict):
        raise ValueError("Campo hourly_units ausente ou inválido.")

    for field, expected in expected_units.items():
        received = units.get(field)

        if received != expected:
            raise ValueError(
                f"Unidade inesperada em {field}: "
                f"esperada {expected}, recebida {received}."
            )

    print("Unidades validadas.")

    # Validar a sequência dos horários.
    times = []

    for value in hourly["time"]:
        if not isinstance(value, str):
            raise ValueError("Horário ausente ou não textual.")

        parsed = datetime.fromisoformat(value)
        times.append(parsed)

    for previous, current in zip(times, times[1:]):
        if current - previous != timedelta(hours=1):
            raise ValueError("Horários repetidos ou não consecutivos.")

    print("Sequência de horários validada.")
    print("Primeiro horário:", hourly["time"][0])
    print("Último horário:", hourly["time"][-1])

    # Validar o fuso do nosso case.
    if payload.get("timezone") != params["timezone"]:
        raise ValueError("Fuso retornado diferente do solicitado.")

    offset = payload.get("utc_offset_seconds")

    if type(offset) is not int or offset != -10800:
        raise ValueError("Deslocamento UTC diferente do esperado para este case.")

    print("Fuso validado:", payload["timezone"])
    print("Deslocamento UTC em segundos:", offset)

    # Validar os valores e contar os nulos.
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

    print("Nulos por variável:", null_counts)

    if any(null_counts.values()):
        print("ATENÇÃO: existem dados ausentes; foram preservados.")
    else:
        print("Valores validados, sem nulos.")

    # Reunir metadados e resposta original.
    document = {
        "source": "Open-Meteo",
        "city": city,
        "run_id": run_id,
        "requested_at": requested_at,
        "collected_at": collected_at,
        "endpoint": endpoint,
        "request_params": params,
        "validation": {
            "record_count": len(hourly["time"]),
            "first_forecast_time": hourly["time"][0],
            "last_forecast_time": hourly["time"][-1],
            "null_counts": null_counts,
            "status": (
                "validated_with_nulls"
                if any(null_counts.values())
                else "validated"
            ),
        },
        "response": payload,
    }

    # Gravar sem sobrescrever coletas anteriores.
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = raw_dir / f"weather_{stamp}_{run_id}.json"

    content = json.dumps(
        document,
        ensure_ascii=False,
        indent=4,
        allow_nan=False,
    )

    with output_path.open("x", encoding="utf-8") as file:
        file.write(content)

    print("Arquivo salvo:", output_path)
if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as error:
        print(
            f"FALHA HTTP ou de conexão: {type(error).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)
    except (ValueError, OSError) as error:
        print(f"FALHA: {error}", file=sys.stderr)
        sys.exit(1)