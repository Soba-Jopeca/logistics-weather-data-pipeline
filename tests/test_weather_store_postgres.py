import json
import os
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import requests

psycopg2 = pytest.importorskip("psycopg2")

import scripts.extract_weather as extractor
import scripts.weather_interface as interface
from scripts.weather_queries import query_forecasts
from scripts.weather_store import (
    WeatherStoreError,
    apply_weather_schema,
    build_load_package,
    connect_weather_database,
    persist_load_package,
)
from scripts.weather_window import build_cycle_window


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

    as_of = now + timedelta(minutes=1)
    rows = query_forecasts(
        "br_sp_test",
        product_type="hourly_bundle",
        as_of=as_of,
    )

    assert len(rows) == 2
    assert {row["run_id"] for row in rows} == {older["runs"][0]["run_id"]}
    assert all(row["fallback_used"] for row in rows)
    assert {row["data_status"] for row in rows} == {"available"}

    historical = query_forecasts(
        "br_sp_test",
        product_type="hourly_bundle",
        as_of=as_of - timedelta(hours=1),
    )
    assert len(historical) == 1
    assert historical[0]["data_status"] == "unavailable"
    assert historical[0]["availability_reason"] == "no_published_version"


def test_offline_raw_batch_loads_and_queries_end_to_end(
    database,
    tmp_path,
    locations,
    monkeypatch,
):
    class LiveClock(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                raise AssertionError("The test clock requires an explicit timezone.")
            return datetime.now(timezone.utc).astimezone(tz)

    cycle_date = (
        datetime.now(ZoneInfo("America/Sao_Paulo")).date() + timedelta(days=1)
    )
    prepared = interface.prepare_extraction(
        cycle_date=cycle_date,
        config={
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "timeout": (10, 30),
        },
        locations=locations,
        project_root=tmp_path,
        orchestration_context={
            "dag_id": "logistics_weather_extract",
            "airflow_run_id": "manual__weather_store_postgres_e2e",
        },
    )
    by_coordinates = {
        (location["latitude"], location["longitude"]): location
        for location in locations
    }

    def fake_get(endpoint, *, params, timeout):
        location = by_coordinates[(params["latitude"], params["longitude"])]
        window = build_cycle_window(cycle_date, location["timezone"])
        timestamps = [
            int(instant.timestamp())
            for instant in window["expected_times_utc"]
        ]
        payload = {
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
                "temperature_2m": [19.0] * len(timestamps),
                "precipitation": [0.0] * len(timestamps),
                "wind_speed_10m": [6.0] * len(timestamps),
            },
        }
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = json.dumps(payload).encode("utf-8")
        return response

    monkeypatch.setattr(extractor, "datetime", LiveClock)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(extractor, "sleep", lambda seconds: None)
    interface.execute_extraction(
        project_root=tmp_path,
        manifest_path=prepared["manifest_path"],
        manifest_sha256=prepared["manifest_sha256"],
    )

    package = build_load_package(prepared["batch_id"], project_root=tmp_path)
    result = persist_load_package(package, connect=connect_weather_database)
    rows = query_forecasts(
        "br_sp_campinas",
        product_type="hourly_bundle",
        as_of=datetime.now(timezone.utc) + timedelta(minutes=1),
    )

    assert result["loaded"] is True
    assert result["forecast_count"] == 160
    assert len(package["raw_staging"]) == 5
    connection = connect_weather_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM weather_mvp.weather_raw_staging")
            assert cursor.fetchone()[0] == 5
            cursor.execute("SELECT COUNT(*) FROM weather_mvp.weather_forecasts")
            assert cursor.fetchone()[0] == 160
    finally:
        connection.close()
    assert len(rows) == 32
    assert {row["data_status"] for row in rows} == {"available"}
    campinas_run_id = next(
        run["run_id"]
        for run in package["runs"]
        if run["location_id"] == "br_sp_campinas"
    )
    assert {row["run_id"] for row in rows} == {campinas_run_id}


def test_staging_rejects_mismatched_batch_run_identity(database):
    """Composite foreign key blocks a batch_id inconsistent with its run."""
    package = _package(now=datetime.now(timezone.utc))
    _load(package)
    connection = connect_weather_database()
    try:
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_raw_staging (
                            batch_id, run_id, location_id, raw_path,
                            raw_sha256, raw_payload
                        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (str(uuid4()), package["runs"][0]["run_id"],
                         package["runs"][0]["location_id"],
                         "data/raw/weather_test.json", "a" * 64, "{}"),
                    )
    finally:
        connection.close()


def test_staging_transaction_rolls_back_with_core(database):
    """A staged JSON insert is rolled back if a subsequent core insert fails."""
    package = _package(now=datetime.now(timezone.utc))
    _load(package)
    connection = connect_weather_database()
    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_raw_staging (
                            batch_id, run_id, location_id, raw_path,
                            raw_sha256, raw_payload
                        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (package["batch"]["batch_id"],
                         package["runs"][0]["run_id"],
                         package["runs"][0]["location_id"],
                         "data/raw/weather_test.json", "a" * 64, "{}"),
                    )
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_forecasts (
                            run_id, location_id, forecast_time_utc,
                            precipitation_mm
                        ) VALUES (%s, %s, %s, -1)
                        """,
                        (package["runs"][0]["run_id"],
                         package["runs"][0]["location_id"],
                         datetime.now(timezone.utc) + timedelta(days=1)),
                    )
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM weather_mvp.weather_raw_staging")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT count(*) FROM weather_mvp.weather_forecasts")
            assert cursor.fetchone()[0] == 2
    finally:
        connection.close()
