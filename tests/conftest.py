from datetime import date, datetime, timezone

import pytest
import requests

import scripts.extract_weather as extractor
from scripts.weather_window import build_cycle_window


@pytest.fixture(autouse=True)
def block_live_http(monkeypatch):
    def blocked_request(*args, **kwargs):
        raise AssertionError(
            "HTTP real bloqueado: o teste deve simular a resposta."
        )

    monkeypatch.setattr(
        requests.sessions.Session,
        "request",
        blocked_request,
    )


@pytest.fixture
def cycle_date():
    return date(2026, 10, 13)


@pytest.fixture
def fixed_clock(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = cls(
                2026, 10, 13, 17, 0,
                tzinfo=timezone.utc,
            )

            if tz is None:
                raise AssertionError(
                    "O teste exige chamadas ao relógio com timezone."
                )

            return instant.astimezone(tz)

    monkeypatch.setattr(extractor, "datetime", FixedDateTime)


@pytest.fixture
def locations():
    return extractor.load_locations()


@pytest.fixture
def config():
    return {
        "endpoint": "https://api.open-meteo.com/v1/forecast",
        "timeout": (10, 30),
    }


@pytest.fixture
def raw_root(tmp_path, monkeypatch):
    monkeypatch.setattr(extractor, "PROJECT_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def payload_factory(cycle_date):
    def make_payload(location, cycle=None):
        window = build_cycle_window(
            cycle if cycle is not None else cycle_date,
            location["timezone"],
        )

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

    return make_payload