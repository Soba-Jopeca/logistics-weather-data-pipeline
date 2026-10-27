import os
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from scripts.weather_queries import query_forecasts
from scripts.weather_store import (
    WeatherStoreError,
    apply_weather_schema,
    connect_weather_database,
    persist_load_package,
)


def _is_disposable_database_configured():
    return (
        os.environ.get("WEATHER_DB_NAME") == "weather_test"
        and os.environ.get("WEATHER_DB_HOST") in {"localhost", "127.0.0.1"}
        and os.environ.get("WEATHER_TEST_DB_RESET") == "1"
    )


pytestmark = pytest.mark.skipif(
    not _is_disposable_database_configured(),
    reason="Requires the explicitly disposable weather_test PostgreSQL database.",
)


@pytest.fixture
def database():
    connection = connect_weather_database()
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS weather_mvp CASCADE")
        apply_weather_schema(connection)
    try:
        yield
    finally:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS weather_mvp CASCADE")
        connection.close()


def _package(*, now, status="validated", publication_status="published", metrics=True):
    batch_id = str(uuid4())
    run_id = str(uuid4())
    location_id = "br_sp_test"
    window_start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    window_end = window_start + timedelta(hours=2)
    collected_at = now - timedelta(minutes=30)
    digest = "a" * 64
    forecasts = []
    if metrics:
        for offset in range(2):
            forecasts.append({
                "run_id": run_id,
                "location_id": location_id,
                "forecast_time_utc": window_start + timedelta(hours=offset),
                "temperature_2m_c": 18.5 + offset,
                "precipitation_mm": 0.0,
                "wind_speed_10m_kmh": 4.0,
            })
    return {
        "batch": {
            "batch_id": batch_id,
            "cycle_date_local": date.fromisoformat(now.date().isoformat()),
            "timezone": "America/Sao_Paulo",
            "window_start_utc": window_start,
            "window_end_utc": window_end,
            "batch_status": "success",
            "started_at": now - timedelta(minutes=35),
            "ended_at": now - timedelta(minutes=20),
            "manifest_path": f"data/orchestration/batches/{batch_id}/manifest.json",
            "manifest_sha256": digest,
            "batch_report_path": f"data/raw/batches/{batch_id}.json",
            "batch_report_sha256": "b" * 64,
        },
        "locations": [{
            "location_id": location_id,
            "name": "Teste",
            "latitude": -23.5,
            "longitude": -46.6,
            "timezone": "America/Sao_Paulo",
        }],
        "runs": [{
            "run_id": run_id,
            "batch_id": batch_id,
            "location_id": location_id,
            "location_name": "Teste",
            "latitude": -23.5,
            "longitude": -46.6,
            "timezone": "America/Sao_Paulo",
            "requested_at": collected_at - timedelta(seconds=2),
            "collected_at": collected_at,
            "source": "Open-Meteo",
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "request_params": {},
            "raw_path": f"data/raw/weather_{run_id}.json",
            "raw_sha256": digest,
            "report_path": f"data/raw/runs/{run_id}.json",
            "report_sha256": digest,
            "run_status": status,
            "validation": {},
        }],
        "attempts": [{
            "attempt_id": str(uuid4()),
            "run_id": run_id,
            "attempt_no": 1,
            "started_at": collected_at - timedelta(seconds=1),
            "ended_at": collected_at,
            "duration_ms": 100,
            "http_status": 200,
            "error_category": None,
            "error_message": None,
        }],
        "forecasts": forecasts,
        "publications": [{
            "run_id": run_id,
            "location_id": location_id,
            "product_type": product_type,
            "status": publication_status if metrics else "unavailable",
            "quality_reasons": [] if metrics else ["incomplete_coverage"],
        } for product_type in (
            "temperature_2m",
            "precipitation",
            "wind_speed_10m",
            "hourly_bundle",
        )],
        "artifacts": [{
            "batch_id": batch_id,
            "artifact_path": f"data/raw/runs/{run_id}.json",
            "artifact_type": "run_report",
            "sha256": digest,
            "size_bytes": 100,
        }],
    }


def _load(package):
    return persist_load_package(package, connect=connect_weather_database)


def test_schema_constraints_and_exact_replay(database):
    now = datetime.now(timezone.utc)
    package = _package(now=now)

    first = _load(package)
    replay = _load(package)

    assert first["loaded"] is True
    assert replay["idempotent_replay"] is True
    assert replay["forecast_count"] == 2

    with pytest.raises(psycopg2.errors.CheckViolation):
        connection = connect_weather_database()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.locations
                            (location_id, name, latitude, longitude, timezone)
                        VALUES ('invalid', 'Invalid', 91, 0, 'UTC')
                        """
                    )
        finally:
            connection.close()


def test_conflicting_batch_hash_is_blocked_without_mutation(database):
    now = datetime.now(timezone.utc)
    package = _package(now=now)
    _load(package)
    conflicting = _package(now=now)
    conflicting["batch"]["batch_id"] = package["batch"]["batch_id"]
    conflicting["batch"]["manifest_sha256"] = "c" * 64

    with pytest.raises(WeatherStoreError, match="conflicting source hashes"):
        _load(conflicting)

    connection = connect_weather_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM weather_mvp.weather_batches")
            assert cursor.fetchone()[0] == 1
    finally:
        connection.close()


def test_replay_detects_mutated_existing_forecast_content(database):
    package = _package(now=datetime.now(timezone.utc))
    _load(package)

    connection = connect_weather_database()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE weather_mvp.weather_forecasts
                    SET temperature_2m_c = 99
                    WHERE run_id = %s
                    """,
                    (package["runs"][0]["run_id"],),
                )
    finally:
        connection.close()

    with pytest.raises(WeatherStoreError, match="forecast records"):
        _load(package)


def test_load_rolls_back_all_rows_on_constraint_failure(database):
    package = _package(now=datetime.now(timezone.utc))
    package["locations"][0]["latitude"] = 91

    with pytest.raises(psycopg2.errors.CheckViolation):
        _load(package)

    connection = connect_weather_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM weather_mvp.weather_batches")
            assert cursor.fetchone()[0] == 0
    finally:
        connection.close()


def test_nullable_measurements_are_persisted_without_zero_substitution(database):
    package = _package(now=datetime.now(timezone.utc))
    package["runs"][0]["run_status"] = "validated_with_nulls"
    package["forecasts"][0]["temperature_2m_c"] = None
    for publication in package["publications"]:
        if publication["product_type"] in ("temperature_2m", "hourly_bundle"):
            publication["status"] = "unavailable"
            publication["quality_reasons"] = ["temperature_2m_c_nulls"]

    _load(package)

    connection = connect_weather_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT temperature_2m_c, precipitation_mm
                FROM weather_mvp.weather_forecasts
                WHERE run_id = %s
                ORDER BY forecast_time_utc
                LIMIT 1
                """,
                (package["runs"][0]["run_id"],),
            )
            assert cursor.fetchone() == (None, 0.0)
    finally:
        connection.close()


def test_query_uses_whole_version_fallback_and_as_of(database):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    older = _package(now=now - timedelta(minutes=45))
    newer = _package(
        now=now - timedelta(minutes=10),
        status="validated_with_nulls",
        publication_status="unavailable",
        metrics=False,
    )
    _load(older)
    _load(newer)

    rows = query_forecasts(
        "br_sp_test",
        product_type="hourly_bundle",
        as_of=now,
    )

    assert len(rows) == 2
    assert {row["run_id"] for row in rows} == {older["runs"][0]["run_id"]}
    assert all(row["fallback_used"] for row in rows)
    assert {row["data_status"] for row in rows} == {"available"}

    historical = query_forecasts(
        "br_sp_test",
        product_type="hourly_bundle",
        as_of=now - timedelta(hours=1),
    )
    assert len(historical) == 1
    assert historical[0]["data_status"] == "unavailable"
    assert historical[0]["availability_reason"] == "no_published_version"
